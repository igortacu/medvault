# MedVault local OCR benchmark

An isolated experiment, based on refreshed `origin/main` at
`9a6915850d205bd4a2ae5e793152f89c3094fc2b`, branch `feat/ocr-benchmark`.
The app is not modified. The user-provided Principal AI/ML Engineer brief informs
this design: reproducible evidence, clinical correctness, explicit failure accounting,
limited privileges and operational cost before model selection.

## Quick start (Python 3.11)

From this directory:

```sh
uv venv --python 3.11
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m pytest tests -q
.venv/bin/python generate_smoke.py --output datasets/smoke --font /path/to/Arial.ttf
.venv/bin/python -m ocrbench run --manifest datasets/smoke/manifest.jsonl --config configs/tesseract.json --output artifacts/tesseract --workers 2 --repeat 2
```

Install `tesseract` separately. `tesseract.json` is deliberately labelled an
**English-only baseline**; it must not be presented as a multilingual engine result.
`configs/tesseract-multilingual.json` specifies pinned tessdata-fast RO/RU/EN models
and checksums. Download each traineddata file to `models/tessdata/` from:
`https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/87416418657359cb625c412a48b6e1d6d41c29bd/{ron,rus,eng}.traineddata`.
Use that config for the multilingual comparison. Models and corpora are ignored by Git.

`summary.json` has aggregate and tag-slice metrics; `predictions.jsonl` has auditable
per-case outputs; `results.sqlite` checkpoints every completed task; `run.json`
records code identity, configuration, platform, versions, startup times and execution
metadata. Worker stderr logs, predictions and databases can contain medical data:
keep artifacts local, use synthetic fixtures for CI and explicitly manage retention.

## Contract and denominators

One JSON object per line, one rendered page per sample:

```json
{"id":"lab-001-p1","cluster_id":"lab-001","input":"images/lab-001-p1.png","text":"Glucose: 7.8 mmol/L","fields":{"glucose":"7.8","unit":"mmol/L"},"table_html":"<table><tr><td>Glucose</td><td>7.8</td></tr></table>","tags":{"language":"en","document_type":"lab","quality":"scan","split":"test"}}
```

Input paths are relative to the manifest. IDs must be unique. Keep pages and augmented
variants of one original document in the same `cluster_id` and dataset split. For PDFs,
use `python render_pdf.py input.pdf --output datasets/rendered --dpi 200` to
render pages once with a fixed renderer, DPI and revision before comparing engines;
do not compare OCR-on-raster with text-layer extraction under one label. Built-in
adapters accept image inputs; pre-rendered pages avoid differing PDF code paths.
Preserve original files separately and add a dedicated PDF hidden-layer track.

Prediction interchange format:

```json
{"id":"lab-001-p1","text":"Glucose: 7.8 mmol/L","fields":{"glucose":"7.8","unit":"mmol/L"},"table_html":"<table><tr><td>Glucose</td><td>7.8</td></tr></table>"}
```

```sh
.venv/bin/python -m ocrbench score --manifest datasets/golden/manifest.jsonl --predictions artifacts/model.jsonl --output artifacts/scored
```

Unknown/duplicate IDs fail validation; missing predictions remain in the denominator
and are scored as empty predictions. Runtime errors and timeouts also get empty-output
quality scores, plus a separate failure count. Empty outputs are also reported separately. Metric exceptions mark a case failed,
not silently skipped. Undefined denominators are `null`, accompanied by coverage/counts.
There is no single aggregate leaderboard score mixing unrelated objectives.

| Metric | Definition / applicability |
|---|---|
| CER / WER | Levenshtein substitutions + deletions + insertions, divided by GT characters / whitespace tokens. Both macro and micro aggregation; can exceed 1. |
| Edit distance | Raw character and token edit counts per sample; normalized distance uses max(reference length, prediction length). |
| Token precision / recall / F1 | Multiset token overlap, preserving duplicate counts. Not layout detection precision/recall. |
| Field precision / recall / F1 | Exact normalized key/value matching; wrong value contributes both FP and FN. Do not credit dose changes as semantically equivalent. |
| Omission | Aligned token deletions / GT token count. Substitutions are counted separately, not called omissions. |
| Failure rate | Missing + error + timeout attempts / all attempted cases; status breakdown retained. |
| TEDS / TEDS-S | Ordered tree edit distance on one explicitly matched HTML table pair; span mismatch costs 1, normalized cell content edit cost; structure-only variant ignores content. Missing table output scores zero on annotated table cases. Independent PubTabNet-style implementation, not yet certified leaderboard parity. |
| CDM | **Formula recognition** metric, imported from a pinned official evaluator. Not a general clinical document similarity metric; `null` without applicable formula annotations and real evaluator results. |
| Semantic similarity | Optional cosine of local sentence-transformers embeddings. Diagnostic only, never the clinical acceptance gate. Full page embeddings can truncate; use short annotated blocks within the chosen model's token limit. |
| Performance | Startup separately; persistent-worker request p50/p95/p99, actual executed requests / wall time in run.json, sampled process-tree peak RSS. GPU VRAM and power are not instrumented. |

