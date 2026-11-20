# Public dataset runs — Windows / RTX 4050 host (2026-11-19)

100-page seeded samples (seed 20261119), built with `prepare_datasets.py`. One worker per engine,
engines run one at a time, except Paddle's FinePDFs-RO pass, which overlapped Docling. Weights match the pinned checksums in `configs/`.
Host: Windows 11, 16 logical CPUs, 16 GiB RAM, RTX 4050 Laptop (6 GiB). No model winner is selected.

| Dataset | Pages | Reference | Notes |
|---|---:|---|---|
| FinePDFs-RO (`bda4f25`) | 100 (1 per source document) | PDF text layer, not human-verified | Absolute CER inflated by reference/visible-text mismatch |
| OmniDocBench (`aa1ee96`) | 100 of 139 eligible | Human annotations | English only; no tables/formulas/masked/ignored regions; not official OmniDocBench scoring |

## Results

Full aggregate and per-slice metrics for each run: `public-datasets-windows/<dataset>-<engine>.json`
(copies of each run's `summary.json`; per-page predictions stay local because OmniDocBench is research-use only).

Reproduce a dataset sample:

```sh
python prepare_datasets.py finepdfs-ro --source datasets/raw/finepdfs-ro --output datasets/finepdfs-ro-100
python prepare_datasets.py omnidocbench --source datasets/raw/omnidocbench --output datasets/omnidocbench-en-100-ascii
```

CER/WER = micro (pooled characters/words). Token F1 = mean per-page multiset overlap, **order-insensitive**.
Latency = request p50/p95, excludes model startup.

### FinePDFs-RO (Romanian)

| Engine | Done | CER | WER | Token F1 | p50 s | p95 s | Peak RSS GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tesseract ron+rus+eng (CPU) | 100/100 | 24.86% | 37.02% | 75.3% | 2.75 | 5.94 | 0.36 |
| Docling (CPU) | 99/100 | 29.57% | 37.28% | 78.0% | 29.74 | 66.40 | 2.52 |
| PaddleOCR PP-OCRv5 latin (GPU) | 100/100 | 24.24% | 33.54% | 79.6% | 1.36 | 2.00 | 2.69 |

### OmniDocBench (English)

| Engine | Done | CER | WER | Token F1 | CER single-column | p50 s | p95 s | Peak RSS GiB |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Tesseract ron+rus+eng (CPU) | 100/100 | 9.46% | 18.59% | 84.8% | 14.0% | 2.87 | 11.31 | 1.01 |
| Docling (CPU) | 99/100 | 15.13% | 21.59% | 86.9% | 17.4% | 28.28 | 71.46 | 2.65 |
| PaddleOCR PP-OCRv5 latin (GPU) | 100/100 | 63.16% | 78.95% | 88.3% | 12.8% | 1.10 | 10.42 | 6.60 |

## Reading the results

* **Paddle recognizes the most words** (highest token F1 on both sets) but the plain PP-OCR pipeline
  has no reading-order/layout step: lines are emitted top-to-bottom across columns. On multi-column
  pages that interleaves columns, so CER is 61–77% there versus 12.8% on single-column pages. A
  layout-aware pipeline (e.g. PP-StructureV3) would be needed before its CER is comparable.
* **Tesseract** has the best CER on OmniDocBench because its page segmentation keeps column order, and it is
  the cheapest by far on CPU.
* **Docling** is slowest on this CPU (~30 s/page) with no accuracy lead here; 1 timeout per dataset.
* FinePDFs-RO per-page (macro) CER is 39–50% with wide bootstrap intervals: a few pages whose PDF text
  layer differs from the visible page dominate. Compare engines relative to each other there.
* Paddle ran on GPU and the others on CPU, so latency is not a like-for-like hardware comparison.
  Paddle CPU (oneDNN disabled because of a Paddle 3.3.1 Windows bug) took ~440 s per A4 page and was abandoned;
  its smoke-set CER was identical to the GPU run (17.25%).

## Windows changes needed to run

* `ocrbench/runner.py`: `os.killpg` fallback; workers get `PYTHONUTF8=1` and `TEMP`, `TMP`,
  `USERPROFILE`, `PROCESSOR_ARCHITECTURE` (the last one is required for Paddle GPU to load cuDNN).
  Workers still need `PYTHONUTF8=1` because they write JSON to stdout; the runner sets it.
* Explicit UTF-8 file I/O, so Romanian/Russian text no longer depends on the Windows locale (cp1252)
  or on Python UTF-8 mode: `ocrbench/runner.py` reads the manifest and writes `predictions.jsonl` and
  `run.json` as UTF-8; `ocrbench/__main__.py` reads config, predictions and external metrics and writes
  `scored.jsonl`, `scoring.json` and `summary.json` as UTF-8. Checked without `PYTHONUTF8`: 17/17
  tests pass, and `run` + `score` on the smoke set give identical CER (1.257%). The results above were
  produced before this change with `PYTHONUTF8=1` set; the metrics are unaffected.
* `configs/win/*.json` (local only, not committed; machine-specific absolute paths): copies of
  `tesseract-multilingual`, `paddle-local-latin` and `docling-local` with absolute venv paths
  (Windows `Popen` rejects the relative `.venv-*/...` form), `enable_mkldnn: false` for Paddle CPU,
  `device: gpu:0` + `paddlepaddle-gpu==3.3.1` (cu126) for Paddle GPU.
* OmniDocBench images renamed to ASCII (`datasets/omnidocbench-en-100-ascii`): Windows Tesseract
  cannot open paths containing CJK characters. IDs, text and image bytes are unchanged.
