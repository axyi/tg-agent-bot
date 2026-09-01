# Implementation report — spec-v1.1

Commits: `c9f7912`, `c1f27c3`, `782a378` (delivered spec-v1 baseline this patch
starts from) on `main`
Executor model: **claude-sonnet-5** (Claude Code harness)
Prompt: `go docs/spec/spec-v1.1.md` — logged as `docs/prompts/05-go-spec-v1.1.md`

Files created: `tests/test_v11_patch.py`, `docs/prompts/04-code-review-v1.md`,
`docs/prompts/05-go-spec-v1.1.md`, `docs/prompts/06-code-review-v1.1.md`,
`docs/reports/report-v1.1.md`, `docs/reports/tg-post-v1.1.md`

Files changed: `config.py`, `storage.py`, `tools.py`, `agent.py`, `bot.py`,
`.env.example`, `.gitignore`, `README.md`, `docs/spec/spec-v1.md`
(documentation notes only), `docs/prompts/03-go-spec-v1.md`,
`docs/reports/report-v1.md`, `tests/test_docker.py`,
`tests/test_v1_guardrails.py`, `docs/llm-usage.md`

## Gates

| # | Gate command | Exit | Notes |
|---|---|---|---|
| 1 | `uv sync --locked` | 0 | 13 packages, lockfile unchanged |
| 2 | `uv run --locked ruff check .` | 0 | All checks passed |
| 3 | `uv run --locked pytest` | 0 | **251 passed** (203 in v1; 48 new in `tests/test_v11_patch.py`) |
| 4 | `uv run --locked python bot.py --selftest` | 0 | `selftest: OK` |
| 5 | `uv run --locked python bot.py --selftest-live` | 0 | 6/6 OK — config, db, docker (29.0.2), telegram, lmstudio, openrouter |

**What gate 5 does and does not prove**, per REQ-V11-ACC-01: it calls
`run_command_docker` directly with no `wrap_timeout` and no `empty_resolv`, so
it proves the daemon, the image and the base argv work. It does **not**
exercise the in-container `timeout` wrapper or the neutralised
`/etc/resolv.conf` — those are covered live only by scenarios C3 and C6 below.
The suite was additionally re-run with `docker` removed from `PATH`
(251 passed, unchanged) to confirm no test — old or new — shells out to a
real daemon; the REQ-V11-WIR-01 seam is the only startup path that touches
`docker`, and it is fully stubbed in the two `main()` tests.

Test-first evidence: after writing section 9.2's new test file
(`tests/test_v11_patch.py`) and applying the section-9.1 amendments, the
first `uv run --locked pytest` failed 55 tests — `TypeError` on the new
`run_command_docker` keyword arguments, `AttributeError` on not-yet-existing
`config.max_secret_length`/`tools.sandbox_usage`/`tools.image_has_timeout`/
`bot._startup_docker_wiring`/`bot._ensure_empty_resolv`, and `AssertionError`
on the streaming-stop and argv-shape assertions. Implementation then proceeded
module by module in the order of section 8, each step re-running the affected
subset of tests before moving on; the offline gates (1–4) were green at the
end of every step.

**Mutation-check evidence for the four corrected tests (REQ-V11-EC-02).** For
each, the production line the audit's mutation targeted was temporarily
removed, the corrected test was confirmed red, the line was restored, and the
test was confirmed green again:

| Test | Line mutated | Red (mutated) | Green (restored) |
|---|---|---|---|
| `test_status_text_is_truncated_and_redacted` (T-V1-VIS-01 companion) | `redact(...)` removed from `bot._status_line` | fetch-variant assertion `"***REDACTED***" in first_edit2` failed | pass |
| `test_t_v11_red_04_summary_reply_redacted_only_by_send` | `redact(part)` → `part` in `bot._send` | `assert all(SENTINEL not in text ...)` failed | pass |
| `test_t_v1_ft_02_truncation_and_non_200` (streaming-stop extension) | the `break` in `fetch_url`'s read loop deleted | `len(produced) <= max_chunks` failed (40 ≤ 10 is false) | pass |
| `test_t_v1_dk_05_timeout_kills_the_container` (outer-timeout extension) | `+ DOCKER_STARTUP_GRACE_S` removed from `run_command_docker` | `seen["timeout_s"] == EXEC_TIMEOUT_S + real_grace` failed (30.0 == 40.0) | pass |

