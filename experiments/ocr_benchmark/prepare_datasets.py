"""Convert downloaded public OCR datasets into ocrbench manifests (seeded page samples).

finepdfs-ro : OpenLLM-Ro/ro_finepdfs_eval Parquet shards -> one page per source document.
omnidocbench: opendatalab/OmniDocBench English pages whose annotation fully covers the
              visible text (no tables, formulas, masks, ignored/abandoned regions), so
              plain-text CER is not computed against an incomplete reference.
"""
import argparse
import glob
import hashlib
import json
import random
from pathlib import Path

TEXT_CATEGORIES = {'text_block', 'title', 'header', 'footer', 'page_number', 'figure_caption',
                   'reference', 'page_footnote', 'list_group', 'code_txt', 'table_caption',
                   'equation_caption', 'figure_footnote', 'table_footnote', 'code_txt_caption'}


def write_manifest(output, rows, provenance):
    path = output/'manifest.jsonl'
    path.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
    provenance['manifest_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    provenance['ids'] = [r['id'] for r in rows]
    (output/'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    print(f'{path}: {len(rows)} pages')


def finepdfs(source, output, count, seed, min_chars):
    import pyarrow.parquet as pq
    shards = sorted(glob.glob(str(Path(source)/'data'/'*.parquet')))
    pages = []
    for shard in shards:
        table = pq.read_table(shard, columns=['id', 'page_number', 'text'])
        for index, row in enumerate(table.to_pylist()):
            if len(row['text'].strip()) >= min_chars:
                pages.append((shard, index, row['id'], row['page_number']))
    by_doc = {}
    for page in pages:
        by_doc.setdefault(page[2], []).append(page)
    rng = random.Random(seed)
    docs = sorted(by_doc)
    rng.shuffle(docs)
    # One page per source document keeps samples independent across clusters.
    chosen = [rng.choice(sorted(by_doc[d], key=lambda p: p[3])) for d in docs[:count]]
    (output/'images').mkdir(parents=True, exist_ok=True)
    rows = []
    cache = {}
    for shard, index, doc_id, page_no in chosen:
        if shard not in cache:
            cache[shard] = pq.read_table(shard).to_pylist()
        row = cache[shard][index]
        short = hashlib.sha256(doc_id.encode()).hexdigest()[:12]
        name = f'ro-{short}-p{page_no}'
        (output/'images'/f'{name}.png').write_bytes(row['image']['bytes'])
        rows.append({'id': name, 'cluster_id': doc_id, 'input': f'images/{name}.png',
                     'text': row['text'],
                     'tags': {'language': 'ro', 'dataset': 'finepdfs-ro', 'split': 'test',
                              'reference': 'pdf-text-layer'}})
    write_manifest(output, rows, {'dataset': 'OpenLLM-Ro/ro_finepdfs_eval',
        'revision': 'bda4f251dda4d002253e5a1cc832942f677ae8a9', 'seed': seed,
        'filter': f'reference text >= {min_chars} chars; one page per document',
        'eligible_pages': len(pages), 'eligible_documents': len(by_doc)})


def omnidocbench(source, output, count, seed):
    source = Path(source)
    data = json.loads((source/'OmniDocBench.json').read_text(encoding='utf-8'))

    def eligible(page):
        if page['page_info']['page_attribute'].get('language') != 'english':
            return False
        for item in page['layout_dets']:
            category = item['category_type']
            if item.get('ignore') or (category != 'figure' and category not in TEXT_CATEGORIES):
                return False
            if '$' in (item.get('text') or ''):
                return False
        return (source/'images'/page['page_info']['image_path']).is_file()

    def reference(page):
        items = [i for i in page['layout_dets'] if i['category_type'] in TEXT_CATEGORIES and i.get('text')]
        def key(item):
            xs, ys = item['poly'][0::2], item['poly'][1::2]
            return (item['order'] is None, item['order'] or 0, min(ys), min(xs))
        return '\n'.join(i['text'].strip() for i in sorted(items, key=key))

    pool = sorted((p for p in data if eligible(p)), key=lambda p: p['page_info']['image_path'])
    rng = random.Random(seed)
    chosen = rng.sample(pool, min(count, len(pool)))
    (output/'images').mkdir(parents=True, exist_ok=True)
    rows = []
    for page in chosen:
        info = page['page_info']
        image = info['image_path']
        # ASCII file names: Windows Tesseract/OpenCV cannot open non-ASCII paths.
        local = 'odb-'+hashlib.sha256(image.encode()).hexdigest()[:16]+Path(image).suffix
        (output/'images'/local).write_bytes((source/'images'/image).read_bytes())
        attrs = info['page_attribute']
        rows.append({'id': Path(image).stem, 'cluster_id': Path(image).stem,
                     'input': f'images/{local}', 'text': reference(page),
                     'tags': {'language': 'en', 'dataset': 'omnidocbench', 'split': 'test',
                              'layout': attrs.get('layout'), 'document_type': attrs.get('data_source')}})
    write_manifest(output, rows, {'dataset': 'opendatalab/OmniDocBench',
        'revision': 'aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec', 'seed': seed,
        'filter': 'english; only text categories (+figures); no ignore, masks, tables, equations or $ inline math',
        'eligible_pages': len(pool),
        'note': 'Reading-order-sensitive CER; multi-column pages tagged by layout. Not official OmniDocBench scoring.'})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('dataset', choices=['finepdfs-ro', 'omnidocbench'])
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--count', type=int, default=100)
    parser.add_argument('--seed', type=int, default=20261119)
    parser.add_argument('--min-chars', type=int, default=50)
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.dataset == 'finepdfs-ro':
        finepdfs(args.source, output, args.count, args.seed, args.min_chars)
    else:
        omnidocbench(args.source, output, args.count, args.seed)
