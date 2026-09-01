# tg-agent-bot

## What it is

A Telegram bot turned into a bounded LLM agent. It runs a minimal harness —
plain Python plus `httpx` and `python-dotenv`, no bot framework and no agent
framework — around a loop that alternates model calls and tool calls under hard
budgets: at most 8 logical rounds, 9 HTTP attempts and 12 tool executions per
user message. The model has three tools: `exec(argv)`, which runs one program
inside a disposable Docker container, `load_skill(name)`, which returns the
instructions of a locally installed skill, and `fetch(url)`, which retrieves one
allowlisted https URL. Conversations live in SQLite, `/new` starts a fresh one
and stores a structured summary of the old one, and only Telegram user ids on an
allowlist are served.

## Requirements

- Linux (the runner uses POSIX process groups)
- [uv](https://docs.astral.sh/uv/) — it installs Python 3.13 for you, pinned by
  `.python-version`
- **Docker**, reachable by the bot user without `sudo`. The sandbox image must
  be pulled in advance — `exec` never pulls at request time:
  ```bash
  docker pull python:3.13-slim
  ```
  Without Docker the bot still starts and still answers; only `exec` refuses.
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

`EXEC_WORKDIR` is bind-mounted read-write into the exec container, so the bot
refuses to start when it is the project root, when it is outside the project
directory entirely, or when it would contain `DB_PATH`, `AUDIT_LOG_PATH` or
`.env`.

`EXEC_SANDBOX_MAX_BYTES` (default `268435456`, 256 MiB) caps the total size of
the sandbox directory; `exec` refuses — without starting a container — once the
sandbox is at or above the limit, and re-checks after every run so an exec that
just crossed it is still reported honestly while the *next* one refuses. See
[Limits](#limits) and the accepted trade-off below.

The bot writes **two** files of its own: `AUDIT_LOG_PATH` (default
`./exec_audit.jsonl`) and `.resolv-empty` next to the database (the neutralised
`/etc/resolv.conf` mounted into every exec container, see
[The exec sandbox](#the-exec-sandbox)). Both default names are git-ignored; if
you point either variable — or `DB_PATH`, which decides where `.resolv-empty`
lands — somewhere else inside the repository, git-ignore that name yourself.

## Run

```bash
uv sync --locked
uv run --locked python bot.py
```

## Commands

| Command | Effect |
|---|---|
| `/new` | summarize the current conversation, store the summary, start a fresh one |
| `/status` | uptime, active provider, provider failure counts, exec backend, database size and schema version, loaded skills |
| `/summary` | summarize the current conversation on demand and show the five-field rendering |
| `/model [lmstudio\|openrouter\|auto]` | show or change the provider override; the override survives restarts |
| `/reload_skills` | re-read `skills/` without restarting the bot |

Any other `/…` text is passed to the model as an ordinary message. Commands are
reachable only by allowlisted senders and are never stored in the conversation.

## Switch provider

`LLM_PROVIDER=lmstudio` (the default) needs `LMSTUDIO_BASE_URL` and
`LMSTUDIO_MODEL`. The loaded LM Studio model **must support native tool
calling** — a model without tool-calling support will never invoke a tool and
the agent will only ever chat.

`LLM_PROVIDER=openrouter` needs `OPENROUTER_API_KEY` and `OPENROUTER_MODEL`.

**Failover.** With `LLM_FAILOVER=auto` (the default) and both providers fully
configured, the bot wraps them: after 3 consecutive failures on the active
provider the same request is re-issued once against the other one, which then
becomes active while the first sits out a 300-second cooldown. When the cooldown
expires the configured primary is tried first again. When both providers fail
the error reaches the agent's normal retry and fallback path — the wrapper never
hides a failure. `/status` and `/model` show which side is answering.

`LLM_FAILOVER=off` keeps the single configured provider.

Each provider carries its own context length (`LMSTUDIO_CONTEXT_LENGTH`,
`OPENROUTER_CONTEXT_LENGTH`); the history budget follows the active side.

## The fetch tool

`fetch(url)` performs one `GET` from the **bot host**, with the bot's network
reach — not from inside the sandbox. Only hosts in `FETCH_ALLOWED_DOMAINS`
(default `wttr.in`) are allowed, matched as the exact domain or a dot-separated
subdomain of it. Redirects are followed manually, at most 3 hops, and every hop
is re-validated against the allowlist.

**Never put an internal hostname or an IP literal in `FETCH_ALLOWED_DOMAINS`.**
The request runs on the bot host, so an internal entry turns the model into an
SSRF client against your own network. This is enforced at startup, not just
advised: an IP literal (IPv4 or IPv6, bracketed or bare), `localhost` or a
`.localhost` suffix, a bare hostname with no dot, or an entry carrying a port
or a path is rejected with a `ConfigError` naming the offending entry.

## Add a skill

Create `skills/<name>.md` with `---` frontmatter carrying `name` and
`description`, put the exact argv arrays (or the exact URL) in the body, and
send `/reload_skills` — no restart needed:

```markdown
---
name: disk-usage
description: Disk usage of the exec sandbox. Use this for any question about free space.
---

Call `exec` with exactly this argv array: ["df", "-h", "/work"]
```

The name and the description go into the system prompt, so the description is
what makes the model choose the skill. The body is delivered only when the model
calls `load_skill`.

## Safety

### The exec sandbox

**`exec` runs arbitrary programs chosen by a language model inside a disposable
Docker container.** Each invocation gets a fresh container with:

- no network (`--network none`);
- a non-root user — the bot's own uid/gid;
- a read-only root filesystem, a 64 MiB `tmpfs` on `/tmp`, and the sandbox
  directory bind-mounted at `/work` as the only writable persistent path,
  capped at `EXEC_SANDBOX_MAX_BYTES`;
- an empty file mounted read-only at `/etc/resolv.conf` — DNS is useless in a
  network-less container, and the host's real resolv.conf would otherwise leak
  the operator's nameservers and search domains into the model's context;
- 512 MiB memory, 1.0 CPU, 128 pids;
- all capabilities dropped and `no-new-privileges`;
- a label (`tgexec=1`) that lets a freshly started bot find and remove
  containers a previous run left behind.

The bot sets exactly three environment variables inside the container (`PATH`,
`LANG`, `HOME`); the image additionally contributes its own public build-time
variables (`HOSTNAME`, `GPG_KEY`, `PYTHON_VERSION`, `PYTHON_SHA256` for the
default image). No host environment variable — including every credential — is
ever forwarded.

**The container is the security boundary** for file access and network reach.
The bot's `.env`, its database, its audit log and the source tree are not
mounted and are unreachable from inside; that is why `EXEC_WORKDIR` may not
contain any of them. Container escape through a kernel or runtime vulnerability
remains out of scope; the defence in depth against it is the value redaction
below and the low-privilege account recommendation, which stays in force.

**Accepted residual risk:** `/proc/self/mountinfo` exposes host overlay paths
(not their contents) inside the container even with the mounts above. Masking
it needs runtime features outside `docker run`'s stock flags and is knowingly
not mitigated in this release.

**No container outlives the bot.** A `--rm` container only cleans itself up
when it exits on its own; a bot process killed mid-run (`kill -9`, a crash)
leaves its container running, holding its memory and CPU slice. Three layers
close this:

1. every container carries the `tgexec=1` label;
2. at startup, when Docker is available, the bot runs `docker ps -aq --filter
   label=tgexec=1` and force-removes whatever it finds, logging how many it
   reaped;
3. when the image provides GNU `timeout` (probed once at startup), the command
   inside the container is wrapped in `timeout --kill-after=5 <budget>`, so the
   container terminates on its own even when no parent is left to kill it. If
   the probe fails — a missing `timeout(1)`, a hung daemon, `docker` itself
   missing — the wrapper is skipped and a warning is logged; orphan protection
   then rests on the startup reap alone.

**This bot is a single process per Docker daemon.** The startup reap removes
*every* container carrying the label, so running two instances of this bot
against the same daemon would let a starting instance kill a running
instance's sandbox. Multi-instance operation is not supported.

**The honest price.** Membership in the `docker` group over a rootful daemon is
**root-equivalent on the host**. The isolation of `exec` is bought at exactly
that cost — and it is held by the *bot process*, not by the sandboxed program.
Rootless Docker is the proper remedy and is deliberately out of scope for this
version. Run the bot under a **dedicated low-privilege account** that owns no
SSH keys, no cloud credentials and no personal data, and understand that this
account is docker-group-privileged.

"Non-root inside the container" only holds while the bot itself is not root: if
the bot runs as uid 0 it refuses to enable `exec` at all and logs the reason.
When Docker is unavailable the tool refuses to execute — **there is no
host-execution fallback** in the serving path. The only host execution left is
inside the operator-invoked `--selftest` harness.

Accepted ambiguity: docker's client reports 125 (daemon/run error), 126 (not
executable) and 127 (program not found) for its own failures. A program that
itself exits with one of those codes inside the container is indistinguishable
from a docker-level failure and is reported as one.

A second, related ambiguity: `timeout(1)` exits 124 when it kills the wrapped
command for exceeding its own budget. While the in-container wrapper is
active, a program that legitimately exits 124 of its own accord is
indistinguishable from one the wrapper killed, and both are reported as
`timed_out: true`. With the wrapper active, the container now almost always
dies on its own before the outer wall-clock kill, so that path (the
`docker kill` on the timeout branch) becomes nearly unreachable in production;
it stays in the code and stays tested, as the fallback for a container that
ignores its own budget.

**Sandbox quota trade-off.** The disk-quota scan (`EXEC_SANDBOX_MAX_BYTES`)
walks the sandbox tree on every `exec`, refusing when it holds more than
200,000 filesystem entries (directories and files, even empty ones) rather
than finishing an unbounded walk. A model that creates that many entries
disables `exec` until the operator clears the sandbox — a self-inflicted
denial of service the model can trigger cheaply. The limit is set high enough
that ordinary work never approaches it, and failing closed is preferred to an
unbounded scan; recovery is one `rm -rf` of the sandbox contents.

**Redaction is defence in depth, not a security boundary.** Every guard below
matches **literal registered values**. Any transformation performed inside the
sandbox — `base64`, `rot13`, chunking, compression — defeats it: the model can
read a secret's absence from the sandbox, but nothing stops it from disguising
data that *is* reachable before handing it back. Redaction protects against
accidental echo, not against an adversary who already controls what runs in
the sandbox; entropy-based or heuristic detection is deliberately out of
scope. The real boundary for secrets is that they are never reachable from the
container at all (see above). Separately, every redaction guard in this
codebase (the tool envelope, the storage guards, the outgoing-message guard)
matches against the **serialised** JSON text in some paths, which cannot
recognise a secret whose JSON encoding differs from its raw form — a value
containing a backslash, a quote or a control character survives there in its
escaped form. Every credential this project handles is escape-free, which is
why the simpler, per-record form is accepted.

### Secrets and the audit trail

Every registered secret is stripped from every tool envelope, every stored
message, every outgoing Telegram text and every audit line. The database file is
`0600`, and so is the audit log.

Every `exec` and every `fetch` — including refused ones — appends one redacted
JSON line to `AUDIT_LOG_PATH`:

```json
{"ts": "2026-09-01T12:00:00Z", "tg_user_id": 424242, "conv_id": 7,
 "tool": "exec", "argv": ["uname", "-a"], "outcome": "ok",
 "exit_code": 0, "timed_out": false, "duration_ms": 812}
```

### Access control and delivery

The Telegram allowlist (`ALLOWED_TG_IDS`) is the primary access control:
everything from an unlisted sender is dropped before any resource is spent — no
storage, no inference, no command, no rate-limit token. Allowlisted senders are
then rate-limited: a token bucket of 10 with one token back every 6 seconds. The
bucket lives in memory only, so a restart forgives everyone.

**Delivery is at-most-once.** The polling cursor is persisted before any side
effect of that update. A crash between persisting the cursor and sending the
reply loses that one reply; the update is never processed twice. Exactly-once
delivery is not provided and is not claimed.

## Limits

| Limit | Value |
|---|---|
| user message length | 4000 characters |
| model output cap | `LLM_MAX_TOKENS` = 2048 |
| context budget | provider context length − system prompt − output cap − 512 |
| context window | 30 messages |
| exec command budget | ~30 s; hard wall-clock kill at 30 + 10 s (container startup grace); the in-container `timeout(1)` wrapper, when available, applies the same ~30 s budget from inside |
| exec output per stream | 4096 bytes (up to that plus the longest registered secret is read before redaction, so a secret split by the cut never leaks a fragment) |
| exec container memory / cpus / pids | 512 MiB / 1.0 / 128 |
| exec sandbox disk quota | `EXEC_SANDBOX_MAX_BYTES` = 268435456 bytes (256 MiB) |
| fetch response cap / timeout / redirects | 65536 bytes / 15 s / 3 hops (same secret-headroom reading as exec output) |
| agent rounds / HTTP attempts / tool executions | 8 / 9 / 12 |
| malformed retries / empty repairs | 2 / 1 |
| LLM request timeout | `LLM_TIMEOUT_S` = 120 s |
| rate limit | 10 burst, 1 per 6 s |
| send retries | 3 attempts |
| summary output cap | 512 tokens |
| failover threshold / cooldown | 3 consecutive failures / 300 s |

## Error behaviour

| Failure | Behaviour | What the user sees |
|---|---|---|
| LLM transport / timeout / 429 / 5xx | retry within the attempt pool | on exhaustion: the "model unavailable" fallback |
| LLM malformed response | up to 2 blind re-asks | on exhaustion: the "model unavailable" fallback |
| LLM 4xx | no retry | the "model unavailable" fallback |
| primary provider persistently down | failover to the secondary | an answer from the secondary; `/status` shows it |
| empty model response | 1 repair round | on repeat: the "empty answer" fallback |
| answer truncated by `max_tokens` | delivered with a notice | `[answer truncated by the model's output token limit]` |
| Docker unavailable / bot run as root | exec refuses, the bot keeps serving | a tool error the model must relay honestly |
| exec timeout | the container is killed (outer kill, or the in-container wrapper) | an envelope with `timed_out: true` |
| sandbox at or over `EXEC_SANDBOX_MAX_BYTES` | exec refuses without starting a container | a tool error envelope naming the used/allowed bytes |
| fetch to a non-allowlisted domain | refused before any request leaves | a tool error envelope |
| Telegram 429 on send | bounded retry honouring `retry_after` | delayed delivery |
| Telegram send fails after retries | the reply is lost and logged | nothing |
| DB error | the exception propagates, the process exits non-zero | a restart is the supervisor's job |
| SIGTERM mid-run | the current round finishes, then the run is interrupted | the "shutting down" fallback, best-effort |
| rate limit exceeded | rejected before storage | the fixed rate-limit message |
| message too long | rejected before storage, no bucket token spent | the fixed too-long message |

## Tests

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
```

The first four are offline and unconditional. The suite is provably offline: any
real outbound HTTP request fails the test, the LLM and the Telegram client are
replaced by fakes, the command runner is injected, and even the `docker` binary
is a stub script on `PATH`. `--selftest` drives one full update through a
temporary database and sandbox without touching the network or the configured
paths.

`--selftest-live` is the only command that talks to the real world. It checks
the config, the database schema, Docker (probe, image present, one real
`echo live-ok` container), Telegram `getMe`, the LM Studio model list and the
OpenRouter model list. It never issues a chat/completions request, so it costs
zero tokens, and it never sends a Telegram message. It exits non-zero if any
check fails; unconfigured providers are skipped, not failed. The `/status`
exec-backend line renders the version probed at **startup**, not a live one.
