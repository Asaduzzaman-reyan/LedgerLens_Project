# LedgerLens — Document Intelligence

A local, working reference implementation of the AI Engineer Task 1.3 assignment. Upload business documents, extract invoice records, inspect source text, validate arithmetic, correct data with an audit trail, search, and compare invoices across files.

**Read the limits before presenting this as production-ready.** Real OCR and learned semantic embeddings run locally. The default invoice extractor is a conservative rules demo, not an LLM. The LLM adapter was tested with mocked failures and a real local Qwen model: a three-file development smoke set scored 23/24 header fields after grounding checks. See `docs/LOCAL_AI.md` for the verified setup. Synthetic evaluation is explicitly scoped and is not a claim of real-world accuracy.

## Quick start

Requirements: Python 3.12, Node.js 20.19+ or 22+, and npm. Windows also needs the Microsoft Visual C++ 2015–2022 x64 runtime for ONNX Runtime. Initial dependency/model downloads require internet access.

From this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

On macOS/Linux, use `source .venv/bin/activate` instead of the PowerShell activation command. Open **http://127.0.0.1:8000**. The built frontend is also included, so Node is only needed when rebuilding it. REST schema is at `/openapi.json`; interactive API documentation is at `/docs` (its CDN assets require internet and the CSP is relaxed only on API documentation pages).

The first semantic indexing operation downloads `BAAI/bge-small-en-v1.5` (~67 MB) into `data/models`. OCR model weights come with the RapidOCR package. The first document can take longer while these models initialize. For a quick offline run after Python dependencies are installed:

```powershell
$env:DOCINT_EMBEDDINGS='off'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keyword search still works when embeddings are off; semantic search explicitly returns 503. Missing embedding downloads do not silently turn semantic search into keyword search.

## Enable AI extraction

For the already verified small local model, follow `docs/LOCAL_AI.md` or use the sibling `Start-LedgerLens-AI.ps1` launcher on the prepared machine.

Use a locally configured Ollama installation, or an explicitly selected provider exposing a compatible chat-completions endpoint. Do not paste credentials into the source code. Example for a separately installed Ollama service:

```powershell
ollama pull qwen2.5:7b
$env:DOCINT_EXTRACTOR='llm'
$env:DOCINT_LLM_URL='http://127.0.0.1:11434/v1/chat/completions'
$env:DOCINT_LLM_MODEL='qwen2.5:7b'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Set `DOCINT_LLM_KEY` only if your provider requires it. Selecting an external URL sends extracted document text to that provider. This build used only synthetic fixtures and did not send document contents to a hosted LLM. The prompt is in `app/extraction.py` and `docs/AI_DISCLOSURE.md`. The verified llama.cpp alternative, model provenance, and live smoke results are in `docs/LOCAL_AI.md`. Rerun `python scripts/evaluate.py` with your chosen provider to measure broader AI extraction; retain the original rules evaluation for comparison.

## Use the application

1. Upload up to 20 files, each up to 30 MB by default. Unsupported and empty files are rejected individually.
2. Jobs move from queued to processing, then completed, needs-review, or failed. The progress counter is completed pages/sheet chunks, not an invented percentage.
3. Inspect invoice fields, line items, validation messages, source text, and history. Download the original when visual verification is needed.
4. Edit values and enter a correction reason. Saving reruns validation. Optimistic version checks prevent one reviewer from overwriting another review. Uncertain-field acknowledgement is explicit.
5. Check two or more processed documents and choose Compare. Matching uses supplier plus invoice number; differences and unmatched invoices are reported. This works across PDF/PDF and PDF/spreadsheet combinations.
6. Search by keyword, filename, supplier, invoice fields, or meaning. Semantic results include similarity and source unit; similarity is not a confidence score or a guarantee of relevance.
7. Retry a failed job after resolving the source/provider issue. Corrupt originals remain corrupt on retry; upload a repaired copy as a new document.

## Input behavior

| Input | Implementation | Limits |
|---|---|---|
| Digital PDF | PyMuPDF page iterator | Up to 1,500 units; 1,000-page digital benchmark included |
| Scanned PDF | Rasterize each sparse-text page, RapidOCR | 2,400-pixel render cap; quality-dependent |
| JPG, PNG, TIFF | Orientation, resize, autocontrast, RapidOCR | Multi-frame TIFF; 40M pixel guard |
| XLSX | openpyxl read-only, all worksheets | Cached formula values only; no recalculation |
| XLS | xlrd, all sheets | Numeric Excel date serials need manual review |
| CSV | UTF-8/BOM, comma/semicolon/tab detection | Other encodings must be converted first |

Structured rows accept the headers used in `fixtures/ledger.csv`. Each row can hold an invoice plus one line item. Rows with the same invoice number and supplier merge; identical purchased lines remain distinct. Simple two-column field/value sheets are also supported. Rules mode recognizes explicit labels and pipe-separated item rows. It deliberately does not claim general layout understanding. More than one invoice embedded in a single unstructured page requires LLM mode or manual separation.

