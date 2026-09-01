# tg-agent-bot — implementation specification v1.1 (patch: audit findings)

This document is the complete contract for a **patch release** on top of the
implemented spec-v1 state. It is a **delta specification**: spec-v0
(`docs/spec/spec-v0.md`) and spec-v1 (`docs/spec/spec-v1.md`) remain in force
except where a requirement here explicitly **amends**, **supersedes** or
**extends** them (section 2 is the authoritative amendment table). Everything
needed to implement, test and accept the work is in this file, in spec-v0/v1,
or in files this spec tells you to change. Do not look for other sources.

Every requirement has a stable `REQ-V11-*` id and is tagged `MUST` or
`NON-GOAL`. v1.1 ids never collide with v0 or v1 ids. `MUST` = required for
acceptance. `NON-GOAL` = out of scope; implementing it is a defect, not a
bonus.

Target platform: **Linux only**. Language: **Python**. Package manager: **uv**.
Executor model for this run: **claude-sonnet-5** — the work is narrow,
mechanical and fully specified below; a larger model is not needed and must
not be substituted for reading this spec less carefully.

**This is a patch release.** Behaviour changes only where a requirement below
says so. No new features, no refactoring beyond what a listed fix requires, no
opportunistic cleanups. Every v1 acceptance property must still hold when you
are done.

Provenance: the defect list comes from two independent post-implementation
audits of the delivered v1 (commits `c9f7912`, `c1f27c3`, `782a378`), both run
in clean contexts:

- an **adversarial security probe** that exercised the running system
  (findings V-1 … V-8, plus one documentation discrepancy);
- a **spec-compliance review** with 37 mutation probes against the test suite,
  of which 4 survived (findings R-1 … R-3, R-6) — surviving mutations are
  places where the suite cannot tell correct code from broken code.

Both audits confirmed the headline v1 property: the v0 secret-exfiltration
hole (`cat ../.env` from the exec sandbox) is **closed**, verified through five
independent vectors. The findings below are the residue. Appendix A maps every
finding to requirements.

This spec was itself reviewed in a clean context before release; that review's
executability findings are already folded in — most consequentially the
REQ-V11-WIR-01 startup seam, without which this patch's startup code would
have executed real `docker rm -f` commands during `pytest`.

---

## 1. Execution contract

**REQ-V11-EC-01 (MUST)** All of spec-v0 section 1 and spec-v1 section 1
(REQ-V1-EC-01 … REQ-V1-EC-05) apply to this run unchanged, with these
adjustments:

- "The gate commands" means the five commands of section 10 of this spec —
  identical to spec-v1's five.
- The repair budget is **5 total** repair-and-rerun cycles (one cycle = one
  fix + one complete run of all gates from the first).
- REQ-V1-EC-01's absolute rule stands: the executor reads and writes
  **nothing outside the repository root**, without exception.
- The Python dependency set is unchanged and MUST stay unchanged: `httpx`,
  `python-dotenv`. The `docker` CLI remains an external host dependency.
  Everything this spec adds uses the standard library (`ipaddress`, `math`,
  `os`, `subprocess`).

**REQ-V11-EC-02 (MUST)** Work test-first: write the new and corrected tests of
section 9 first, observe them fail for the right reason, then implement in the
order of section 8. All **four** corrected tests (REQ-V11-TST-01 …
REQ-V11-TST-04) currently pass against broken code — for each of the four,
first prove the defect by
temporarily breaking the production code the way the audit's mutation did,
confirm the corrected test fails, restore the code, and confirm it passes.
Record in the report that this check was performed.

**REQ-V11-EC-03 (MUST)** The v1 test suite is 203 passing tests. No test may be
deleted. Tests may be **modified only** where section 9.1 lists them.
Section 9.1 is exhaustive; changing any other existing test is a defect. When
a change makes an unlisted test fail, that is a signal the change is wrong —
stop and reconsider, do not edit the test.

**REQ-V11-EC-04 (MUST)** Secrets discipline is unchanged (REQ-V1-EC-04): the
values of `TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY` and any other credential
MUST never be printed, logged, committed, or quoted in `docs/`. Presence
checks are done by key **name** only. Tests use the existing synthetic
sentinel pattern, never a real credential.

**REQ-V11-EC-05 (MUST)** Backward compatibility, same rule as REQ-V1-EC-05:
every new parameter, config field and helper introduced here has a default
that reproduces current behaviour when absent, so that unlisted tests and
fakes keep passing. In particular `_Capture(cap)` keeps working with one
positional argument, and the new sandbox/quota/label wiring is defaulted.

---

## 2. Amendments to spec-v0 / spec-v1 — authoritative table

**REQ-V11-AMEND-01 (MUST)** Apply exactly these changes. Requirements not
listed here stay in force verbatim.

| id | Status in v1.1 | Replacement / change |
|---|---|---|
| REQ-V1-SEC-01 | extended | the `execute_tool` choke point stays; `storage` gains a last-line guard so no write path can bypass redaction (REQ-V11-RED-01) |
| REQ-V1-SEC-03 | amended | audit redaction of the serialised record is the normative behaviour; its one limitation (a secret containing JSON escapes) is documented, not fixed (REQ-V11-DOC-03) |
| REQ-V1-SEC-06 | extended | redaction at the storage boundary additionally covers **model-authored tool-round content and tool-call arguments**, before both the database write and the outgoing payload; the v1 upstream redaction in `finish()`, `process_update` and `execute_tool` **stays exactly as delivered** and keeps `T-V1-RED-02` valid (REQ-V11-RED-01) |
| REQ-V1-DK-03 | amended | `build_docker_argv` gains the container label, the neutralised `/etc/resolv.conf` mount and the in-container hard budget wrapper (REQ-V11-ORP-01, REQ-V11-INF-01, REQ-V11-ORP-03) |
| REQ-V1-DK-04 | amended | the runner refuses when the sandbox is over quota (REQ-V11-QTA-02), re-checks size afterwards (REQ-V11-QTA-03), and maps in-container exit 124 to `timed_out: true` while the wrapper is active (REQ-V11-ORP-03) |
| REQ-V1-DK-05 | extended | startup additionally reaps orphaned containers (REQ-V11-ORP-02), probes the image for `timeout` (REQ-V11-ORP-04) and prepares the empty resolv file (REQ-V11-INF-01) — all three behind the single seam of REQ-V11-WIR-01; `exec_backend_status` keeps its v1 signature and 2-tuple return |
| REQ-PATH-04 | amended | the bot now writes **two** files of its own: the audit log and the empty `/etc/resolv.conf` source file (REQ-V11-INF-01). All other logging still goes to stderr only |
| REQ-V1-SEC-07 | extended | `.gitignore` additionally covers `.resolv-empty` (REQ-V11-INF-01) |
| REQ-V1-AUD-02 | extended | the exec audit record gains the additive optional key `sandbox_over_quota` (REQ-V11-QTA-03) |
| REQ-V1-FT-03 | amended | `_is_pre_network` gains `URL_MALFORMED` so a URL refused before any request still audits as `refused`, not `error` (REQ-V11-DOC-04) |
| REQ-V1-DK-06 | amended | the exec tool description states the sandbox size limit (REQ-V11-QTA-04) |
| REQ-V1-CFG-02 | extended | new variable `EXEC_SANDBOX_MAX_BYTES` (REQ-V11-QTA-01) |
| REQ-V1-CFG-03 | amended | `EXEC_WORKDIR` must be a strict descendant of the project root (REQ-V11-CFV-02) |
| REQ-V1-CFG-04 | extended | `.env.example` gains the new variable with its default (REQ-V11-QTA-01) |
| REQ-V1-FT-02 | amended | body reading gains secret headroom (REQ-V11-TRN-02); a URL that fails to parse gets its own message (REQ-V11-DOC-04); allowlist entries are validated at config time (REQ-V11-CFV-01) |
| REQ-V1-TB-05 | extended | the limits table gains the sandbox quota, the secret headroom and the in-container budget |
| REQ-V1-VIS-02 | amended | wording corrected to match delivered behaviour: the status message is edited before **each** tool execution including the first (REQ-V11-DOC-02) |
| REQ-V1-ACC-01 | extended | Appendix B of this spec is executed in addition to spec-v1's Appendix B (REQ-V11-ACC-01) |
| T-V1-DK-01 / T-V1-DK-02 | amended | updated for the new argv (section 9.1) |
| T-V1-VIS-01 | amended | the status-line assertions are made non-vacuous (REQ-V11-TST-01) |
| T-V1-FT-02 | extended | proves reading stops at the cap (REQ-V11-TST-03) |
| T-V1-DK-05 | extended | asserts the outer timeout actually carries the startup grace (REQ-V11-TST-04) |
| T-V1-CFG-01 | extended | gains the outside-project-root case (REQ-V11-CFV-02, section 9.1) |
| T-V1-FT-01 | amended | an unparsable URL now expects `URL_MALFORMED` (REQ-V11-DOC-04, section 9.1) |
| `test_main_binds_the_container_runner_not_the_host_runner` and `test_main_disables_exec_when_the_backend_is_down` | amended | new runner keywords and the REQ-V11-WIR-01 seam (section 9.1) — without this the run cannot pass its own gates |

