# Prompt 02 — code review of the spec-v0 implementation

Agent: `code-reviewer` subagent (`.claude/agents/code-reviewer.md`), clean
context, read-only tools.
Date: 2026-08-28

## Prompt as sent

```
Review commit 89ea2fa on branch feat/spec-v0-implementation of this repository:
the complete implementation of docs/spec/spec-v0.md.

The spec is the contract. Read AGENTS.md and docs/spec/spec-v0.md first, then
review every source file (config.py, storage.py, tools.py, llm/*.py, agent.py,
bot.py), the two skills, the test suite and README.md.

The four gates already pass (uv sync --locked; uv run --locked ruff check .;
uv run --locked pytest -> 113 passed; uv run --locked python bot.py --selftest
-> selftest: OK), so do not re-derive what the linter and the tests prove.

Focus on:
1. Spec violations - any REQ-* whose stated behaviour differs from the code,
   including exact error strings, exact orderings and the exact system prompt.
2. Tests that assert something weaker than the T-* row they implement, or that
   would still pass against a wrong implementation.
3. REQ-DB-09 / REQ-DB-10: the turn-group window; REQ-AG-04..AG-08: the budget
   accounting; REQ-TG-06: the update filter order.
4. Security: secret leakage into logs or exception strings, the exec threat
   model, anything README.md claims that the code does not do.
5. Non-goals (section 8) implemented by accident.

Report findings with file:line, severity and a concrete failure scenario.
```

No runtime data is recorded here — REQ-EC-10.

## Outcome

Verdict: request changes, scoped to one test. Applied in fix cycle 1/5:

- **T-TG-05** rewritten to drive a real HTTP 429 carrying
  `{"parameters": {"retry_after": 7}}` through `TelegramClient`, so REQ-TG-02's
  `retry_after` body parser is executed and asserted (it previously was not:
  mis-nesting the lookup left 113/113 green).
- `tests/fakes.py`: the `subprocess.Popen` guard folded into `RecordingRunner`
  as `forbid_real_processes`, matching REQ-TEST-01's description.
- Assertions strengthened so five previously surviving mutations now fail:
  REQ-CFG-02's `chmod(0o700)`, REQ-TOOL-03's ordering, REQ-TG-06's ordering,
  REQ-AG-10 (T-AG-13's system-row check was vacuous — the schema `CHECK` made
  it un-failable).
- `agent.py`: `finish()` now receives the literal `response.content` per
  REQ-AG-05; only the "content non-empty" test stays whitespace-aware.
- `tools.py`: the skill-parse warning now passes through `config.redact()` —
  the one log call in the codebase that bypassed REQ-CFG-04.
- `bot.py`: `get_me` shape failures handled per REQ-TG-04 step 6, and a
  malformed `chat` can no longer raise `KeyError` out of the poll loop.
- `README.md`: REQ-README-01 section 1 given its heading.
