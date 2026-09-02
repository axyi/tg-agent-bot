# Prompt 23 — v1.3 TC5: O6 model routing by purpose (stage C)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Owner of:** `config.py` (`LLM_SUMMARY_MODEL`), `llm/__init__.py`, `bot.py`
  summary wiring, `tests/test_routing.py` (new), `.env.example`
- **REQ ids:** REQ-V13-RTE-01

## Brief as sent (abridged)

```
Implement O6 as CONFIGURATION ONLY — it is deliberately not enabled during the
benchmark. LLM_SUMMARY_MODEL=<provider>:<model>, validated (provider in
{lmstudio, openrouter} AND configured, else ConfigError). Route only
summarize_conversation to that client, built on the SAME httpx.Client, no
failover for it; the agent loop keeps the main client; llm_calls.model shows the
routed model. There is no LLM_REASONING in this tree and you must not add one.
```
