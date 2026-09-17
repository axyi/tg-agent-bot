# Prompt 210 — v1.10.1 T6a: the six `v1101-*` mutation entries

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (§16.1: `delegate? yes`);
  general-purpose subagent, briefed by `docs/spec/task-briefs/v1101-T6a.md`.
- **Harness:** Claude Code (background session, subagent)
- **Stage:** T6 (first half — mutation entries and gate registration; the
  orchestrator runs the full live gate sequence, including gate 8,
  immediately after as a separate step)
- **Owner of:** `devtools/mutation_check.py` (append only),
  `config/quality_gates.yaml`, `tests/test_v1101_gates.py` (extending)
- **REQ ids:** REQ-V1101-GATE-02, REQ-V1101-RUN-02 (timeout-move sentence)

## Goal

Six `v1101-*` mutation entries, each empirically proven killed via
`--select "v1101-"`; `mutation-v1101` registered with a measured timeout;
`mutation-all`'s stale count comment corrected to 133; `agent-eval`'s
timeout moved to T0's measured 1800s figure.

## Constraints

Touch only the files listed in the task brief. Do not run the full
`mutation_check.py` (no `--select`) — only the fast `--select "v1101-"`
verification. Never gate 5, 7, or 8. Leave a clean, fully committed tree
— the orchestrator captures `tested_tree` immediately after your commit.
`--no-verify` never used.

## Acceptance

`--select "v1101-"` reports 6/6 killed, 0 survived/errored/drifted. Gates
1-4 exit 0. `mutation-v1101` registered and added to `mutation-subsets`.
`mutation-all`'s count comment states 133, backed by a test that reads
`len(MUTATIONS)` rather than a hardcoded number. `agent-eval.timeout_seconds`
is 1800.

## Stop

A `find` string that doesn't match exactly once, or a mutation that
survives despite genuine effort to target it correctly — report back
rather than weakening the mutation to force a kill.
