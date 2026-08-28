# tg-agent-bot

A Telegram bot turned into a bounded LLM agent. It runs a minimal harness —
plain Python plus `httpx` and `python-dotenv`, no bot framework and no agent
framework — around a loop that alternates model calls and tool calls under hard
budgets: at most 8 logical rounds, 9 HTTP attempts and 12 tool executions per
user message. The model has two tools: `exec(argv)`, which runs one program on
the host, and `load_skill(name)`, which returns the instructions of a locally
installed skill. Conversations live in SQLite, `/new` starts a fresh one, and
only Telegram user ids on an allowlist are served.

## Requirements

- Linux (the runner uses POSIX process groups)
- [uv](https://docs.astral.sh/uv/) — it installs Python 3.13 for you, pinned by
  `.python-version`
- Optionally a running LM Studio server, if you use the local provider

## Create the bot

Open Telegram, talk to [@BotFather](https://t.me/BotFather), send `/newbot`,
choose a display name and a username ending in `bot`, and copy the token it
returns. It looks like `123456789:AA...`.

## Find your Telegram user id

Send any message to your new bot and read the line the bot logs to stderr:

```
WARNING bot unauthorized update from tg_id=424242
```

That number is your user id. Alternatively ask
[@userinfobot](https://t.me/userinfobot). In a private chat the user id equals
the chat id.

## Configure

```bash
cp .env.example .env
```

Fill in `TELEGRAM_BOT_TOKEN` and `ALLOWED_TG_IDS` (comma-separated ids).
`.env` is git-ignored and is the only place secrets live.

## Run

```bash
uv sync --locked
uv run --locked python bot.py
```

## Switch provider

`LLM_PROVIDER=lmstudio` (the default) needs `LMSTUDIO_BASE_URL` and
`LMSTUDIO_MODEL`. The loaded LM Studio model **must support native tool
calling** (for example `qwen3.6-35b-a3b`) — a model without tool-calling support
will never invoke `exec` or `load_skill` and the agent will only ever chat.

`LLM_PROVIDER=openrouter` needs `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`.

## Add a skill

Create `skills/<name>.md` with `---` frontmatter carrying `name` and
`description`, put the exact argv arrays in the body, and restart the bot:

```markdown
---
name: disk-usage
description: Disk usage of the bot host. Use this for any question about free space.
---

Call `exec` with exactly this argv array: ["df", "-h"]
```

The name and the description go into the system prompt, so the description is
what makes the model choose the skill. The body is delivered only when the model
calls `load_skill`.

## Safety

**`exec` is bounded arbitrary execution, not a sandbox in the security sense.**

- It runs **arbitrary programs** chosen by a language model, with the same
  operating-system privileges as the bot process.
- The working directory, the environment allowlist (`PATH`, `LANG`, `HOME`), the
  30-second timeout and the 4096-byte output caps bound *resource usage and
  accident blast radius*. They are **not a security boundary**. A program
  started through `exec` can read any file the bot user can read, open network
  connections, write outside the sandbox directory, and start descendants that
  outlive the process group by calling `setsid` — those descendants are not
  killed.
- Therefore run the bot under a **dedicated low-privilege operating system
  account** that owns no SSH keys, no cloud credentials and no personal data.
  The Telegram whitelist (`ALLOWED_TG_IDS`) is the primary access control:
  everything from an unlisted sender is dropped before any inference or command
  runs.

**Delivery is at-most-once.** The polling cursor is persisted before any side
effect of that update. A crash between persisting the cursor and sending the
reply loses that one reply; the update is never processed twice. Exactly-once
delivery is not provided and is not claimed.

## Tests

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
```

The suite is provably offline: any real outbound HTTP request fails the test,
the LLM and the Telegram client are replaced by fakes, and the command runner is
injected. `--selftest` drives one full update through a temporary database and
sandbox without touching the network or the configured paths.
