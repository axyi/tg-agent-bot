# Prompt 83 — spec-v1.6.0 T9: repeat-call refusal

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §14.1 marks T9 "delegate: no" -- the refusal
  decision sits directly inside `_execute_tool_calls`'s existing
  budget/excess branching (agent.py), which a fresh subagent would need to
  re-derive from scratch; the change is small and self-contained enough
  that direct implementation is cheaper than a delegation round-trip
- **Harness:** Claude Code
- **Stage:** T9
- **Owner of:** `agent.py` (`_call_key`, `_canonical_arguments`,
  `_normalized_error_class`, `_repeat_failure_count`,
  `TOOL_REPEAT_REFUSAL_THRESHOLD`, `REFUSED_REPEAT_RESULT`,
  `_execute_tool_calls`, `_run_agent_turn`'s new `repeat_failures` state),
  `tests/test_v160_observability.py` (T9's tests, appended)
- **REQ ids:** REQ-V160-TQ-04

## Goal

A `dict[(call_key, normalized_error_class), int]` scoped to one user
message (created in `_run_agent_turn` alongside `turn_id`, discarded when
the function returns) tracks how many times each exact tool call has
failed. `call_key = sha256(_wire_name(call) + "\x00" + canonical_arguments)`,
computed before dispatch. When a `call_key`'s failures — summed across its
error classes — reach `TOOL_REPEAT_REFUSAL_THRESHOLD` (2), the next
identical call is not executed: it gets the literal
`REFUSED_REPEAT_RESULT` envelope, `outcome = "refused_repeat"`,
`duration_ms = 0`, and the span attribute `tg_agent.tool.fingerprint` (the
first 16 hex characters of `call_key`), and still consumes one unit of
`TOOL_EXECUTION_LIMIT`, exactly as an execution would.

## Constraints

- The refusal check runs **before** the existing
  `tools_used < TOOL_EXECUTION_LIMIT` budget branch, not after: a call
  already known to fail twice must not spend budget on a third doomed
  attempt, and REQ-V160-TQ-04 says the refusal itself "counts toward
  TOOL_EXECUTION_LIMIT exactly as an execution would" — so it increments
  `tools_used` on its own refusal branch, independent of whether ordinary
  budget remains.
- `_normalized_error_class` is called only after `_tool_outcome` has
  already confirmed the result parses as a dict carrying `"error"` — no
  redundant validation duplicating an invariant the caller already
  established (matches this repo's "trust internal guarantees" convention).
- `tg_agent.tool.fingerprint` was already in `tracing.ATTRIBUTE_KEYS`
  (added at T1 alongside `tg_agent.summary.truncated`, both anticipating
  their T8/T9 consumers) — no `tracing.py` change needed.
- `repeat_failures` is passed as an explicit parameter through
  `_execute_tool_calls`, not read from a module-level or contextvar-backed
  global: it must never leak between conversations or survive past one
  `run_agent` call, and an explicit parameter makes that lifetime
  structurally obvious rather than merely documented.
- Zero existing tests needed amendment: no test calls `_execute_tool_calls`
  directly, and the new `repeat_failures` keyword-only parameter has no
  default precisely because every call site (production and test) must
  decide explicitly what state it is threading.
- One prompt → one commit, referencing this file.

## Acceptance

- `tests/test_v160_observability.py`'s new T9 section (3 tests) covers:
  `_call_key` ignoring argument key order while differing on tool name or
  argument value; the full refusal sequence at the `_execute_tool_calls`
  level (two failures under two different error classes, summed not maxed;
  the third identical call refused without a third dispatch; the literal
  envelope; `duration_ms = 0`; the `tg_agent.tool.fingerprint` span
  attribute; `tools_used` incrementing on the refusal; a fresh state dict
  re-allowing the same call, modelling "a fresh user message starts the
  count again"); and one end-to-end run through `agent.run_agent` proving
  the wiring from `_run_agent_turn`'s new `repeat_failures` local through
  three real rounds.
- `uv run --locked ruff check .` exits 0.
- `uv run --locked pytest` exits 0, 960 passed (957 + 3 new).
- `uv run --locked python bot.py --selftest` exits 0 (`selftest: OK`).
- `uv run --locked python devtools/mutation_check.py` exits 0, 72/72 killed.
- No existing test needed any amendment.

## Stop

None triggered: the change stayed inside `_execute_tool_calls`'s existing
branching structure and no unlisted test was affected.