Normalization is NFC plus whitespace collapse, case-sensitive, preserving diacritics,
minus signs, decimal separators and units. CER here excludes whitespace layout.
For exact reading order, layout IoU/mAP and formula scoring, use the official document
benchmark tracks below. Keep these definitions when comparing runs.

95% CER bootstrap intervals resample original-document clusters, not repeated inferences.
Synthetic templates are not independent clinical samples. These intervals describe this
corpus; they are not population guarantees. Quality summaries include failures; latency
percentiles include only successful, measured requests. Inspect both together.

## Model adapters and compute isolation

Built-ins: Tesseract CLI, PaddleOCR `PaddleOCR.predict`, PaddleOCR-VL
`PaddleOCRVL.predict`, and Docling `DocumentConverter`. Paddle and Docling examples
are templates: replace `SET_EXACT...` with package version + exact weight identity;
placeholder revisions are rejected. The PaddleOCR adapter was additionally tested with real PP-OCRv5 weights using
`configs/paddle-local-latin.json` and `requirements-paddle.lock.txt`. Local model
directories require explicit matching model names: specifying directories disables
`lang`/`ocr_version` selection in the tested SDK, otherwise defaults may select v6.
Docling has now been validated with real inference using docling-local.json.
PaddleOCR-VL v1 has been validated with the official pipeline and a local MLX 4-bit
service using paddle-vl-mlx-local.json. The native CPU variant exceeded the practical
RAM budget on this 16 GiB host and was stopped before completing a page.

Use a separate environment per model, keeping its torch/paddle dependencies out of
FastAPI. Set config `python` to that environment's absolute executable. Pre-download
weights, configure local model directories in `options`, record all weight checksums
in `artifacts` (`path -> sha256`) and freeze that environment. `revision` labels alone
are not cryptographic attestation. Package versions are emitted in worker handshakes;
Tesseract executable version is captured too. Set a new revision after upgrades and use
an output directory per hardware/model/configuration. Never call an unpinned run
reproducible. Pipeline caches check code/config/input/annotation content.

Models load once per worker. Concurrency is bounded at `2 * workers` pending tasks;
model instances are never shared between worker processes. Raw predictions stay in
SQLite/on disk; aggregation retains per-case metrics (O(n), not constant-memory).
`warmup_requests` optionally discards initial predictions per worker. Startup and
warmup are excluded from request percentiles but included in end-to-end wall time.
Do not increase workers on one GPU blindly: start at 1 and measure memory. RSS is
sampled every 50 ms and may miss peaks; it is not GPU memory. Score TEDS/CDM separately
from inference for clean accelerator utilization at large scale.

Every request has a wall deadline; a timeout or protocol error kills the complete
worker process group, then the next task gets a new worker. Successful and failed
results are resumable; use `--retry-failures` to rerun failed cases. Code changes
invalidate the cache. Stdout is NDJSON protocol, logs go to stderr. A custom worker
can be supplied as a shell-free `command` argv; it must emit `{"ready":true}` then one
prediction object per input `{"input":"/absolute/page.png"}`. Output is capped at 16 MiB.
Only input path is sent to the model process: never GT labels or security expectations.

Offline environment flags and removing application env variables are defense in depth,
**not a sandbox**. For untrusted documents, enforce OS/container isolation: no network,
no real credentials, read-only input/model mounts, temporary writable scratch, process,
CPU and memory limits. The supplied Dockerfile implements a Tesseract baseline:

```sh
docker build -t medvault-ocrbench .
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --memory 4g --cpus 2 --tmpfs /tmp:rw,noexec,nosuid,size=512m -v "$PWD/datasets:/bench/datasets:ro" -v "$PWD/artifacts:/bench/artifacts:rw" medvault-ocrbench python -m ocrbench run --manifest datasets/smoke/manifest.jsonl --config configs/tesseract.json --output artifacts/container --workers 1
```

Build/download is an explicit preparation stage. Never mount the application's secrets
or all of HOME. Docker execution is documented but was not exercised on this host.

## Existing benchmarks worth reusing

