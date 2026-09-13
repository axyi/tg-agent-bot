# Prompt 195 — v1.10.0 T3: the judge route configuration

- **Date:** 2026-09-14
- **Executor model:** claude-sonnet-5 (delegated subagent, general-purpose)
- **Model reason:** small, precisely specified config addition mirroring an
  existing pattern; no reasoning-tier need.
- **Harness:** Claude Code (background session, delegated via Agent tool)
- **Stage:** T3
- **Owner of:** `config.py`, `llm/__init__.py`, `.env.example`,
  `tests/test_v1100_config.py`
- **REQ ids:** REQ-V1100-CFG-01

## Goal

Add `LLM_JUDGE_MODEL` as a routed purpose, mirroring `LLM_EVAL_CHAT_MODEL`
exactly, plus the `.env.example` documentation block with the uncommented
default `openrouter:openai/gpt-4.1`, exactly as
`docs/spec/task-briefs/v1100-T3.md` specifies.

## Constraints

Touch only `config.py`, `llm/__init__.py`, `.env.example`,
`tests/test_v1100_config.py`. Never touch the real `.env`. Gates 1–4 only.

## Acceptance

Gates 1–4 exit 0; `T-V1100-CFG-01…04` pass; `purpose="agent"` construction
byte-unchanged; exactly one uncommented `LLM_JUDGE_MODEL=` line in
`.env.example`.

## Stop

If mirroring `LLM_EVAL_CHAT_MODEL` does not fit cleanly (e.g. the routing
helper's shape has changed since this brief was written), stop and report
the discrepancy rather than improvising a different mechanism.
