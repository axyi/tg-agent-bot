# Prompt 146 -- v1.9.0 T3: document parsing and chunking

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for a spec-driven implementation task with a fully normative brief (exact algorithms, exact limits); no exploratory judgement calls needed beyond the brief itself.
- **Harness:** Claude Code
- **Stage:** T3
- **Owner of:** `documents.py`, `devtools/pdf_fixture.py`, `tests/test_v190_parsing.py`, `tests/test_v190_chunking.py`
- **REQ ids:** REQ-V190-DOC-01, REQ-V190-DOC-02, REQ-V190-DOC-03, REQ-V190-DOC-06

## Goal

Implement the parsing/chunking half of `documents.py` (DOC-01, DOC-02,
DOC-03) plus the standard-library PDF fixture writer `devtools/pdf_fixture.py`
(DOC-06), test-first, per `docs/spec/task-briefs/v190-T3.md`.
`documents.index_document` (DOC-04, DOC-05) is out of scope -- that is T4's
task, built on top of `extract`/`chunk_text` as defined here.

## Constraints

- No dependency beyond the five already pinned in `pyproject.toml` as of T1
  (`pypdf==6.18.0`, `python-docx==1.2.0` used here).
- `documents.py` writes no file anywhere: no `open(`, no `Path(`, no
  `tempfile`; extraction runs entirely on in-memory `bytes`
  (`T-V190-SEC-04` greps this). Neither `documents.py` nor `rag.py` (T5,
  not this prompt) imports `bot`.
- `Extracted`/`ExtractedPage` are defined exactly once, no `page_numbers`
  field, no `tuple[str, ...]` form.
- `chunk_text` does not know about pages or `chunk_index`; those are T4's
  `index_document`'s job. No budget parameter added to `extract` or
  `chunk_text` pre-emptively.
- Fixtures generated in memory only (txt/md literals, DOCX via
  `python-docx` into `io.BytesIO`, PDF via `devtools/pdf_fixture.write_pdf`);
  nothing binary committed.
- Do not run `devtools/mutation_check.py` or any `--selftest-live`/live
  gate in this task.

## Acceptance

- `uv run --locked ruff check .` exits 0.
- `uv run --locked pytest` exits 0 (1359 collected, up from 1304 before
  this task; all 55 new `T-V190-DOC-01..06` tests in
  `tests/test_v190_parsing.py` and `tests/test_v190_chunking.py` pass).
- `uv run --locked python bot.py --selftest` exits 0.

## Stop

Would stop and report instead of continuing if the DOC-03 chunking
algorithm's stated invariant ("1,200 is the hard ceiling everywhere") could
not be reconciled with the accumulation rule's offset bookkeeping without an
undisclosed design choice -- it could be reconciled (see the `hard_max`
clamp in `_start_new_chunk`, documented in the function's own docstring),
so no stop was needed. Would also stop on a pre-existing test broken by this
task's changes outside REQ-V190-EC-03's amendment list; none was found --
`documents.py` and `devtools/pdf_fixture.py` are both new files with no
existing callers to disturb.
