# Project plan — tg-agent-bot

Course assignment 3: turn a Telegram bot into an LLM agent — minimal harness
(agent loop with hard budgets), a universal `exec` console tool with bounded
mechanics, description-driven skills, `/new` context switching, SQLite dialog
storage with a turn-group context window, and a fail-closed Telegram user
whitelist. The specification is the primary authored artifact; the
implementation is produced by an AI agent from it.

## Status

| Milestone | State |
|---|---|
| Repository scaffold | done |
| `docs/spec/spec-v0.md` (implementation spec, 113 requirements) | done — reviewed, gate passed (0 high/medium findings, 3 review cycles) |
| Implementation (`bot.py`, `agent.py`, `llm/`, `tools.py`, `storage.py`, tests) | done — all four gates green on the first full run, 113 tests, 1 fix cycle of 5 (closing the code review's finding) |
| Live run against Telegram + LM Studio / OpenRouter | **pending — never executed**; the suite and `--selftest` are provably offline, so no real bot token, Telegram API or inference server has been exercised yet |

## How the implementation run works

An AI agent is started with the single instruction `go docs/spec/spec-v0.md`.
The spec opens with an Execution contract: repo root, tests-first
implementation order, acceptance gates verbatim, at most 5 repair-and-rerun
cycles, report or blocker template at the end. Prompts are logged under
`docs/prompts/`, tokens/cost appended to `docs/llm-usage.md`.

## Acceptance gates (from the spec, verbatim)

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
```

## Key design decisions (fixed in the spec)

- Plain Telegram Bot API long polling over httpx — no bot framework; Linux.
- Swappable inference plugin: `llm/lmstudio.py` + `llm/openrouter.py`
  (OpenAI-compatible chat-completions), selected via `LLM_PROVIDER`.
- Hard budgets per user message: ≤8 logical rounds, ≤9 HTTP attempts
  (shared pool), ≤12 tool executions; round 8 exposes no tools.
- `exec(argv)` = bounded arbitrary execution (assignment requires a
  universal console tool): shell=False, sandbox cwd, process-group
  TERM→KILL, capped streaming capture, env allowlist — honestly documented
  as NOT a security boundary; container isolation is a v0 non-goal.
- Storage: conversations / messages (with `turn_id`, `tool_calls_json` +
  `json_valid` CHECK) / `bot_state` for the polling cursor; at-most-once
  delivery semantics; context window of 30 messages selected as whole turn
  groups.
- Tests are provably offline: FakeLLM, injected HTTP transport, injected
  command runner; deterministic `--selftest`.
