# Prompt 10 — v1.3 TA1: v1.2 carry-over (stage A)

- **Sent to:** `general-purpose` subagent (clean context), Claude Code
- **Model reason:** inherits spec-v1.3's claude-opus-5 pin for this run (docs/llm-usage.md row 31); same judgment rationale as prompt 09, applied to this task.
- **Owner of:** `bot.py` (`_remove_sandbox_entry` only), `devtools/mutation_check.py`
  (`--only` exit code only), `tests/test_v13_carryover.py` (new),
  `tests/test_v12_patch.py` / `tests/test_v11_patch.py` (chmod-000 hygiene only),
  `README.md` (three wordings), `docs/llm-usage.md` (v1.2 row)
- **REQ ids:** REQ-V13-CO-01 … REQ-V13-CO-08

## Brief as sent

```
Repo: /home/akh/aihome/coders-su/projects/tg-agent-bot (Python 3.13, uv). Read
docs/spec/spec-v1.3.md section 5 (REQ-V13-CO-01..08) and section 11.1 — that is
your contract; implement exactly it, nothing else.
Test-first: write the failing test, then the fix. New tests go in
tests/test_v13_carryover.py (one test per CO-01..06, CO-05 = three tests).
Run `uv run --locked ruff check .` and `uv run --locked pytest` until green.
Do NOT touch: llm/, agent.py, storage.py, tools.py, config.py, devtools/bench*,
metrics.py, or any part of bot.py other than _remove_sandbox_entry.
NEVER open .env. No new dependencies. Secrets never appear in code/tests/docs.
Return a <=15-line summary: tests added (names), files touched, gate results.
Never paste file contents.
```
