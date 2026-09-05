# Prompt 79 — spec-v1.6.0 T5 follow-up: record the gate-5 deviation

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** bookkeeping; no design decision
- **Harness:** Claude Code
- **Stage:** T5 (follow-up)
- **Owner of:** `docs/reports/report-v1.6.0.md`
- **REQ ids:** REQ-V12-REP-02, REQ-V160-PRE-04

## Goal

`docs/prompts/78-v160-t5-dashboard-render.md`'s own Acceptance section
(committed as part of `b3cb9a0`) records that gate 5 (`bot.py
--selftest-live`) was run and passed during T5 — a task REQ-V160-PRE-04
reserves exclusively for T15. This was not requested by the T5 delegation
brief and was not recorded in the report's Deviations log by the delegated
subagent. Discovered by the orchestrator after T5's commit; verified with a
fresh, independent agent working only from committed artefacts (no memory
of T5's actual execution). This prompt's only job is to record that
deviation prominently, per REQ-V12-REP-02 process honesty, with the
evidence and the bounded blast-radius assessment (no paid inference, per
`bot.py`'s `run_selftest_live` design; no secret exposure beyond normal use;
T15's own PRE-03/PRE-04 resolution is unaffected and still runs in full).

## Constraints

No source or test file is touched. Report-only.

## Acceptance

`docs/reports/report-v1.6.0.md` carries a second T5 Deviations entry naming
the violated requirement, the exact quoted claim, what could and could not
be independently confirmed, and why no corrective rerun of T5 itself was
performed.

## Stop

N/A — this is a documentation-only follow-up.
