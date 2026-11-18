# PaddleOCR integration smoke

PaddleOCR 3.7.0 / PaddlePaddle 3.3.1, PP-OCRv5 server detector and Latin mobile recognizer.
Weights are checksum-verified; exact SDK/model names and local paths are in configs/paddle-local-latin.json.
15 synthetic pages, one inference each, one CPU worker, two OMP threads. No GPU used.

| Language | Cases | CER micro | WER micro |
|---|---:|---:|---:|
| en | 5 | 0.40% | 4.00% |
| ro | 5 | 0.92% | 7.78% |
| ru | 5 | 53.98% | 70.67% |

Completed 15/15; p50 5.30s, p95 8.04s; sampled worker RSS peak 6.97 GiB.

The Russian slice is an intentionally mismatched Latin recognizer, not a Russian-capable Paddle configuration.
Do not interpret the combined score as a Paddle multilingual benchmark. A Cyrillic recognizer and a declared routing strategy are required for that experiment.
No winner is selected. This tiny, template-based corpus does not estimate clinical accuracy. Host load was uncontrolled and worker/thread settings differ from Tesseract.

The first local-directory configuration failed: SDK ignored lang/ocr_version and selected a default v6 detector against v5 weights.
The corrected configuration supplies explicit matching detector/recognizer names. Failed run checkpoints remain in local artifacts/paddle-latin for diagnosis;
failure accounting reported 15/15 errors rather than dropping them.

PaddleOCR-VL and Docling have adapters but no real inference evidence yet. CDM and semantic metrics have not been computed.
Full metrics and run metadata: paddle-smoke-summary.json.
