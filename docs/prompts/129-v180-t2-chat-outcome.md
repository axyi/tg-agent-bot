# Prompt 129 — v1.8.0 T2: delete-on-success, structured outcome

- **Date:** 2026-09-09
- **Executor model:** claude-sonnet-5
- **Model reason:** `docs/handoff-v1.8.0.md` §Models: sonnet-5 executed
  v1.5, v1.6.0 and v1.7.0 end to end in this repository; T2 is a contained
  behaviour change to `bot.py`/`agent.py` with a full offline test suite,
  well inside the pattern sonnet-5 has already run for this codebase.
- **Harness:** Claude Code
- **Stage:** T2
- **Owner of:** `bot.py`, `agent.py`, `tests/test_v180_chat.py`,
  `tests/test_v12_patch.py` (one amendment site), `docs/prompts/129-v180-t2-chat-outcome.md`
- **REQ ids:** REQ-V180-CHAT-01, REQ-V180-CHAT-02, REQ-V180-CHAT-03,
  REQ-V180-CHAT-04, REQ-V180-CHAT-07 (outcome contract, proved by
  `T-V180-CHAT-08`), REQ-V180-CHAT-08 items 1/3/4/5 (item 2, the typing
  indicator, is out of scope — T3)

## Goal

Execute `docs/spec/task-briefs/v180-T2.md` (spec-v1.8.0 §4, items 1-4):
add `TelegramClient.delete_message`; replace `_StatusMessage.finish()` with
`finish(*, ok: bool)` so a successful run deletes the status message
instead of editing it to `STATUS_DONE` (now removed), and a failed run
edits it to the new `STATUS_FAILED`; carry the agent loop's failure
signal out as a structured `AgentOutcome` (`agent.py`'s `run_agent_outcome`,
with `run_agent` becoming a one-line wrapper over it); and reorder
`process_update`'s call site (steps 1, 3, 4, 5 of REQ-V180-CHAT-08 — step
2, the typing indicator, does not exist until T3) so the reply is sent
before the status is resolved, with an exception arm that marks the status
failed and re-raises.

## Constraints

`run_agent`'s signature, name and `-> str` return are byte-unchanged; its
~25 existing test call sites across eleven files are untouched. No branch,
round cap, fallback text or control-flow change in `agent.py` beyond
relocating the return values into `AgentOutcome` (NG-06). No typing
indicator, no `_TypingIndicator`, no `TYPING_*` constant — all T3. No file
outside this repository read or written (EC-01). Only the two sites the
brief names may be amended in existing test files —
`bot.py:1113-1135`/`:1236-1244` (`_SelftestTelegram` and the
`_selftest_failure` assertion) and `tests/test_v12_patch.py`'s
`_FakeSelftestTg` — every other test file is untouched by this prompt.
Only `ruff check .` and the full `pytest` suite run here, not the six-gate
sequence (gate 5 is live, gate 6 is slow — T8/T10's job).

## Acceptance

`uv run --locked ruff check .` exits 0. `uv run --locked pytest
tests/test_v180_chat.py` exits 0 (`T-V180-CHAT-01` through `-04`, `-08`,
`-09`, `-10`, each red before its code landed and green after). The full
`uv run --locked pytest` run stays green except the two amended assertions
(`bot.py`'s `_selftest_failure`, `tests/test_v12_patch.py`'s
`test_t_v12_id_04_selftest_pairing_check`), which are green under their
amended shape.

## Stop

Stop and report instead of silently patching around it if implementing the
spec as written turns any test outside the two scoped amendment sites red
— that is a gap in the brief's line-number audit, not license to edit a
third test file. That happened here: `tests/test_pricing.py`'s
`test_prc02_the_resolver_reaches_run_agent` (patches `agent.run_agent`,
which the call site no longer calls) and
`tests/test_v1_guardrails.py`'s `test_t_v1_vis_01_status_message` (asserts
the now-deleted `STATUS_DONE` edit text) both go red as a direct,
unavoidable consequence of REQ-V180-CHAT-02/-04/-08 correctly implemented.
Both are reported as the blocker rather than edited.
