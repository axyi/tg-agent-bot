# Prompt 207 — v1.10.1 T4: prompt/tool literals compel a document search

- **Date:** 2026-09-17
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (§16.1: `delegate? yes`);
  general-purpose subagent, briefed by `docs/spec/task-briefs/v1101-T4.md`.
- **Harness:** Claude Code (background session, subagent)
- **Stage:** T4
- **Owner of:** `agent.py` (comment + docs line), `tools.py`
  (`search_documents` description), `tests/test_prefix.py:29`,
  `tests/test_v190_tool.py:372-390`
- **REQ ids:** REQ-V1101-PRM-01, REQ-V1101-PRM-02

## Goal

Two exact literal changes (the system-prompt docs line, the
`search_documents` tool description) so OpenRouter models reliably search
uploaded documents before answering from memory — the carried
v1.9.4/v1.10.0 tail. `PROMPT_LIMIT` 700 → 800. Measure gate 7's advisory
conversation-aware smoke before and after the edit, exactly twice.

## Constraints

Touch only the files listed in the task brief. Gates 1–4 offline first,
then gate 7 live **exactly twice**, in sequence — before the edit, then
after. Never gate 5, 6, or 8. `tests/test_v1_guardrails.py:829-864` stays
green unamended. `--no-verify` never used.

## Acceptance

Gates 1–4 exit 0. Both gate-7 runs exit 0 with `hybrid` recall@5 at or
above its floor. The rendered `SYSTEM_PROMPT` (with `{skill_lines}`
removed) is exactly 736 characters. The four-cell before/after table
(TOOL-06 pin, context-proof) is recorded verbatim, whatever it shows — the
verdicts are advisory (NG-07), not a pass/fail gate for this task.

## Stop

`recall@5` dropping below its floor in either run is a real regression —
stop and report back rather than treating it as advisory. Any other
gate-7 red is a normal repair-and-report.
