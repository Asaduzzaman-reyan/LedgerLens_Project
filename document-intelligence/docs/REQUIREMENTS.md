# Assignment analysis and execution map

The source brief describes an AI-powered document intelligence system with seven tasks and nine deliverables. Its five-day submission window is relative; no absolute start date is supplied. This repository implements a runnable local baseline and explicitly records what remains unverified.

## Execution order

1. Define document/job, source unit, invoice, issue, and audit data contracts.
2. Implement bounded digital, OCR, and spreadsheet ingestion with corrupt-input handling.
3. Add conservative extraction plus a provider-configurable AI adapter; preserve source evidence.
4. Validate numeric relationships, missing fields, duplicates, and cross-file discrepancies.
5. Expose durable background jobs, REST endpoints, search, and audited corrections.
6. Build a React review workflow around the actual API.
7. Generate labeled fixtures, execute tests and measured evaluation, inspect the UI, and package reproducible results.

## Acceptance map

| Brief requirement | Implementation / evidence | Qualification |
|---|---|---|
| Multiple PDFs/images/XLSX/XLS/CSV | `app/processing.py`, real-format tests | Bounded uploads and parser limits |
| Multi-page, multiple sheets, poor images | Page/frame/sheet iterators; degraded scan fixture | OCR depends on quality; no universal layout guarantee |
| Invoice fields and line items | `app/models.py`, `app/extraction.py` | Rules demo plus live small-model smoke test; limited evaluation |
| Do not invent missing information | Null values, uncertain fields, evidence gates | Exact grounding does not establish semantic truth |
| Financial validation | Decimal arithmetic, tolerance by common minor units | Common invoice model only |
| Duplicate invoices | Hash plus supplier/invoice identity | Advisory, new record flagged |
| PDF/PDF and PDF/Excel verification | `/api/compare` and comparison UI | Exact identity matching |
| REST upload/status/results/search/edit/retry | `app/main.py`, integration tests | Single-tenant local API |
| Background OCR and AI | Durable SQLite queue, worker, lease heartbeat | Cooperative deadline; native-process isolation is future work |
| Metadata/text/results/errors/history | `docs/schema.sql` | SQLite alternative explained |
| Keyword and semantic search | FTS5 + learned BGE vectors | In-process cosine scan; not a production vector index |
| React interface | `frontend/src/main.jsx` | All core workflows backed by API |
| Tests and actual metrics | `tests/`, `reports/` | Small synthetic dataset; no real-customer holdout |
| Approximately 1,000-page PDFs | Streaming benchmark | Digital parsing only; not full OCR/LLM load testing |
| Repository and setup | Local Git repository, README, lock files | Remote hosting not performed |
| Recorded walkthrough | Packaged UI walkthrough | See recording notes for exact format |
| Prompts and AI assistance disclosure | `docs/AI_DISCLOSURE.md` | Candidate must review and understand the implementation |

## Remaining work before claiming full production acceptance

Select and evaluate a production-suitable LLM, test on diverse independently labeled invoices, score complete line-item and multi-invoice recall, benchmark end-to-end 1,000-page scanned documents, verify Docker in the target environment, implement tenant/user access control and worker isolation, perform security/load testing, and provide the submission destination if remote hosting is desired. These are not disguised as completed validations.
