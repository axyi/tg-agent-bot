# Prompt 157 — v1.9.0 T11 review fix: the envelope-arithmetic comment

- **Date:** 2026-09-11
- **Executor model:** claude-sonnet-5
- **Model reason:** repo-standard executor for spec-driven implementation and review-fix tasks in this run.
- **Harness:** Claude Code
- **Stage:** T11 (review fix)
- **Owner of:** `tools.py` (the `RAG_PASSAGE_CHARS`/envelope-cap comment, lines 112-131); `tests/test_v190_tool.py` (the `documents` import and the new worst-case test)
- **REQ ids:** REQ-V190-TOOL-02

## Goal

Fix one finding from T11's clean-context code review of the `go
docs/spec/spec-v1.9.0.md` run (RAG over documents). The `tools.py:112-117`
comment proving the `search_documents` envelope's 12,000-char cap "never
bisects a passage" assumed a header of at most ~120 chars, but
`_render_passage_block`'s real header -- `"[{index}] {filename} — "` plus
optional `"page {page} | "` plus `"chunk {chunk_index}: "` -- can reach 150
chars once `filename` sits at `documents.CLEAN_FILENAME_MAX_CHARS` (120) and
`page`/`chunk_index` reach 3 digits. Recompute the true worst case, correct
the comment's arithmetic so the proof is right as written (not just true by
luck), and add one empirical test that exercises exactly that worst case.

## Constraints

No runtime behaviour or constants change unless the recomputation shows the
12,000-char cap is actually violated. It is not: true worst case is 10
blocks x (1,000-char body + 150-char header) = 11,500, plus the `"Found 10
passages:"` line (18 chars) and 10 `"\n\n"` separators (20 chars) = 11,538,
still under 12,000 (empirically measured at 11,529 chars, since 9 of the 10
headers are 1 char shorter than the index-10 worst case). Only the comment
and the test suite change.

## Acceptance

- `uv run --locked ruff check .` exit 0.
- `uv run --locked pytest` exit 0, 1558 passed / 1 skipped (was 1557 passed /
  1 skipped before this prompt) -- `--collect-only -q` totals 1559.
- `uv run --locked python bot.py --selftest` exit 0.
- New test `test_t_v190_tool_02_worst_case_envelope_never_bisects_a_passage`
  (`tests/test_v190_tool.py`) builds 10 passages with a 120-char filename, a
  3-digit page (500) and chunk_index (999), and a body of exactly
  `RAG_PASSAGE_CHARS`; asserts the envelope stays under
  `RAG_SEARCH_ENVELOPE_MAX_CHARS`, contains no `"…"`, and that every
  `_render_passage_block` output (header + full body) appears intact in the
  final envelope text -- the empirical proof the comment previously lacked.

## Stop

Not applicable -- the recomputation confirmed the cap holds (11,529 <
12,000, ~470-char margin), so no runtime constant was touched and no repair
loop was needed.