Everything else in spec-v1 — the Docker isolation posture, the redaction choke
point, failover, structured memory, commands, rate limiting, the error matrix,
the token budget — is unchanged and MUST keep working.

---

## 3. Preconditions (verify before writing any code)

**REQ-V11-PRE-01 (MUST)** Verify each item; on failure stop and emit the
blocker template (v0 section 7.2) instead of guessing.

1. Repository state: branch `main`, clean tree, HEAD at the delivered v1
   (`docs/spec/spec-v1.md` and `docs/reports/report-v1.md` both present).
2. All five v1 gates green **before** you change anything (section 10). This
   is the baseline: a gate that is already red is a blocker, not something to
   fix silently inside this run.
3. Provisioned credentials: the git-ignored `.env` exists at the repository
   root and contains `TELEGRAM_BOT_TOKEN`, `TELEGRAM_BOT_NAME`,
   `ALLOWED_TG_IDS`, `LLM_PROVIDER`, `LMSTUDIO_BASE_URL`, `LMSTUDIO_MODEL`,
   `LMSTUDIO_CONTEXT_LENGTH`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.
   Validate **presence by key name only**. Do not create, overwrite or
   display `.env`. `ALLOWED_TG_IDS` now holds the operator's real Telegram
   id, so live scenarios needing a real sender are executable.
4. Docker: `docker version` succeeds without `sudo`; the sandbox image
   (`EXEC_DOCKER_IMAGE`, default `python:3.13-slim`) is present locally
   (`docker image inspect`) — exec never pulls at request time.
5. The image provides GNU `timeout`: the hardened probe of REQ-V11-ORP-04
   succeeds. If it does not, REQ-V11-ORP-03's wrapper degrades by design —
   record the fact in the report rather than treating it as a blocker.

---

## 4. Required file tree (delta)

**REQ-V11-TREE-01 (MUST)** New files:

```
tests/test_v11_patch.py     # every new test of section 9.2
docs/prompts/04-code-review-v1.md    # the missing v1 review prompt (REQ-V11-DOC-01)
docs/prompts/05-go-spec-v1.1.md      # this run's own go prompt
docs/prompts/06-code-review-v1.1.md  # this run's review prompt (REQ-V11-REV-01)
docs/spec/spec-v1.1.md      # this file [exists, unchanged]
```

**Prompt numbering, fixed to avoid a collision:** `04` is the reconstructed v1
review prompt, `05` is the `go` prompt that starts this run, `06` is this run's
code-review prompt. Use exactly these numbers.

Changed files: `config.py`, `storage.py`, `tools.py`, `agent.py`, `bot.py`,
`.env.example`, `.gitignore` (REQ-V11-INF-01), `README.md`,
`docs/spec/spec-v1.md` (documentation notes only, REQ-V11-DOC-02 and
REQ-V11-DOC-07), `docs/prompts/03-go-spec-v1.md`, `docs/reports/report-v1.md`,
plus exactly the test files named in section 9.1.

No new module is created: every fix belongs to an existing owner
(REQ-V1-TREE-02). New constants live beside their existing neighbours —
sandbox/label/grace constants in `tools.py`, secret helpers in `config.py`.

---

## 5. Security fixes

### 5.1 Redaction of model-authored content (finding V-1)

The delivered v1 redacts tool envelopes (`execute_tool`), final replies
(`finish()`), incoming user text, audit records and everything leaving through
Telegram. It does **not** redact the assistant's own content and tool-call
arguments in a tool round: `agent.py` passes `response.content` and the
serialised `wire_tool_calls` straight into `storage.add_tool_turn` and into the
next request payload. A secret the model quotes back — from a skill file, from
an earlier turn, from anything the model composes — is therefore stored
verbatim in SQLite and re-sent to the provider, which under OpenRouter means a
third party. The audit demonstrated all three legs. A code comment in
`agent.py` already claims this path is redacted; this requirement makes the
claim true.

**REQ-V11-RED-01 (MUST)** Redaction becomes a property of the storage layer
and of the outgoing payload, not of individual call sites:

1. `storage.py` redacts what it writes, at the moment it writes it, using
   `config.redact()`. The list is **exhaustive** — exactly these four writers,
   no others:
   - `add_user_message` — the message text;
   - `add_assistant_message` — the message text;
   - `add_tool_turn` — the `content` argument, the serialised `tool_calls`
     JSON payload, and each tool result string;
   - `add_summary` — the stored JSON.
   `set_state` and the cursor writer are **excluded**: they carry bot-internal
   values (polling cursor, provider override), never model or user text, and
   redacting them would only add noise.
   `config.redact` is idempotent (the placeholder contains no secret), so
   the existing upstream redaction of `finish()`, `execute_tool` and
   `process_update` stays in place as defence in depth and double redaction
   is harmless and expected.
2. `agent.py` redacts the assistant turn **once**, before either sink sees
   it, and uses that same redacted pair for the database and for
   `messages.append`:

   ```python
   content = config.redact(response.content or "")
   wire_tool_calls = _redact_tool_calls([_to_wire(call) for call in normalized])
   storage.add_tool_turn(conn, conv_id, content, wire_tool_calls, results)
   messages.append(
       {"role": "assistant", "content": content, "tool_calls": wire_tool_calls}
   )
   ```

   `_redact_tool_calls(calls: list[dict]) -> list[dict]` is a module-level
   helper in `agent.py`: it serialises each call's `function.arguments`
   string through `config.redact()` and leaves the structure otherwise
   untouched (ids, names and shape are preserved byte-for-byte, because the
   provider matches `tool_call_id` against them).
3. The stale comment at the summary writer that claims "the redaction path
   every other stored model output takes" stays, and is now accurate.

**REQ-V11-RED-02 (MUST)** The suite must fail if any guard is removed. Five
mutations MUST be caught (section 9.2, T-V11-RED-01/02): deleting the
`config.redact` call in `agent.py`'s assistant-turn assembly, and deleting the
guard inside each of the four storage writers listed above. A test that covers
only `add_tool_turn` does not satisfy this requirement.

### 5.2 Truncation must not split a secret (finding V-2)

`_Capture` keeps the first 4096 bytes of each stream and discards the rest;
redaction runs afterwards. A secret straddling the cut leaves a fragment that
`config.redact` — which matches whole values — cannot recognise. The audit
recovered fragments of ≥16 characters this way. The same shape exists in
`fetch_url`, which cuts the body at 65536 bytes before the envelope is
redacted. Note that `bot._status_line` already gets this right (it redacts
before truncating) and its comment explains exactly this hazard.

