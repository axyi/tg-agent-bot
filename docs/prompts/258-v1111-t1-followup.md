# Prompt 258 — v1.11.1 T1 follow-up: report completeness corrections

- **Date:** 2026-09-24
- **Executor model:** claude-sonnet-5
- **Model reason:** commands-only/artefacts-only orchestration; a
  self-caught documentation-completeness correction to T1's just-landed
  commit, before T2 starts.
- **Harness:** Claude Code (background session)
- **Stage:** T1 (follow-up to prompt 257, commit `7b910fd`)
- **Owner of:** this prompt file, `docs/reports/report-v1.11.1.md`,
  `docs/llm-usage.md` (row 171), `docs/prompts/257-v1111-t1-out.md`
- **REQ ids:** REQ-V1111-EC-02, REQ-V1111-EC-03, REQ-V1111-GATE-01

## Goal

Close six gaps found by the T1 subagent's own post-commit `advisor`
review of `7b910fd`, plus two the orchestrator found separately: (1)
stale line-range citations (`bot.py:221-274`/`:277-292`, should be
`:221-272`/`:274-288`) across the report, `docs/llm-usage.md` row 170 and
`docs/prompts/257-v1111-t1-out.md`; (2) `tests/test_v1110_out.py`'s full
suite was recorded as "12 passed", the real count is 11; (3) the
test-first claim overstated the authoring order (tests were written
after the source edit, not before — the red-check against the
pre-change tree via `git stash` is still valid evidence, but the
*authoring* order was implementation-first); (4) `T-V1111-OUT-02` was
not flagged as outside EC-02's four named carve-out ids even though it
passed pre-change; (5) T0's own two delegation-record bullets
(`report-v1.11.1.md`) were wrapped across multiple physical lines, so
`checks._lint_report_delegation`'s `^- T\d+ \| .*$` regex only captured
each bullet's first line (3 cells, not 5) — collapsed to one physical
line each; (6) the `## T2`–`## T6` "not reached" headings lacked the
`: <reason>` suffix `_EXEMPT_SECTION_RE` requires — added one each.
Also recorded `7b910fd`'s own `gitleaks-tree` result (the per-commit
window had closed by the time this follow-up's edits started).

## Constraints

Docs-only: `docs/reports/report-v1.11.1.md`, `docs/llm-usage.md`,
`docs/prompts/257-v1111-t1-out.md`, this prompt file. No source, test or
config file touched. Same `.env`/`data/` boundary as every other prompt
this run.

## Acceptance

All eight gaps closed; `checks._lint_report_delegation` run directly
against `docs/reports/report-v1.11.1.md` returns `[]` (verified by
importing `devtools.checks` and calling it, since `lint-docs`'s own
`report_path` config still names `report-v1.11.0.md` and won't check
this file until T6); gates 1–4 (`uv sync --locked`, `uv run --locked
ruff check .`, `uv run --locked pytest`, `uv run --locked python bot.py
--selftest`) and `uv run --locked python devtools/checks.py lint-docs`
all exit 0; the standalone `gitleaks-tree` block run against this
commit, exit 0, recorded.

## Stop

None triggered — a documentation correction, not a repair cycle against
a red gate.
