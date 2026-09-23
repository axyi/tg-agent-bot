# Prompt 249 — v1.11.0 T7 Phase D: fix REV-01 finding 1 (cancel-before-commit race)

- **Date:** 2026-09-23
- **Executor model:** claude-sonnet-5
- **Model reason:** a scoped review-fix task (test-first bug fix plus two
  new tests) within one already-reviewed file pair — no architecture
  decision, no cross-file design tradeoff.
- **Harness:** Claude Code (delegated subagent)
- **Stage:** T7 (Phase D)
- **Owner of:** `bot.py` (`IngestWorker._mark_committing`),
  `tests/test_v1110_ing.py` (`T-V1110-ING-12`, `T-V1110-ING-13`)
- **REQ ids:** REQ-V1110-ING-04, REQ-V1110-REV-01

## Goal

Fix REV-01's one 🔴 must-fix finding (`docs/reports/report-v1.11.0.md`
`## T7` Phase C): a `/cancel` landing in the gap between `index_document`'s
last cancellation checkpoint and `IngestWorker._mark_committing` (the
`before_commit` callable) was silently lost — the job committed anyway and
sent a `✅ …` success reply despite the user having already been told
`Cancelling <name>…`. Test-first (EC-02): add the new test(s), watch them
fail for the right reason on the unfixed code, then apply the fix.

## Constraints

Test-first; do not touch anything outside `bot.py`/
`tests/test_v1110_ing.py`. `documents.py`'s `index_document` calls
`before_commit()` with no `try`/`except` around it — this must stay true
(confirmed unchanged, `documents.py:568-569`), since the fix relies on
`IndexCancelled` propagating naturally to `IngestWorker._process`'s
existing `except documents.IndexCancelled:` clause.
`T-V1110-ING-09` (the other half of this boundary — `/cancel` arriving
*after* the `committing` transition) must still pass unamended. Do not run
gate 5, `mutation_check.py`, `rag_eval.py`, `agent_eval.py`, or
`bench.py`. Do not run `ruff format`, only `ruff check .`.

## Acceptance

`tests/test_v1110_ing.py::test_t_v1110_ing_12_cancel_in_the_gap_before_before_commit`
and `::test_t_v1110_ing_13_mark_committing_checks_cancel_under_lock` both
fail on the unfixed tree (for the right reason) and pass after the fix;
`::test_t_v1110_ing_09_cancel_in_commit_phase` passes unamended throughout.
Gates 1-4 green (`uv run --locked ruff check .`, `uv run --locked pytest`,
`uv run --locked python bot.py --selftest`).

## Stop

Not applicable — the fix and its tests landed within the brief's exact
scope; no widening was needed.