**REQ-V11-TRN-01 (MUST)** `config.py` gains two helpers:

- `max_secret_length() -> int` — the length in **bytes** (UTF-8) of the
  longest registered secret, or `0` when none are registered.
- `strip_secret_fragment(text: str) -> str` — removes from the **end** of
  `text` the longest suffix that is a proper prefix of some registered
  secret and is at least `SECRET_FRAGMENT_MIN = 8` characters long; returns
  `text` unchanged when there is no such suffix. Comparison is exact
  (no case folding).

**REQ-V11-TRN-02 (MUST)** Capture with headroom, then redact, then cut:

1. `_Capture(cap: int, *, headroom: int = 0)` keeps up to `cap + headroom`
   bytes and sets `truncated` as soon as **more than `cap`** bytes have been
   fed. The one-argument construction keeps v1 semantics exactly
   (`headroom=0`).
2. `_run_process` builds its captures with
   `headroom=config.max_secret_length()`.
3. Envelope assembly for `stdout`/`stderr` becomes, in this order: decode the
   captured bytes **with `errors="replace"`** → `config.redact(...)` →
   `strip_secret_fragment(...)` → re-encode UTF-8 → cut to
   `EXEC_MAX_STREAM_BYTES` bytes → decode again **with `errors="replace"`**.
   Both decodes MUST be lenient: a strict decode would raise on the binary
   stdout that `T-EX-11` feeds in. The `truncated` flag comes from the capture, never
   from the post-redaction length (redaction can shorten the text, and a
   shortened text is not "untruncated").
4. `fetch_url` reads until `len(body) > max_bytes + config.max_secret_length()`
   and then stops, and applies the same decode → redact →
   `strip_secret_fragment` → cut-to-`max_bytes` order. `truncated` is
   `True` when more than `max_bytes` bytes were read.

The byte cap that reaches the model is therefore unchanged (4096 per stream,
65536 per body); only the amount read before redaction grows, by at most the
longest registered secret.

### 5.3 Orphaned containers (finding V-5)

A container survives the death of the bot process: `--rm` fires only when the
container exits, and `docker kill` is issued only on the timeout path of a
living bot. The audit killed the bot's process group and observed the
container still running, holding 512 MiB and a CPU. Three layers fix it: a
label, a reap at startup, and a hard budget inside the container itself.

**REQ-V11-ORP-01 (MUST)** Every container is labelled. `build_docker_argv`
inserts `"--label", CONTAINER_LABEL` (with `CONTAINER_LABEL = "tgexec=1"`)
immediately after the `--name` pair. The label is the only reliable handle on
containers whose names the restarted process no longer knows.

**REQ-V11-WIR-01 (MUST)** One named startup seam — this is a **safety
requirement, not a style choice**. Everything this spec adds to startup (the
reap of REQ-V11-ORP-02, the image probe of REQ-V11-ORP-04, the empty-resolv
file of REQ-V11-INF-01) lives behind a single function:

```python
bot._startup_docker_wiring(cfg, docker_ok: bool) -> tuple[bool, Path | None]
```

returning `(wrap_timeout, empty_resolv_path)` and doing nothing at all — no
subprocess, no file creation — when `docker_ok` is false. `main()` calls it
exactly once, right after `exec_backend_status()`.

Why it must be a single named seam: the existing tests
`test_main_binds_the_container_runner_not_the_host_runner` and
`test_main_disables_exec_when_the_backend_is_down`
(`tests/test_v1_guardrails.py`) monkeypatch `bot.exec_backend_status` to return
`("27.1.2", True)` **without** touching `PATH`. Any startup code that shells out
to `docker` would therefore run **real** `docker ps` / `docker rm -f` /
`docker run` commands during `pytest` — deleting the operator's live `tgexec`
containers and failing the suite on machines without a daemon. Section 9.1
requires both tests to stub this one seam; no other startup path may call
`docker`.

`exec_backend_status` keeps its v1 signature and its 2-tuple return
(`tests/test_docker.py` unpacks it in three places and is not in section 9.1).

**REQ-V11-ORP-02 (MUST)** Startup reap, invoked only from REQ-V11-WIR-01. When
`docker_ok` is true, `bot.py` runs once at startup, before serving:

```
docker ps -aq --filter label=tgexec=1
```

and, when the output is non-empty, `docker rm -f <id>…` for those ids. Both
calls use `subprocess.run(..., timeout=REAP_TIMEOUT_S, capture_output=True)`
with `REAP_TIMEOUT_S = 15.0` and the REQ-V1-DK-08 environment passthrough.
Failures are logged at WARNING and never prevent startup. When containers were
removed, log `INFO reaped N orphaned exec container(s)`.

**Stated assumption, MUST be documented in `README.md`:** this bot is a single
process per Docker daemon. The reap removes *every* container carrying the
label, so running two instances of this bot against the same daemon would let
a starting instance kill a running instance's sandbox. Multi-instance operation
is not supported (v0 REQ-NG / v1 REQ-V1-NG-07 already exclude it).

**REQ-V11-ORP-03 (MUST)** In-container hard budget. When the image provides
GNU `timeout` (probed once at startup, REQ-V11-ORP-04), the command inside the
container is wrapped:

```
["timeout", "--kill-after=5", str(int(EXEC_TIMEOUT_S)), *argv]
```

so the container terminates on its own budget even when no parent is left to
kill it. The wrapper is built from the **module constant** `EXEC_TIMEOUT_S`,
not from the `timeout_s` of the individual call: `run_command_docker`'s
`timeout_s` parameter is only ever overridden by tests, and keeping the two
independent avoids a second, subtly different budget inside the container.
`build_docker_argv` takes a defaulted keyword-only parameter
`wrap_timeout: bool = False` and applies the wrapper only when it is true.
When the wrapper is absent, orphan protection rests on REQ-V11-ORP-02 alone;
this degradation MUST be logged once at startup and stated in `README.md`.

**One situation, one envelope.** `timeout(1)` exits with **124** when it kills
the command for exceeding the budget. Budget exhaustion must not produce two
different envelopes depending on which killer won the race — the outer
`_run_process` kill (which sets `timed_out: true`) or the in-container wrapper.
Therefore, when `wrap_timeout` is true for the invocation,
`run_command_docker` maps exit code **124** to `timed_out: true` in the
returned envelope; `exit_code` keeps the value the client reported and tests
never assert an exact code (as in REQ-V1-DK-04 step 3). With
`wrap_timeout=False` the mapping does not apply and 124 stays an ordinary
program exit code.

The mapping lives in `run_command_docker`, in the same place that already
classifies docker-level exit codes (REQ-V1-DK-04 step 4). There is no overlap:
124 is disjoint from 125/126/127, so the two classifications cannot collide.

Accepted ambiguity, MUST be documented in `README.md` next to the 125/126/127
note of REQ-V1-DK-04 step 4 and treated as the same class of trade-off: a
program that legitimately exits with 124 of its own accord, while the wrapper
is active, is indistinguishable from one the wrapper killed and will be
reported as timed out.

Consequence to note in the run report: with the wrapper active the container
now almost always dies on its own before the outer 40-second wall, so the
`docker kill` path of REQ-V1-DK-04 step 3 becomes nearly unreachable in
production. It stays in the code and stays tested — it is the fallback for a
container that ignores its own budget.

**REQ-V11-ORP-04 (MUST)** Image capability probe.
`tools.image_has_timeout(image: str) -> bool` runs

```
docker run --rm --pull never --network none --user <uid>:<gid> --read-only
  --cap-drop ALL --security-opt no-new-privileges <image> timeout --version
```

