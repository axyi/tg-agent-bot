# Prompt 82 — spec-v1.6.0 T8: truncated-summary retry, LLM_SUMMARY_MAX_TOKENS, closed outcome vocabulary

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §14.1 marks T8 "delegate: no" -- the retry
  logic interleaves with `_ask_for_summary`'s existing malformed-JSON repair
  path and the shared `_record_llm_call` transaction sequence closely enough
  that a fresh subagent would need to re-derive the T3 control-flow
  understanding already in hand
- **Harness:** Claude Code
- **Stage:** T8
- **Owner of:** `agent.py` (`TOOL_OUTCOMES`, `_record_tool_call`'s
  vocabulary check, `_ask_for_summary`, `summarize_conversation`),
  `config.py` (`llm_summary_max_tokens`, `_check_timeout_budget`),
  `bot.py` (both `summarize_conversation` call sites), `.env.example`,
  `tests/test_v160_observability.py` (T8's tests, appended); plus two
  forced, mechanical amendments outside §15.1 (see Constraints)
- **REQ ids:** REQ-V160-TQ-01, -02, -03

## Goal

`_ask_for_summary` rejects a `finish_reason == "length"` response without
parsing, records it with `error_kind = "truncated"`, and signals the
truncation back to its caller instead of returning a parse result.
`summarize_conversation` retries exactly once at the larger
`retry_max_tokens` budget (recorded as `attempt = 2`); a second truncation
proceeds without a summary, no exception escaping. `Config.llm_summary_max_tokens`
(default 1536, range 256-8192) is parsed the existing way;
`_check_timeout_budget` is extended to `max(llm_max_tokens,
llm_summary_max_tokens)` and its `ConfigError` now names both variables.
`agent.TOOL_OUTCOMES = ("ok", "error", "budget", "rejected",
"refused_repeat")` is a closed vocabulary `_record_tool_call` asserts
membership against before writing.

## Constraints

- **Two forced, mechanical test amendments outside §15.1's exhaustive
  list**, both driven by the same cause: `summarize_conversation` gained a
  keyword-only `retry_max_tokens` parameter, and `bot.py` now always passes
  it. Two pre-existing test doubles fully replace
  `agent.summarize_conversation` (a `monkeypatch.setattr` stub in
  `tests/test_pricing.py::test_prc02_the_resolver_reaches_the_summarizer`
  and a lambda in
  `tests/test_v11_patch.py::test_t_v11_red_04_summary_reply_redacted_only_by_send`,
  the latter's own comment already noting it "mirrors the *whole*
  caller-visible signature"), and Python raises `TypeError` on the
  now-unexpected keyword before either test's own assertions run. Both
  stubs gained `retry_max_tokens=None` in their signature and nothing else
  -- no behavioural change, the exact shape of T2's precedent (a schema
  version bump forcing two unlisted amendments, documented rather than
  silently accepted or used to block the run).
- `summarize_conversation`'s new `max_tokens`/`retry_max_tokens` keywords
  both default to `SUMMARY_MAX_TOKENS` (512), so every caller that does not
  pass them keeps today's behaviour untouched (REQ-V1-EC-05); `bot.py`
  passes `retry_max_tokens=cfg.llm_summary_max_tokens` and nothing else, so
  attempt 1 stays at 512 in production too.
- The JSON-malformed repair path (pre-existing, REQ-V13-OBS-04) is
  unchanged: both its rows still land at `attempt = 1`. Only the new
  truncation retry is recorded at `attempt = 2` -- the two mechanisms are
  orthogonal and never combine (a truncation retry that itself parses as
  malformed JSON returns `None` rather than triggering a further repair,
  matching REQ-V160-TQ-01 item 4's "no second retry").
- `_record_tool_call`'s vocabulary check raises before `BEGIN IMMEDIATE`,
  so an unknown outcome never reaches even the span table, not just
  `tool_calls`.
- `tg_agent.summary.truncated` was already in `tracing.ATTRIBUTE_KEYS`
  (added at T1 in anticipation) -- no `tracing.py` change needed, keeping
  T8's reading inside `agent.py`/`config.py` as §14.1 maps it.
- One prompt → one commit, referencing this file.

## Acceptance

- `tests/test_v160_observability.py`'s new T8 section (9 tests) covers:
  double truncation (`N8` half one: two truncated rows, one terminal
  failure, `tg_agent.summary.truncated` on every `chat` span);
  single-truncation-then-success (retry succeeds, only the attempt=2 row
  parses, not a terminal failure); the malformed-but-not-truncated path
  staying at `attempt = 1` for both rows; `N8`'s other half (a lone
  non-truncation `error_kind` is a terminal failure too); the retry budget
  never being requested when nothing truncates; `LLM_SUMMARY_MAX_TOKENS`
  parsing and its unchanged-at-default-configuration timeout floor; the
  `ConfigError` naming both `LLM_MAX_TOKENS` and `LLM_SUMMARY_MAX_TOKENS`;
  and the closed outcome vocabulary (`T-V160-TQ-03`) recording all five
  outcomes into `tool_health` plus the pre-database raise on an unknown one.
- `uv run --locked ruff check .` exits 0.
- `uv run --locked pytest` exits 0, 957 passed (949 + 8 new).
- `uv run --locked python bot.py --selftest` exits 0 (`selftest: OK`).
- `uv run --locked python devtools/mutation_check.py` exits 0, 72/72 killed.
- No test outside the two documented above and `tests/test_v1_guardrails.py:1398`
  (T7's own amendment) needed any change.

## Stop

If a third existing test had needed amendment beyond the two forced by the
`retry_max_tokens` signature widening, that would be the "stop and
reconsider" signal REQ-V160-EC-03 describes; none did.