All four corrected tests previously passed against the broken production
line they now guard (that is exactly what made them vacuous); after the
correction, each one fails against the mutation and passes against the
delivered code.

## Preconditions (section 3)

1. Repository on `main`, clean tree, HEAD at the delivered v1 state
   (`docs/spec/spec-v1.md` and `docs/reports/report-v1.md` both present); all
   five v1 gates green before any edit.
2. `.env` present; all eight required keys verified **by key name only**
   (`grep -oE '^[A-Z_]+='`); no secret value was displayed, logged or copied.
   `ALLOWED_TG_IDS` holds the operator's real Telegram id.
3. Docker 29.0.2 reachable without `sudo`; `python:3.13-slim` present locally
   (`docker image inspect`).
4. The image provides GNU `timeout` 9.7 (Debian package) — the hardened probe
   of REQ-V11-ORP-04 succeeded, so `wrap_timeout` is armed in the live
   environment; no degradation to record.

## Appendix B — acceptance scenarios

Executed as a scripted driver against the live environment (real Docker,
real storage/redaction code, a scripted LLM only where the scenario needs the
model's *compliance* — echoing a synthetic secret on demand is not something
a real model can be reliably coaxed into in a single throwaway run). No
Telegram message was sent for any scenario: none of them need one, and the
Telegram-boundary redaction is already proven by `T-V11-RED-04` plus its
mutation check above. `ALLOWED_TG_IDS` holds a real id, so nothing here is
`OPERATOR-PENDING`.

The synthetic secret (`SYNTHETIC-V11-CANARY-<16 hex chars>`) was generated
fresh, registered only via `OPENROUTER_API_KEY` with `LLM_PROVIDER=lmstudio`
and `LLM_FAILOVER=off` (so it was never validated against a real provider and
never left the process), and discarded with its scratch directory
(`_appendix_b_scratch/`, deleted at the end of the run, git-status confirmed
clean). `EXEC_WORKDIR`, `DB_PATH` and `AUDIT_LOG_PATH` all pointed at that
scratch tree — the operator's real database, sandbox and audit log were never
touched.

| # | Scenario | Result | Evidence |
|---|---|---|---|
| C1 | a secret quoted by the model never lands in the database | **PASS** | scripted tool-round (content + tool-call arguments both carry the sentinel) driven through `agent.run_agent` with the real container runner and real `storage`; the stored assistant row and the following round's payload both carry `***REDACTED***`, neither carries the sentinel — everything except the model's choice to echo is live |
| C2 | a secret straddling the output cap leaks no fragment | **PASS** | a file with the sentinel positioned across the 4096-byte boundary, `cat`-ed through the real container runner; the envelope carries neither the sentinel nor any ≥8-char prefix of it, `truncated: true`, exit 0 |
| C3 | no container outlives the bot | **PASS** | a real labelled container was started by a wrapper process mimicking the bot's own process-group isolation, the wrapper was `kill -9`-ed; `docker ps` showed the container still running; `bot._reap_orphaned_containers()` removed it; `docker ps` was then clean |
| C4 | the sandbox cannot fill the disk | **PASS** | `EXEC_SANDBOX_MAX_BYTES=8 MiB`; a `dd` of 64 MiB succeeded on its own terms and set `sandbox_over_quota: true`; the next real exec in the same sandbox returned the fixed "sandbox is full" envelope without starting a container; a third exec in a fresh sandbox still succeeded — the bot keeps answering |
| C5 | an SSRF-shaped allowlist is refused at startup | **PASS** | `python bot.py` with `FETCH_ALLOWED_DOMAINS` set to `169.254.169.254`, `localhost` and `internalhost` each exited 2, each with the offending entry named on stderr |
| C6 | the sandbox learns nothing about host DNS | **PASS** | `cat /etc/resolv.conf` through the real container runner with `empty_resolv` explicitly passed (gate 5 does **not** wire this — see above) returned an empty file, exit 0 |
| C7 | v1 posture intact | **PASS** | see B1/B3/B4/B10 below |