via `subprocess.run(..., timeout=IMAGE_PROBE_TIMEOUT_S, capture_output=True)`
with `IMAGE_PROBE_TIMEOUT_S = 15.0` and the DK-08 passthrough, and returns
`rc == 0`. `--pull never` is mandatory: without it a bot start could pull from
the network, contradicting section 3 item 4 and REQ-V1-DK-03. The probe
container carries the same hardening as a real exec container, minus the mount
and the tmpfs it does not need.

**It never raises.** Like `docker_probe` (`tools.py`), it wraps the call in
`except (OSError, subprocess.SubprocessError): return False` — a missing
`docker` binary or a hung daemon must degrade exec, exactly as v1 does, and
must never take `main()` down. It is invoked only from REQ-V11-WIR-01. On
`False`, log
`WARNING exec container self-timeout unavailable: <image> has no timeout(1); relying on startup reap`.

### 5.4 Sandbox disk quota (finding V-4)

The sandbox bind mount is unbounded: the audit wrote 300 MB in 0.145 s
(2.2 GB/s), so a single 30-second exec can fill a host disk. The tmpfs at
`/tmp` is capped; the mount is not.

**REQ-V11-QTA-01 (MUST)** New configuration variable
`EXEC_SANDBOX_MAX_BYTES`, parsed like the other integer variables: default
`268435456` (256 MiB), minimum `1048576` (1 MiB), maximum `4294967296`
(4 GiB); out-of-range or non-numeric → `ConfigError`. It joins `Config` as
`exec_sandbox_max_bytes` and `.env.example` with its default and a one-line
comment.

