"""Render PDFs once, before inference; invoke only inside the document sandbox."""
import argparse
import hashlib
import json
from pathlib import Path

import pypdfium2 as pdfium


def render(source, output, dpi=200, max_pages=100, max_pixels=30_000_000):
    if not 72 <= dpi <= 400:
        raise ValueError('DPI must be between 72 and 400')
    source, output = Path(source), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    pages = []
    with pdfium.PdfDocument(source) as document:
        if len(document) > max_pages:
            raise ValueError('Page limit exceeded')
        for index in range(len(document)):
            page = document[index]
            width, height = page.get_size()
            if width * height * (dpi/72)**2 > max_pixels:
                raise ValueError('Rendered page pixel limit exceeded')
            bitmap = page.render(scale=dpi/72)
            name = f'page-{index+1:04}.png'
            bitmap.to_pil().save(output/name)
            pages.append({'page':index+1, 'input':name,
                          'sha256':hashlib.sha256((output/name).read_bytes()).hexdigest()})
            bitmap.close()
            page.close()
    provenance = {'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                  'dpi':dpi,'renderer':'pypdfium2', 'pages':pages}
    (output/'render.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return provenance


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('--output',required=True)
    parser.add_argument('--dpi',type=int,default=200)
    args=parser.parse_args()
    render(args.source,args.output,args.dpi)
