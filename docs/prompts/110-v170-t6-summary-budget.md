# Prompt 110 — spec-v1.7.0 T6: the summary wall-clock budget

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T6
- **Owner of:** `agent.py`, `bot.py`, `config.py` (SUMMARY_BUDGET_FLOOR_S,
  duplicated), `tests/test_pricing.py`, `tests/test_v11_patch.py` (two
  disclosed stub-signature fixes), `tests/test_v170_reasoning.py` (extended),
  `docs/prompts/110-v170-t6-summary-budget.md` (new)
- **REQ ids:** REQ-V170-SUM-01, -02, -03, -04, -05

## Goal

Land the shared wall-clock budget for the whole summary path: one deadline
taken before attempt 1, a non-positive-remaining rule for attempt 1 and a
stricter floor rule for the retry/repair, every request's HTTP timeout
derived from the same remaining budget, and the rescue retry forced to
`reasoning="off"` regardless of policy.

## Constraints

- `budget_s is None` (every existing caller) is byte-identical to today's
  behaviour -- no deadline, no timeout override.
- A skipped request writes no `llm_calls` row; the outcome is one redacted
  `log.warning` line, never a raised exception.
- The retry/repair reasoning is always produced by
  `resolve_reasoning("off", frozenset(), "summary")`, never hand-built.
- Only the two test-double signatures found broken by this task's own
  `bot.py` change are touched; no other line in either file changes.
- One prompt -> one commit, referencing this file.

## Acceptance

- `tests/test_v170_reasoning.py` green (18 new tests: SUM-01…-05, N5).
- Full suite green: `uv run --locked pytest` (1103 collected).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python bot.py --selftest` and `--selftest-live` both
  exit 0.
- `uv run --locked python devtools/mutation_check.py` exits 0 (83/83
  killed).
- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
  exits 0.

## Stop

None triggered.