**REQ-V11-QTA-02 (MUST)** `tools.sandbox_usage(path: Path) -> tuple[int, bool]`
returns the total size in bytes of regular files under `path` and a flag
saying the scan was cut short. It walks with `os.walk(path, followlinks=False)`
summing `os.lstat(...).st_size` for regular files only (symlinks contribute
their own size, never their target's), stops after
`SANDBOX_SCAN_MAX_ENTRIES = 200000` entries and returns `(total, True)` in that
case. `OSError` on an individual entry is skipped, not raised. **A missing
directory returns `(0, False)`**, so the pre-existing
`{"error": "sandbox directory is missing"}` check of the runner still fires
first and `test_missing_sandbox_is_reported_before_docker_runs`
(`tests/test_docker.py`) keeps passing unchanged.

The limit source is explicit: the runner signature becomes
`run_command_docker(argv, *, workdir, image, docker_ok, sandbox_max_bytes: int = 268435456, wrap_timeout: bool = False, empty_resolv: Path | None = None, timeout_s=EXEC_TIMEOUT_S)`.
The default equals the config default (REQ-V11-EC-05, so existing direct calls
in tests keep working); `bot.py` binds `cfg.exec_sandbox_max_bytes` into the
runner partial.

`run_command_docker` calls `sandbox_usage` **before** building the argv. Do
**not** add a directory-existence check of your own: the missing-sandbox error
belongs to `_run_process` and stays there (adding a second one would violate
REQ-V11-NG-06). The `(0, False)` guarantee above is what keeps the two from
colliding — a missing directory is never reported as a full one. When the usage
is at or above `sandbox_max_bytes`, or the scan was cut short, it returns —
without starting a container —

```json
{"error": "sandbox is full: <used> bytes of <limit> allowed; ask the operator to clear the sandbox directory"}
```

(the scan-cut-short case reports the same envelope and additionally logs
`WARNING sandbox scan hit the entry limit; treating the sandbox as full`).

**Accepted trade-off, MUST be documented in `README.md` beside the limit and
listed among the accepted risks of REQ-V11-REP-01:** refusing on a cut-short
scan means a model that creates more than `SANDBOX_SCAN_MAX_ENTRIES` files —
even empty ones — disables `exec` until the operator clears the sandbox. That
is a self-inflicted denial of service the model can trigger cheaply. The limit
is set high (200 000 entries) so ordinary work never approaches it, and
failing closed is preferred to walking an unbounded tree on every call; the
recovery is one `rm -rf` of the sandbox contents by the operator.

**REQ-V11-QTA-03 (MUST)** After a container finishes, `run_command_docker`
re-runs `sandbox_usage`. When the sandbox is now at or above the limit it logs
`WARNING sandbox over quota after exec: <used>/<limit> bytes` and the fact is
recorded in that invocation's audit line.

The mechanism, because the runner has no access to the audit record (it is
assembled by `tools._run_exec`, which wraps the runner):

1. `run_command_docker` sets `"sandbox_over_quota": True` on the dict it
   returns — and only when it is true, never as a `False` key.
2. `_run_exec` **pops** it out of the payload into the audit record
   (`record["sandbox_over_quota"] = payload.pop("sandbox_over_quota", False)`)
   **before** the payload is turned into the envelope the model sees.

Consequence, and the point of the pop: the envelope reaching the model is
byte-for-byte the v1 shape — an internal bookkeeping key must never leak into
the model's context or into the stored tool row. `T-V11-QTA-03` asserts the
success-envelope key set is exactly the v1 set, so a forgotten `pop` fails the
suite. The program's own result is reported honestly; the *next* exec is the
one that refuses.

**REQ-V11-QTA-04 (MUST)** The exec tool description in `tool_specs()` gains one
clause: the sandbox directory holds at most `EXEC_SANDBOX_MAX_BYTES` bytes and
commands that would exceed it are refused. `README.md` documents the variable
next to the other exec limits.

**REQ-V11-QTA-05 (MUST)** `bot._live_docker` (the gate-5 check) MUST pass
`sandbox_max_bytes=cfg.exec_sandbox_max_bytes` into `run_command_docker`.
Without it the live check runs against the built-in 256 MiB default, so an
operator who raised the limit and whose sandbox legitimately exceeds 256 MiB
would see gate 5 fail with "sandbox is full" while the running bot is
perfectly healthy — a gate contradicting the configuration it is meant to
verify.

### 5.5 Configuration hardening (findings V-6, V-7)

Two misconfigurations silently produce exactly the postures v1 claims to
prevent. Both are cheap to reject at load time, where the error is visible to
the operator instead of to an attacker.

**REQ-V11-CFV-01 (MUST)** `config._parse_domains` rejects an entry — with
`ConfigError` naming the offending entry — when any of these holds:

- it parses as an IP literal: `ipaddress.ip_address(entry.strip("[]"))`
  succeeds (stdlib `ipaddress`; covers IPv4 and bracketed or bare IPv6);
- it equals `localhost` or ends with `.localhost`;
- it contains no `.` (bare hostnames resolve through search domains and are
  therefore internal by construction);
- it contains `:` or `/` (a port or a path is not a domain).

The default (`wttr.in`) and ordinary domains keep working. The message MUST
say why, e.g.
`FETCH_ALLOWED_DOMAINS rejects "169.254.169.254": IP literals are not allowed (SSRF)`.
`README.md`'s existing warning about internal hosts stays, now backed by
enforcement.

**REQ-V11-CFV-02 (MUST)** `config._check_sandbox_placement` gains a first
check: the resolved `exec_workdir` MUST be a **strict descendant of
`PROJECT_ROOT`**, otherwise `ConfigError`
(`EXEC_WORKDIR must live inside the project directory; got "<path>"`). This
subsumes the delivered checks (which stay): not the project root itself, not
an ancestor of `DB_PATH`, `AUDIT_LOG_PATH` or `.env`. It closes the audit's
`EXEC_WORKDIR=/etc` case, where a system directory was accepted, mounted
read-write into the container and `chmod 0700`-ed. `PROJECT_ROOT` is read
dynamically at call time, as in REQ-V1-SEC-04, so test monkeypatching works.

### 5.6 Information disclosure (finding V-8)

A container with `--network none` still receives a generated
`/etc/resolv.conf` carrying the host's nameservers and search domains. The
audit read the operator's internal DNS server and internal search domains out
of the sandbox; that text flows into the model's context and, under OpenRouter,
to a third party. DNS is useless in a network-less container, so the file can
simply be empty.

**REQ-V11-INF-01 (MUST)** At startup (when `docker_ok`), `bot.py` ensures an
empty file exists next to the database — `<db_path>.parent / ".resolv-empty"`,
created with mode `0o644` if missing — and passes its resolved path to the
runner. `build_docker_argv` takes a defaulted keyword-only parameter
`empty_resolv: Path | None = None` and, when it is given, appends

```
"--mount", f"type=bind,source={empty_resolv},target=/etc/resolv.conf,readonly"
```

immediately after the sandbox mount. The file lives outside the sandbox mount —
the guarantee comes from the delivered `REQ-V1-CFG-03` placement check, which
already forbids `EXEC_WORKDIR` from containing `DB_PATH` — so the container
cannot rewrite it. When `empty_resolv` is `None` the argv is exactly the v1
argv plus the other v1.1 additions; no behaviour depends on the file existing.

Creation happens inside the REQ-V11-WIR-01 seam (never at import time, never
in a test path). Because this is the bot's **second** self-written file, two
housekeeping requirements come with it: `.gitignore` gains `.resolv-empty`
(amending REQ-V1-SEC-07) so a default-layout repository never shows it as
untracked, and `README.md`'s "files the bot writes" statement is updated from
one file to two (amending REQ-PATH-04).

**REQ-V11-INF-02 (MUST)** `/proc/self/mountinfo` exposes host overlay paths
inside the container. Masking it requires runtime features outside `docker
run`'s stock flags, so it is an **accepted residual risk**: `README.md` MUST
state that a program in the sandbox can learn host storage paths (not their
contents), and that this is knowingly not mitigated in this release.

### 5.7 Documented residual risk of value-based redaction (finding V-3)

**REQ-V11-DOC-05 (MUST)** `README.md` (and a short note in this spec's
section 12) MUST state plainly: redaction matches **literal values**, so any
transformation performed inside the sandbox — `base64`, `rot13`, chunking,
compression — defeats it, as the audit demonstrated with `base64`. Redaction
is therefore **defence in depth against accidental echo**, not a control
against an adversary who already controls what runs in the sandbox. The real
boundary for secrets is that they are not reachable from the container at all
(REQ-V1-DK-01). Do not attempt entropy-based detection (REQ-V11-NG-04).

---

## 6. Test-suite defects (mutation survivors)

Four mutations survived the delivered suite. Each is a place where the tests
assert something weaker than the requirement they are named after. Fixing them
is not optional polish: REQ-V1-VIS-02 is currently the only security-relevant
v1 requirement with **no** effective coverage.

**REQ-V11-TST-01 (MUST)** `T-V1-VIS-01`'s companion test
`test_status_text_is_truncated_and_redacted`
(`tests/test_v1_guardrails.py`) is vacuous: it places the sentinel and the
90-character filler in `argv[1]`, while `agent._first_argument` returns
`argv[0]` for `exec`, so both assertions run against the string
`"⚙️ exec: cat…"`. Deleting either `redact(...)` or `[:STATUS_MAX_CHARS]` from
`bot._status_line` leaves the suite green. Correct it so the value under test
actually reaches the status line: put the sentinel and the filler in
**`argv[0]`** (e.g. `exec_call(1, [SENTINEL + "-" + "y" * 90])`), keep both
assertions (`SENTINEL not in first_edit`, `len(first_edit) <= 64`), and add a
third asserting the redaction placeholder is present. A `fetch` variant with a
long sentinel-bearing URL MUST also be asserted, because `_first_argument`
takes a different branch for `fetch`.

**REQ-V11-TST-02 (MUST)** Redaction at the Telegram boundary (`bot._send`,
REQ-V1-SEC-02) has no test that fails when `redact` is removed: the existing
one is satisfied by the earlier redaction inside `finish()`. Add a test in
which a sentinel-bearing text reaches `_send` **without** passing through
`finish()` and **without** passing through a storage guard.

The vector, chosen because the obvious candidates do not work — `/status`
renders only bot-internal values with nowhere for a sentinel to enter, and a
`/summary` read from the database would already be redacted by REQ-V11-RED-01:
monkeypatch `agent.summarize_conversation` to return a JSON summary whose
`goal` field contains the sentinel. `bot._handle_summary` renders and sends
**the returned string**, so the only redaction standing between the sentinel
and Telegram is the one inside `_send`. Assert the sentinel never appears in
what `RecordingTelegram` received, and confirm by mutation that deleting
`redact` in `_send` fails this test.

**REQ-V11-TST-03 (MUST)** `T-V1-FT-02` proves the body is truncated but not
that reading **stops**: removing the cap break from `fetch_url` keeps the suite
green, so the "never buffered whole" guarantee is unverified. Add a test whose
`MockTransport` returns a streaming response backed by a counting iterator of
fixed-size chunks, and assert the iterator produced no more than
`ceil((max_bytes + max_secret_length() + 1) / chunk_size) + 1` chunks — i.e.
reading stopped shortly past the cap rather than consuming the whole body.
Make the body large enough (e.g. 40 chunks of 8192 bytes) that a full read is
unmistakable.

**REQ-V11-TST-04 (MUST)** `T-V1-DK-05` monkeypatches `DOCKER_STARTUP_GRACE_S`
to `0.0`, so removing `+ DOCKER_STARTUP_GRACE_S` from `run_command_docker`
survives. Add an assertion — in `tests/test_docker.py` or the new file — that
with the real constant, the `timeout_s` handed to a monkeypatched
`_run_process` equals `EXEC_TIMEOUT_S + DOCKER_STARTUP_GRACE_S`.

---

## 7. Documentation and reporting corrections

These change no behaviour. They exist because a report that overstates what
was verified is worse than no report.

**REQ-V11-DOC-01 (MUST)** The v1 code review's prompt was never logged, though
the project standard requires one file per prompt and v0's equivalent
(`docs/prompts/02-code-review.md`) exists. Create
`docs/prompts/04-code-review-v1.md` following the shape of `02`: the prompt
text actually used to invoke the `code-reviewer` subagent for the v1 run, with
a header noting it is reconstructed after the fact **and clearly labelled as
such** — do not present a reconstruction as a verbatim record.

**REQ-V11-DOC-02 (MUST)** Two undeclared deviations are added to the
"Deviations from the spec" section of `docs/reports/report-v1.md`:

1. REQ-V1-SEC-03 asks for per-element redaction of argv, URL and the stderr
   excerpt; the implementation redacts the serialised JSON record as a whole.
   Equivalent except for a secret that contains JSON-escapable characters.
2. REQ-V1-VIS-02 says the status message is edited before each **subsequent**
   tool execution; the implementation edits before the first one too (which
   is better, and what the tests pin).

The matching sentence in `docs/spec/spec-v1.md` REQ-V1-VIS-02 is corrected to
"before each execution, including the first", tagged `[doc-fix v1.1]`.

**REQ-V11-DOC-03 (MUST)** The report's Review section already discusses the
serialised-record redaction limitation; keep it and cross-reference the new
Deviations entry so the two agree. Extend the note to say that the same
limitation now applies in two more places introduced by this patch — the
`_redact_tool_calls` helper and the storage guard over the serialised
`tool_calls` payload both redact JSON text, so a secret containing characters
that JSON escapes (a backslash, a quote, a control character) survives in its
escaped form. Every credential this project handles is escape-free, which is
why the simple form is accepted.

**REQ-V11-DOC-04 (MUST)** `fetch_url` returns `URL_NOT_HTTPS` for a URL that
fails to parse at all, which misdescribes the failure. Add a distinct constant
`URL_MALFORMED = "url could not be parsed"` and return it from the two
`except (httpx.InvalidURL, ValueError)` branches that currently return
`URL_NOT_HTTPS`. The scheme check itself keeps `URL_NOT_HTTPS`.

**The new constant MUST also be added to the prefix tuple of
`tools._is_pre_network`**, next to `URL_REQUIRED`, `URL_NOT_HTTPS`,
`URL_NO_HOST` and `URL_DOMAIN_PREFIX`. That predicate decides whether the audit
line says `outcome: "refused"` (validation stopped the request before anything
left the process) or `outcome: "error"` (the request left and failed). Adding
the constant without adding it there would silently reclassify every malformed
URL as a network error — a regression of REQ-V1-AUD-02, and exactly the kind of
drift the helper's own comment warns about. `T-V11-URL-01` (section 9.2) pins
both halves; `T-V1-FT-01` is updated per section 9.1.

**REQ-V11-DOC-06 (MUST)** Reconcile the repair-cycle count.
`docs/prompts/03-go-spec-v1.md` says "0/5 repair cycles used";
`docs/reports/report-v1.md` says "Fix cycles used: 1/5". Both are true of
different things. Make both read: **0/5 gate-repair cycles on the first full
gate run; 1 additional fix round applied after the clean-context code review**
— identical wording in both files.

**REQ-V11-DOC-07 (MUST)** Correct the container-environment claim. The audit
found the container's real environment is seven variables, not three: `PATH`,
`LANG`, `HOME` from `--env`, plus `HOSTNAME`, `GPG_KEY`, `PYTHON_VERSION` and
`PYTHON_SHA256` that Docker merges in from the image. None is a secret and
nothing changes behaviourally — but two places state it wrongly and a third
does not state it at all. Precisely:

1. `tests/test_docker.py`, the comment above the `--env` assertion —
   "the container environment is fixed, and it is these three only" — is
   corrected to say the assertion covers the `--env` **flags the bot passes**,
   not the container's resulting environment. (The assertion itself is already
   an argv assertion and needs no change; only the comment lies.)
