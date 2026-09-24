# Prompt 263 — v1.11.1 T5: clean-context review, gates 1–8, `tested_tree`, gate 8

- **Date:** 2026-09-24
- **Executor model:** claude-sonnet-5
- **Model reason:** the review step is *the task is itself the
  clean-context review* (delegated to `code-reviewer`, its own clean
  context, per REV-01); the gates and `tested_tree` sequencing are
  *commands only*; the report-only landing commit is *artefacts only* —
  none of T5's three parts is a source-writing task for the
  orchestrator itself.
- **Harness:** Claude Code (background session, orchestrator, main
  context; one `code-reviewer` subagent for the review)
- **Stage:** T5
- **Owner of:** `docs/reports/report-v1.11.1.md`, this prompt file,
  `docs/llm-usage.md`
- **REQ ids:** REQ-V1111-REV-01, REQ-V1111-REV-02, REQ-V1111-GATE-01

## Goal

Run the required clean-context review of the full v1.11.0..HEAD diff
against REV-01's nine checklist items, resolve any findings (fix on
must-fix only, else waive with a reason), then run gates 1–8 in
GATE-01's exact schedule: gates 1–6 (gate 6 alone, wall time `W`
measured and checked against the 1300s/2400s thresholds), a clean
worktree and `tested_tree`, gate 7, the pre-gate-8 checks (override
count, `doctor`, `lint-docs`, the collection count), then gate 8 —
the release's one and only invocation, never rerun.

## Constraints

The review subagent may not run any gate script (`mutation_check.py`,
`rag_eval.py`, `agent_eval.py`, `checks.py run --profile full`) and may
not write any file. Gates 6, 7 and 8 never run in parallel with one
another or any other gate. Nothing is committed between gates 1-6 and
gate 8 — the worktree stays exactly at `tested_tree`. `.env`, `data/`,
`bot.db`, `sandbox/`, `exec_audit.jsonl` never opened beyond the two
permitted reads (the override count, twice). `--no-verify` never used.

## Acceptance

All nine REV-01 checklist items pass or are explicitly waived with a
reason; gates 1–6 exit 0, `W ≤ 2400s` (recorded regardless, a hunk only
if `W > 1300s`); `tested_tree` recorded against a clean worktree; gate 7
exits 0 (`hybrid recall@5 ≥ 0.8`, every answerable item's rerank flags
`True`); the pre-gate-8 checks all green; gate 8 exits 0 (every floor
met, judge mean ≥ 0.8); one report-only commit lands this task's record.

## Stop

A must-fix finding without a viable fix, `W > 2400s`, an unreachable LM
Studio or non-zero override count at either checkpoint, or gate 8
exiting 1, are each a stop condition per ERR-01/REV-03 — none occurred
this task.
