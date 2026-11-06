# Measured evaluation

Measured on 4 November 2026. These are executed local results, not estimates. See the JSON files and JUnit XML for machine-readable evidence.

## Results

| Measure | Observed result |
|---|---|
| Automated tests | 37 unique tests passed across a 36-test full run and a final 20-test AI/API/validation regression run; zero failures/errors |
| Header-field extraction accuracy | 99/104 = 95.19% |
| Valid document processing success | 13/13 = 100% |
| Success across all supplied inputs | 13/15 = 86.67% |
| Failure across all supplied inputs | 2/15 = 13.33%; both intentionally corrupt |
| Expected success/failure outcome accuracy | 100% |
| Mean extraction time | 2.826 seconds/file |
| Median extraction time | 0.060 seconds/file |
| Total extraction evaluation time | 42.391 seconds |
| 1,000-page digital parsing + rules extraction | 1.938 seconds; 515.99 pages/second |
| Peak RSS in digital parsing benchmark | 75.94 MB, including imports and prior PDF creation |
| 1,000-page API + queue + persistence benchmark | 50.545 seconds; 1,000 invoice records, status review |

## Measurement boundaries

The dataset contains 15 synthetic files: digital invoices, a multi-page PDF, PNG/JPG/TIFF variants, scanned PDF, a degraded image, multi-frame TIFF, CSV, multi-sheet XLSX, legacy XLS, and two deliberate corruptions. Valid format variants share one invoice template. This is a reproducibility set, not a diverse held-out business benchmark.

The main 15-file extraction evaluation used **rules**. OCR used real RapidOCR models. Scalar scoring uses the first invoice and eight header fields, normalizing decimal numeric equality and requiring exact other values. Missing-field nulls are scored. Line-item accuracy, invoice-count recall, and the second XLSX invoice are not included in this metric; targeted tests cover some of these behaviors. A separate live local-model smoke evaluation is described below.

Evaluation timing includes parser and OCR startup/inference but excludes uploads, queue waits, embeddings and API overhead. Tests and evaluation ran concurrently on the same host, so contention affects these single-run timings. No p95, load capacity, confidence interval or real-world generalization is inferred.

The standalone large-PDF benchmark measures digital parsing and extraction only. The separate API benchmark includes TestClient upload, durable queue, validation, and SQLite writes with embeddings disabled; it excludes browser/network transit, scanned-page OCR and LLM work. It ran alongside automated tests. Both use a generated 1,000-page PDF, not a production corpus.

Semantic search was exercised using actual `BAAI/bge-small-en-v1.5` inference. `semantic-search.json` captures one real query response; it establishes integration, not retrieval precision/recall.

## Per-file measurements

| File | Outcome | Seconds | Header fields correct |
|---|---|---:|---:|
| invoice.pdf | success | 0.2361 | 8/8 |
| incorrect-total.pdf | success | 0.0216 | 8/8 |
| missing-fields.pdf | success | 0.0204 | 8/8 |
| multipage.pdf | success | 0.0088 | 8/8 |
| invoice.png | success | 15.6854 | 8/8 |
| invoice.jpg | success | 7.1831 | 7/8 |
| invoice.tiff | success | 4.4826 | 8/8 |
| scanned.pdf | success | 3.2064 | 7/8 |
| poor-scan.png | success | 5.5030 | 5/8 |
| multipage.tiff | success | 5.9497 | 8/8 |
| ledger.csv | success | 0.0090 | 8/8 |
| ledger.xlsx | success | 0.0203 | 8/8 |
| ledger.xls | success | 0.0599 | 8/8 |
| corrupt.pdf | failure | 0.0029 | 0/0 |
| corrupt.xlsx | failure | 0.0015 | 0/0 |

## Failure analysis

JPEG and scanned-PDF OCR each lost one header field; the degraded scan lost three. The system retained uncertain/missing values for review. The two corrupt files raised parser errors as expected. Rules mode always requests human verification, even when arithmetic passes. Passing this fixture set does not establish general invoice extraction quality.

The final test run emitted one upstream deprecation warning: Starlette recommends its newer HTTP client testing integration. The current HTTPX TestClient path executed all tests successfully. Docker was not executed. A local LLM endpoint was subsequently exercised as described below.

## Live local LLM development smoke test

Qwen2.5-0.5B-Instruct Q4_K_M through llama.cpp b6000 (CPU, 2 threads, 4,096-token context) scored 23/24 = 95.83% on three synthetic development fixtures. All three returned schema-constrained responses. The digital invoice and missing-fields cases each scored 8/8; the degraded scan scored 7/8. The model/schema prompt was refined on this set, so this is not a held-out benchmark. See live-llm-evaluation.json for outputs and timings.

A real upload-to-worker-to-model-to-database run also completed with status review: the model flagged uncertain fields and the application retained those warnings. See live-llm-api.json. No hosted provider or customer data was used. Local weights/provenance and reproduction are documented in docs/LOCAL_AI.md.

## Reproduce

Run the commands in the README. For the API benchmark, first generate the 1,000-page file with `scripts/benchmark_large_pdf.py`, then run `python scripts/benchmark_api.py data/benchmark-1000.pdf data/api-benchmark`. The API benchmark asserts 1,000 persisted units and invoices. Use fresh data directories for independent runs.