Spec-v1 regression (REQ-V11-ACC-01):

| # | Scenario | Result | Evidence |
|---|---|---|---|
| B1 | secret exfiltration yields nothing | **PASS** | `cat ../.env`, `cat /work/../.env` and `cat /app/.env` all exited non-zero inside the real container; `ls -la /` showed no project tree (`bot.py` absent) |
| B3 | Docker down degrades, bot lives | **PASS (scoped, as in v1)** | `docker_ok=False` returns the fixed unavailable-backend envelope without spawning anything; stopping the real daemon needs root, so this probes the same `docker_ok=False` path the startup wiring sets |
| B4 | timeout kills the container | **PASS** | a 120 s sleep with a 5 s budget returned `timed_out: true`; `docker ps` showed no leftover `tgexec-*` container afterwards |
| B10 | fetch allowlist | **PASS** | `https://wttr.in/Berlin?format=3` → HTTP 200; `https://example.com/x` → `domain not allowed: example.com` |

## Deviations from the spec

**Corrected retroactively per REQ-V12-DOC-02 item 4** (spec-v1.2's compliance
review named this section's original "None" as false — both facts below
were visible in adjacent prose, but this is the section a reader checks):

1. The whole run was delivered as **one commit** although it consumed two
   prompts (`05` go, `06` review).
2. Appendix B was executed by a **scripted driver with a scripted model**,
   not by Telegram messages from the operator's account, as its scenarios
   describe.

Beyond those two process deviations, the technical scope was followed
exactly: section 9.1's amendment list was applied exactly as written; no test
outside that list was modified, and no test was deleted (`git diff --stat`
shows only the two new/amended test files touched, plus the new
`tests/test_v11_patch.py`).

