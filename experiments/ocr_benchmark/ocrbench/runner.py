"""Bounded persistent workers, hard process-group timeout, content-addressed resume."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import platform
import queue
import signal
import sqlite3
import subprocess
import sys
import threading
import time

import psutil

from .metrics import field_metrics, text_metrics, teds

MAX_LINE = 16 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def load_manifest(path):
    seen = set()
    with Path(path).open() as stream:
        for index, line in enumerate(stream, 1):
            sample = json.loads(line)
            if not isinstance(sample.get('id'), str) or not isinstance(sample.get('text'), str):
                raise ValueError(f'Invalid id/text at line {index}')
            if sample['id'] in seen:
                raise ValueError(f'Duplicate id: {sample["id"]}')
            seen.add(sample['id'])
            file = (Path(path).resolve().parent / sample['input']).resolve()
            if not file.is_file():
                raise ValueError(f'Missing input at line {index}')
            sample['input'] = str(file)
            sample['input_sha256'] = digest(file.read_bytes())
            for key in ('fields',):
                if key in sample and not isinstance(sample[key], dict):
                    raise ValueError(f'Invalid {key} at line {index}')
            yield sample


class Worker:
    def __init__(self, config, log_path):
        self.config = config
        self.log = open(log_path, 'ab')
        # Do not forward the app's .env or credentials to model workers.
        env = {k: v for k, v in os.environ.items() if k in
               ('PATH', 'HOME', 'LANG', 'TMPDIR', 'SYSTEMROOT', 'VIRTUAL_ENV', 'DYLD_LIBRARY_PATH',
                'TEMP', 'TMP', 'USERPROFILE', 'PROCESSOR_ARCHITECTURE')}
        env.update({'PYTHONUTF8': '1', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
                    'TOKENIZERS_PARALLELISM': 'false', 'PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK': 'True', 'OMP_NUM_THREADS': str(config.get('cpu_threads', 1))})
        command = config.get('command') or [config.get('python', sys.executable), '-m', 'ocrbench.worker', canonical(config)]
        self.proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=self.log, start_new_session=True, env=env)
        self.messages = queue.Queue(maxsize=2)
        self.peak_rss = 0
        self.stopped = threading.Event()
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._memory, daemon=True).start()
        try:
            self.info = self.receive(config.get('startup_timeout_s', 180))
            if self.info.get('ready') is not True:
                raise ValueError('Missing ready handshake')
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            while True:
                line = self.proc.stdout.readline(MAX_LINE + 1)
                if not line:
                    self.messages.put(RuntimeError('Worker exited'))
                    return
                if len(line) > MAX_LINE:
                    raise ValueError('Worker output exceeds limit')
                self.messages.put(json.loads(line))
        except Exception as error:
            self.messages.put(error)

    def _memory(self):
        while not self.stopped.wait(.05):
            try:
                proc = psutil.Process(self.proc.pid)
                processes = [proc] + proc.children(recursive=True)
                self.peak_rss = max(self.peak_rss, sum(p.memory_info().rss for p in processes))
            except psutil.Error:
                pass

    def receive(self, timeout):
        try:
            value = self.messages.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError('Worker deadline exceeded') from None
        if isinstance(value, Exception):
            raise value
        if not isinstance(value, dict):
            raise ValueError('Worker response must be an object')
        return value

    def predict(self, sample):
        self.proc.stdin.write((canonical({'input': sample['input']})+'\n').encode())
        self.proc.stdin.flush()
        prediction = self.receive(self.config.get('timeout_s', 60))
        if not isinstance(prediction.get('text'), str) or not isinstance(prediction.get('fields', {}), dict):
            raise ValueError('Invalid prediction schema')
        return prediction

    def close(self):
        self.stopped.set()
        # Model servers may detach their own inference subprocesses into new groups.
        try:
            descendants = psutil.Process(self.proc.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            descendants = []
        if self.proc.poll() is None:
            try:
                if hasattr(os, 'killpg'):
                    os.killpg(self.proc.pid, signal.SIGKILL)
                else:  # Windows: no process groups; descendants are killed below.
                    self.proc.kill()
            except ProcessLookupError:
                pass
            except PermissionError:
                if self.proc.poll() is None:
                    self.proc.kill()
        for descendant in reversed(descendants):
            try:
                descendant.kill()
            except psutil.NoSuchProcess:
                pass
        self.proc.wait()
        for handle in (self.proc.stdin, self.proc.stdout, self.log):
            handle.close()


def evaluate(sample, prediction):
    result = text_metrics(sample['text'], prediction['text'])
    if 'fields' in sample:
        result['fields'] = field_metrics(sample['fields'], prediction.get('fields', {}))
    if 'table_html' in sample:
        result['teds'] = teds(sample['table_html'], prediction.get('table_html', ''))
        result['teds_structure'] = teds(sample['table_html'], prediction.get('table_html', ''), True)
    if sample.get('security'):
        # These tests grade output manipulation only, never claim network isolation.
        policy = sample['security']
        result['security'] = {
            'forbidden_output_observed': any(marker in prediction['text'] for marker in policy.get('forbidden_outputs', [])),
            'protected_fields': field_metrics(policy.get('protected_fields', {}), prediction.get('fields', {})),
            'external_actions': 'not_instrumented',
        }
    return result


def run(manifest, config, output, workers=1, repeat=1, retry_failures=False):
    if workers < 1 or repeat < 1:
        raise ValueError('workers and repeat must be positive')
    if not config.get('revision') or config['revision'].startswith('SET_'):
        raise ValueError('Set revision to exact model/artifact version, not latest')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(output / 'results.sqlite')
    db.execute('CREATE TABLE IF NOT EXISTS results (key TEXT PRIMARY KEY, result TEXT NOT NULL)')
    local = threading.local()
    live = []
    lock = threading.Lock()
    for path, expected_hash in config.get('artifacts', {}).items():
        if digest(Path(path).read_bytes()) != expected_hash:
            raise ValueError(f'Artifact checksum mismatch: {path}')
    code_hash = digest(b''.join(p.read_bytes() for p in sorted(Path(__file__).parent.glob('*.py'))))
    snapshot = output / 'code'
    snapshot.mkdir(exist_ok=True)
    for source in Path(__file__).parent.glob('*.py'):
        (snapshot / source.name).write_bytes(source.read_bytes())
    identity = digest(canonical({'config': config, 'code': code_hash}).encode())
    started = time.perf_counter()
    records = []
    cache_hits = 0

    def task(sample, repetition, key):
        before = time.perf_counter()
        result = {'id': sample['id'], 'key': key, 'repetition': repetition,
                  'tags': sample.get('tags', {}), 'cluster_id': sample.get('cluster_id', sample['id']),
                  'input_sha256': sample['input_sha256']}
        try:
            if not getattr(local, 'worker', None):
                local.worker = Worker(config, output / f'worker-{threading.get_ident()}.log')
                with lock:
                    live.append(local.worker)
            worker = local.worker
            if not getattr(local, 'warmed', False):
                for _ in range(config.get('warmup_requests', 0)):
                    worker.predict(sample)
                local.warmed = True
            tick = time.perf_counter()
            prediction = worker.predict(sample)
            request_seconds = time.perf_counter()-tick
            result.update(status='ok', prediction=prediction, metrics=evaluate(sample, prediction),
                          request_s=request_seconds, worker_info=worker.info,
                          worker_peak_rss_bytes=worker.peak_rss)
        except Exception as error:
            result.update(status='timeout' if isinstance(error, TimeoutError) else 'error',
                          error_type=type(error).__name__,
                          metrics=evaluate(sample, {'text': '', 'fields': {}}))
            if getattr(local, 'worker', None):
                local.worker.close()
                local.worker = None
                local.warmed = False
        result['total_s'] = time.perf_counter()-before
        return result

    def jobs():
        nonlocal cache_hits
        for sample in load_manifest(manifest):
            for repetition in range(repeat):
                key = digest(canonical([identity, sample, repetition]).encode())
                cached = db.execute('SELECT result FROM results WHERE key=?', (key,)).fetchone()
                cached_result = json.loads(cached[0]) if cached else None
                if cached_result and not (retry_failures and cached_result['status'] != 'ok'):
                    cache_hits += 1
                    cached_result.pop('prediction', None)
                    records.append(cached_result)
                else:
                    yield sample, repetition, key

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            pending = set()
            for args in jobs():
                pending.add(pool.submit(task, *args))
                if len(pending) >= workers * 2:
                    done, pending = concurrent.futures.wait(pending, return_when=concurrent.futures.FIRST_COMPLETED)
                    for future in done:
                        save(db, records, future.result())
            for future in concurrent.futures.as_completed(pending):
                save(db, records, future.result())
    finally:
        for worker in live:
            worker.close()
    elapsed = time.perf_counter()-started
    with (output / 'predictions.jsonl').open('w') as stream:
        for result in sorted(records, key=lambda r: (r['id'], r['repetition'])):
            raw = db.execute('SELECT result FROM results WHERE key=?', (result['key'],)).fetchone()[0]
            stream.write(raw+'\n')
    db.close()
    metadata = {'config': config, 'code_sha256': code_hash, 'identity': identity,
                'platform': platform.platform(), 'python': sys.version,
                'workers': workers, 'repeat': repeat, 'wall_s': elapsed,
                'cache_hits': cache_hits, 'executed': len(records)-cache_hits,
                'executed_requests_per_wall_s': (len(records)-cache_hits)/elapsed if elapsed else None,
                'resume_note': 'executed throughput excludes cache hits; request latency excludes startup/warmup/scoring'}
    (output / 'run.json').write_text(canonical(metadata)+'\n')
    return records


def save(db, records, result):
    db.execute('INSERT OR REPLACE INTO results VALUES (?, ?)', (result['key'], canonical(result)))
    db.commit()
    records.append({k: v for k, v in result.items() if k != 'prediction'})
