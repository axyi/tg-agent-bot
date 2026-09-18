# Prompt 223 — v1103 T3: the delegation-record lint (LINT-01)

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** source-writing task, delegated per EC-03 default.
- **Harness:** Claude Code (general-purpose subagent)
- **Stage:** T3
- **Owner of:** `devtools/checks.py`, `config/quality_gates.yaml`,
  `tests/test_v1103_lint.py`, `tests/test_v1103_gates.py`
- **REQ ids:** REQ-V1103-LINT-01, REQ-V1103-ERR-01 (rows 3-4)

## Goal

Add `_lint_report_delegation`, a sibling of `_lint_report_ledger`, wired
behind a new boolean `delegation_record` yaml key on `lint-docs`, which
checks every non-exempt `## T<n>` report section for a valid five-cell
delegation-record bullet. Repoint `lint-docs`'s `report_path` to
`docs/reports/report-v1.10.3.md` in the same commit. Full grammar in
`docs/spec/task-briefs/v1103-T3.md`.

## Constraints

Test-first. An absent `delegation_record` key must mean the check does
not run (earlier reports are never re-linted). Do not touch
`_lint_report_ledger` or any other existing lint function. The four
EC-02-authorized `report_path` literal sites are exactly:
`tests/test_v1101_gates.py:254-256`, `tests/test_v190_agents.py:286-299`,
`tests/test_v1102_gates.py:44-46`, `tests/test_v170_bench.py:316-331`
(pre-verified by the orchestrator via a fresh grep — no fifth site
exists). If you find a test failing at a site NOT in the 19-row
amendment table, do not fix it — stop and report it (the shared repair
budget is at 2 of 3 cycles spent).

## Acceptance

See the brief's Acceptance section — the lint is green against the
current `docs/reports/report-v1.10.3.md` (T0-T2's sections already
carry valid bullets) and red against `docs/reports/report-v1.10.2.md`
when the function is called directly in a test.

## Stop

If your new lint's check of the current `docs/reports/report-v1.10.3.md`
finds T0, T1 or T2's own bullet invalid, stop and report the exact
validation failure rather than silently editing an earlier task's report
section.
