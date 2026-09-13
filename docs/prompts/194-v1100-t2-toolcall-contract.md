# Prompt 194 — v1.10.0 T2: outbound payload pin and the tool-call contract

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5 (delegated subagent, general-purpose)
- **Model reason:** tests-only task over an already-correct contract; no
  reasoning-tier need.
- **Harness:** Claude Code (background session, delegated via Agent tool)
- **Stage:** T2
- **Owner of:** `tests/test_v1100_sanitization.py` (append), `tests/test_v1100_toolcall.py` (new)
- **REQ ids:** REQ-V1100-OUT-02, REQ-V1100-TC-01

## Goal

Tests only, no source change: pin the Telegram send-payload builder (plain
`{chat_id, text}`, no `parse_mode`/`entities`) and the tool-call wire
coercion feeding `tools.execute_tool`'s four-envelope decode point, exactly
as `docs/spec/task-briefs/v1100-T2.md` specifies.

## Constraints

No production file may change; `git diff --stat` proves it. Gates 1–4 only.

## Acceptance

Gates 1–4 exit 0; `T-V1100-OUT-04`, `-05`, `T-V1100-TC-01…03` all pass;
`git diff --stat` shows `tests/` only.

## Stop

If pinning OUT-02 or TC-01 requires touching production source (it should
not — both are already-correct behaviour), stop and report the
discrepancy instead of changing source.