Empty pages and unreadable OCR are flagged. Password-protected PDFs, corruption, unsupported contexts, or parser failures produce failed jobs. A single bad unit fails the document while retaining previously read units for diagnosis. No silent partial success. More than 100 columns, 100,000 rows per sheet, 500,000 text characters per unit, or 200 MB expanded XLSX content is rejected. CSV/sheet work is chunked into 500-row units. AI input is limited to 24,000 characters per unit and rejects larger units rather than silently truncating extraction. The selected provider may impose a lower context limit; output is capped at 2,048 tokens.

## Tests and evaluation

```powershell
python scripts/generate_fixtures.py
python -m pytest -q --junitxml=reports/tests.xml
python scripts/evaluate.py
python scripts/benchmark_large_pdf.py
```

See `reports/EVALUATION.md`, `reports/evaluation.json`, `reports/tests.xml`, `reports/large-pdf.json`, and `reports/large-pdf-api.json`. The test suite exercises real OCR, all file formats, arithmetic, missing values, corruption, duplicate detection, AI schema/grounding failures (mocked provider), API authentication, corrections, comparison, size limits, and restart recovery. Browser verification is documented separately.

The synthetic dataset is deliberately small and shares one layout. Header-field accuracy scores the first invoice only; line items and the additional XLSX invoice are tested but not included in the extraction accuracy denominator. Both valid-only success rate and all-input failure rate are reported so deliberate corruption does not hide in an ambiguous metric. The 1,000-page benchmark is digital parsing and rule extraction only, not an end-to-end OCR/LLM throughput claim.

## Configuration

See `.env.example`. Export values in your shell; the Python application does not automatically load a `.env` file. Docker Compose reads `.env` for substitution.

| Variable | Default | Purpose |
|---|---|---|
| DOCINT_DATA | data | Database, originals, model cache |
| DOCINT_TOKEN | empty | Optional shared bearer token; use outside an isolated local demo |
| DOCINT_EXTRACTOR | rules | `rules` or `llm` |
| DOCINT_EMBEDDINGS | fastembed | `fastembed` or `off` |
| DOCINT_LLM_SCHEMA | 0 | Set 1 for llama.cpp schema-constrained JSON; provider-specific |
| DOCINT_MAX_MB | 30 | Per-file upload bound |
| DOCINT_MAX_UNITS | 1500 | Pages or sheet chunks per document |
| DOCINT_JOB_SECONDS | 3600 | Cooperative processing deadline checked between units |

For frontend development, run `npm run dev` in `frontend` alongside the API on port 8000. Vite proxies `/api` to the backend. To use Docker: `docker compose up --build`; the port binds to loopback. The Docker recipe is supplied but was not executed in the authoring environment.

## Architecture and deployment judgment

See `docs/ARCHITECTURE.md`, `docs/schema.sql`, and `docs/REQUIREMENTS.md`. Python/FastAPI keeps OCR, spreadsheets, validation, and API code together. SQLite WAL and a durable leased queue make the exercise runnable without Redis/Postgres. A worker thread performs slow work; leases and heartbeats recover abandoned jobs. A restart reprocesses a stale job from its beginning, rather than pretending to checkpoint LLM output.

This is a single-machine reference implementation. Before processing thousands of customer documents daily: isolate parsers in resource-limited worker processes, add an external durable queue, PostgreSQL, object storage, an indexed vector store, tenant-aware authorization, malware scanning, rate limiting, encrypted backups, retention/deletion controls, monitoring, and representative load testing. Current vector search scans stored vectors, current document JSON retains whole result sets, and the worker can be blocked by native OCR. A cooperative deadline is not a hard subprocess timeout. OCR engine sharing is designed for one process worker; do not run multiple threaded workers in the same process.

Source documents are untrusted data. The LLM receives no tool access; output is schema-validated and unsupported scalar values are withheld. Exact excerpt checks reduce hallucinations but cannot prove semantic correctness. High-stakes financial acceptance still needs human review and production controls. Duplicate detection is advisory, and only newly processed documents receive duplicate flags; existing records are not retroactively flagged. Cross-document matching is exact normalized identity, not fuzzy vendor resolution. Currency checks validate format, not the full ISO registry. Validation assumes subtotal + tax = total and does not model shipping, withholding, discounts, credit-note semantics, or currency conversion.

## Submission materials

- Source and built React frontend in this repository.
- Requirements analysis, architecture, schema, prompt, and AI assistance disclosure in `docs/`.
- Synthetic labeled fixtures in `fixtures/`.
- Test results, measured evaluation, benchmark, and UI evidence in `reports/`.
- A 65-second captioned video assembled from genuine UI screen captures in `reports/walkthrough.mp4`, with recording limitations and live narration instructions in `reports/WALKTHROUGH.md`.

The local Git repository has a committed snapshot. No remote Git hosting, recruiter submission, or public deployment is performed by this package.

## Primary references

- [FastAPI upload documentation](https://fastapi.tiangolo.com/tutorial/request-files/)
- [RapidOCR project](https://github.com/RapidAI/RapidOCR)
- [FastEmbed documentation](https://qdrant.github.io/fastembed/)
- [Ollama compatible API](https://docs.ollama.com/api/openai-compatibility)
