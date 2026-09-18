# Prompt 226 — v1103 T6 (mutations part): five `v1103-*` entries, isolated verification (GATE-02)

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** source-writing task (mutation authoring), delegated
  per EC-03 default; the live-gate part of T6 is commands-only, run
  separately by the orchestrator.
- **Harness:** Claude Code (general-purpose subagent)
- **Stage:** T6 (mutations part)
- **Owner of:** `devtools/mutation_check.py`, `config/quality_gates.yaml`,
  `tests/test_v1100_gates.py`, `tests/test_v1101_gates.py`,
  `tests/test_v1102_gates.py`
- **REQ ids:** REQ-V1103-GATE-02, REQ-V1103-ERR-01 (row 7)

## Goal

Add five `v1103-*` mutation entries (exact `find`/`replace` pairs given
in `docs/spec/task-briefs/v1103-T6.md`, pre-verified unique in the
current tree), each independently verified killed in isolation before
being added for real. Update `config/quality_gates.yaml`'s
`mutation-v1103` gate, `mutation-subsets`, and `mutation-all`'s comment.

## Constraints

**Zero repair-cycle budget remains for this entire run** (T1+T2+T4
spent all 3). Do not run `mutation-all`, `--select v1103-`, or any gate
beyond 1-4. Do not run `git write-tree`. Do not touch
`docs/reports/report-v1.10.3.md`. If any mutant is killed only by the
uniqueness check or an import/collection error, or if any EC-02 edit
site is missing from the 19-row table, STOP immediately and report —
this is not fixable within this run.

## Acceptance

See `docs/spec/task-briefs/v1103-T6.md`'s Acceptance section — five
entries, each verified killed in isolation with import proof +
named-assertion red; `config/quality_gates.yaml` updated; exactly one
"is now" in the whole yaml file; gates 1-4 green.

## Stop

Any construction defect (an entry not killed by its own named
assertion alone) or any out-of-table test failure is an immediate stop
— report file:line and the exact symptom, do not attempt a workaround.
