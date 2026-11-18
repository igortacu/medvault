"""Persistent NDJSON worker. Stdout is protocol only; model logs go to stderr."""
import contextlib
import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from urllib.parse import urlparse


def main():
    config = json.loads(sys.argv[1])
    engine = config['engine']
    started = time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        if config.get('service_command'):
            health_url = config['service_health_url']
            if urlparse(health_url).hostname not in ('127.0.0.1', 'localhost'):
                raise ValueError('Local model service must bind to loopback')
            service = subprocess.Popen(config['service_command'], stdin=subprocess.DEVNULL,
                                       stdout=sys.stderr, stderr=sys.stderr)
            deadline = time.monotonic() + config.get('service_startup_timeout_s', 120)
            while True:
                if service.poll() is not None:
                    raise RuntimeError('Local model service exited during startup')
                try:
                    with urllib.request.urlopen(health_url, timeout=1) as response:
                        health = json.load(response)
                    if health.get('model_ready'):
                        break
                    if health.get('preload_failures'):
                        raise RuntimeError('Local model service failed to preload weights')
                except (urllib.error.URLError, TimeoutError):
                    pass
                if time.monotonic() > deadline:
                    raise TimeoutError('Local model service startup deadline exceeded')
                time.sleep(.2)
        if engine == 'paddle':
            from paddleocr import PaddleOCR
            model = PaddleOCR(**config.get('options', {}))
        elif engine == 'paddle-vl':
            from paddleocr import PaddleOCRVL
            model = PaddleOCRVL(**config.get('options', {}))
        elif engine == 'docling':
            from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.datamodel.accelerator_options import AcceleratorOptions, AcceleratorDevice
            from pathlib import Path
            options = PdfPipelineOptions(
                accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU,
                                                       num_threads=config.get('cpu_threads', 1)),
                enable_remote_services=False)
            if config.get('artifacts_path'):
                options.artifacts_path = Path(config['artifacts_path'])
            model = DocumentConverter(format_options={
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=options),
                InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
        elif engine != 'tesseract':
            raise ValueError('Unsupported engine')
    versions = {}
    for name in ('paddleocr', 'paddlepaddle', 'docling', 'torch'):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    if engine == 'tesseract':
        versions['tesseract'] = subprocess.check_output(['tesseract', '--version'], stderr=subprocess.STDOUT).decode().splitlines()[0]
    print(json.dumps({'ready': True, 'startup_s': time.perf_counter()-started, 'versions': versions}), flush=True)
    for line in sys.stdin:
        request = json.loads(line)
        start = time.perf_counter()
        with contextlib.redirect_stdout(sys.stderr):
            if engine == 'tesseract':
                proc = subprocess.run(['tesseract', request['input'], 'stdout'] +
                                      (['--tessdata-dir', config['tessdata_dir']] if config.get('tessdata_dir') else []) + ['-l',
                                       config.get('languages', 'eng'), '--psm', str(config.get('psm', 3))],
                                      capture_output=True, check=True)
                result = {'text': proc.stdout.decode('utf-8'), 'fields': {}}
            elif engine == 'paddle':
                lines = []
                for page in model.predict(request['input']):
                    data = page.json
                    if isinstance(data, str):
                        data = json.loads(data)
                    lines.extend(data.get('res', data).get('rec_texts', []))
                result = {'text': '\n'.join(lines), 'fields': {}}
            elif engine == 'paddle-vl':
                pages = list(model.predict(request['input'], **config.get('predict_options', {})))
                blocks = []
                for page in pages:
                    data = page.json
                    if isinstance(data, str):
                        data = json.loads(data)
                    blocks.extend(block['block_content'] for block in
                                  data.get('res', data).get('parsing_res_list', []))
                result = {'text': '\n'.join(blocks),
                          'markdown': '\n\n'.join(page.markdown['markdown_texts'] for page in pages),
                          'fields': {}}
            else:
                document = model.convert(request['input']).document
                result = {'text': document.export_to_text(traverse_pictures=True),
                          'markdown': document.export_to_markdown(), 'fields': {}}
        # Preserve HTML tables emitted by document VLMs; multiple tables need upstream matching.
        tables = re.findall(r'<table\b[^>]*>.*?</table>', result.get('markdown', result['text']), flags=re.DOTALL | re.IGNORECASE)
        if len(tables) == 1:
            result['table_html'] = tables[0]
        result['inference_s'] = time.perf_counter()-start
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
