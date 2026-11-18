import argparse
import json
from pathlib import Path

from .report import report
from .runner import canonical, digest, evaluate, load_manifest, run


def main():
    parser = argparse.ArgumentParser(description='Local OCR benchmark; inputs and outputs may contain medical data.')
    sub = parser.add_subparsers(dest='action', required=True)
    execute = sub.add_parser('run')
    execute.add_argument('--manifest', required=True)
    execute.add_argument('--config', required=True)
    execute.add_argument('--output', required=True)
    execute.add_argument('--workers', type=int, default=1)
    execute.add_argument('--repeat', type=int, default=1)
    execute.add_argument('--retry-failures', action='store_true')
    score = sub.add_parser('score', help='Evaluate predictions from any engine without running inference')
    score.add_argument('--manifest', required=True)
    score.add_argument('--predictions', required=True)
    score.add_argument('--output', required=True)
    score.add_argument('--semantic-model', help='Existing LOCAL sentence-transformers model directory')
    score.add_argument('--external-metrics', help='JSON with provenance and per-id official CDM scores in [0,1]')
    args = parser.parse_args()
    if args.action == 'run':
        records = run(args.manifest, json.loads(Path(args.config).read_text()),
                      args.output, args.workers, args.repeat, args.retry_failures)
    else:
        predictions = {}
        for line in Path(args.predictions).read_text().splitlines():
            row = json.loads(line)
            if row['id'] in predictions:
                raise ValueError('Duplicate prediction id')
            predictions[row['id']] = row
        external = None
        if args.external_metrics:
            external = json.loads(Path(args.external_metrics).read_text())
            if not all(external.get(k) for k in ('evaluator', 'revision', 'dataset_sha256', 'scores')):
                raise ValueError('External metrics require evaluator/revision/dataset_sha256/scores')
        if external and external['dataset_sha256'] != digest(Path(args.manifest).read_bytes()):
            raise ValueError('External metric dataset hash does not match manifest')
        semantic = None
        if args.semantic_model:
            from sentence_transformers import SentenceTransformer
            if not Path(args.semantic_model).is_dir():
                raise ValueError('Semantic model must be a local directory')
            semantic = SentenceTransformer(args.semantic_model, local_files_only=True)
        records = []
        samples = list(load_manifest(args.manifest))
        unknown = set(predictions)-{s['id'] for s in samples}
        if unknown:
            raise ValueError(f'Unknown prediction ids: {sorted(unknown)}')
        for sample in samples:
            row = predictions.get(sample['id'])
            prediction = row.get('prediction', row) if row else {'text': '', 'fields': {}}
            status = row.get('status', 'ok') if row else 'missing'
            if status != 'ok':
                prediction = {'text': '', 'fields': {}}
            if not isinstance(prediction.get('text'), str):
                raise ValueError('Prediction text must be a string')
            metrics = evaluate(sample, prediction)
            if semantic and status == 'ok' and sample['text'] and prediction['text']:
                if any(len(semantic.tokenizer.encode(text)) > semantic.max_seq_length
                       for text in (sample['text'], prediction['text'])):
                    raise ValueError('Semantic input exceeds model token limit; score shorter annotated blocks')
                embeddings = semantic.encode([sample['text'], prediction['text']], normalize_embeddings=True)
                metrics['semantic_similarity'] = float(embeddings[0] @ embeddings[1])
            if external and sample['id'] in external['scores']:
                value = external['scores'][sample['id']]
                if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    raise ValueError('CDM must be in [0,1]')
                metrics['cdm'] = value
            records.append({'id': sample['id'], 'status': status, 'tags': sample.get('tags', {}),
                            'cluster_id': sample.get('cluster_id', sample['id']),
                            'metrics': metrics, 'request_s': row.get('request_s') if row else None})
        out = Path(args.output)
        out.mkdir(parents=True, exist_ok=True, mode=0o700)
        (out/'scored.jsonl').write_text('\n'.join(canonical(r) for r in records)+'\n')
        (out/'scoring.json').write_text(canonical({'semantic_model': args.semantic_model,
                                                  'external_metrics': external})+'\n')
    summary = report(records)
    Path(args.output, 'summary.json').write_text(canonical(summary)+'\n')
    print(json.dumps(summary['overall'], indent=2))


if __name__ == '__main__':
    main()
