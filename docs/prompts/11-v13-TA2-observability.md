# Prompt 11 — v1.3 TA2: observability core (stage A)

- **Date:** 2026-09-02
- **Executor model:** claude-opus-5
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Harness:** Claude Code (`general-purpose` subagent, clean context)
- **Stage:** TA2
- **Owner of:** `llm/base.py`, `llm/lmstudio.py`, `llm/openrouter.py`,
  `llm/failover.py` (`describe()` + usage/reasoning parsing + `REQUEST_DEFAULTS`),
  `storage.py` (schema v3), `agent.py` (call recording only), `metrics.py` (new),
  `bot.py` (`/stats` + the `/status` token line only),
  `tests/test_observability.py` (new)
- **REQ ids:** REQ-V13-OBS-01 … REQ-V13-OBS-09, and the `CostResolver` type of
  REQ-V13-PRC-02 (type only — `llm/pricing.py` belongs to TA3)
- **Runs before TA3** (TA3 implements `make_resolver` against this type).

## Brief as sent

```
Repo: /home/akh/aihome/coders-su/projects/tg-agent-bot (Python 3.13, uv, stdlib
only + httpx/python-dotenv). Read docs/spec/spec-v1.3.md sections 6.1, 6.2,
11.2 and Appendix B (features "usage is recorded", "think blocks", "/stats") —
that is your contract; implement exactly it.
Also define in llm/base.py, next to Usage, the type
CostResolver = Callable[[str, str, Usage | None], tuple[float | None, str | None]]
and thread the keyword-only `resolve_cost: CostResolver | None = None` through
run_agent and summarize_conversation (default None -> store NULL/NULL). Test it
with stub resolvers only; do NOT create llm/pricing.py (TA3 owns it).
Lift the request-control literals (temperature 0, stream False, tool_choice
"auto") into a module-level REQUEST_DEFAULTS in llm/base.py that the payload
builder reads; values unchanged.
Test-first. Do NOT touch: tools.py, config.py, devtools/, README, docs/.
Do NOT change CONTEXT_WINDOW_MESSAGES, EXEC_MAX_STREAM_BYTES, FETCH_MAX_BYTES,
ROUND_LIMIT, TOOL_ROUND_LIMIT, TOOL_EXECUTION_LIMIT, HTTP_ATTEMPT_LIMIT or any
request-control value.
NEVER open .env. Gates: ruff check . and pytest must be green.
Return a <=15-line summary: schema/migration, row counts, tests added, gates.
Never paste file contents.
```
