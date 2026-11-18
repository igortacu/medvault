"""Summarize independent benchmark outputs without selecting a model winner."""
import argparse
import csv
import json
from pathlib import Path


def compare(root):
    root = Path(root)
    rows, full = [], {}
    for name in ('tesseract', 'paddle', 'docling', 'paddle-vl'):
        path = root/name/'summary.json'
        if not path.exists():
            rows.append({'model': name, 'status': 'no_report'})
            continue
        summary = json.loads(path.read_text())
        full[name] = summary
        value = summary['overall']
        row = {'model': name, 'status': f"{value['succeeded']}/{value['attempted']}",
               'cer': value['cer_micro'], 'wer': value['wer_micro'],
               'failure_rate': value['failure_rate'], 'p50_s': value['latency_p50_s'],
               'p95_s': value['latency_p95_s'],
               'peak_rss_gib': (value['worker_peak_rss_bytes']/1024**3
                                if value['worker_peak_rss_bytes'] is not None else None)}
        for language in ('en', 'ro', 'ru'):
            row['cer_'+language] = summary['slices'].get('language='+language, {}).get('cer_micro')
        rows.append(row)
    columns = ['model','status','cer','wer','cer_en','cer_ro','cer_ru','failure_rate','p50_s','p95_s','peak_rss_gib']
    with (root/'comparison.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    (root/'comparison.json').write_text(json.dumps(full,indent=2)+'\n')
    lines = ['# Local concurrent smoke runs', '',
             '15 synthetic pages; 3 source templates. Host contention affects latency.',
             'PaddleOCR-VL uses the local MLX 4-bit backend; native CPU run was stopped for resource pressure.',
             'Paddle uses a Latin recognizer. Russian results do not represent a Cyrillic-capable configuration.',
             'Missing metrics or reports are not successful tests. No production model winner is selected.', '',
             '| Model | Completed | CER | WER | Failure | p50 s | p95 s | Peak RSS GiB |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    def fmt(value, percent=False):
        return 'N/A' if value is None else (f'{value:.2%}' if percent else f'{value:.2f}')
    for row in rows:
        lines.append('| '+ ' | '.join([row['model'],row['status'],
            fmt(row.get('cer'),True),fmt(row.get('wer'),True),fmt(row.get('failure_rate'),True),
            fmt(row.get('p50_s')),fmt(row.get('p95_s')),fmt(row.get('peak_rss_gib'))])+' |')
    (root/'comparison.md').write_text('\n'.join(lines)+'\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('root')
    compare(parser.parse_args().root)