2. `docs/spec/spec-v1.md`'s description of `T-V1-DK-02` ("`--env` values are
   exactly the three allowed ones") gains the same clarification, tagged
   `[doc-fix v1.1]`.
3. `README.md` has **no** statement about the container environment at all —
   add one: the bot sets exactly three variables, the image contributes its
   own public build-time variables, and no host environment (including every
   credential) is ever forwarded.

The residual-risk paragraph of REQ-V11-DOC-05 (section 5.7) also lands in
`README.md`.

---

## 8. Implementation order

**REQ-V11-ORD-01 (MUST)** Follow this order; each step ends with the offline
gates green (1–4) before the next begins.

1. Tests first: write section 9.2's new tests and apply section 9.1's
   corrections. Run the mutation check of REQ-V11-EC-02 for the four
   corrected tests.
2. `config.py`: `max_secret_length`, `strip_secret_fragment`,
   `SECRET_FRAGMENT_MIN`, `EXEC_SANDBOX_MAX_BYTES`, `_parse_domains`
   validation, `_check_sandbox_placement` descendant rule.
3. `storage.py`: redaction guards on every write path.
4. `agent.py`: `_redact_tool_calls` and the redacted assistant turn.
5. `tools.py`: `_Capture` headroom and the redact-then-cut order in
   `_run_process` and `fetch_url`; `URL_MALFORMED`; `sandbox_usage`; the
   quota checks; `build_docker_argv` additions (`--label`, resolv mount,
   `wrap_timeout`); `image_has_timeout`; tool-description text.
6. `bot.py`: the REQ-V11-WIR-01 seam first (reap, image probe and
   empty-resolv file all live inside it), then the wiring of the new runner
   parameters into the partial. Verify at this point that
   `uv run --locked pytest` still runs **without** a Docker daemon reachable —
   if any test shells out to `docker`, the seam is wired wrongly.
7. `.env.example`, `README.md`, then the documentation corrections of
   section 7.
8. Gate 5, then Appendix B, then review, then report.

---

## 9. Tests

### 9.1 Amendments to existing tests (exhaustive — nothing else may change)

| Test | Change |
|---|---|
| `test_status_text_is_truncated_and_redacted` (T-V1-VIS-01 companion) | sentinel and filler move to `argv[0]`; add the placeholder assertion and the `fetch` variant (REQ-V11-TST-01) |
| T-V1-DK-01 | expected argv gains `--label tgexec=1` after the `--name` pair, the read-only `/etc/resolv.conf` mount after the sandbox mount, and — when `wrap_timeout=True` — the `timeout --kill-after=5 30` prefix before `*argv`. Still asserted flag-for-flag, order included |
| T-V1-DK-02 | assert the **`--env` flags** are exactly the three the bot sets (wording per REQ-V11-DOC-07); assert exactly two bind mounts (sandbox rw, resolv ro) and no others; assert the label is present |
| T-V1-DK-05 | add the outer-timeout assertion of REQ-V11-TST-04 |
| T-V1-FT-01 | if it pins `URL_NOT_HTTPS` for an unparsable URL, retarget that case to `URL_MALFORMED` (REQ-V11-DOC-04); the `http://` case keeps `URL_NOT_HTTPS` |
| T-V1-FT-02 | extend with the streaming-stop assertion (REQ-V11-TST-03) |
| T-V1-CFG-01 | add the `EXEC_WORKDIR` outside-project-root case → `ConfigError` (REQ-V11-CFV-02) |
| `test_main_binds_the_container_runner_not_the_host_runner` (`tests/test_v1_guardrails.py`) | **required, or the run cannot pass its own gates.** The test asserts `runner.keywords` by exact equality, so the three new bound parameters must be added to the expectation: `sandbox_max_bytes` (`cfg.exec_sandbox_max_bytes`), `wrap_timeout` and `empty_resolv` (both from the REQ-V11-WIR-01 seam). `runner.func is tools.run_command_docker` and `runner.func is not tools._run_process` MUST still hold — bind through `functools.partial`, never a lambda or a wrapper function. The test additionally monkeypatches `bot._startup_docker_wiring` to return a fixed `(True, None)`, so no `docker` command runs during `pytest` |
| `test_main_disables_exec_when_the_backend_is_down` (`tests/test_v1_guardrails.py`) | same seam stub, asserting the seam is **not** called (or returns `(False, None)`) when `docker_ok` is false, and that no docker subprocess is attempted |
| `tests/test_docker.py` `--env` comment | comment-only correction per REQ-V11-DOC-07 item 1; no assertion changes |
| T-EX-01…T-EX-13 | unchanged assertions; they exercise `_run_process` with `headroom=0` behaviour identical to v1 |
| `test_missing_sandbox_is_reported_before_docker_runs` | unchanged, and MUST stay green: `sandbox_usage` returning `(0, False)` for a missing directory keeps the missing-sandbox error first (REQ-V11-QTA-02) |

Nothing else. If another test fails, the production change is wrong.

### 9.2 New tests (`tests/test_v11_patch.py`)

