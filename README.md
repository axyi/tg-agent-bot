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
SSRF client against your own network. Three layers enforce this, not just
advice:

1. **at config load** — an IP literal (IPv4 or IPv6, bracketed or bare, or
   shortened/hex/octal-shaped like `127.1` or `0x7f.1`), `localhost` or a
   `.localhost` suffix, a bare hostname with no dot, or an entry carrying a
   port or a path is rejected with a `ConfigError` naming the offending entry;
2. **at startup** — every allowlisted domain is resolved once; one that
   resolves to a loopback, private, link-local, multicast, reserved or
   unspecified address is logged as a warning (not fatal, in case DNS is
   transiently wrong at boot);
3. **at request time** — the initial URL and every redirect hop are resolved
   again immediately before the request, and refused if the resolved address
   falls in any of those same forbidden scopes.

**Layer 3 fails open, on purpose.** If resolution itself fails (a transient
DNS error), the request-time check finds no address to judge and lets the
request proceed rather than refusing — the allowlist is the primary control,
and a DNS hiccup should degrade `fetch` into an ordinary connection error, not
an unexplainable refusal; the connection itself will fail moments later
anyway. This is the only place in this project that fails open, stated here
precisely because everything else in this document fails closed.

**Accepted residual risks:** the request-time check (layer 3) and the actual
TCP connect are not atomic, so a small DNS-rebinding window remains between
"resolved to a public address" and "connected to it". Separately, the
allowlist constrains the **domain**, not the **port** — an allowlisted domain
answering on a non-standard port is still reachable. Both are narrowed by the
layers above but not closed by them.

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

**Accepted residual risk:** the empty `/etc/resolv.conf` file is created at a
predictable path next to the database. Creation refuses a symlink and
verifies the result is a plain, empty, single-linked file this process owns
(`O_NOFOLLOW`/`O_TRUNC` plus an `fstat` check), and refuses outright to place
it in a sticky-but-world-writable directory — but a directory shared with an
untrusted local user, if one is not one of those two rejected shapes, still
carries a residual TOCTOU race on that predictable path.

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

**This bot is a single process per Docker daemon.** The startup reap now skips
any container whose owner label names a still-live process (checked against
`/proc/<pid>/stat`'s start time, so a recycled pid cannot forge ownership), so
starting a second instance no longer kills a first instance's running exec.
Multi-instance operation is still not a supported configuration — a second
instance's own sandbox directory, database and audit log are independent of
the first's, and nothing coordinates the two beyond this one no-longer-fatal
interaction on the shared Docker daemon.

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
command for exceeding its own budget, and 137 when the command ignored
`SIGTERM` and was finished off by `--kill-after`. While the in-container
wrapper is active, a program that legitimately exits 124 or 137 of its own
accord is indistinguishable from one the wrapper killed, and both are
reported as `timed_out: true`. With the wrapper active, the container now
almost always dies on its own before the outer wall-clock kill, so that path
(the `docker kill` on the timeout branch) becomes nearly unreachable in
production; it stays in the code and stays tested, as the fallback for a
container that ignores its own budget (see Appendix-B scenario D6 in
`docs/reports/report-v1.2.md`).

**Sandbox quota trade-off.** The disk-quota scan (`EXEC_SANDBOX_MAX_BYTES`)
walks the sandbox tree on every `exec`, refusing — naming which of "too many
entries" or "could not be measured" it is — when it holds more than 200,000
filesystem entries (directories and files, even empty ones) or when any
subtree cannot be read, rather than finishing an unbounded or partial walk.
A model that creates that many entries, or makes a directory unreadable,
disables `exec` until the operator clears the sandbox — a self-inflicted
denial of service the model can trigger cheaply. The limit is set high enough
that ordinary work never approaches it, and failing closed is preferred to an
unbounded or silently-partial scan.

**The sandbox is scratch space and is emptied on every start by default:**
`EXEC_SANDBOX_CLEAN_ON_START=true` is the default, and at every startup the
bot empties the sandbox directory, logging how many entries it cleared —
anything a previous run left there is deleted, so an operator does not need
to find and run `rm -rf` by hand. Set `EXEC_SANDBOX_CLEAN_ON_START=false` to
keep files in the sandbox across restarts instead, **accepting that a
sandbox filled past the quota then stays broken (`exec` refused) until it is
cleared by hand.** Separately, the cleanup itself chmods and retries an entry
it cannot remove (the `chmod 000` case); if even that retry fails, it logs
`could not clear <path> from the sandbox; clear it by hand` and continues —
that log line names the manual fallback: `chmod`/`chown` the named path
yourself, then delete it, since the bot owns those entries only because the
container ran as its own uid.

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
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 and 6 are offline and unconditional; only gate 5 needs the live
environment. The suite is provably offline: any
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

`devtools/mutation_check.py` is a standard-library-only mutation-testing gate:
for each of a fixed list of one-line production edits, it applies the edit,
reruns the suite, restores the original byte-for-byte, and fails if the suite
stayed green (the edit "survived" — meaning nothing tests that line).

### Verification

Gates 1–4 prove the code runs and behaves as its tests say; gate 5 proves the
live environment (Docker, Telegram, the model providers) actually works; gate
6 proves the tests can tell correct code from broken code. None of the six
proves the requirements themselves are the right ones — that needs an
adversarial pass against a running instance, which is how every finding
closed by spec-v1.1 and spec-v1.2 was found.
