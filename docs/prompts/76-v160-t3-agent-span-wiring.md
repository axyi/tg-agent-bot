# Prompt 76 — spec-v1.6.0 T3: agent.py span wiring

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §"Executor: claude-sonnet-5"; the TRC-07
  transaction sequence and TRC-08 turn_id repair require precise control-flow
  reasoning over `agent.py`'s existing retry/failover logic
- **Harness:** Claude Code
- **Stage:** T3
- **Owner of:** `agent.py` (four span seams, content capture, limit-hit
  tracking), `tests/test_v160_observability.py` (T3's tests, appended),
  `tests/test_observability.py` (one authorized amendment),
  `devtools/mutation_check.py` (one pre-existing mutation's `find` string,
  forced by REQ-V160-TRC-08's turn_id repair)
- **REQ ids:** REQ-V160-TRC-04, -07, -08, -09, -10, -14

## Goal

Wire `tracing.py` (T1) and `storage.py`'s span helpers (T2) into `agent.py`'s
four recording seams: the root `invoke_agent tg-agent-bot` span around
`run_agent`'s round loop, one `chat {model}` span per LLM invocation
(failed/retried attempts included), one `execute_tool {tool}` span per
recorded tool call (`budget`/`rejected` outcomes included), and the summary
call's own `chat {model}` span. Implement the exact TRC-07 transaction
sequence (`BEGIN IMMEDIATE` inside the `try`, span finish as the sole writer,
the call row, `COMMIT`; guarded `ROLLBACK` on any failure) for all three
owning spans (root, chat, execute_tool). Repair `turn_id`: mint it once
before each round's attempt loop and thread the same value through every
`_record_llm_call`/`_record_tool_call` of that round, failed attempts
included. Wire opt-in content capture (`cfg.obs_capture_content`) into the
chat span's four `gen_ai.*` content attributes, redacted and bounded via
`tracing.set_content_attribute`. Record `tg_agent.limit_hit` on the root span
at each of the seven budget constants' actual exhaustion points.

## Constraints

- **Delegation deviation from §14.1's map (RPT-02 item 5):** T3 is marked
  "delegate: yes", but this task was implemented directly rather than
  handed to a subagent. Rationale: correctly threading TRC-08's turn_id
  repair through `agent.py`'s existing retry control flow (HTTP retries,
  malformed retries and empty-repair retries all re-enter the same `while`
  iteration without advancing `round_no`) required deep, already-paid-for
  reading of the exact control flow; re-deriving that from scratch in a
  fresh subagent risked a subtle correctness error in one of the seven
  high-risk mechanisms this release requires mutation proof for. The
  reading stayed within the map's named ranges (`agent.py:25-44, 245-295,
  560-620, 640-700, 790-820`) plus the two files T1/T2 already produced.
- No nested `BEGIN IMMEDIATE`: verified by moving it *inside* each `try`
  block per REQ-V160-TRC-07's canonical sequence exactly, so a failed
  `BEGIN IMMEDIATE` itself is never followed by a bare `ROLLBACK`
  (REQ-V160-TRC-14).
- `add_tool_turn`'s own signature and behaviour for its existing (non-root)
  caller stay byte-identical (T2 already split it; T3 doesn't touch it).
- One pre-existing mutation (`v13-llm-call-not-recorded-on-error`) had its
  `find` string updated to match the new, unified (success+failure)
  `_record_llm_call` call site the TRC-08 turn_id repair produces; same id,
  same underlying property, narrowly scoped -- not the ten new `v160-*`
  entries, which stay T13's job.
- One prompt → one commit, referencing this file.

## Acceptance

- `tests/test_v160_observability.py`'s T3 section (13 new tests) covers
  T-V160-TRC-03 (span tree shape), -04 (chat/llm_calls bijection + rollback),
  -05 (execute_tool/tool_calls bijection + rollback, `budget`/`rejected`
  outcomes), -09/-10 (content capture off by default, on redacts and bounds),
  -14 (persistence failure escapes over operation failure; a genuinely
  locked database proves no bare `ROLLBACK` follows a failed `BEGIN
  IMMEDIATE`), plus two tests on the `tg_agent.limit_hit` mechanism feeding
  the full aggregate T4 will add (`metrics.limit_hits` doesn't exist yet).
- `tests/test_observability.py:545`'s amendment matches §15.1 exactly
  (`assert rows[0]["turn_id"] == rows[1]["turn_id"] is not None`).
- `uv run --locked pytest` exits 0, 888 passed (875 + 13 new).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python devtools/mutation_check.py` exits 0, 72/72 killed.

## Stop

If threading `turn_id` through a retry path produced a value that changed
between the failed attempt and the eventual success within the same round,
that would be a defect worth stopping over — verified not to happen: TRC-04's
bijection tests assert the failed-attempt row's `turn_id` and the
eventual-success row's `turn_id` are recorded consistently per round.
