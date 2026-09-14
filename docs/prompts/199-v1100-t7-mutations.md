# Prompt 199 — v1.10.0 T7: mutation entries

- **Date:** 2026-09-14
- **Executor model:** claude-sonnet-5 (delegated subagent, general-purpose)
- **Model reason:** mechanical mutation-table authoring against an
  established convention, verified empirically; no reasoning-tier need.
- **Harness:** Claude Code (background session, delegated via Agent tool,
  exclusive repo access required for this task's duration)
- **Stage:** T7
- **Owner of:** `devtools/mutation_check.py`, `config/quality_gates.yaml`,
  `tests/test_v1100_gates.py`
- **REQ ids:** REQ-V1100-GATE-02

## Goal

Add the seven `v1100-*` mutation entries, register `mutation-v1100` with a
freshly measured timeout, and add `T-V1100-GATE-01`, exactly as
`docs/spec/task-briefs/v1100-T7.md` specifies — verifying each entry's
actual killer test empirically rather than trusting the spec's stated one.

## Constraints

Exclusive repo access for the task's duration (nothing else runs
concurrently — `mutation_check.py` mutates tracked files in place). Touch
only the three files the brief names. Gates 1-4 plus
`mutation_check.py --select "v1100-"` only. Never the full mutation run,
never 5, 7, 8, never `--profile full`.

## Acceptance

All seven entries' `find` strings match exactly once; `--select "v1100-"`
is 7/7 killed; `T-V1100-GATE-01` passes; gates 1-4 exit 0.

## Stop

If an entry's spec-stated killer test doesn't actually kill it, do not
force it to — find and record the real killer, exactly as T1's delegate
already did for one of these seven; report the discrepancy rather than
silently matching the spec's claim.
