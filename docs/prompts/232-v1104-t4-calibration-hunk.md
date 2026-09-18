# Prompt 232 — v1.10.4 T4: the localized mutation-v1103 calibration comment hunk

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** one small, mechanical, already-fully-resolved YAML
  comment edit; delegated per §10.1/EC-03's explicit rule that this hunk
  is delegated even though the rest of T4 is commands-only.
- **Harness:** Claude Code (background session, delegated subagent)
- **Stage:** T4
- **Owner of:** `config/quality_gates.yaml` (the `mutation-v1103`
  comment block only)
- **REQ ids:** REQ-V1104-GATE-02

## Goal

Replace the `mutation-v1103` gate's placeholder calibration comment with
the dated measured-wall/formula comment, in the exact style of
`mutation-v1102`'s own precedent paragraph. The wall (16s) and the
computed value (110, unchanged) are already resolved by the
orchestrator — this task only writes the comment text. Full detail in
`docs/spec/task-briefs/v1104-T4.md`.

## Constraints

Exactly one localized hunk — the placeholder paragraph only.
`timeout_seconds: 110` and everything else in the file stays untouched.
No gate 6 run this task (the orchestrator runs it directly afterward, on
its own write-tree). No `bot.py --selftest-live`,
`devtools/rag_eval.py`, or `devtools/agent_eval.py`. `--no-verify` never
used.

## Acceptance

`git diff 2caa595 -- config/quality_gates.yaml` shows exactly one hunk;
`ruff check .` clean; full `pytest -q` green (no-op check, since no test
changed).

## Stop

If the placeholder text has drifted from what the brief quotes, disclose
it as an EC-02 amendment in your report and proceed with the equivalent
edit — do not guess at unrelated changes, and do not touch anything
outside the one comment paragraph.