One nuance the review surfaced and worth recording: section 9.1's row for
`T-V1-FT-01` is conditional ("*if* it pins `URL_NOT_HTTPS` for an unparsable
URL, retarget..."). The delivered v1 test never had such a case, so the
condition was false and the test needed no edit — confirmed against
`c1f27c3`. Coverage for REQ-V11-DOC-04 is provided entirely by the new
`T-V11-URL-01`. Not a deviation; recorded so a future reader doesn't wonder
why that row produced no diff.

## Accepted risks and residual limitations (REQ-V11-REP-01)

Findings this patch closes (see Appendix A of the spec for the full
traceability table): V-1 (RED-01/02), V-2 (TRN-01/02), V-4 (QTA-01..04),
V-5 (ORP-01..04, WIR-01), V-6 (CFV-01), V-7 (CFV-02), the env-allowlist
documentation defect (DOC-07), and all nine R-1..R-9 test/documentation
defects (TST-01..04, DOC-01..04, DOC-06).

Findings this patch documents but deliberately does not fix — accepted risks
carried forward, per section 12's non-goals and section 5's own text:

- **REQ-V11-INF-02** — `/proc/self/mountinfo` exposes host overlay paths
  (not their contents) inside the container; masking it needs runtime
  features outside `docker run`'s stock flags.
- **REQ-V11-DOC-05** — redaction matches literal registered values; any
  in-sandbox transformation (`base64`, `rot13`, chunking, compression)
  defeats it. Defence in depth against accidental echo, not a control
  against an adversary who already controls the sandbox's contents.
- **REQ-V11-QTA-02's sandbox-scan self-DoS trade-off** — refusing on a
  cut-short scan (>200,000 filesystem entries, directories and files, even
  empty ones) means a model that creates that many entries disables `exec`
  until the operator clears the sandbox. Failing closed on an unbounded walk
  is preferred; recovery is one `rm -rf`.
- **The 124/125/126/127 exit-code ambiguities** — a program that legitimately
  exits 124 while the in-container wrapper is active, or 125/126/127 at any
  time, is indistinguishable from the docker-level/wrapper-level condition of
  the same code and is reported as one.
- **The docker-group cost**, unchanged from v1: membership in the `docker`
  group over a rootful daemon is root-equivalent on the host.

**Consequence recorded per REQ-V11-ORP-03:** with the in-container `timeout`
wrapper active (armed in this environment, per precondition 4 above), the
container now almost always dies on its own before the outer 40 s wall-clock
kill, so the `docker kill` path of REQ-V1-DK-04 step 3 is nearly unreachable
in production. It stays in the code and stays tested (`T-V11-ORP-04`'s
outer-kill-path assertion) as the fallback for a container that ignores its
own budget.

## Review

Performed by the `code-reviewer` subagent in a clean context, after all five
gates and Appendix B passed. Prompt logged in
`docs/prompts/06-code-review-v1.1.md`. Verdict: **request changes**, scoped
to reporting completeness — the reviewer found no code-level spec violation,
hallucinated behaviour or security gap, and independently reproduced two of
the four mutation checks (`bot._status_line`'s `redact` and `agent.py`'s
tool-round `redact`) with the exact result this report claims.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | 🔴 | `docs/reports/report-v1.1.md` listed `tg-post-v1.1.md` and `docs/llm-usage.md` as delivered while the review read the tree mid-flight — both were being written concurrently by later documentation steps | **fixed** — `docs/llm-usage.md` rows 25–26 appended with the measured session-transcript totals; `tg-post-v1.1.md` had in fact been written by the time this report was finalised, the review's snapshot simply predated it |
| 2 | 🟢 | `tools.py`'s `DOCKER_CLIENT_EXIT_CODES` branch (docker exit 125/126/127) skipped the post-run sandbox-quota re-check that the `timed_out` and normal-completion paths both have | **fixed** — `_record_sandbox_quota` now runs on that branch too; no existing test's key-set assertion changed (an empty test sandbox never crosses the quota) |
| 3 | 🟢 | `config._reject_ssrf_shaped_domain` cannot catch BSD/glibc shorthand IPv4 (`127.1` for `127.0.0.1`) — not covered by REQ-V11-CFV-01's four enumerated checks | **not fixed** — a gap in the spec's own enumeration, not an implementation deviation; not claimed exploitable (`getaddrinfo` generally needs `AI_NUMERICHOST` for that form); recorded below for the next spec delta |
| 4 | 🟢 | `T-V1-FT-01` needed no edit under section 9.1's conditional wording | recorded in Deviations above; no action |
| 5 | 🟢 | `fetch_url`'s post-redaction cut can trim bytes with `truncated: False` when the placeholder outgrows a short secret | confirmed spec-blessed by REQ-V11-TRN-02 step 3; no action |

## Fix cycles

**1/5 repair cycles used.** The cycle was spent on findings 1 and 2 above;
all five gates were re-confirmed green afterward (251 passed, `ruff check`
clean, both selftests OK).

## Spec risk carried forward to the next delta

`config._reject_ssrf_shaped_domain` (REQ-V11-CFV-01) implements exactly the
four checks the spec enumerates — IP-literal, `localhost`/`.localhost`,
dotless, port-or-path — and each is verified by `T-V11-CFV-01`. The review
found one shape those four checks do not cover: BSD/glibc's shorthand
decimal-dotted IPv4 forms (`127.1` for `127.0.0.1`, `10.1` for `10.0.0.1`)
parse as neither a valid `ipaddress` literal nor a dotless hostname, so they
pass all four checks and would be accepted into `FETCH_ALLOWED_DOMAINS`.
Real-world exploitability is unclear — `getaddrinfo(3)` normally requires the
`AI_NUMERICHOST` flag to resolve that shorthand rather than attempting (and
usually failing) a DNS lookup — so this is recorded as a spec gap for the
next delta to close with a fifth check, not fixed here: REQ-V11-EC-01's
patch-release discipline means this run implements exactly what
REQ-V11-CFV-01 lists, not a superset of it.