* [OmniDocBench](https://github.com/opendatalab/OmniDocBench): text, reading order,
  layout, tables (TEDS/TEDS-S), formulas (CDM). Pin repository AND dataset revisions.
  Run their native matching/evaluation for published comparability. Export model
  predictions as per-page Markdown alongside their original dataset annotations.
* [PubTabNet](https://github.com/ibm-aur-nlp/PubTabNet): table-focused evaluation and
  original TEDS implementation. Useful for validating our TEDS implementation before
  making any claim of parity. Scientific tables are not Moldovan lab forms.
* [olmOCR-Bench](https://github.com/allenai/olmocr/tree/main/olmocr/bench): targeted
  content, ordering and table tests that complement character averages. Run native
  benchmark assertions; don't rename these results CER or MedVault field F1.

No third-party datasets or model weights are vendored. Check dataset/model licenses
and record source/revision/split and original-document IDs when preparing corpora.
Public benchmark performance does not replace a held-out MedVault RO/RU/EN corpus.
Start with 100 manually verified original documents, balanced by language/document
type and including low-quality images; reserve a test split by original document
before tuning. This is a collection plan, not existing labelled data.

### Official CDM results and optional semantic scores

Run the official OmniDocBench formula evaluator in its isolated environment with its
rendering dependencies and resource limits. Do not execute untrusted TeX unrestricted.
Import **per-page aggregated formula CDM in [0,1]**, not the 0..100 leaderboard display:

```json
{"evaluator":"OmniDocBench/CDM","revision":"EXACT_COMMIT","dataset_sha256":"SHA256_OF_MANIFEST_BYTES","scores":{"formula-page-001":0.93}}
```

```sh
.venv/bin/python -m ocrbench score --manifest datasets/golden/manifest.jsonl --predictions artifacts/model.jsonl --external-metrics artifacts/official-cdm.json --output artifacts/scored
# In a scoring-only environment with sentence-transformers installed and local weights:
.venv/bin/python -m ocrbench score --manifest datasets/blocks/manifest.jsonl --predictions artifacts/blocks.jsonl --semantic-model /absolute/local/model --output artifacts/semantic
```

The import checks dataset hash, evaluator provenance and score range. It does not
implement or run CDM itself, or attest that imported scores are genuine. Semantic
model weights/revision must be recorded alongside the scoring run; embedding model
loading is local-only. Embeddings are not calibrated clinical correctness scores.

## Prompt injection and clinical integrity

The smoke generator covers English/Romanian/Russian clean, blur, rotation, visible
instruction and white-on-white instruction images (15 pages). The visible attack's
text belongs in faithful transcription GT. Merely transcribing it is not executing
it. Hidden source marker appearance is an observation, not proof of data exfiltration.
`security.protected_fields` checks exact extraction against known clinical values;
`security.forbidden_outputs` checks only markers absent from visible source.

Security reports explicitly mark external actions as `not_instrumented`. The harness
has no app credentials or action tools, but that alone does not prove network or
filesystem isolation. Unit tests verify the grader; OS isolation needs separate tests
with disposable canary files, monitored egress and process traces in the sandbox.
Never grade a crash, blank refusal or unobserved channel as a blocked attack.

Before deployment, expand the corpus with PDF hidden layers/metadata (including the
P05 Terramed fixture available on dev, absent from this main base), off-page/tiny text,
Unicode/encoded attacks, benign clinical instructions, altered dose/decimal/unit,
wrong-patient requests and repeated variants. Test extractor output schema separately
from authorization: patient ID and write permissions must come from backend context.
Keep extraction a proposal until reviewed; no model gets direct application write tools.

## Current evidence and limits

See `reports/smoke-baseline.md` and `reports/paddle-smoke.md`. Tesseract and the PaddleOCR Latin configuration have actually run here.
All four adapters now have real inference evidence in reports/parallel-all.md.
PaddleOCR-VL uses a quantized MLX backend, so this is not a native CPU comparison.
TEDS has unit coverage; CDM and semantic similarity remain uncomputed in the smoke run,
reported as null with zero coverage. No representative medical accuracy, model winner,
production capacity, or comprehensive injection resistance has been established.

## Run all prepared engines in the terminal

From this directory, after installing the matching per-engine lock files and local weights:

```sh
.venv/bin/python run_all.py --parallel 2 --output artifacts/parallel-all
```

The launcher uses one worker per model and two concurrent models by default for
this 16 GiB host. Native PaddleOCR-VL is not selected: the tested MLX 4-bit
configuration is used. The MLX service binds only to 127.0.0.1:8111, is launched as a
worker child and shares its timeout/cleanup lifecycle. Its weights are pre-downloaded.
A fresh comparison is saved as Markdown, CSV and JSON under the output directory.
Concurrent-run latency is subject to contention; compare dedicated runs for capacity planning.

Transcription scores now use Docling's plain text export and PaddleOCR-VL's
structured block text; Markdown is retained separately. This avoids penalizing an
engine solely for adding heading markers. The smoke corpus still has no labelled
tables, formulas or extracted fields.
