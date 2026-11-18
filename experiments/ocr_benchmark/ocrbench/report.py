import collections
import math
import random
import statistics

from .metrics import ratio


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered)-1)*fraction
    low = int(position)
    return ordered[low] + (ordered[math.ceil(position)]-ordered[low])*(position-low)


def summarize(records):
    total = len(records)
    ok = [r for r in records if r['status'] == 'ok']
    metrics = [r['metrics'] for r in records if 'metrics' in r]
    fields = [m['fields'] for m in metrics if 'fields' in m]
    tp, fp, fn = (sum(f[k] for f in fields) for k in ('tp', 'fp', 'fn'))
    chars = sum(m['characters']['reference_length'] for m in metrics)
    words = sum(m['words']['reference_length'] for m in metrics)
    latencies = [r['request_s'] for r in ok if isinstance(r.get('request_s'), (int, float))]
    result = {
        'attempted': total, 'succeeded': len(ok),
        'failure_rate': ratio(total-len(ok), total),
        'statuses': dict(collections.Counter(r['status'] for r in records)),
        'cer_micro': ratio(sum(m['characters']['edit_distance'] for m in metrics), chars),
        'wer_micro': ratio(sum(m['words']['edit_distance'] for m in metrics), words),
        'token_omission_rate_micro': ratio(sum(m['words']['deletions'] for m in metrics), words),
        'field_precision_micro': ratio(tp, tp+fp), 'field_recall_micro': ratio(tp, tp+fn),
        'field_f1_micro': ratio(2*tp, 2*tp+fp+fn),
        'latency_p50_s': percentile(latencies, .5), 'latency_p95_s': percentile(latencies, .95),
        'latency_p99_s': percentile(latencies, .99),
        'worker_peak_rss_bytes': max((r.get('worker_peak_rss_bytes', 0) for r in ok), default=None),
    }
    for key in ('cer', 'wer', 'token_precision', 'token_recall', 'token_f1',
                'normalized_edit_distance', 'teds', 'teds_structure', 'cdm', 'semantic_similarity'):
        values = [m[key] for m in metrics if m.get(key) is not None]
        result[key+'_macro'] = statistics.mean(values) if values else None
        result[key+'_coverage'] = len(values)
    security = [r['metrics']['security'] for r in ok if 'security' in r.get('metrics', {})]
    result['empty_output_rate'] = ratio(sum(m['characters']['reference_length'] > 0 and
        m['characters']['prediction_length'] == 0 for m in metrics), len(metrics))
    result['security'] = {'output_cases': len(security),
                          'inconclusive_cases': sum(r['status'] != 'ok' and
                              'security' in r.get('metrics', {}) for r in records),
                          'forbidden_output_observed': sum(s['forbidden_output_observed'] for s in security),
                          'protected_field_cases': sum(bool(s['protected_fields']['tp'] + s['protected_fields']['fn']) for s in security),
                          'protected_field_mismatch_cases': sum(s['protected_fields']['fn'] > 0 for s in security),
                          'external_actions': 'not_instrumented'}
    # Resample document clusters, keeping repetitions together. Descriptive CI on this corpus.
    clusters = collections.defaultdict(list)
    for r in records:
        if r.get('metrics', {}).get('cer') is not None:
            clusters[r.get('cluster_id', r['id'])].append(r['metrics']['cer'])
    if len(clusters) >= 2:
        values = [statistics.mean(v) for v in clusters.values()]
        rng = random.Random(42)
        boot = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(1000)]
        result['cer_document_macro_bootstrap_95'] = [percentile(boot, .025), percentile(boot, .975)]
    return result


def report(records):
    groups = collections.defaultdict(list)
    for record in records:
        for key, value in record.get('tags', {}).items():
            groups[f'{key}={value}'].append(record)
    return {'overall': summarize(records),
            'slices': {key: summarize(value) for key, value in sorted(groups.items())}}
