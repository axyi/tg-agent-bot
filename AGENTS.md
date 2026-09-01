# tg-agent-bot — agent rules

Telegram bot turned into an LLM agent: minimal harness, bounded agent loop,
exec tool, skills (course assignment 3).

Standards summary (self-contained): SDD — the spec is the contract; atomic commits (one prompt → one commit); review in a clean context; deterministic gates before done.

## Stack

- Language: Python 3.13 (pinned via .python-version; requires-python ">=3.12,<3.14"), environment managed by **uv**
- Runtime dependency of the host: the **`docker` CLI** — `exec` runs every
  command inside a disposable container and never falls back to the host
- Frameworks/libs: `httpx` (Telegram Bot API and LLM HTTP calls),
  `python-dotenv` (config from `.env`); standard library for everything else —
  no bot framework, no agent framework
- Tooling: uv (lockfile-pinned), pytest, ruff
- Platform: Linux

## Project layout

- `bot.py` — entry point: Telegram long-polling loop, `--selftest` mode
- `agent.py` — the bounded agent loop (plan → tool call → observation), with a
  hard iteration cap
- `llm/` — inference behind one swappable interface (local ↔ cloud provider),
  hard timeouts, clean error path
- `tools.py` — tool definitions, including the exec tool
- `storage.py` — conversation/state persistence
- `skills/` — skill definitions loaded by the agent
- `tests/` — pytest suite
- `docs/` — spec, prompt log, reports, token accounting

Context boundaries: agents work inside this repository only. Never read or edit
anything above the repository root.
The exec tool runs untrusted model output — it executes only inside the
sandbox described in the spec, never against the host working tree.

## Commit format

- Conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`.
- **One prompt → one commit.** Reference the prompt file in the body:
  `(prompt: docs/prompts/NN-<slug>.md)`.
- Never mix results of different prompts in one commit or MR.

## Branch strategy

- One task → one branch: `feat/<slug>`, `fix/<slug>`, `docs/<slug>`.
- Exception: a single-agent run implementing a whole spec end-to-end may
  commit directly to `main`; branches are for parallel or partial work.
- Parallel agent work: **one git worktree per agent**, merge via MR; never two
  agents in one working tree.

## Gates — run before reporting success

All six must exit 0, run in this order:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 are unconditional and offline. Gate 5 needs the live environment
(a provisioned `.env`, a reachable Docker daemon with the sandbox image pulled,
LM Studio and an OpenRouter key); it spends no inference tokens and sends no
Telegram message. Gate 6 is the mutation-testing gate (`devtools/mutation_check.py`):
offline, but slow (minutes, since it reruns the test suite once per mutation).

## go protocol

`go docs/spec/spec-v0.md` is a standing instruction meaning: **execute that spec
end-to-end, following its own Execution contract section.** Concretely:

- run the gate commands above **verbatim** — same commands, same order, no
  substitutions, no "equivalent" invocations;
- on a failing gate, use the bounded fix loop defined in the spec (fixed maximum
  number of iterations); when the budget is exhausted, stop and report instead
  of retrying;
- log every prompt sent to an LLM as its own file in `docs/prompts/`, and record
  tokens/cost in `docs/llm-usage.md`;
- report the task as done only when every gate is green.

The spec is the contract. Where the spec and this file disagree, stop and ask.

## Spec sync

The spec under docs/spec/ is the contract. Any change that alters
architecture, behaviour, limits, security posture, storage schema or the
command set MUST update the relevant spec delta (or add a new one) in the
same commit. A PR that changes behaviour without touching docs/spec/ is
incomplete.

## Review

Code review is performed by the `code-reviewer` subagent
(`.claude/agents/code-reviewer.md`) in its own clean context — never
self-review in the writing context.

## Reporting

Every prompt sent to an LLM is logged in `docs/prompts/` (one file per
prompt), tokens/cost in `docs/llm-usage.md`, run results in `docs/reports/`.

After each run report, generate `docs/reports/tg-post-vN.md` — a
ready-to-paste Telegram post, written in **Russian**: constraints → result →
metrics (executor model — always named; spec tokens, prompts, first-run,
bugs, tokens in/out, cost — when the harness does not expose tokens/cost,
keep that note and add an estimate at public API prices) → a
link to this project's GitHub repository
(https://github.com/axyi/tg-agent-bot). Under ~1500 characters.


## Secrets

Secrets live in `.env` (git-ignored) — the Telegram bot token and the LLM API
key never leave it. Never write secrets into code, docs, prompts, or reports.