| ID | Asserts |
|---|---|
| T-V11-RED-01 | a scripted `FakeLLM` tool round whose `content` **and** whose tool-call arguments contain the sentinel: the stored assistant row contains neither (placeholder instead), and the payload of the following round contains neither. Deleting the `agent.py` redaction makes this fail |
| T-V11-RED-02 | each of the four storage writers of REQ-V11-RED-01, called directly with sentinel-bearing text, stores it redacted: `add_user_message`, `add_assistant_message`, `add_tool_turn` (content, tool-calls payload and each result) and `add_summary`. Parametrise over the four so removing any single guard fails |
| T-V11-RED-03 | `_redact_tool_calls` preserves ids, names and structure byte-for-byte while redacting only `function.arguments` |
| T-V11-TRN-01 | `max_secret_length` and `strip_secret_fragment`: no registered secret → `0` and identity; a text ending in a ≥8-character prefix of a secret loses exactly that tail; a 7-character tail is kept; a text ending in a complete secret is handled by `redact` before this helper ever sees it |
| T-V11-TRN-02 | a stub process writing `"A" * (4096 - len(SENTINEL) // 2) + SENTINEL + "B" * 100` to stdout: the envelope contains neither the sentinel nor any ≥8-character prefix of it, `truncated is True`, and the stdout field is at most 4096 bytes |
| T-V11-TRN-03 | the same for `fetch_url` with a body whose sentinel straddles the 65536-byte cap |
| T-V11-TRN-04 | with no secrets registered, `_run_process` output is byte-for-byte identical to the v1 behaviour for a truncated stream (headroom 0 changes nothing) |
| T-V11-ORP-01 | (REQ-V11-ORP-01/03) `build_docker_argv(..., wrap_timeout=True)` produces the `timeout --kill-after=5 30` prefix; with `wrap_timeout=False` it does not; `--label tgexec=1` is present in both |
| T-V11-ORP-02 | (REQ-V11-ORP-02) with the stub `docker` on PATH, the seam issues `ps -aq --filter label=tgexec=1` and then `rm -f` with exactly the returned ids; an empty listing issues no `rm`; a failing reap logs a warning and startup continues. **The existing stub (`tests/test_docker.py`) knows only the `version` and `kill` verbs — extend it with `ps` (prints ids from `mode.json`) and `rm` (records and exits 0), and reuse the existing `docker_stub` fixture rather than writing a second stub** |
| T-V11-ORP-03 | (REQ-V11-ORP-04) `image_has_timeout` returns True on stub rc 0, False on rc 1, and False — without raising — when the stub is absent from `PATH` entirely and when it hangs past the probe timeout (**monkeypatch `tools.IMAGE_PROBE_TIMEOUT_S` to ~0.5 s for that sub-case; the real 15 s would stall the suite**); the argv carries `--pull never` and the hardening flags; a False result yields `wrap_timeout=False` in the runner wiring and logs the degradation warning |
| T-V11-ORP-04 | (REQ-V11-ORP-03) budget-exhaustion envelopes agree regardless of the killer: with a stub docker exiting **124** and `wrap_timeout=True`, the envelope has `timed_out is True`; the same stub with `wrap_timeout=False` yields `timed_out is False` and the plain exit code; the outer-kill path of T-V1-DK-05 still yields `timed_out is True` |
| T-V11-WIR-01 | (REQ-V11-WIR-01) `_startup_docker_wiring(cfg, docker_ok=False)` returns `(False, None)` and runs **no** subprocess and creates **no** file (`subprocess.run` monkeypatched to fail the test); with `docker_ok=True` and the stub docker it performs reap, probe and file creation exactly once each |
| T-V11-QTA-01 | `sandbox_usage` sums regular files, ignores symlink targets, survives an unreadable entry, and reports the cut-short flag past the entry limit |
| T-V11-QTA-02 | a sandbox at or above the limit → the fixed "sandbox is full" envelope, and **no** subprocess was spawned (`_run_process` monkeypatched to fail the test); below the limit the run proceeds |
| T-V11-QTA-03 | crossing the limit during the run leaves the program's result untouched, logs the warning and sets `sandbox_over_quota` in the audit record; **and the success envelope the model receives has exactly the v1 key set** — the internal key was popped, not leaked (REQ-V11-QTA-03) |
| T-V11-QTA-04 | `EXEC_SANDBOX_MAX_BYTES` parsing: default, below minimum, above maximum, non-numeric |
| T-V11-CFV-01 | `_parse_domains` rejects `169.254.169.254`, `127.0.0.1`, `[::1]`, `localhost`, `sub.localhost`, `internalhost`, `example.com:8080`, `example.com/path`, each with the offending entry named; accepts `wttr.in`, `sub.wttr.in`, `example.co.uk` |
| T-V11-CFV-02 | `EXEC_WORKDIR` outside the project root (`/etc`, `/tmp/x`, a sibling of the project) → `ConfigError`; the default `./sandbox` passes; the v1 cases (project root itself, ancestor of db/audit/.env) still raise |
| T-V11-INF-01 | the empty-resolv file is created `0o644` when missing and reused when present; `build_docker_argv(empty_resolv=…)` mounts it read-only at `/etc/resolv.conf` right after the sandbox mount; `empty_resolv=None` omits the mount entirely |
| T-V11-RED-04 | (REQ-V11-TST-02) a `/summary` reply whose text comes from a monkeypatched `agent.summarize_conversation` carrying the sentinel is redacted before `send_message` receives it — the only guard on that path is the one inside `_send` |
| T-V11-URL-01 | (REQ-V11-DOC-04) an unparsable URL yields `{"error": URL_MALFORMED}` **and** audits as `outcome: "refused"`; an `http://` URL still yields `URL_NOT_HTTPS` and also audits as `refused` |

Offline discipline is unchanged and MUST hold: `tests/conftest.py`'s
no-network guard stays in force, no new test touches the network, and no new
test requires a real Docker daemon — the docker layer is exercised through the
argv builder and the stub-executable pattern already established in
`tests/test_docker.py`.

---

## 10. Gates

