# Prompt 149 — v1.9.0 T4 erratum: post-chunking zero-chunk guard

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation tasks in this run (T1-T4 used the same model).
- **Harness:** Claude Code
- **Stage:** T4 (erratum)
- **Owner of:** `documents.py`; `tests/test_v190_errors.py`
- **REQ ids:** REQ-V190-DOC-04

## Goal

Close the gap T4 (prompt 148) itself found and reported rather than
silently fixed: DOC-04's extraction-time "empty document" floor sums
non-whitespace characters across every page, but DOC-03 chunks each PDF
page independently and `chunk_text` applies its own per-call floor to each
page's chunk set on its own. A multi-page PDF can clear the summed floor
while every individual page falls under `chunk_text`'s own floor, so
chunking yields zero chunks overall -- previously stored as a
`documents` row with `chunk_count=0`, no chunks, no vectors, and no error;
visible in `/documents` forever, permanently unsearchable. Add a
post-chunking guard in `index_document`: if `chunk_rows` is empty after
chunking completes (across every page for a PDF, or the single
`chunk_text` call for txt/md/docx), raise `documents.EmptyDocumentError`
-- the same class the extraction-time check already raises -- before the
embed/store stages, so ERR-01 row 4 ("The document contains no readable
text.") covers both paths identically downstream, and the existing
transactional-safety guarantee (raise before `BEGIN IMMEDIATE`, nothing
written) extends to this path too.

## Constraints

This is an operator-authorized fix for a gap T4's own subagent surfaced
during T4's own work -- it is not a requirement spelled out anywhere in
`docs/spec/spec-v1.9.0.md`'s DOC-04 row list; the orchestrator reviewed
the finding and the operator made the call to close it now rather than
carry it as a known issue. Narrow scope only: `documents.py` and its
tests. Reuse `EmptyDocumentError` -- do not invent a second exception
class for the same user-facing outcome. Do not touch `bot.py`, T7's
Telegram-facing error strings, or `_handle_document` (unowned by this
prompt, same boundary T4 itself respected). Do not run
`devtools/mutation_check.py`, `--selftest-live`, or any live gate.

## Acceptance

`uv run --locked ruff check .`, `uv run --locked pytest` (1379 collected,
up from 1378 after T4), `uv run --locked python bot.py --selftest` all
exit 0. New test
`test_t_v190_err_01_row_4_pdf_zero_chunks_across_pages_raises_and_stores_nothing`
in `tests/test_v190_errors.py` reproduces the exact scenario: two PDF
pages of 15 non-whitespace chars each (30 summed, clears the 20-char
extraction-time floor; 15 each, under `chunk_text`'s own 20-char
single-chunk floor, so each page chunks to `[]`) -- asserts
`documents.EmptyDocumentError` is raised and that `documents`, `chunks`
and `vec_chunks` are all empty for the user afterward. The pre-existing
extraction-time empty-text test
(`test_t_v190_err_01_row_4_empty_document_raises_and_stores_nothing`,
plain txt under the 20-char floor) passes unchanged -- this prompt adds a
second path to the same outcome, not a replacement for the first.

## Stop

Not applicable -- the fix was small and converged in one pass: no repair
loop was needed, no second exception class was found necessary, and no
further gap surfaced while implementing this one.
