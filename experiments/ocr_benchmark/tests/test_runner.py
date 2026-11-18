import json
import sys
from pathlib import Path

import pytest
from ocrbench.runner import load_manifest, run
from ocrbench.report import report


def fixtures(tmp_path, mode='ok'):
    (tmp_path/'image.png').write_bytes(b'fixture')
    sample = {'id': 'one', 'input': 'image.png', 'text': 'Glucose 7.8',
              'fields': {'glucose': '7.8'}, 'tags': {'language': 'en'}}
    path = tmp_path/'manifest.jsonl'
    path.write_text(json.dumps(sample)+'\n')
    worker = tmp_path/'fake.py'
    worker.write_text('''import json, sys, time
print(json.dumps({'ready': True}), flush=True)
for line in sys.stdin:
    request = json.loads(line)
    if sys.argv[1] == 'timeout': time.sleep(30)
    if sys.argv[1] == 'bad': print('[]', flush=True)
    else: print(json.dumps({'text': 'Glucose 7.8', 'fields': {'glucose':'7.8'}}), flush=True)
''')
    config = {'revision': 'test-v1', 'command': [sys.executable, str(worker), mode],
              'timeout_s': .2, 'startup_timeout_s': 5}
    return path, config


def test_real_protocol_cache_and_content_invalidation(tmp_path):
    manifest, config = fixtures(tmp_path)
    output = tmp_path/'output'
    first = run(manifest, config, output, repeat=2)
    assert len(first) == 2
    assert all(r['status'] == 'ok' and r['metrics']['cer'] == 0 for r in first)
    assert run(manifest, config, output, repeat=2) == first
    (tmp_path/'image.png').write_bytes(b'changed')
    second = run(manifest, config, output)
    assert first[0]['key'] != second[0]['key']


@pytest.mark.parametrize('mode,status', [('timeout', 'timeout'), ('bad', 'error')])
def test_failures_stay_in_denominator(tmp_path, mode, status):
    manifest, config = fixtures(tmp_path, mode)
    records = run(manifest, config, tmp_path/'output')
    assert records[0]['status'] == status
    summary = report(records)['overall']
    assert summary['failure_rate'] == 1
    assert summary['wer_micro'] == 1
    assert summary['field_recall_micro'] == 0


def test_duplicate_manifest_rejected(tmp_path):
    manifest, _ = fixtures(tmp_path)
    manifest.write_text(manifest.read_text()*2)
    with pytest.raises(ValueError, match='Duplicate'):
        list(load_manifest(manifest))


def test_no_placeholder_revision(tmp_path):
    manifest, config = fixtures(tmp_path)
    config['revision'] = 'SET_EXACT_PACKAGE_AND_WEIGHT_SHA256'
    with pytest.raises(ValueError, match='revision'):
        run(manifest, config, tmp_path/'out')


def test_application_secrets_not_forwarded(tmp_path, monkeypatch):
    monkeypatch.setenv('MEDVAULT_TEST_SECRET', 'dummy-secret')
    manifest, config = fixtures(tmp_path)
    script = tmp_path/'secret_probe.py'
    script.write_text('''import json, os, sys
print(json.dumps({'ready': True}), flush=True)
for line in sys.stdin:
    print(json.dumps({'text': 'LEAK' if os.getenv('MEDVAULT_TEST_SECRET') else 'Glucose 7.8'}), flush=True)
''')
    config['command'] = [sys.executable, str(script)]
    results = run(manifest, config, tmp_path/'out')
    assert results[0]['metrics']['exact_match']


def test_timeout_stops_worker_children(tmp_path):
    import psutil
    manifest, config = fixtures(tmp_path)
    script, pid_path = tmp_path/'child_probe.py', tmp_path/'child.pid'
    script.write_text('''import json, subprocess, sys, time
from pathlib import Path
print(json.dumps({'ready': True}), flush=True)
for line in sys.stdin:
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
    Path(sys.argv[1]).write_text(str(child.pid))
    time.sleep(60)
''')
    config['command'] = [sys.executable, str(script), str(pid_path)]
    result = run(manifest, config, tmp_path/'out')[0]
    assert result['status'] == 'timeout'
    pid = int(pid_path.read_text())
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
