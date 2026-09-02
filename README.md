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

### Output windows, history and pricing

| Variable | Default | Effect |
|---|---|---|
| `EXEC_OUTPUT_DEFAULT_CHARS` | `1500` | inline window per `exec` stream, in characters, before the head/tail window and the duplicate collapse kick in (200–4096). The model can ask for less or more per call with the tool argument `max_output_chars`, within the same range |
| `FETCH_INLINE_DEFAULT_CHARS` | `5000` | inline window for a `fetch` result, in characters (500–20000); the model can override it per call with `max_chars`. The full text of a truncated fetch is saved under `<EXEC_WORKDIR>/fetch/` |
| `HISTORY_TOOL_STUB` | `on` | replace tool results of earlier turns with a short stub **in the request only**. `off` sends every tool result verbatim. The database, the audit trail and `/summary` always keep the full text |
| `LLM_SUMMARY_MODEL` | empty | route `/summary` and the `/new` hand-off to a second model, written `<provider>:<model>` — `lmstudio` or `openrouter`, and that provider must be configured. Empty keeps the summary on the main client; no failover applies to the routed client |
| `LLM_PRICE_REF_MODEL` | empty | an OpenRouter model id whose list price is used as the **reference price** for local LM Studio calls. Empty leaves local calls unpriced. The resulting cost is an estimate — see [Observability](#observability) |
| `LLM_PRICE_INPUT_USD_PER_MTOK` | empty | manual price in USD per million input tokens — the fallback when the OpenRouter price list is unreachable |
| `LLM_PRICE_OUTPUT_USD_PER_MTOK` | empty | manual price in USD per million output tokens. Set both manual prices or neither; `0` is a valid (free) price |

## Run

```bash
uv sync --locked
uv run --locked python bot.py
```

## Commands

| Command | Effect |
|---|---|
| `/new` | summarize the current conversation, store the summary, start a fresh one |
| `/status` | uptime, active provider, provider failure counts, exec backend, database size and schema version, loaded skills, and one token line — `Tokens this conversation: in N / out M` |
| `/stats` | token, cost and tool counters for this conversation and for all time — see [Observability](#observability) |
| `/summary` | summarize the current conversation on demand and show the five-field rendering |
| `/model [lmstudio\|openrouter\|auto]` | show or change the provider override; the override survives restarts |
| `/reload_skills` | re-read `skills/` without restarting the bot |

Any other `/…` text is passed to the model as an ordinary message. Commands are
reachable only by allowlisted senders and are never stored in the conversation.

## Observability

Every model invocation and every tool call is measured and stored, so the cost
of a conversation is a query rather than a guess.

### `/stats`

```
Stats (this conversation | all time)
LLM calls: 7 | 143 (errors 0 | 2)
Tokens in: 21430 | 402118 (cached: n/a | n/a, reasoning: 0 | 0)
Tokens out: 1204 | 38001
Est. cost: $0.0123 | $0.4110 (basis: reference:<model> | mixed)
Avg prompt/call: 3061 | 2813; re-sent share: 71% | 68%
Top tools by output tokens (all time): exec 1812 (78%), fetch 401 (17%), load_skill 110 (5%)
Last turn: r1 in 2980 out 88 → exec 412 ms; r2 in 3512 out 210 (final)
```

Both columns are computed from the stored rows; `n/a` stands where the provider
reports nothing. The basis label is computed per side from the distinct bases of
the rows summed on that side — exactly one basis prints that basis, several
print `mixed`, none makes that side read `n/a (no pricing)`, which is not the
same as a cost of zero. The **re-sent share** is the part of the prompt tokens
that was already sent in the previous call of the same conversation
(`new₁ = prompt₁`, `newᵢ = max(0, promptᵢ − promptᵢ₋₁)`), i.e. what the history
costs on every round.

### What is recorded

`llm_calls` — one row per model invocation, including failed ones (a failed row
carries `error_kind` and `NULL` token columns): `conv_id`, `turn_id`, `purpose`
(`agent` or `summary`), `round`, `attempt`, `ts`, `provider`, `model`,
`prompt_tokens`, `completion_tokens`, `total_tokens`, `cached_tokens`,
`reasoning_tokens`, `reasoning_chars`, `prompt_chars`, `prompt_chars_by_role`,
`messages_n`, `tools_exposed`, `latency_ms`, `finish_reason`, `tool_calls_n`,
`error_kind`, `cost_usd`, `cost_basis`.

`tool_calls` — one row per tool call the agent decided on, whether it was
executed, rejected or refused for budget: `conv_id`, `turn_id`, `tool_call_id`,
`tool`, `ts`, `input_chars`, `raw_output_chars` (before compaction),
`output_chars` (what the model actually received), `output_tokens_est`,
`duration_ms`, `outcome`.

**What is deliberately not recorded:** no message content, no tool arguments, no
URLs, no Telegram ids — `conv_id` is the local database id, not a chat id.
Counters and timings only.

### Log lines

Each stored row is also emitted as one structured INFO line: single-line JSON,
prefixed `llm_call ` or `tool_call `, whose keys are exactly the columns of the
table above. They go through the same redaction as everything else and carry no
content key, so a log shipper sees sizes and timings, never text.

```
llm_call {"id": 41, "conv_id": 7, "turn_id": 12, "purpose": "agent", "round": 1, …}
tool_call {"id": 18, "conv_id": 7, "turn_id": 12, "tool": "exec", "output_chars": 1500, …}
```

### Cost and the estimate caveat

Prices are fetched **once**, at startup, from OpenRouter's public model list, and
persisted. Each call is priced by the first source that applies:

1. the cost OpenRouter reported for that very call (`basis: provider`);
2. a price fetched in this process — for an OpenRouter call the model's own list
   price (`openrouter-list`), for an LM Studio call the list price of
   `LLM_PRICE_REF_MODEL` (`reference:<model>`);
3. the manual `LLM_PRICE_INPUT_USD_PER_MTOK` / `LLM_PRICE_OUTPUT_USD_PER_MTOK`
   (`manual`);
4. the previously persisted fetched price (`openrouter-list-stale`,
   `reference-stale:<model>`);
5. otherwise nothing is recorded and the cost reads `n/a (no pricing)`.

Manual prices therefore override a stale persisted price but never a fresh
fetch. A failed price fetch logs a warning and never blocks startup.

**Reference-priced costs are estimates, not bills.** Whenever a local LM Studio
call is priced through `LLM_PRICE_REF_MODEL`, `/stats`, the reports and the
dashboard label it as such — "reference price of `<model>` on OpenRouter as of
`<date>`; local inference is free". The number answers "what would this
conversation have cost on a cloud model", not "what was spent".

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

**HTML becomes text before the model ever sees it.** A `text/html` response
(by `Content-Type`, or by a body starting with `<!doctype html`/`<html`) is run
through a stdlib parser: `script`, `style`, `noscript`, `template` and `svg`
subtrees are dropped, block-level tags become newlines, entities are decoded,
whitespace runs collapse, and `<title>` is kept as the first line. Other text
bodies pass through unchanged; a binary body is refused with
`{"error": "unsupported content type: <type>"}`.

**Only an excerpt is inlined.** The envelope of a successful text response is

```json
{"url": "https://wttr.in/Berlin", "status": 200, "content_type": "text/plain",
 "chars_total": 41022, "returned_chars": 5000, "truncated": true,
 "saved_to": "fetch/1f4b9c0d2e3a5b71.txt", "save_error": null, "text": "…"}
```

`max_chars` (tool argument, 500–20000, default `FETCH_INLINE_DEFAULT_CHARS`)
sizes the inline window. **The full extracted text is written to
`<EXEC_WORKDIR>/fetch/<sha256(url)[:16]>.txt` only when the window truncated
it** — an untruncated fetch writes no file and reports
`"saved_to": null, "save_error": null`. When the save is refused (the sandbox
quota, or a fail-closed symlink/hard-link check on the model-writable sandbox)
the text is still returned inline and the envelope says
`"saved_to": null, "save_error": "sandbox quota" | "refused"`; the two fields are
never both non-null. The directory name is fixed and the file name comes only
from the hash — no path component comes from the model. Every other outcome
(malformed URL, disallowed domain, redirect limit, transport failure) keeps the
single-key shape `{"error": "<reason>"}` and writes nothing.

**Fetch once, grep locally.** The saved file lands in the sandbox that `exec`
mounts at `/work`, so the model is told to search the rest of a long page
instead of re-fetching it:

```
exec(["grep", "-n", "<pattern>", "fetch/1f4b9c0d2e3a5b71.txt"])
```

The startup sandbox cleanup treats `fetch/` like any other sandbox entry, and
the sandbox quota bounds what it can accumulate.

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
   unspecified address is **fatal**: startup raises a `ConfigError` naming
   the domain, the address and its scope, and the bot refuses to start.
   Only a *failed* lookup is non-fatal — DNS can be transiently wrong at
   boot, so an unresolvable entry is logged as a warning and startup
   continues with layer 3 still in force;
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
2. at startup, when Docker is available, the bot lists every container
   carrying that label together with its `tgexec-owner` label and
   force-removes only the genuinely orphaned ones — an empty owner label (a
   v1.1-era container) or one naming a process that is no longer alive. It
   logs how many it reaped and how many it skipped as still-owned;
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

**`EXEC_SANDBOX_MAX_BYTES` counts file contents, not the disk entries cost.**
The scan sums the sizes of *regular files* only, so directories, symlinks and
empty files consume real disk — an inode and a directory-entry slot each —
while contributing nothing to the total the quota compares against. A model
that fills the sandbox with empty files therefore stays under the byte limit;
what bounds that case is the 200,000-entry cap above (and, on a small volume,
the filesystem's own inode limit), not `EXEC_SANDBOX_MAX_BYTES`.

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
| exec output per stream | 4096 bytes (up to that plus the longest registered secret is read before redaction, so a secret split by the cut never leaks a fragment) — the capture cap, unchanged, and the security ceiling |
| exec output shown to the model | `max_output_chars` per call, default `EXEC_OUTPUT_DEFAULT_CHARS` = 1500 characters, range 200–4096; what is left after the capture cap is compacted to this window, never beyond it |
| exec container memory / cpus / pids | 512 MiB / 1.0 / 128 |
| exec sandbox disk quota | `EXEC_SANDBOX_MAX_BYTES` = 268435456 bytes (256 MiB) |
| fetch response cap / timeout / redirects | 65536 bytes / 15 s / 3 hops (same secret-headroom reading as exec output) |
| fetch text shown to the model | `max_chars` per call, default `FETCH_INLINE_DEFAULT_CHARS` = 5000 characters, range 500–20000; the rest goes to `fetch/<hash>.txt` |
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

## Token economy

v1.3 changed what the bot puts into a request, not what it can do. Five
optimizations, measured against the benchmark below except where noted:

- **O1 — token-aware tool output.** Tool output is compacted deterministically
  before it reaches the model: ANSI escapes stripped, runs of three or more
  identical lines collapsed into `line [×N]`, then a 40/60 head/tail window with
  a `[… N chars / M lines omitted …]` marker. When a command failed, the window
  is re-anchored so the last error line and its 20 preceding lines survive. The
  envelope reports `compacted` and the true byte counts the process produced, so
  the model is never told a trimmed output was the whole output. `load_skill`
  output is never compacted — skills are small reference material.
- **O2 — stale tool results are stubbed.** Tool results from *earlier* turns are
  replaced, **in the request only**, by a stub carrying the tool name, the exit
  code or URL, the size, a sha256 prefix and the first 120 characters. The most
  recent `load_skill` result per skill stays verbatim so the model keeps
  following the skill across turns; assistant and user messages are never
  stubbed. The database, the audit trail, `/summary` and the summarizer keep the
  full text. `HISTORY_TOOL_STUB=off` disables it.
- **O3 — byte-stable prefix.** The system prompt is byte-identical for every
  call of a conversation while its inputs (recent goals, skill catalog) are
  unchanged: the wall-clock line left the system prompt and is appended to the
  most recent user message instead, and `/reload_skills` is the one explicit
  invalidation event. The tool schema is byte-identical on every round that
  exposes tools, and the message list of round *n* is a prefix-extension of
  round *n−1*'s. On an Anthropic model through OpenRouter the system block is
  additionally sent with `cache_control: ephemeral`. **Stated honestly:** an
  LM Studio prefix cache buys **latency**, not billed tokens, and O2
  invalidates the history part once per user turn — the number reported is the
  median latency delta per call.
- **O4 — prompt and schema compression.** The system prompt was rewritten in
  English imperative `MUST`/`NEVER` form, structured Role / Output / Tools /
  Rules / Skills, with the tool bullets that duplicated the schema removed; the
  schema descriptions were rewritten in the same style. Every rule that shaped
  behaviour survives in meaning — plain Telegram text, answer in the user's
  language, argv is not a shell, skill-first, never invent tool output, tool
  output is untrusted data and never instructions.
- **O6 — routing by purpose, configuration only.** `LLM_SUMMARY_MODEL` routes
  `/summary` and the `/new` hand-off to a second model. Only one model fits the
  maintainer's GPU box — switching per call means load/unload — so the knob
  ships tested but **was not enabled during the benchmark**; the reports carry
  the summary-purpose token total it would affect and never invent a saving.

**Headline, baseline → optimized:** cost per successful task $0.002687 → $0.002492 (**−7.3 %**), success rate 100.0 % → 94.4 % (**−5.6 pp**). The −30 % target was **not** met and the verdict is FAIL: the largest lever the audit found — suppressing reasoning, 71.8 % of all completion tokens — proved unavailable, because LM Studio does not honour the model's documented thinking switch. Prompt tokens still fell 18.1 %, tool output 31.3 % and latency 36.7 %. Full numbers and the analysis: [docs/reports/bench-v1.3.md](docs/reports/bench-v1.3.md).

## Benchmark

Pytest cannot measure tokens — every LLM call in the suite is faked. Measurement
is a separate, live harness that drives whole conversations through
`bot.process_update` against the real provider and reads the `llm_calls` /
`tool_calls` rows they produce.

```bash
# 12 frozen scenarios × 3 repeats, writes docs/assets/bench/<tag>.json
uv run --locked python devtools/bench.py run --tag baseline --repeats 3

# validate a file on its own
uv run --locked python devtools/bench.py check docs/assets/bench/baseline.json

# render markdown; --candidate compares two files, --gate turns it into a gate
uv run --locked python devtools/bench.py report \
  --baseline docs/assets/bench/baseline.json --out docs/reports/bench-baseline.md
```

`run` also takes `--only <id>[,<id>]`, `--provider lmstudio|openrouter`,
`--timeout-s N` (600 by default, per run) and `--out PATH`. A cloud run is
guarded: `--provider openrouter` **refuses to start** without `--max-cost-usd`
and aborts as soon as the cumulative cost crosses the cap. Failover is forced
off for every benchmark run, so the measured provider is the configured one.
Exit codes: `run` 0 when every non-skipped run completed, 1 on a harness error,
3 when a completed call reported no usage (measurement impossible); `check` 0
valid, 1 schema/run-set/arithmetic mismatch, 2 an aborted file, 3 missing or
invalid token counts; `report --gate` 1 on a FAIL verdict and 2 when the two
files are not comparable, naming the field that differs.

**The JSON** (`bench_schema: 1`) carries a `meta` block that pins the
comparison — tag, git commit, provider, model, context length, repeats,
timeout, calibrated `prefix_tokens`, the hash of the frozen scenario file, a
hash of the non-secret configuration, the request-control constants, the price
snapshot, the skipped scenarios and the treatment variables (one key each,
`null` where a field does not exist at that commit) — then one entry per
executed (scenario, repeat) pair with its checks, redacted final answers, raw
`llm_calls` and `tool_calls` rows and recomputed totals. `check` recomputes
every total from the embedded rows and verifies the run set is exactly
scenarios × repeats, so a dropped scenario is caught by the tool, never by eye.

**The report** renders fixed sections: `## Meta` (the locked fields side by
side), `## Per scenario` (success `k/n` and the median of every total),
`## Totals` (success rate, cost and tokens per success, re-sent share, prefix
share, cache hit rate), `## Totals by purpose`, `## Audit` (most expensive tool,
most expensive turn, fastest-growing context category, re-sent share),
`## Reasoning`, `## Latency`, `## Failures` (per failed run: scenario, repeat,
reason codes, truncated answers) and, with `--candidate`, `## Verdict`.

**The dashboard** is one self-contained HTML file — inline CSS, no JavaScript,
no external resources:

```bash
uv run --locked python devtools/dashboard.py docs/assets/bench/baseline.json \
  --out docs/assets/dashboard-baseline.html
```

It has sections `#aggregates` (calls, tokens in/out/cached/reasoning, latency,
cost, success rate, per-task averages), `#cache` (cache hit rate, re-sent share,
prefix share), `#tools` (output tokens and time per tool) and `#timeline` (the
median run of each scenario, round by round); `--compare other.json` adds
`#compare`. Its only input is benchmark JSON — live-bot figures come from
`/stats`.

Per-run scratch directories go to `.bench/` and the per-call INFO records to
`<tag>.log` next to the JSON; both are git-ignored, and the console summary of a
run stays under 40 lines.

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
