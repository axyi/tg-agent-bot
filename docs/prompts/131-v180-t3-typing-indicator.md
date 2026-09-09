# Prompt 131 — v1.8.0 T3 typing indicator

- **Date:** 2026-09-09
- **Executor model:** claude-sonnet-5
- **Model reason:** small, well-scoped implementation task with a fully verified line-number map in the brief; no open design search needed.
- **Harness:** Claude Code
- **Stage:** T3
- **Owner of:** `bot.py`, `tests/test_v180_chat.py`, `tests/test_bench.py` (unplanned, see Stop)
- **REQ ids:** REQ-V180-CHAT-05, REQ-V180-CHAT-06 item 3, REQ-V180-CHAT-08 step 2, REQ-V180-EC-05

## Goal

Add the typing indicator (§4 part 2 of spec-v1.8.0): three new keyword-only
timeout parameters on `TelegramClient.call` so all four `httpx.Timeout`
phases are callable per request; a new `_TypingIndicator` class in `bot.py`
that sends `sendChatAction`/`typing` on a fixed interval via one unretried
`tg.call`, bounded by `cfg.llm_timeout_s`, with named constructor seams
(`monotonic`, `stop_event`) for deterministic testing; and wiring it into
`process_update` beside `_StatusMessage` so it starts alongside the status
message and stops-and-joins before the reply is sent on every exit path,
including before `status.finish(ok=False)` fires on the exception path.

## Constraints

- No new environment variable, no new `Config` field.
- `bot.py` alone constructs `_TypingIndicator`; `agent.py` untouched.
- No file outside this repository read or written.
- Do not run the full six-gate sequence — only `ruff check .` and the whole
  `pytest` suite.

## Acceptance

`T-V180-CHAT-06`/`-07` (new, in `tests/test_v180_chat.py`) green;
`T-V180-CHAT-09`/`-10` (T2) re-run unmodified and still green; `ruff check .`
clean; whole `pytest` suite green at 1163 (baseline) + 5 new = 1168 passed,
1 skipped, run three times in a row with no flakiness.

## Stop

Running the whole suite (as the brief requires) surfaced a real interaction
outside the brief's file map: `tests/test_bench.py::
test_sigint_takes_the_same_abort_path_immediately` monkeypatches
`threading.Thread.join` to raise `KeyboardInterrupt` on the first call
anywhere in the process, assuming that call is always the bench harness's
own `worker.join(timeout_s)`. `_TypingIndicator.stop()` now also calls
`.join()` on its own worker thread from inside `bot.process_update`, which
executes on that same harness worker thread and can — and, once observed,
reliably did — reach its own `.join()` call before the harness's outer join,
consuming the simulated SIGINT and silently letting both scenarios run to
completion instead of aborting.

This falls outside the brief's cited map (`bot.py`, `config.py`) and touches
neither `agent.py` nor anything the brief named — flagged per AGENTS.md's
context-discipline trigger rather than expanded silently. Fix applied: scope
the test's monkeypatch to the harness's own worker thread by name
(`self.name.startswith("bench-")`, matching the name `_execute_run` already
gives that thread), rather than intercepting the first `Thread.join` call
process-wide. `tests/test_bench.py` re-run alone and as part of the full
suite (three consecutive runs) after the fix: all green, no flakiness.
