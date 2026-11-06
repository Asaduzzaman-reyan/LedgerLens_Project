# Browser verification

The built React frontend was served by the real FastAPI application on loopback and exercised through the in-app browser on 4 November 2026 (Asia/Dhaka).

Verified actions:

- Multi-file chooser uploaded a PDF invoice, two-sheet XLSX ledger, incorrect-total PDF, and corrupt PDF together.
- Background polling showed processed records and the failed corrupt input.
- Invoice fields and two line items rendered from the backend response.
- Validation displayed `subtotal + tax != total` for the known incorrect-total fixture.
- A manual correction changed total 290.00 to 275.00 with an explicit demo reason. The status changed to completed; the original evidence remained 290.00.
- History showed before/after values and the correction reason.
- PDF-to-XLSX comparison matched INV-1042 and reported the second XLSX invoice as unmatched.
- Semantic search for “furniture for an office” returned the real BGE-indexed ledger and invoice records; this is a smoke check, not a relevance benchmark.
- Retrying the corrupt file queued another attempt, then failed again with another recorded history event.
- Desktop layout was checked at 1366 x 900, and mobile at 390 x 844. The mobile document scroll width equaled its available viewport width (375 CSS pixels excluding scrollbar), with tables scrolling within their containers.
- Browser error log inspection returned no errors during the verified workflow.

Screenshots are in `desktop.jpg`, `mobile.jpg`, and `walkthrough/`. The captioned walkthrough video is assembled from these genuine captured UI states. It is a silent, stepped screen-capture walkthrough, not an uninterrupted real-time screen recording or a narration by the candidate. The desktop viewport screenshot mechanism produced softer text on some captures; the full-page overview is sharper.

API authorization, version-conflict handling, provider failures, corrupt formats, limits, and durable queue recovery are covered by automated tests rather than asserted from screenshots. The final comparison precision and duplicate-refresh fixes were verified by automated regression tests after this browser pass.
