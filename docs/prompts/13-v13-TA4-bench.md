# Prompt 13 — v1.3 TA4: benchmark harness (stage A)

- **Date:** 2026-09-02
- **Executor model:** claude-opus-5
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Harness:** Claude Code (`general-purpose` subagent, clean context)
- **Stage:** TA4
- **Owner of:** `devtools/bench.py` (new), `devtools/bench_scenarios.py` (new),
  `tests/test_bench.py` (new), `tests/fixtures/bench/` (new), `.gitignore`
- **REQ ids:** REQ-V13-BEN-01 … REQ-V13-BEN-14, Appendix C (the 12 scenarios),
  the section 7.4 field contract, section 13.3 (the verdict `report --gate`
  computes)

## Brief as sent

```
Repo: /home/akh/aihome/coders-su/projects/tg-agent-bot (Python 3.13, uv, stdlib
only + httpx/python-dotenv). Read docs/spec/spec-v1.3.md section 7 in full
(7.1-7.8, REQ-V13-BEN-01..14), section 13.3 (the verdict formulas report --gate
implements), section 11.4 and Appendix C — that is your contract; implement
exactly it, including the exact JSON field names and the arithmetic table of 7.4.
Critical: `check` recomputes every runs[].totals and summary value FROM THE
EMBEDDED llm_calls/tool_calls ROWS, never from the stored aggregates. Mirror
bot.main()'s wiring literally (REQ-V13-BEN-03 spells out the partials).
Add `.bench/` and `docs/assets/bench/*.log` to .gitignore.
Tests are offline: FakeLLM/RecordingRunner/FakeFetcher, no Docker, no network.
Do NOT change CONTEXT_WINDOW_MESSAGES, EXEC_MAX_STREAM_BYTES, FETCH_MAX_BYTES,
ROUND_LIMIT, TOOL_ROUND_LIMIT, TOOL_EXECUTION_LIMIT, HTTP_ATTEMPT_LIMIT or
llm.base.REQUEST_DEFAULTS — record them, never edit them.
Do NOT touch: agent.py, storage.py, tools.py, llm/, config.py, metrics.py, bot.py.
NEVER open .env. Never run the harness against the live box.
Return a <=15-line summary: subcommands, exit codes, tests added, gates.
Never paste file contents.
```
