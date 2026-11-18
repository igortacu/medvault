import json
import subprocess
import sys


def test_missing_prediction_is_not_silently_dropped(tmp_path):
    (tmp_path/'a.png').write_bytes(b'image')
    manifest = tmp_path/'manifest.jsonl'
    manifest.write_text(json.dumps({'id':'a','input':'a.png','text':'hello','fields':{'dose':'0.5'}})+'\n')
    predictions = tmp_path/'predictions.jsonl'
    predictions.write_text('')
    output = tmp_path/'scores'
    subprocess.run([sys.executable, '-m', 'ocrbench', 'score', '--manifest', str(manifest),
                    '--predictions', str(predictions), '--output', str(output)], check=True, capture_output=True)
    report = json.loads((output/'summary.json').read_text())['overall']
    assert report['attempted'] == 1
    assert report['failure_rate'] == 1
    assert report['cer_micro'] == 1
    assert report['field_recall_micro'] == 0
    assert report['latency_p95_s'] is None
