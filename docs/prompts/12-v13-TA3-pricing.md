# Prompt 12 — v1.3 TA3: pricing and cost basis (stage A)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Owner of:** `llm/pricing.py` (new), `config.py` (the three pricing variables
  only), `bot.py` (pricing wiring only), `tests/test_pricing.py` (new),
  `.env.example`
- **REQ ids:** REQ-V13-PRC-01 … REQ-V13-PRC-03, the three pricing variables of
  REQ-V13-PRE-04, REQ-V13-PRE-05 (context7 verification + citation)
- **Runs after TA2** (uses the `CostResolver` type from `llm/base.py`).

## Brief as sent

```
Repo: /home/akh/aihome/coders-su/projects/tg-agent-bot (Python 3.13, uv, stdlib
only + httpx/python-dotenv). Read docs/spec/spec-v1.3.md section 6.3
(REQ-V13-PRC-01..03), REQ-V13-PRE-04 (the three LLM_PRICE_* variables only —
NOT the stage-C ones) and section 11.3 — that is your contract.
llm/base.py already defines CostResolver and Usage; run_agent and
summarize_conversation already accept resolve_cost. Add make_resolver(...) in
llm/pricing.py and the SINGLE bot.py wiring (startup fetch, bot_state
pricing_json persist, build the resolver once, pass it down). Nobody else
touches that path.
REQ-V13-PRE-05: verify the OpenRouter /models pricing field names and the usage
accounting flag against current docs via mcp__context7__resolve-library-id +
mcp__context7__query-docs (or openrouter.ai official docs) and return the
citation URL. Never assume a field exists.
Test-first, no network in tests (mock transport). NEVER open .env.
Do NOT touch: agent.py, storage.py, tools.py, devtools/, metrics.py, README.
Gates: ruff check . and pytest green.
Return a <=15-line summary: verified field names + doc URL, precedence tests,
files touched, gates. Never paste file contents.
```
