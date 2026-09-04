# Prompt 75 — spec-v1.6.0 T2 follow-up: record deviations

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** bookkeeping; no design decision
- **Harness:** Claude Code
- **Stage:** T2 (follow-up)
- **Owner of:** `docs/reports/report-v1.6.0.md`
- **REQ ids:** REQ-V12-REP-02, REQ-V160-EC-03

## Goal

T2's subagent amended two existing tests
(`tests/test_observability.py::test_obs03_a_future_version_is_still_refused`,
`tests/test_summary.py::test_t_v1_sum_01_migration_from_version_one`)
outside §15.1's exhaustive list, both forced, mechanical consequences of the
`SCHEMA_VERSION` 3→4 bump the spec itself mandates. This prompt's only job
is to record that deviation prominently in the running report, per
REQ-V12-REP-02 process honesty, rather than leave it in the T2 commit
message body alone. Verified independently: swept the test tree for any
remaining hardcoded schema-version literal and confirmed no third instance
survives.

## Constraints

No source or test file is touched. Report-only.

## Acceptance

`docs/reports/report-v1.6.0.md` carries a "Deviations (running log)" section
naming both tests, the reason the change was forced rather than optional,
and the independent verification sweep.

## Stop

N/A — this is a documentation-only follow-up.
