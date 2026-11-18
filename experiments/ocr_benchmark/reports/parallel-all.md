# Local concurrent smoke runs

15 synthetic pages; 3 source templates. Host contention affects latency.
PaddleOCR-VL uses the local MLX 4-bit backend; native CPU run was stopped for resource pressure.
Paddle uses a Latin recognizer. Russian results do not represent a Cyrillic-capable configuration.
Missing metrics or reports are not successful tests. No production model winner is selected.

| Model | Completed | CER | WER | Failure | p50 s | p95 s | Peak RSS GiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| tesseract | 15/15 | 0.84% | 4.58% | 0.00% | 0.24 | 0.32 | 0.10 |
| paddle | 15/15 | 17.13% | 26.25% | 0.00% | 5.79 | 8.58 | 6.99 |
| docling | 15/15 | 17.54% | 22.92% | 0.00% | 1.03 | 2.20 | 2.40 |
| paddle-vl | 15/15 | 1.86% | 10.00% | 0.00% | 4.25 | 6.05 | 1.51 |
