# Prompt 193 — v1.10.0 T1: inbound sanitisation and outbound text

- **Date:** 2026-09-13
- **Executor model:** claude-sonnet-5 (delegated subagent, general-purpose)
- **Model reason:** small, precisely specified source edit plus tests; no
  reasoning-tier need.
- **Harness:** Claude Code (background session, delegated via Agent tool)
- **Stage:** T1
- **Owner of:** `bot.py` (three edits: `utf16_length`, the SAN-02 cap
  comparison, `reply_parts` at its five call sites), `tests/test_v1100_sanitization.py`
- **REQ ids:** REQ-V1100-SAN-01, REQ-V1100-SAN-02, REQ-V1100-OUT-01

## Goal

Implement §3's SAN-01 (test-only pin), SAN-02 (the UTF-16 inbound cap) and
OUT-01 (`reply_parts`: redact before split, at all five call sites) exactly
as `docs/spec/task-briefs/v1100-T1.md` specifies.

## Constraints

Touch only `bot.py` and `tests/test_v1100_sanitization.py`. Gates 1–4 only;
never 5–8; never `checks.py run --profile full`. `tests/test_v1_guardrails.py:556`,
`:571` and `tests/test_telegram.py:223` must stay green, unamended.

## Acceptance

Gates 1–4 exit 0; the six new test ids pass; `split_message(` occurs
exactly twice in `bot.py`'s final source.

## Stop

Any of the pinned pre-existing tests goes red and can't be reconciled
without touching them → stop and report; do not edit those test files.