**REQ-V11-GATE-01 (MUST)** Run verbatim, in order, from the repository root:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
```

Gates 1–4 are unconditional and offline. Gate 5 requires the section-3
preconditions and MUST print OK for all six checks. The test count MUST be
**greater than 203** (nothing was deleted, tests were added); state the exact
number in the report.

---

## 11. Acceptance, review and report

**REQ-V11-ACC-01 (MUST)** After the gates are green, execute Appendix B of
this spec against the live bot, plus spec-v1's Appendix B scenarios B1, B3,
B4 and B10 as a regression check that the patch did not weaken v1's posture.
Record pass/fail per scenario in the report.

**What gate 5 does and does not prove, to be stated in the report:** the live
docker check runs a real container, but it calls the runner directly and
therefore **without** `wrap_timeout` and **without** `empty_resolv`. It proves
the daemon, the image and the base argv work; it does **not** exercise the
in-container `timeout` wrapper or the neutralised `/etc/resolv.conf`. Those two
are covered live only by scenarios C3 and C6 respectively. The report MUST NOT
present a green gate 5 as evidence for them. `ALLOWED_TG_IDS` now holds a real
id, so no scenario should be recorded `OPERATOR-PENDING`; if one still must
be, say why.

**REQ-V11-REV-01 (MUST)** Code review by the `code-reviewer` subagent in a
clean context, after the gates pass and before the final report. Findings are
fixed, or explicitly waived with a reason in the report. **Log the review
prompt** in `docs/prompts/06-code-review-v1.1.md` (numbering per section 4) —
the omission this patch fixes for v1 must not repeat for v1.1.

**REQ-V11-REP-01 (MUST)** Report per the project standard:
`docs/reports/report-v1.1.md` (gates table with all five commands and the exact
test count, Appendix-B results, the mutation-check evidence required by
REQ-V11-EC-02, deviations, fix cycles), `docs/llm-usage.md` rows appended,
every prompt logged in `docs/prompts/`, then `docs/reports/tg-post-v1.1.md`
(Russian, per `AGENTS.md`). The report MUST state plainly which findings this
patch closes and which remain accepted risks: REQ-V11-INF-02 (host storage
paths visible via `/proc/self/mountinfo`), REQ-V11-DOC-05 (redaction is
defeated by any in-sandbox transformation), the sandbox-scan self-DoS
trade-off of REQ-V11-QTA-02, the 124/125/126/127 exit-code ambiguities, and
the docker-group cost already stated in v1. The report MUST also note the
consequence recorded in REQ-V11-ORP-03: with the in-container wrapper active,
the outer `docker kill` path is now nearly unreachable in production while
remaining tested.

---

## 12. Non-goals for v1.1

Implementing any of these is a defect.

| ID | NON-GOAL |
|---|---|
| REQ-V11-NG-01 | Everything the next assignment owns: token/cost accounting middleware, usage tables, dashboards, per-call metrics, cost reports, token optimisation. This release must stay a clean "before" baseline. |
| REQ-V11-NG-02 | Rootless Docker, micro-VMs, gVisor, seccomp/AppArmor profiles, image building, masked-path runtimes. The docker-group cost stays documented, not solved. |
| REQ-V11-NG-03 | Filesystem quotas at the kernel level (XFS project quotas, loop devices, per-mount `--storage-opt`). The scan-and-refuse of REQ-V11-QTA-02 is the whole mechanism. |
| REQ-V11-NG-04 | Entropy-based or heuristic secret detection; redaction stays exact-value matching (REQ-V11-DOC-05). |
| REQ-V11-NG-05 | `asyncio`, threads beyond the existing reader threads, parallel update processing, multi-instance support. |
| REQ-V11-NG-06 | New Python dependencies; new modules; refactoring not required by a requirement above. |
| REQ-V11-NG-07 | New features of any kind — commands, tools, providers, storage shapes. |

---

## Appendix A — finding traceability

| Finding | Source | Severity | Requirements |
|---|---|---|---|
| V-1 model-authored content and tool-call arguments bypass redaction into SQLite and the provider payload | adversarial probe (confirmed independently in `agent.py`) | MEDIUM | REQ-V11-RED-01, REQ-V11-RED-02 |
| V-2 stream truncation splits a secret and leaks a fragment | adversarial probe | MEDIUM | REQ-V11-TRN-01, REQ-V11-TRN-02 |
| V-3 in-container transformation (`base64`) defeats value-based redaction | adversarial probe | LOW (inherent) | REQ-V11-DOC-05 (documented, not fixed) |
| V-4 unbounded sandbox bind mount → host disk exhaustion | adversarial probe | MEDIUM | REQ-V11-QTA-01…04 |
| V-5 container survives the bot's death | adversarial probe | MEDIUM | REQ-V11-ORP-01…04 |
| V-6 `FETCH_ALLOWED_DOMAINS` accepts IP literals and `localhost` (SSRF by misconfiguration) | adversarial probe | LOW | REQ-V11-CFV-01 |
| V-7 `EXEC_WORKDIR=/etc` accepted, mounted rw and chmod-ed | adversarial probe | LOW | REQ-V11-CFV-02 |
| V-8 host DNS config and host storage paths readable from the sandbox | adversarial probe | LOW | REQ-V11-INF-01 (resolv.conf), REQ-V11-INF-02 (mountinfo: accepted) |
| env-allowlist claim ("exactly three") is inaccurate — docker merges image `ENV` | adversarial probe | doc | REQ-V11-DOC-07 |
| R-1 status-line test is vacuous; both `_status_line` mutations survive | compliance review (mutation) | 🟡 | REQ-V11-TST-01 |
| R-2 Telegram-boundary redaction untested; mutation survives | compliance review (mutation) | 🟡 | REQ-V11-TST-02 |
| R-3 fetch "never buffered whole" untested; mutation survives | compliance review (mutation) | 🟡 | REQ-V11-TST-03 |
| R-4 repair-cycle count contradicts between prompt log and report | compliance review | 🟡 | REQ-V11-DOC-06 |
| R-5 v1 code-review prompt not logged | compliance review | 🟡 | REQ-V11-DOC-01 |
| R-6 startup-grace term uncovered (grace monkeypatched to 0) | compliance review (mutation) | 🟢 | REQ-V11-TST-04 |
| R-7 serialised-record audit redaction not declared as a deviation | compliance review | 🟢 | REQ-V11-DOC-02, REQ-V11-DOC-03 |
| R-8 status message edited before the first tool too, undeclared | compliance review | 🟢 | REQ-V11-DOC-02 |
| R-9 unparsable URL reported as "must use https" | compliance review | 🟢 | REQ-V11-DOC-04 |

Findings deliberately **not** acted on: R-10 (`T-V1-ST-01`'s near-vacuous
project-root assertion — the real check lives in `_selftest_failure`, so the
behaviour is covered), R-11 (`T-V1-TB-04`'s loose `0 < len <= 6` bound — the
adjacent byte-exact assertion carries the proof), R-12 (`docker_image_present`
missing from the module-responsibility table — cosmetic). Each is recorded
here so a later reader knows they were seen and judged, not missed.

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# SAFETY RULE FOR EVERY SCENARIO BELOW: never use a live credential as the
# test secret. C1 and C2 send their secret to Telegram and to the LLM
# provider, so a real token would be disclosed to third parties by the very
# act of testing.
#
# There is no "extra secret" variable: load_config registers exactly two
# values (TELEGRAM_BOT_TOKEN and, per REQ-V1-SEC-05, OPENROUTER_API_KEY).
# So the throwaway run for C1 and C2 is configured like this:
#
#   OPENROUTER_API_KEY=SYNTHETIC-V11-CANARY-<random hex>   # >= MIN_SECRET_LENGTH
#   LLM_PROVIDER=lmstudio
#   LLM_FAILOVER=off
#
# REQ-V1-SEC-05 registers the key whenever it is non-empty, so the synthetic
# value becomes a redaction target; with the provider pinned to LM Studio and
# failover off, the fake key is never validated and never leaves the process.
# Restore the real .env afterwards.

Scenario: C1 — a secret quoted by the model never lands in the database
  Given a synthetic throwaway secret is registered for this run and no live
        credential is used anywhere in this scenario
  And the operator sends a message containing that synthetic value and asks
      the bot to repeat it while also running a tool
  When the model echoes the value in the same round as its tool call
  Then the assistant row stored for that round contains the redaction
       placeholder and not the synthetic value
  And the request payload of the following round contains no synthetic value

Scenario: C2 — a secret straddling the output cap leaks no fragment
  Given the same synthetic throwaway secret, and a file in the sandbox
        containing filler followed by that value positioned across the
        4096-byte boundary
  When the operator asks the bot to cat that file
  Then the tool envelope contains neither the synthetic value nor any
       eight-character prefix of it
  And the envelope still reports truncated true

Scenario: C3 — no container outlives the bot
  Given the bot runs a long exec command
  When the bot process group is killed and the bot is started again
  Then the startup log reports the orphaned container was reaped
  And docker ps shows no container labelled tgexec

Scenario: C4 — the sandbox cannot fill the disk
  Given EXEC_SANDBOX_MAX_BYTES is temporarily set to 8 MiB in a throwaway run
  When the operator asks the bot to write a 64 MiB file into the sandbox
  Then the first exec succeeds or fails on its own terms
  And the next exec is refused with the "sandbox is full" envelope without
      starting a container
  And the bot keeps answering ordinary messages

Scenario: C5 — an SSRF-shaped allowlist is refused at startup
  Given FETCH_ALLOWED_DOMAINS is set to 169.254.169.254 in a throwaway run
  When the bot starts
  Then it exits with a configuration error naming that entry
  And the same happens for localhost and for a dotless hostname

Scenario: C6 — the sandbox learns nothing about host DNS
  Given the bot runs with Docker available
  When the operator asks the bot to cat /etc/resolv.conf
  Then the file is empty
  And no host nameserver or search domain appears in the reply

Scenario: C7 — v1 posture intact
  When spec-v1 scenarios B1, B3, B4 and B10 are re-run
  Then each still passes exactly as it did for v1
```
