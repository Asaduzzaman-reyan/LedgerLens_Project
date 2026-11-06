# Walkthrough

Play `walkthrough.mp4` in this folder. It is a captioned, silent sequence of actual application screen captures; it is not a continuous desktop recording. The original still captures are retained in `walkthrough/` for inspection.

Suggested live narration if the recipient requires a continuous candidate-recorded video:

1. Start the API using the README; open the local application.
2. Upload `invoice.pdf`, `ledger.xlsx`, `incorrect-total.pdf`, and `corrupt.pdf` from `fixtures/`.
3. Show background processing and the corrupt file failure.
4. Inspect the incorrect-total invoice and its arithmetic warning.
5. Correct the total to 275.00 with a clear demo reason, save, and show preserved evidence plus history.
6. Select the invoice PDF and ledger XLSX; compare the matching invoice and explain the unmatched second invoice.
7. Search semantically for office furniture, then show keyword search.
8. Retry the corrupt file and explain that reprocessing does not repair damaged source bytes.
9. Open the reports and disclose that extraction metrics use a synthetic dataset and rules mode; the separate local-model smoke test is only three development fixtures.

The application does not require a hosted account to demonstrate these workflows. For a live local AI-extraction demonstration, use the verified setup in `docs/LOCAL_AI.md`. The captured UI walkthrough itself uses rules mode.
