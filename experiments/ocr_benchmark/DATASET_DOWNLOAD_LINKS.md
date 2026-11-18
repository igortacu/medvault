# OCR datasets — download handoff

Prepared on 2026-11-18. This document contains links and commands only;
no dataset download was performed on the current machine.
Revisions below were resolved from the publishers' Hugging Face repositories.
Sizes are the sum of repository file sizes at those revisions (decimal GB/TB),
not required working space after preprocessing or caching.

| Dataset | Pinned revision | Full repository size | Format |
|---|---|---:|---|
| NVIDIA OCR Synthetic Multilingual v1 | `69696a1cc543ef3a0f8e9892a89c17293e915263` | ~5.45 TB | HDF5 images, full-page labels, boxes |
| Romanian FinePDFs Eval | `bda4f251dda4d002253e5a1cc832942f677ae8a9` | ~0.914 GB | 3 Parquet shards, page images and extracted reference text |
| OmniDocBench | `aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec` | ~1.55 GB | Page images and rich JSON annotations |

## 1. NVIDIA OCR Synthetic Multilingual v1

- [Dataset card and terms](https://huggingface.co/datasets/nvidia/OCR-Synthetic-Multilingual-v1)
- [All files at the pinned revision](https://huggingface.co/datasets/nvidia/OCR-Synthetic-Multilingual-v1/tree/69696a1cc543ef3a0f8e9892a89c17293e915263)
- [English test shards](https://huggingface.co/datasets/nvidia/OCR-Synthetic-Multilingual-v1/tree/69696a1cc543ef3a0f8e9892a89c17293e915263/en/test)
- [Russian test shards](https://huggingface.co/datasets/nvidia/OCR-Synthetic-Multilingual-v1/tree/69696a1cc543ef3a0f8e9892a89c17293e915263/ru/test)
- [Direct download: English test_000.h5](https://huggingface.co/datasets/nvidia/OCR-Synthetic-Multilingual-v1/resolve/69696a1cc543ef3a0f8e9892a89c17293e915263/en/test/test_000.h5?download=true)
- [Direct download: Russian test_000.h5](https://huggingface.co/datasets/nvidia/OCR-Synthetic-Multilingual-v1/resolve/69696a1cc543ef3a0f8e9892a89c17293e915263/ru/test/test_000.h5?download=true)
- [Pinned README](https://huggingface.co/datasets/nvidia/OCR-Synthetic-Multilingual-v1/resolve/69696a1cc543ef3a0f8e9892a89c17293e915263/README.md)

The complete repository includes training, validation and test data for six language
folders: en, ja, ko, ru, zh_hans, zh_hant. For the first MedVault evaluation, use only
the EN/RU test split. One shard is a smaller download option, not the complete test
split or a random sample of the whole corpus. Record chosen shards and sample IDs.
License in the publisher's card: CC BY 4.0.

## 2. Romanian FinePDFs Eval

- [Dataset card and terms](https://huggingface.co/datasets/OpenLLM-Ro/ro_finepdfs_eval)
- [Pinned file browser](https://huggingface.co/datasets/OpenLLM-Ro/ro_finepdfs_eval/tree/bda4f251dda4d002253e5a1cc832942f677ae8a9)
- [Direct download: Parquet shard 1/3](https://huggingface.co/datasets/OpenLLM-Ro/ro_finepdfs_eval/resolve/bda4f251dda4d002253e5a1cc832942f677ae8a9/data/test-00000-of-00003.parquet?download=true)
- [Direct download: Parquet shard 2/3](https://huggingface.co/datasets/OpenLLM-Ro/ro_finepdfs_eval/resolve/bda4f251dda4d002253e5a1cc832942f677ae8a9/data/test-00001-of-00003.parquet?download=true)
- [Direct download: Parquet shard 3/3](https://huggingface.co/datasets/OpenLLM-Ro/ro_finepdfs_eval/resolve/bda4f251dda4d002253e5a1cc832942f677ae8a9/data/test-00002-of-00003.parquet?download=true)

Approximately 1,250 Romanian pages. Reference text was extracted from PDFs;
do not describe it as fully human-verified transcription. Retain document ID and
page number to group pages by source document. Dataset card lists ODC-BY.

## 3. OmniDocBench

- [Dataset card and research-use terms](https://huggingface.co/datasets/opendatalab/OmniDocBench)
- [Pinned file browser](https://huggingface.co/datasets/opendatalab/OmniDocBench/tree/aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec)
- [Direct download: OmniDocBench.json annotations](https://huggingface.co/datasets/opendatalab/OmniDocBench/resolve/aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec/OmniDocBench.json?download=true)
- [Page images at the same revision](https://huggingface.co/datasets/opendatalab/OmniDocBench/tree/aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec/images)
- [Official evaluator source](https://github.com/opendatalab/OmniDocBench)

Keep image filenames and JSON annotations together. This pinned main revision is
not the older v1.5 release with 1,355 pages. Pin a compatible evaluator revision
before reporting official scores. The dataset publisher restricts the content to
research use and excludes commercial use.

## Optional download commands — execute only on the storage machine

Install the Hugging Face CLI there using the environment manager of choice:

```sh
python -m pip install huggingface_hub
```

Set an actual storage mount path, then download the complete smaller datasets:

```sh
DATASET_ROOT=/storage/ocr-datasets

hf download OpenLLM-Ro/ro_finepdfs_eval --repo-type dataset \
  --revision bda4f251dda4d002253e5a1cc832942f677ae8a9 \
  --local-dir "$DATASET_ROOT/finepdfs-ro"

hf download opendatalab/OmniDocBench --repo-type dataset \
  --revision aa1ee96d106dbe53d0ae59474d75c6e6d9b53fec \
  --local-dir "$DATASET_ROOT/omnidocbench"
```

NVIDIA option A: one EN and one RU test shard for an initial evaluation:

```sh
hf download nvidia/OCR-Synthetic-Multilingual-v1 \
  README.md en/test/test_000.h5 ru/test/test_000.h5 \
  --repo-type dataset --revision 69696a1cc543ef3a0f8e9892a89c17293e915263 \
  --local-dir "$DATASET_ROOT/nvidia-ocr"
```

NVIDIA option B: all EN/RU test shards, excluding training and other languages:

```sh
hf download nvidia/OCR-Synthetic-Multilingual-v1 --repo-type dataset \
  --revision 69696a1cc543ef3a0f8e9892a89c17293e915263 \
  --include 'en/test/*' --include 'ru/test/*' --include 'README.md' \
  --local-dir "$DATASET_ROOT/nvidia-ocr"
```

NVIDIA option C: the entire ~5.45 TB repository, including all training data:

```sh
hf download nvidia/OCR-Synthetic-Multilingual-v1 --repo-type dataset \
  --revision 69696a1cc543ef3a0f8e9892a89c17293e915263 \
  --local-dir "$DATASET_ROOT/nvidia-ocr"
```

Append `--dry-run` to inspect a selection before downloading. Preserve the pinned
README files, download selection and SHA-256 inventory alongside the evaluation.

## Benchmark handoff status

The downloads are raw datasets, not ready-to-run benchmark manifests. Dataset
importers for these three formats have not yet been implemented in this worktree.
The existing harness expects JSONL rows with unique `id`, `cluster_id`, image `input`,
reference `text` and dataset/language/split `tags`; optional `table_html` and field GT
must be matched to the correct task. Do not compute text CER against an incomplete
page reference that omits visible tables or formulas. Use official OmniDocBench
matching/evaluation for comparable TEDS/CDM scores.

Once inputs have been converted and a model config has been prepared on the target:

```sh
cd experiments/ocr_benchmark
.venv/bin/python -m ocrbench run \
  --manifest /storage/ocr-datasets/prepared/manifest.jsonl \
  --config /path/to/target-model-config.json \
  --output /storage/ocr-results/run-001 --workers 1
```

That command is conditional on preparation above. The current `run_all.py` defaults
to a synthetic smoke manifest and local Mac paths; do not use it unchanged for these
datasets on another host. MLX requires Apple Silicon; a Linux/NVIDIA GPU machine
needs a compatible PaddleOCR-VL backend and regenerated model paths/checksums.
Benchmark code is on branch `codex/ocr-benchmark` in the MedVault repository.
Check out that branch or copy `experiments/ocr_benchmark` in addition to the dataset
links. Local environments, model weights and generated datasets are excluded from Git.
