# Prompt 147 -- v1.9.0 T3 erratum: test strengthening

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for a bounded, test-only follow-up with a fully normative brief (exact assertions, exact code paths to read first); no design judgement needed.
- **Harness:** Claude Code
- **Stage:** T3 (erratum)
- **Owner of:** `tests/test_v190_chunking.py`, `tests/test_v190_parsing.py`
- **REQ ids:** REQ-V190-DOC-02, REQ-V190-DOC-03

## Goal

T3 (commit c53becf) implemented `documents.py`'s `classify`/`extract`/
`chunk_text` and `devtools/pdf_fixture.py`, all gates green, but T3's own
subagent flagged two of its own new tests as weaker than warranted for a
spec-mandated "high effort/high care" algorithm (DOC-03 chunking). This
prompt strengthens exactly those two tests, against the already-reviewed and
confirmed-correct implementation -- no production-code change.

1. Chunking overlap edge case (DOC-03): `_start_new_chunk`'s
   `char_start = max(char_start, span_end - hard_max)` clamp shrinks the
   200-char overlap when a paragraph separator plus a near-`target`-length
   paragraph would otherwise push the new chunk's total length past
   `hard_max` (1200). The prior test for "overlap is exactly 200" only used
   single-paragraph text, which never reaches this clamp. Added a new test
   with two 1000-char paragraphs separated by `\n\n`, asserting both (a)
   `char_end - char_start <= 1200` and (b) `char_start >
   previous_chunk.char_end - 200`, proving the clamp fired; and a companion
   test for the common multi-paragraph case (short separators, pieces well
   under target) confirming overlap stays exactly 200 there.
2. Corrupted-PDF exception-type precision (DOC-02): the truncated-PDF test
   used bare `pytest.raises(Exception)`. Read `documents.py`'s PDF branch
   (`_extract_pdf`, no `except` clause of its own) and confirmed empirically
   that a truncated fixture raises `pypdf.errors.PdfStreamError` (a
   `PdfReadError`, a `PyPdfError`). Tightened the test to that exact type,
   and added a new test proving the boundary holds the other way: a
   `PdfTooManyPagesError` from a >500-page fixture is not an instance of
   `pypdf.errors.PdfReadError`/`PyPdfError` -- the two failure classes are
   genuinely distinguishable by type.

## Constraints

- Test-file-only change: `documents.py` and `devtools/pdf_fixture.py`'s
  logic is untouched (both already reviewed and confirmed correct by the
  orchestrator before this prompt started).
- If a genuine production bug were found while tightening the exception-type
  assertion, stop and report rather than patching `documents.py`. None was
  found: the exception-boundary rule (DOC-02) already holds by construction
  (`PdfTooManyPagesError` is `documents.py`'s own class, unrelated to
  pypdf's `PyPdfError` hierarchy).
- No dependency changes; no changes outside the two named test files.

## Acceptance

- `uv run --locked ruff check .` exits 0.
- `uv run --locked pytest` exits 0 (1362 collected, up from 1358 before this
  prompt; the two new tests --
  `test_t_v190_doc_04_overlap_clamped_when_paragraph_gap_pushes_past_hard_max`
  and
  `test_t_v190_doc_02_too_many_pages_is_not_the_corrupted_pdf_class` -- plus
  the companion `test_t_v190_doc_04_overlap_is_exactly_200_across_paragraph_boundaries`
  and the tightened `test_t_v190_doc_02_pdf_truncated_is_corrupted_pdf_class`
  all pass).
- `uv run --locked python bot.py --selftest` exits 0.

## Stop

Would stop and report instead of continuing if tightening the PDF exception
assertion had revealed the exception boundary did not actually hold by type
(e.g. `PdfTooManyPagesError` incorrectly overlapping pypdf's own exception
hierarchy), or if the chunking edge case had turned out to require an
actual logic fix in `_start_new_chunk`/`chunk_text` rather than a stronger
test. Neither happened: both failure classes were confirmed distinct by
type, and the hard_max clamp already behaves as the T3 orchestrator's review
described.
