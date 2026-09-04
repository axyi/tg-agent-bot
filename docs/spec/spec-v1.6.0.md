# tg-agent-bot — implementation specification v1.6.0 (LLM observability, tool quality, a fresh baseline and SemVer)

Complete contract for a **minor release** on the implemented v1.5.1 state
(`main` at `859d12d`). It is a **delta specification**: spec-v0 … spec-v1.5
remain in force except where a requirement here explicitly **amends**,
**supersedes** or **extends** them (§2 is the authoritative amendment table).
Everything needed to implement, test and accept the work is in this file, in the
earlier specs, or in files this spec tells you to change.

Every requirement has a stable `REQ-V160-*` id and is tagged `MUST` or
`NON-GOAL`; v1.6.0 ids never collide with v0…v1.5 ids. `MUST` = required for
acceptance; `NON-GOAL` = out of scope, and implementing it is a defect. Requirement groups: **EC** (execution contract), **AMEND**, **PRE**,
**TREE**, **TRC** (tracing), **MET** (metrics), **DSH** (dashboard pages),
**API** (JSON endpoints), **SRV** (HTTP server and process model), **TQ** (tool
quality), **BEN** (baseline and bench), **VER** (SemVer and CLI), **RPT**
(reporting), **GATE**, **TST** (tests), **ACC**, **REV**, **ORD**, **NG**. The
first eleven carry this release's new content; the rest follow the v1.5
convention.

Target platform: **Linux only**. Language **Python 3.14**, package manager
**uv**.

Executor: **claude-sonnet-5**. Reviewer: **sonnet in a clean context**. A
larger model is not needed, because every schema, route, attribute name, bucket
boundary, check kind and test id is already written out below.

**This is a minor release.** It adds observable surface — a local dashboard, a
span table, six benchmark scenarios, four environment variables, three CLI
flags — and it changes bot behaviour in exactly two places that the benchmark
can see (§10's truncated-summary retry and the repeat-call refusal). Both are
declared benchmark-affecting up front, hence the **fresh baseline** of §11.
Nothing else in v0…v1.5 may change behaviour.

**Provenance**, cited where used: `/verify-run` on v1.5.1 (843 tests, `full`
profile 15/15, no tag); the v1.4 run's `RSN-06 STOP` and its `FAIL` verdict,
which left `docs/assets/bench/baseline-v1.4.json` as the standing baseline and
handed tool-use quality to this release (REQ-V15-NG-01); the seven `llm_calls`
and two `tool_calls` columns written since v1.3 and never read by any consumer;
and the **OpenTelemetry GenAI semantic conventions**, read as a naming contract
only — verified 2026-09-04, they are stability **`development`** (experimental)
and now live in the separate repository `open-telemetry/semantic-conventions-genai`
rather than in `open-telemetry/semantic-conventions`. Appendix A maps every
requirement to source and verifying artefact.

---

## 1. Execution contract

**REQ-V160-EC-01 (MUST)** Section 1 of every earlier spec applies unchanged, with
these adjustments:

- "the gate commands" means §14's set — the six of `AGENTS.md` plus the
  `config/quality_gates.yaml` profiles, with one gate added (REQ-V160-GATE-02);
- the repair budget is **5 total** repair-and-rerun cycles (one cycle = one fix
  + a complete run of all gates from the first); exhausted → stop and report;
- **no project or lab file outside the repository root may be read or written.**
  The only permitted external effects are the LM Studio probe of
  REQ-V160-PRE-03, the benchmark's own inference traffic, and tool-owned caches.
  The lab ledger `economics.md` lives above the root: the operator writes it,
  never the executor (REQ-V160-RPT-01);
- the **runtime** dependency set is unchanged and MUST stay so: `httpx`,
  `python-dotenv`, and the `docker` CLI as a host dependency. **Zero new Python
  dependencies** (REQ-V160-NG-06), no CDN asset and no web font. The
  **developer** tool set of v1.5 (ruff, gitleaks, semgrep, trivy, skylos, rtk,
  pytest) is unchanged and no pin moves.

**REQ-V160-EC-02 (MUST)** Test-first: write §15's tests, watch them fail for the
right reason, then implement in §17's order. Every `MUST` in §§5–13 has a named
unit test, a negative test, a Gherkin scenario in Appendix B, or a recorded
artefact; Appendix A is the map and is complete. The seven high-risk mechanisms
of §15.4 additionally require mutation proof through `devtools/mutation_check.py`.

**REQ-V160-EC-03 (MUST)** The v1.5.1 suite is **843 collected tests**
(`uv run --locked pytest --collect-only -q`, reported 2026-09-04 at `859d12d`;
the two docs-only commits since — this spec and its round-1 revision — leave the
count untouched). The executor **re-measures at HEAD** at T0 and records the number;
if it differs, the measured number is the floor. No test may be deleted; tests
may be modified **only** where §15.1 lists them, and that list is exhaustive. A
change making an unlisted test fail means the change is wrong — stop and
reconsider, do not edit the test.

**REQ-V160-EC-04 (MUST)** Secrets discipline unchanged (REQ-V1/V11/V12/V15-EC-04):
credential **values** are never printed, logged, committed or quoted in `docs/`;
presence checks are by key **name** only; tests use the synthetic sentinel
pattern. `data/`, `sandbox/`, `*.db` and `exec_audit.jsonl` are never opened,
printed or quoted by any task of this run.

**`.env`: no disclosure, three permitted machine reads.** Its contents and values
are never emitted — not printed, logged, `cat`-ed, diffed, quoted or pasted into
any file. Permitted: `grep -q '^KEY=' .env` for named-key presence (exit status
only); `python-dotenv` loading by the bot and bench commands; and PRE-03's
`sed -i 's|^LMSTUDIO_BASE_URL=.*|LMSTUDIO_BASE_URL=<url>|' .env` followed by
`grep -q '^LMSTUDIO_BASE_URL=<url>$' .env` — non-zero fails, `sed -i` being
silent when the key is absent. Any other read, by the executor or a subagent, is
a defect, and **no backup copy may be made**: a `.env.bak*` file is itself a
secrets-discipline defect.

**REQ-V160-EC-05 (MUST)** Backward compatibility as in REQ-V1-EC-05: every new
parameter, config field, environment variable and helper defaults to **current
behaviour** when absent, so unlisted tests and fakes keep passing. It sizes
`LLM_SUMMARY_MAX_TOKENS` (REQ-V160-TQ-02) and keeps `_check_timeout_budget`'s
floor where it is at default configuration.

**REQ-V160-EC-06 (MUST) — this release IS benchmark-affecting, and says so.**
`AGENTS.md` requires that a behaviour change touching prompts, tool schemas,
tool output, history assembly or routing be accompanied by a benchmark run
before and after. Two requirements here touch tool output:

1. REQ-V160-TQ-01, the truncated-summary retry — it changes when a summary
   exists, which S12 and S18 observe;
2. REQ-V160-TQ-04, the repeat-call refusal — it injects a tool result the model
   has never seen before.

Both are declared **before** implementation, and §11 records a **fresh baseline**
(`baseline-v1.6.0.json`) per REQ-V160-BEN-01 and -02 — a **new post-change
baseline**, not a comparable before/after measurement, the only "before" being
non-comparable by construction. **The `AGENTS.md` before/after rule is
explicitly superseded, for the changes this spec declares, by this requirement**,
and the report MUST NOT claim it satisfied. A **cost or quality gate**
against that baseline is **not** part of this release (REQ-V160-NG-02).

If a *further* benchmark-affecting change is proposed or discovered at any
point: (1) stop the task that proposed it; (2) record it and its trigger in the
report under "Benchmark-affecting changes"; (3) either drop it and hand it to
v1.7.0, or fold it in **before** the baseline recording task (T16). Recording
the baseline and *then* changing behaviour voids it.

**REQ-V160-EC-07 (MUST) — the RLM execution rule.** REQ-V15-EC-07 applies
verbatim. A task exceeding **one** of these thresholds is delegated to a
subagent: more than one
file or folder **to explore beyond the files and line ranges the task's own
reading map names**; a single read over **100 lines** or **8 KB**; more than
**10 edits** to one file in a task; applying a review or critique to a spec. The
subagent gets a **≤ 5-line brief** with no history and MUST return a **summary
only**, never a raw file dump. In the main context, reads use `Read` with
`offset`/`limit` or `grep`/`find` with line context — never a whole-file read,
never a directory walk. §14.1's map is authoritative for the file-count
threshold; the report records **per task** whether the executor delegated and to
what.

**REQ-V160-EC-08 (MUST)** Every prompt file carries the seven-bullet header
(`Date`, `Executor model`, `Model reason`, `Harness`, `Stage`, `Owner of`,
`REQ ids`) then exactly four level-2 blocks in order — `## Goal`,
`## Constraints`, `## Acceptance`, `## Stop` — per REQ-V15-PRM-01 and
`docs/prompts/TEMPLATE.md`, unchanged by this release. `checks.py lint-docs`
enforces it in the `full` profile.

**REQ-V160-EC-09 (MUST) — `--no-verify` stays forbidden.** REQ-V15-EC-09 applies
unchanged: no commit or push in this run may use `git commit --no-verify`,
`git push --no-verify`, `-n`, or any other bypass (environment switches, a
temporary `core.hooksPath` change, `git config --unset`, deleting and restoring
a hook). The report MUST contain the sentence *"No commit or push in this run
used `--no-verify` or any other hook bypass."* — and MUST omit it, with an
explanation, if that is untrue. `devtools/checks.py replay --range
<base>..<implementation-tip>` supplies the evidence; the two historical
exceptions v1.5.1 documented are expected to persist.

**REQ-V160-EC-10 (MUST) — one prompt, one commit, Conventional Commits.** Each
task of §17 is one prompt file under `docs/prompts/` and one commit whose body
carries `(prompt: docs/prompts/NN-….md)`. The installed `.githooks/` chain
(`commit-msg`, `pre-commit`, `pre-push`) is live from the first commit of this
run; `devtools/install_hooks.py --check` must exit 0 at T0. A whole-spec solo
run may commit to `main`, where the branch-name gate is warn-only.

---

## 2. Amendments to spec-v0 … spec-v1.5 — authoritative table

**REQ-V160-AMEND-01 (MUST)** Apply exactly these; unlisted requirements stay in
force verbatim.

| id | Status | Change |
|---|---|---|
| `storage.SCHEMA_VERSION = 3` (storage.py:18) | amended | → `4`; `_MIGRATION_3_TO_4` added, `init_schema`'s accepted tuple (storage.py:205) becomes `(1, 2, 3, SCHEMA_VERSION)` (REQ-V160-TRC-05) |
| REQ-V13-OBS-03 (`llm_calls`, `tool_calls` shape) | extended | both tables gain nullable `trace_id` and `span_id`; a third table `spans` is added. No column is removed, renamed or retyped |
| `agent.py:255-263` LLM error path | amended | the failed-invocation row carries the **real** `turn_id` of its round instead of `None` (REQ-V160-TRC-08) |
| `agent.py:44` `SUMMARY_MAX_TOKENS = 512` | extended | stays the **first-attempt** summary budget; the truncation retry uses `LLM_SUMMARY_MAX_TOKENS` (REQ-V160-TQ-02) |
| `storage.add_tool_turn` (:291-305) | extended | split into a transaction-**body** helper plus today's wrapper, so the root span's sequence reuses the body without nesting a transaction; signature and callers unchanged, **no** `span=` parameter (REQ-V160-TRC-07) |
| `_ask_for_summary` (agent.py:792) `turn_id=None` | unchanged | summary rows keep `turn_id = NULL` (REQ-V160-TRC-04); `tests/test_observability.py:592` stays untouched |
| `bench.BENCH_SCHEMA = 1` (bench.py:70) | amended | → `2`; `runs[].spans` added. `_validate` gains an **informational** mode accepting `{1, 2}` (REQ-V160-BEN-03) |
| `bench.REQUIRED_LLM_ROW_KEYS` (bench.py:176) | unchanged | stays a **literal**, so schema-1 documents keep validating; `LLM_ROW_KEYS`/`TOOL_ROW_KEYS` stay derived |
| `bench.scenarios_sha256` gate (bench.py:1026) | extended | `check` and `report --gate` keep today's hard failure; plain `report` downgrades a mismatch to a printed banner (REQ-V160-BEN-03) |
| `devtools/bench_scenarios.py` `SCENARIOS` | extended | six new scenarios S13…S18; a new `Check` kind `tool_calls_max` with a `max_calls` field (REQ-V160-TQ-06); no existing scenario's `id`, `title`, `turns` or checks change |
| REQ-V14-NG-04 (scenario set frozen) | superseded | v1.4's freeze protected `baseline-v1.4`; the fresh baseline of REQ-V160-BEN-01 permits extension — **existing** scenarios still may not change |
| REQ-V13-BEN-* baselines | extended | `baseline-v1.6.0.json` becomes the standing baseline; `baseline-v1.4.json` is retained as an **informational** S01–S12 comparison, never a gate |
| `bot.py:61` `USAGE` | amended | → `"usage: bot.py [--selftest|--selftest-live|--version] [--no-dashboard]"` (REQ-V160-VER-03) |
| `bot.py` `main()` (:1306-1321) exact-match argv | superseded | replaced by the grammar of REQ-V160-VER-03 |
| `/status` (`_render_status`, bot.py:776-803) | extended | gains an **eighth and last** line, `Dashboard: …` (REQ-V160-SRV-09); the first seven lines and their order do not change, so `tests/test_v1_guardrails.py:1144` needs no amendment |
| `metrics.py` (7 functions) | extended | gains the aggregate functions of §6 **in the same module** (REQ-V160-MET-01); no parallel metrics module may be created |
| `devtools/dashboard.py` (668 lines) | amended | refactored onto `dashboard_render.py`; its CLI contract (`bench --compare --out`, exit codes) is unchanged, and it accepts `bench_schema ∈ {1, 2}` |
| REQ-V11-NG-06 `devtools/` exception | clarified | `devtools/` is still never imported by production code; the shared renderer lives at **top level** and `devtools/dashboard.py` imports **it**, never the reverse (REQ-V160-DSH-01) |
| `pyproject.toml` `version = "0.1.0"` | amended | → `"1.6.0"` (REQ-V160-VER-01) |
| REQ-V15-GATE-11 profile matrix | superseded | the authoritative matrix is **§14 of this spec**; v1.5's is frozen as a historical record, no longer machine-checked. `tests/test_v15_standards.py:1726` is repointed (§15.1) |
| `config/quality_gates.yaml` | extended | one new gate `mutation-v160` in the `pre-push` profile; `mutation-all`'s `timeout_seconds` re-measured (REQ-V160-GATE-02); no existing gate command is edited, reordered or removed |
| `AGENTS.md` "Gates", "Local quality gates", "Stack", project layout | extended | the new gate, the new top-level modules, the new environment variables and the measured test count, in the same commits as the changes described |
| `README.md` | extended | `## Dashboard` and `## Versioning` sections, four new env-var rows, `--version` / `--no-dashboard`, the `/status` line |
| `docs/prompts/TEMPLATE.md` | unchanged | already correct; untouched by this release |
| REQ-V12-REP-02 (process honesty) | extended | Deviations also records, per task, whether the RLM rule was applied |

Everything else in v0…v1.5 — Docker isolation, the redaction choke points, the
SSRF allowlist, failover, structured memory, commands, rate limiting, the error
matrix, the token budget, the pricing resolver, the hook chain and the four
scanners — is unchanged and MUST keep working.

---

## 3. Preconditions

**REQ-V160-PRE-01 (MUST)** Verify each; on failure stop and emit the blocker
template (v0 §7.2) instead of guessing.

1. **Repository**: branch `main`, clean tree, HEAD carrying the delivered v1.5.1
   (`docs/spec/spec-v1.5.md`, `docs/reports/report-v1.5.md`,
   `docs/reports/report-v1.5.1.md`) **and this spec, already committed**:
   `docs/spec/spec-v1.6.0.md` and `docs/prompts/71-v160-spec-authoring.md` exist
   at HEAD, `71` is the highest-numbered prompt, and the spec's `sha256` is
   recorded at T0 and MUST NOT change during the run — the executor materialises
   nothing. **Record the starting HEAD SHA as `<base>`** before the first commit;
   it is the lower bound of every `--since` and `replay --range` in this run.
2. **The offline gates green before anything changes**: at T0,
   `python3 devtools/checks.py run --profile full --since <base>` exits 0 **with
   its live member deferred**, and gates 1–4 and 6 of §14 exit 0 in their own
   right. An already-red gate is a blocker, not something to fix silently here.
   Gate 5 (`bot.py --selftest-live`) and the `full` profile's live member are
   **not** waived: they run at **T15**, immediately before the baseline, once
   PRE-03 has resolved the address and REQ-V160-PRE-04 has identified the
   instrument. An unreachable LM Studio is therefore not a T0 blocker — it is a
   T15 blocker, which is where the run stops.
3. **Test count re-measured** at HEAD: `uv run --locked pytest --collect-only -q`.
   Record the number; it is the floor of REQ-V160-EC-03.
4. **Hooks**: `python3 devtools/install_hooks.py --check` exits 0 and
   `python3 devtools/checks.py doctor` exits 0 against the six pinned tools.
5. **Credentials**: the git-ignored `.env` exists with the keys spec-v1.2 §3.3
   lists, plus `LMSTUDIO_BASE_URL`. Presence is established **only** by
   `grep -q '^KEY=' .env` per key name, whose exit status is the whole result
   (REQ-V160-EC-04); the file is never created, overwritten, printed or scanned.
6. **Docker**: `docker version` succeeds without `sudo`; the digest-pinned
   `python:3.14-slim` image of REQ-V15-IMG-01 is locally present. `exec` never
   pulls at request time.
7. **Ports**: TCP `127.0.0.1:8765` is free on the development host, or the
   operator names a free port in the T0 skeleton's `## Operator inputs`. A busy
   port is **not** a blocker — REQ-V160-SRV-07 makes it a degraded start, and
   is recorded.

**REQ-V160-PRE-02 (MUST) — the semantic-convention read is a naming exercise,
not a dependency.** Before T2 the executor reads the OpenTelemetry GenAI
semantic conventions from the upstream documentation and records, in the report:
the document URL, the version read, the span-name rule
`invoke_agent {gen_ai.agent.name}` of REQ-V160-TRC-04, and the resolved values
of the two VERIFY markers in §6 — the explicit bucket boundaries for
`gen_ai.client.operation.duration` and for `gen_ai.client.token.usage`. The
conventions were verified 2026-09-04 as stability **`development`**
(experimental) and as having moved to the repository
`open-telemetry/semantic-conventions-genai`; the report states whether that is
still true at run time. **Nothing is installed.** No `opentelemetry-*` distribution may appear in
`pyproject.toml` or `uv.lock`.

**REQ-V160-PRE-03 (MUST) — LM Studio, reached without reading `.env`.** The
benchmark of §11 runs against LM Studio on a roaming address. Probe, in order,
until one answers:

```bash
for h in 172.16.50.233 192.168.0.145 192.168.178.170; do
  curl -sS -m 3 "http://$h:1234/v1/models" >/dev/null && echo "$h" && break
done
```

The winning address is written into `.env` by a **single-line rewrite only**:

```bash
sed -i 's|^LMSTUDIO_BASE_URL=.*|LMSTUDIO_BASE_URL=http://<addr>:1234/v1|' .env
```

Success is confirmed by `grep -q '^LMSTUDIO_BASE_URL=http://<addr>:1234/v1$'
.env`; a non-zero status is a blocker, `sed -i` being silent when the key is
absent (REQ-V160-EC-04). The probe runs at **T15**. If no address answers,
the run stops there with the blocker template — the code, mutation and review
tasks T1–T14 do not need LM Studio and are not blocked by it.

**REQ-V160-PRE-04 (MUST) — the instrument is identified before it is measured,
and identification blocks.** PRE-03 resolves an *address*; T15 must also resolve
*what is answering*, and stop if it cannot. Four values:

| value | source | rule |
|---|---|---|
| served model id | `GET <LMSTUDIO_BASE_URL>/models`, OpenAI-compatible, field `data[].id` | exactly the read `_live_lmstudio` already performs (bot.py:1273-1283); the list MUST contain `cfg.lmstudio_model`. **Not** operator input; populated at T15 |
| LM Studio version | the text of the `go` request that starts the run | a non-empty string, copied verbatim into the T0 skeleton's `## Operator inputs` |
| loaded context length | the same `go` request | a **positive integer**, copied verbatim into that section; it is **not** `meta.context_length`, which is `LMSTUDIO_CONTEXT_LENGTH` from `config.py` |
| generation settings actually sent | `llm.base.build_payload` and the call sites REQ-V160-BEN-05 names | REQ-V160-BEN-05 |

`[[VERIFY: an LM Studio Bionic 1.1 REST endpoint exposing the application
version and the loaded context length — if the executor finds one at run time,
the API value is recorded alongside the operator value and the report names the
endpoint and field; **on disagreement the operator value wins** and both are
recorded]]`

**The inference preflight.** Immediately before the eighteen-scenario run, one
chat completion is issued against the resolved address with the resolved model,
**no tools**, a fixed one-line prompt and `max_tokens = 16`; it MUST return a
non-empty assistant message. That is the one condition a `/models` read cannot
see — a model listed but not loaded.

**What blocks, and when.** The two operator values arrive in the `go` request's
own text (the lab's `go` protocol) and T0 checks them first: a missing version,
or a context length that is not a positive integer, **stops the executor at
T0** — blocker template, no T1. A served model id not containing
`LMSTUDIO_MODEL`, or a failed preflight, stops the run at T15, before the
baseline and never after forty minutes of inference. All four values land
in the report (REQ-V160-RPT-02.7) and in `meta` (REQ-V160-BEN-05). LM Studio is
**Bionic 1.1.x** on the operator's host; this supersedes REQ-V15-DEP-06's "not
inspected" escape.

---

## 4. Required file tree (delta)

**REQ-V160-TREE-01 (MUST)** New files:

```
tracing.py                     # §5   spans, tracer, contextvars, SpanSink, SqliteSpanSink
dashboard_render.py            # §7   the ONE view layer: HTML fragments + inline SVG
dashboard_server.py            # §9   ThreadingHTTPServer, routing, /api/*, security headers
tests/test_v160_observability.py   # §15.2 TRC-*, MET-*
tests/test_v160_dashboard.py       # §15.2 DSH-*, API-*, SRV-*
tests/test_v160_tool_quality.py    # §15.2 TQ-*, VER-*, BEN-*
docs/prompts/72-go-spec-v1.6.0.md  # the `go` prompt, created at T0
docs/prompts/73-v160-*.md …        # one per task of §17
docs/reports/report-v1.6.0.md
docs/reports/tg-post-v1.6.0.md
docs/assets/bench/baseline-v1.6.0.json   # §11, committed
docs/assets/dashboard-v1.6.0.html        # §11, the static report over that baseline
```

**REQ-V160-TREE-02 (MUST)** Changed files: `storage.py`, `agent.py`,
`metrics.py`, `bot.py`, `config.py`, `devtools/bench.py`,
`devtools/bench_scenarios.py`, `devtools/dashboard.py`,
`devtools/mutation_check.py`, `config/quality_gates.yaml`, `pyproject.toml`,
`.env.example`, `README.md`, `AGENTS.md`, `docs/plan.md`, plus exactly the test
files named in §15.1. `llm/base.py` is **not** changed: `describe_client` already
returns the provider and model the span needs.

**REQ-V160-TREE-03 (MUST) — module naming and the shadowing guard.** The three
new modules are **top level**: `bot.py` imports them and production code never
imports `devtools/` (REQ-V11-NG-06). None of them may be a package
directory, and none may be named `config`, `storage`, `metrics`, `agent`,
`tools`, `dashboard` or `logging` — the `tools/` vs `tools.py` hazard of
spec-v1.2 §4 and the `config/` vs `config.py` guard of REQ-V15-TREE-02.
`T-V160-TRC-01` asserts this.

The dependency direction is a **MUST** and is tested: `dashboard_render.py`
imports nothing from `devtools/`; `devtools/dashboard.py` imports
`dashboard_render`; `dashboard_server.py` imports `dashboard_render`,
`metrics`, `storage` and `tracing` — the last for `dropped_spans()`
(REQ-V160-API-06). `T-V160-DSH-01` asserts it by static inspection of the module source.

**Prompt numbering.** `70-v151-advisor-followup.md` closes v1.5.1 and
`71-v160-spec-authoring.md` is this spec's authoring prompt; both, and
`spec-v1.6.0.md` itself, are committed **before** this run and are therefore
neither new nor changed files here (PRE-01.1). `71` not being the highest prompt
at T0 is a precondition failure. This run's first artefact is the `go` prompt
`72-go-spec-v1.6.0.md`, created at T0; per-task prompts continue from `73` as
`NN-v160-t<k>-<slug>.md`. Numbering never restarts and no earlier file is
renamed; three-number naming is REQ-V160-VER-05.

---

## 5. Tracing (TRC)

This section is **self-built**: it borrows OpenTelemetry's *names* and *span
shape*, none of its code.

**REQ-V160-TRC-01 (MUST) — the span record.** `tracing.py` defines a frozen
dataclass `Span` with exactly these fields:

| field | type | meaning |
|---|---|---|
| `trace_id` | `str` | 32 lower-case hex characters, from `secrets.token_hex(16)` |
| `span_id` | `str` | 16 lower-case hex characters, from `secrets.token_hex(8)` |
| `parent_span_id` | `str \| None` | the enclosing span, `None` for a root |
| `name` | `str` | §5's naming rules; never contains user text |
| `kind` | `str` | `"INTERNAL"` or `"CLIENT"` — no other value |
| `start_ns` | `int` | `time.monotonic_ns()` at start; **persisted** (REQ-V160-TRC-05) and the sole basis for offsets and ordering within a trace |
| `end_ns` | `int` | `time.monotonic_ns()` at end |
| `ts` | `str` | `storage.utc_now_iso()` at start, for display only |
| `status` | `str` | `"ok"` or `"error"` — no other value |
| `status_message` | `str \| None` | `None` when `ok`; otherwise bounded and redacted |
| `attributes` | `dict[str, object]` | allowlisted keys only (REQ-V160-TRC-03) |
| `conv_id` | `int \| None` | the conversation, when one exists |
| `turn_id` | `int \| None` | the turn id current when the span started |

`status_message` is passed through `config.redact()` and truncated to **200
characters** *after* redaction, appending `"…"` when truncated; `T-V160-TRC-11`
pins that ordering (spec-v1.1's truncation-headroom finding).

**REQ-V160-TRC-02 (MUST) — the tracer.** `tracing.py` exposes:

```python
current_span() -> Span | None            # reads the contextvar
start_span(name, kind, *, sink: SpanSink | None = None, attributes=None,
           conv_id=None, turn_id=None, trace_id=None) -> ContextManager[MutableSpan]
new_trace_id() -> str
new_span_id() -> str
dropped_spans() -> int                   # process-wide sink-write failures
```

`sink=None` is normalised to `NullSink()` inside `start_span`, so existing
callers, fakes and tests need no argument (REQ-V160-EC-05).

`start_span` is a `contextlib.contextmanager`. On entry it mints a `span_id`,
takes `parent_span_id` and `trace_id` from `current_span()` when one exists —
otherwise starting a new trace with `trace_id or new_trace_id()` — sets the
`contextvars.ContextVar` and yields a `MutableSpan` handle carrying
`set_attribute(key, value)`, `add_limit_hit(name)` and `set_error(exc_or_kind)`.
`MutableSpan` also carries **`finish()`**: it stamps `end_ns`, resolves
`status`, calls `sink.write(span)` and marks the span written; a **second**
`finish()` raises `RuntimeError` (`T-V160-TRC-13`). On exit `start_span` resets
the contextvar **through the token returned by `set`**, never by assigning
`None`, and calls `finish()` **only when the body did not** — no auto-finish
over a span the body already wrote. Every span owning a call row is finished
inside the body by REQ-V160-TRC-07's sequence, error path included, so
`sink.write` runs exactly once per span either way.

An exception leaving the block sets `status = "error"` and `status_message =
redact(f"{type(exc).__name__}: {exc}")` and is **re-raised**; on the TRC-07 path
`set_error` resolved both **before** the span was finished, so exit only resets
the contextvar.

**Sink failure is not uniformly best-effort.** `SqliteSpanSink.write` raises
unchanged, because REQ-V160-TRC-07 puts its insert in the same transaction as
the call row and REQ-V160-TRC-04's bijection depends on the two failing
together. Every **other** sink — `NullSink` today, an exporter later — is
best-effort: a raising `write` is caught, counted in the process-wide
`tracing.dropped_spans` that `/api/health` reports as `spans_dropped`, logged
once at `WARNING` through `redact`, and never masks the body's exception
(`T-V160-TRC-12`).

**REQ-V160-TRC-03 (MUST) — the attribute allowlist, fail-closed.** `tracing.py`
defines `ATTRIBUTE_KEYS: frozenset[str]`. `set_attribute` with a key not in it
raises `ValueError` naming the key; there is no pass-through path. The set is
exactly:

*OpenTelemetry GenAI names, used verbatim as the naming contract:*
`gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`,
`gen_ai.response.model`, `gen_ai.response.finish_reasons`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.usage.cache_read.input_tokens`,
`gen_ai.usage.reasoning.output_tokens`, `gen_ai.conversation.id`,
`gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.agent.name` — the last
confirmed present in the GenAI attribute registry ("Human-readable name of the
GenAI agent provided by the application"), verified 2026-09-04.

*Content attributes, opt-in only (REQ-V160-TRC-09):* `gen_ai.system_instructions`,
`gen_ai.input.messages`, `gen_ai.output.messages`, `gen_ai.tool.definitions`.

*Application-specific, namespaced `tg_agent.*`:* `tg_agent.purpose`,
`tg_agent.round`, `tg_agent.attempt`, `tg_agent.error_kind`,
`tg_agent.tool.outcome`, `tg_agent.tool.fingerprint`, `tg_agent.limit_hit`,
`tg_agent.summary.truncated`, `tg_agent.cost_usd`, `tg_agent.cost_basis`,
`tg_agent.scenario_id`, `tg_agent.bench_tag`.

Of the well-known `gen_ai.operation.name` values this release emits exactly
`chat`, `execute_tool` and `invoke_agent`. `gen_ai.provider.name` permits custom
values, so this project emits **`lmstudio`** and **`openrouter`** verbatim — the
two strings `describe_client` already returns.

Values are restricted to JSON-serialisable scalars, or a list of strings for
`gen_ai.response.finish_reasons`. Anything else raises.

**REQ-V160-TRC-04 (MUST) — the span tree.** Exactly one shape per user message:

```
invoke_agent tg-agent-bot                       INTERNAL, root, one per user message
├── chat {model}                                CLIENT, one per LLM invocation
│   └── (one span per `llm_calls` row: every attempt, retry and failover attempt is its own sibling span)
├── execute_tool {tool}                          INTERNAL, one per tool execution
├── chat {model}                                CLIENT, the next round
└── chat {model}                                CLIENT, the summary call,
                                                 tg_agent.purpose = "summary"
```

1. `invoke_agent tg-agent-bot` is created once per user message, before the
   first LLM invocation, and carries `gen_ai.operation.name = "invoke_agent"`,
   `gen_ai.agent.name = "tg-agent-bot"`, `gen_ai.conversation.id = <conv_id>`.

2. `chat {model}` is created for **every** LLM invocation, **failed invocations
   and every failover attempt included** — one span per row written to
   `llm_calls`, so `llm_calls` and `chat` spans are in bijection within a trace.
   Kind `CLIENT`. Name is `f"{gen_ai.operation.name} {gen_ai.request.model}"`,
   e.g. `chat qwen/qwen3.8-27b`.
3. `execute_tool {tool}` is created for every recorded tool execution, including
   the `budget`, `rejected` and `refused_repeat` outcomes, so the span set and
   the `tool_calls` rows are in bijection within a trace. Kind `INTERNAL`.
4. The summary call is a `chat {model}` span **under the same root** when one is
   active, distinguished by `tg_agent.purpose = "summary"` and
   `tg_agent.round = 0`. When `summarize_conversation` is called with no active
   span — `/new`, or a direct call from a test — the summary span is its own
   root with a fresh `trace_id`. `tests/test_observability.py:592`'s
      `turn_id is None` assertion for summary rows therefore stands unamended.
5. A span is never created for a Telegram poll, a command that does not reach
   the agent, or a `/status`, `/stats`, `/model` or `/new` dispatch.

**REQ-V160-TRC-05 (MUST) — schema 3 → 4, additive and chained.**
`storage.SCHEMA_VERSION` becomes `4`, following `_MIGRATION_1_TO_2`
(storage.py:144) and `_MIGRATION_2_TO_3` (:151) exactly:

- a new fragment `_SPANS_DDL` is appended to `_SCHEMA` (storage.py:141) so a
  fresh database is born at 4;
- `_OBSERVABILITY_DDL` (storage.py:49) gains `trace_id TEXT` and `span_id TEXT`
  in **both** `CREATE TABLE` statements, so a fresh database has them from the
  start;
- `_MIGRATION_3_TO_4 = "BEGIN IMMEDIATE;" + _SPANS_DDL + <four ALTER TABLE
  statements> + "UPDATE schema_version SET version = 4 WHERE id = 1; COMMIT;"`
    — the `ALTER TABLE … ADD COLUMN` statements exist only in the migration;
- `init_schema` (storage.py:200-216) accepts `(1, 2, 3, SCHEMA_VERSION)` at :205
  and chains `1→2→3→4`, each step guarded by the version it starts from, then
  executes `_SCHEMA` and re-checks the version as it does today.

```sql
CREATE TABLE IF NOT EXISTS spans (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id        TEXT NOT NULL,
    span_id         TEXT NOT NULL UNIQUE,
    parent_span_id  TEXT,
    conv_id         INTEGER REFERENCES conversations(id),
    turn_id         INTEGER,
    name            TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('INTERNAL', 'CLIENT')),
    ts              TEXT NOT NULL,
    start_ns        INTEGER NOT NULL,
    duration_ms     INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    status_message  TEXT,
    attributes_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans (trace_id, id);
CREATE INDEX IF NOT EXISTS idx_spans_conv  ON spans (conv_id, id);
```

`attributes_json` is a JSON **object**, never an array and never `null`; an
empty attribute set is `"{}"`. `start_ns` is the raw `time.monotonic_ns()`
reading: every span of a trace is minted in the **same process** as its root, so
within-trace differences are exact, while comparing `start_ns` across processes
is meaningless and is never done — nothing orders or subtracts across traces.

A tuple `SPAN_COLUMNS` mirrors the column list exactly as `LLM_CALL_COLUMNS`
(storage.py:25) and `TOOL_CALL_COLUMNS` (:31) do, and every consumer derives from
it; `T-V160-TRC-06` asserts it equals `PRAGMA table_info(spans)`.

**REQ-V160-TRC-06 (MUST) — `trace_id` and `span_id` on the existing tables.**
`llm_calls` and `tool_calls` each gain `trace_id TEXT` and `span_id TEXT`, both
**nullable** so pre-existing rows migrate untouched. Rows written from this
release on always carry both: `llm_calls.span_id` is the `chat` span's id and
`tool_calls.span_id` is the `execute_tool` span's id.

The `storage` module logs one JSON line per inserted row
(`tests/test_observability.py:726-740`). Those payloads MUST be **derived from
the column tuples**, not a hand-written key list — making a literal payload
derived is part of this requirement — so they gain `trace_id` and `span_id`
automatically and `test_obs06_log_lines_mirror_the_stored_rows` keeps passing
unamended. Span inserts are logged the same way under
the event name `span`, and the payload keys equal `SPAN_COLUMNS`.

**REQ-V160-TRC-07 (MUST) — the sink seam.** `tracing.py` defines

```python
class SpanSink(Protocol):
    def write(self, span: Span) -> None: ...
```

with exactly two implementations in this release: `NullSink` (drops; the default
wherever no sink is supplied, so existing callers and fakes keep working —
REQ-V160-EC-05) and `SqliteSpanSink(conn)` (inserts one row into
`spans` through `storage.add_span`).

`SqliteSpanSink` writes **on span end, from the thread that ran the span** (the
bot's main thread), reusing the connection the agent already holds.
No queue, no background writer, no second connection, no lock. The dashboard
never writes (REQ-V160-SRV-06), so the process has exactly one writer.

**One transaction, or neither row.** `storage.connect` is `isolation_level=None`
(autocommit) and the module has **no** `with conn:` anywhere: its idiom is the
explicit `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` triple of
`start_new_conversation` (storage.py:248-262) and `add_tool_turn` (:291-305).
Span persistence follows it, wrapping **only the two inserts** — never the
traced operation, so no write lock is held across inference or a tool execution.

**One executable sequence, for every span that owns a call row** — `chat`,
`execute_tool` and the root alike; the operation runs inside the span scope and
outside any transaction:

```python
with start_span(...) as span:            # sink = SqliteSpanSink(conn)
    failure = None
    try:
        result = <operation>             # inference, or tool execution
    except Exception as exc:
        span.set_error(exc); failure = exc
    try:
        conn.execute("BEGIN IMMEDIATE")
        span.finish()                    # the SOLE span writer: add_span
        add_llm_call(...) | add_tool_call(...)
        conn.execute("COMMIT")
    except BaseException:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    if failure is not None:
        raise failure
```

`failure` is re-raised **after** the `try`, never in a `finally` — which would
replace a `finish()`, insert, `COMMIT` or `ROLLBACK` failure with it and mask the
persistence defect — and `ROLLBACK` is guarded, a failed `BEGIN IMMEDIATE`
leaving none (`T-V160-TRC-14`).

Both rows land or `ROLLBACK` leaves neither, on success and on failure alike, so
REQ-V160-TRC-04's bijection holds by construction and a failing LLM call yields
exactly one `spans` row and one `llm_calls` row in the **same** transaction
(`T-V160-TRC-04`, `-13`).

**The root `invoke_agent` span** runs that same sequence, its row insert being
the turn. `add_tool_turn` is therefore refactored to expose a
**transaction-body helper** without the triple, keeps its own signature and
triple for today's callers, and the root path calls the body inside the
sequence's transaction. `add_tool_turn` gains **no** `span=` parameter and
issues **no** span insert. **No nested `BEGIN IMMEDIATE` is ever issued** —
SQLite forbids it, `T-V160-TRC-13` proves none is attempted, and an unstored
turn leaves no root span.

`SqliteSpanSink` never swallows: a failure raises out of the seam as an
`add_llm_call` failure does today, and `spans_dropped` stays 0 for this sink.

The future `OtlpHttpSpanSink` — OTLP/HTTP JSON over the same `Span` objects,
`POST`ed to a collector with `httpx` — is a **NON-GOAL** here (REQ-V160-NG-01).

**REQ-V160-TRC-08 (MUST) — the recording seams, and the `turn_id` repair.**
Spans are created at exactly four places, and nowhere else:

| seam | file:line (v1.5.1) | span |
|---|---|---|
| the agent turn entry point | `agent.py` `run(...)`, around the round loop | `invoke_agent tg-agent-bot` |
| the LLM invocation | `agent.py` around the call whose result reaches `_record_llm_call` (:644) | `chat {model}` |
| the tool execution | `agent.py` around the call whose result reaches `_record_tool_call` (:584) | `execute_tool {tool}` |
| the summary call | `agent.py` `_ask_for_summary` (:792) | `chat {model}`, `tg_agent.purpose = "summary"` |

**The `turn_id` repair.** Today the failed-invocation row is recorded with
`turn_id=None` (`agent.py:255-263`) because the turn id is only minted on
success at `:282`. `storage.next_turn_id` (:580) is a pure read, safe before `add_tool_turn`
allocates the same value, and a failed invocation inserts no message row. Therefore: **read the turn id once, before the attempt loop of each
round, and pass that same value to every `_record_llm_call` of that round,
failed attempts included, and to every `_record_tool_call` of that round.**  The value is identical to the one `:282` computes today; only the `NULL` on
error rows disappears. This amends
exactly one assertion, listed in §15.1.

**REQ-V160-TRC-09 (MUST) — content capture is off, and provably off.** The four
content attributes are written **only** when `config.OBS_CAPTURE_CONTENT` is
true. The environment variable `OBS_CAPTURE_CONTENT` is parsed with the existing
helper style, `_parse_bool(source, "OBS_CAPTURE_CONTENT", False)`, and lands on
the frozen `Config` as `obs_capture_content: bool = False`.

When it is **false**, the four keys are **absent** from `attributes_json` — not
present-and-empty, not present-and-null.

When it is **true**, each captured value is (a) passed through
`config.redact()`, (b) truncated to **2000 characters** per attribute *after*
redaction, and (c) serialised as a JSON string. There is no code path that
writes a content attribute without both steps; `T-V160-TRC-10` proves it, and
the mutation `v160-content-redact-bypassed` must be killed by it.

**REQ-V160-TRC-10 (MUST) — limit hits are recorded on the root span.** The seven
budget constants of `agent.py:29-37` — `ROUND_LIMIT = 8`, `TOOL_ROUND_LIMIT = 7`,
`HTTP_ATTEMPT_LIMIT = 9`, `TOOL_EXECUTION_LIMIT = 12`,
`MAX_TOOL_CALLS_PER_RESPONSE = 3`, `MALFORMED_RETRY_LIMIT = 2`,
`EMPTY_REPAIR_LIMIT = 1` — bound the agent. When any of them is reached during
a turn, the **root** span's `tg_agent.limit_hit`
attribute records it as a sorted, comma-separated list of the constant names hit
(e.g. `"MAX_TOOL_CALLS_PER_RESPONSE,TOOL_ROUND_LIMIT"`), with each name appearing
at most once per turn.  Attribute, not span event; `/tools` and `/api/tools` aggregate it.

**REQ-V160-TRC-11 (MUST) — bench runs are traced for free.** `devtools/bench.py`
drives the same `agent.py` code path, so scenario runs produce spans with no
bench-specific tracing code. The bench harness sets two attributes on the root
span of each scenario turn — `tg_agent.scenario_id` (e.g. `"S13"`) and
`tg_agent.bench_tag` (the `--tag` value) — through a module-level hook in
`tracing.py` (`set_run_context(scenario_id=None, bench_tag=None)`) that the bench
sets once per run and the bot never calls.

**REQ-V160-TRC-12 (MUST) — storage helpers.** `storage.py` gains exactly three
public functions, each a thin, parameterised SQL wrapper in the style of the
existing ones:

```python
add_span(conn, *, trace_id, span_id, parent_span_id, conv_id, turn_id,
         name, kind, ts, start_ns, duration_ms, status, status_message,
         attributes_json) -> int
spans_for_trace(conn, trace_id) -> list[sqlite3.Row]        # ordered by id
recent_traces(conn, *, limit, conv_id=None) -> list[sqlite3.Row]
```

`recent_traces` returns one row per `trace_id` — the root span's `ts`, `name`,
`status`, `conv_id`, the span count and the total duration — newest first,
bounded by `limit`. All three take the connection first and build no SQL by string interpolation
of caller data (`T-V160-SRV-08`).

---

## 6. Metrics (MET)

**REQ-V160-MET-01 (MUST) — one module, one set of functions.** Every aggregate
below is added to **`metrics.py`**, alongside its existing seven functions
(`conversation_stats` :40, `global_stats` :47, `resent_tokens` :57,
`context_growth` :76, `prefix_share` :100, `top_tools` :114, `turn_timeline`
:129). No parallel metrics module may be created, and `/stats` (bot.py:806-826), the
dashboard pages and the JSON API MUST all call the same functions
(`T-V160-MET-08`).

**REQ-V160-MET-02 (MUST) — revive the dead columns.** Ten columns have been
written since v1.3 and read by nothing: `llm_calls.attempt`, `.ts`, `.provider`,
`.model`, `.total_tokens`, `.messages_n`, `.finish_reason`, and
`tool_calls.ts`, `.outcome`, `.output_tokens_est`. This release makes each of
them load-bearing:

| column | first consumer |
|---|---|
| `llm_calls.finish_reason` | `error_breakdown` — share of calls by finish reason |
| `llm_calls.error_kind` | `error_breakdown` — share by error kind, `NULL` = success |
| `llm_calls.provider`, `.model` | `usage_by(group="model")` and the provider split |
| `llm_calls.ts` | `usage_by(group="day")` |
| `llm_calls.attempt` | `retry_rate` — invocations with `attempt > 1` |
| `llm_calls.total_tokens` | the token histogram's totals row |
| `llm_calls.messages_n` | `context_pressure` — mean and max messages per call |
| `tool_calls.ts` | `/tools` day filtering |
| `tool_calls.outcome` | `tool_health` — per-tool outcome rates |
| `tool_calls.output_tokens_est` | `tool_health.output_tokens_est` — the per-tool sum |

**REQ-V160-MET-03 (MUST) — the aggregate functions.** Exactly these, with these
names and these return shapes:

```python
usage_by(conn, *, group, since=None) -> list[UsageRow]
error_breakdown(conn, *, since=None) -> ErrorBreakdown
latency_histogram(conn, *, since=None) -> list[Histogram]
token_histogram(conn, *, token_type, since=None) -> list[Histogram]
tool_health(conn, *, since=None) -> list[ToolHealthRow]
limit_hits(conn, *, since=None) -> dict[str, int]
retry_rate(conn, *, since=None) -> tuple[int, int]
context_pressure(conn, *, since=None) -> tuple[float, int]
```

- `group` ∈ `{"model", "day", "purpose", "scenario"}`; anything else raises
  `ValueError` naming the value. Each names an exact key: `"model"` groups by
  the **pair** `(llm_calls.provider, llm_calls.model)` — never the model alone,
  so one model id served by two providers stays two rows — labelled
  `f"{provider}/{model}"`; `"day"` by `substr(llm_calls.ts, 1, 10)`, the UTC
  date; `"purpose"` by `llm_calls.purpose`; `"scenario"` by the root span's
  `tg_agent.scenario_id`, plus one `"(none)"` row for traces carrying none. A
  `NULL` component renders `"(none)"` in the label and stays `None` in the field.
- `since` is a `datetime.date` or `None`; when given, rows with
  `ts < since.isoformat()` are excluded. The comparison is lexicographic on the
  fixed-width ISO-8601 UTC strings `storage.utc_now_iso()` already writes.
- `UsageRow` is a frozen dataclass carrying its dimensions **explicitly** —
  `provider: str | None`, `model: str | None`, `purpose: str | None`,
  `scenario: str | None`, `day: str | None`, a grouping populating only its own
  and leaving the rest `None` — so no consumer parses a composite string back
  apart. Then `key`, the label above, **display only** and never parsed; and
  `calls`, `errors`, `input_tokens`,
  `output_tokens`, `cached_tokens`, `reasoning_tokens`, `cost_usd`,
  `cost_basis`, `cache_hit_share`, `reasoning_share`. `cache_hit_share` is
  `cached_tokens / input_tokens` over rows where both are non-`NULL`, and is
  `None` — not `0.0` — when no row qualifies. `reasoning_share` is
  `reasoning_tokens / output_tokens` under the same rule. `cost_basis` is
  the set of distinct bases in the group, joined by `", "`.
- `ErrorBreakdown` carries `by_finish_reason: dict[str, int]`,
  `by_error_kind: dict[str, int]`, `total: int`, `error_rate: float`. A `NULL`
  `finish_reason` is bucketed as `"(none)"`; a `NULL` `error_kind` is bucketed as
  `"ok"`. Both keys are provider free text, so **each dictionary returns at most
  100 named buckets plus `"(other)"`**, count descending then key ascending, the
  omitted counts folded in; `total` and `error_rate` count **all** rows and the
  fold leaves both unchanged (REQ-V160-MET-07).
- `ToolHealthRow`: `tool`, `calls`, `ok`, `error`, `budget`, `rejected`,
  `refused_repeat`, `error_rate`, `p50_ms`, `p95_ms`, `max_consecutive_repeats`,
  `output_tokens_est`. `max_consecutive_repeats` is the longest run of
  consecutive `tool_calls` rows naming the same tool **within one `turn_id` of
  one conversation**, ordered by `id` (REQ-V160-TQ-04). `output_tokens_est` is
  `SUM(tool_calls.output_tokens_est)` over the group — the stored `INTEGER NOT
  NULL` column of `_OBSERVABILITY_DDL` (storage.py:89), written since v1.3 and
  read by nothing until now; it is a **tenth** revived column, added to
  REQ-V160-MET-02's table.
- `retry_rate` counts **rows, not turns or logical invocations**: `(COUNT(*)
  WHERE attempt > 1, COUNT(*))` over `llm_calls` under the same `since` filter.
  A row is the unit because `attempt` is a row column and no invocation key exists.
- `context_pressure` returns `(mean_messages_n, max_messages_n)` over
  `purpose = 'agent'` rows.

**REQ-V160-MET-04 (MUST) — histograms carry the OpenTelemetry metric contract.**
The **names, units and bucket boundaries** are taken

| metric | name | unit | attributes |
|---|---|---|---|
| operation duration | `gen_ai.client.operation.duration` | `s` | `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model` |
| token usage | `gen_ai.client.token.usage` | `{token}` | the same three, plus **required** `gen_ai.token.type` ∈ `{input, output}` |

`Histogram` is a frozen dataclass: `name`, `unit`,
`attributes: tuple[tuple[str, str], ...]`, `boundaries: tuple[float, ...]`,
`counts: tuple[int, ...]` of length `len(boundaries) + 1` (the last is the
overflow bucket), `total: int`, `sum: float`, `p50`, `p95`.

**One histogram per attribute tuple.** A single global histogram cannot carry
three dimensions, so both functions return a **list**: one `Histogram` per
distinct attribute tuple in the data. `attributes` is the `(key, value)` pairs
**sorted by key** — `gen_ai.operation.name`, `gen_ai.provider.name`,
`gen_ai.request.model`, plus `gen_ai.token.type` for the token metric; a `NULL`
dimension renders `"(none)"`. The list is ordered by `attributes` and capped at
**20** (REQ-V160-MET-07), the remainder folded into a final histogram whose
`attributes` is `(("gen_ai.request.model", "(other)"),)`. Bucket `i` counts
values `v` with `boundaries[i-1] < v <= boundaries[i]`; the implementation uses `bisect.bisect_left`,
so the boundary value itself lands in the lower bucket.

Explicit boundaries:

- duration, seconds:
  `[0.01, 0.02, 0.04, 0.08, 0.16, 0.32, 0.64, 1.28, 2.56, 5.12, 10.24, 20.48, 40.96, 81.92]`
  `[[VERIFY: the recommended explicit bucket boundaries for
  gen_ai.client.operation.duration — confirm this 14-value list against the GenAI
  metrics document in open-telemetry/semantic-conventions-genai at run time and
  record the document version; if upstream differs, upstream wins and the report
  records the substitution]]`
- tokens:
  `[1, 4, 16, 64, 256, 1024, 4096, 16384, 65536, 262144, 1048576, 4194304, 16777216, 67108864]`
  `[[VERIFY: the recommended explicit bucket boundaries for
  gen_ai.client.token.usage — same document, same treatment]]`

`latency_histogram` reads `llm_calls.latency_ms` and divides by 1000.0 to reach
the `s` unit the convention requires; `T-V160-MET-05` pins it.

**REQ-V160-MET-05 (MUST) — `/stats` grows, compatibly.** `_render_stats`
(bot.py:806-826) keeps its eight existing lines, in order, byte-identical in
shape, and gains **two** lines at the end:

```
Errors: <n> (<finish reasons: a=1, b=2>; kinds: <k=1, …>)
Summaries: <n> ok, <n> truncated-retried, <n> failed
```

The three summary numbers are `summary_health.ok`, `.retried` and `.failed`
respectively — "truncated-retried" is `retried`, and `failed` is REQ-V160-MET-06's
terminal-failure count over **rows**, every non-truncation `error_kind` included.
Both lines
are **appended**, so `/stats`'s existing indexed assertions keep passing, and
both are built from `metrics.error_breakdown` and `metrics.summary_health`,
never from their own SQL.

**REQ-V160-MET-06 (MUST) — summary health is counted, in rows.** `metrics.py`
gains `summary_health(conn, *, since=None) -> SummaryHealth` with fields
`attempts`, `ok`, `truncated`, `retried`, `failed`. Summary rows carry
`turn_id = NULL` by construction (agent.py:801; REQ-V160-TRC-04 item 4), so
**no field here counts turns** — each counts `llm_calls` rows with
`purpose = 'summary'` under the same `since` filter. Over that row set `S`:

| field | SQL over `S` |
|---|---|
| `attempts` | `COUNT(*)` |
| `ok` | `COUNT(*) WHERE error_kind IS NULL` |
| `truncated` | `COUNT(*) WHERE error_kind = 'truncated'` |
| `retried` | `COUNT(*) WHERE attempt = 2` |
| `failed` | terminal failures: `COUNT(*) WHERE (error_kind IS NOT NULL AND error_kind <> 'truncated') OR (attempt = 2 AND error_kind = 'truncated')` |

`failed` is every summary row carrying a **non-truncation** error — timeout,
provider error, parse or repair failure, any other `error_kind` — plus a retry
truncated a second time; a first truncation alone is `truncated`, not yet a
failure, because TQ-01 retries it. **Row-based limitation:** no summary
invocation id exists, so `failed` counts rows, not invocations — a turn whose
first attempt errored and whose retry succeeded adds one to `failed` and one to
`ok`; `/stats` shows `failed` under exactly this definition, never as turns.

`attempt = 2` marks the truncation retry uniquely: every summary row is written
`attempt = 1` today, the JSON-repair call (agent.py:777-784) included — a second
**row**, not a second attempt (agent.py:798-799) — so REQ-V160-TQ-01's retry is
its only writer. `/tools` renders all five.

**REQ-V160-MET-07 (MUST) — every aggregate is bounded.** No function of §6 may
return an unbounded list **or dictionary**. `usage_by` caps at **500** groups and
reports a `"(other)"` row carrying the remainder; `error_breakdown` caps **each**
dictionary at **100** named buckets plus its `"(other)"` fold
(`T-V160-MET-11`); `tool_health` caps at **50** tools;
`latency_histogram` and `token_histogram` cap at **20** histograms with the
`"(other)"` fold of REQ-V160-MET-04; `recent_traces` is capped by its `limit`
parameter, itself bounded by REQ-V160-API-03.

---

## 7. Dashboard pages (DSH)

**REQ-V160-DSH-01 (MUST) — one view layer, two callers.** `dashboard_render.py`
is the **only** module in the repository that emits HTML. It exposes pure
functions — data in, `str` out — with no I/O, no database handle, no
`Path`, no `print`:

```python
page(title, *, nav, body, generated_at) -> str        # the full document
usage_section(rows, *, group, totals) -> str
histogram_svg(histogram, *, width, height, title) -> str
bar_svg(pairs, *, width, height, title) -> str
trace_list_section(traces) -> str
trace_tree_section(spans: Sequence[ServedSpan]) -> str
gantt_svg(spans: Sequence[ServedSpan], *, width) -> str
tool_health_section(rows, *, summary) -> str
compare_section(baseline, candidate) -> str
served_span(row_or_mapping) -> ServedSpan             # REQ-V160-DSH-09
SERVED_SPAN_ATTRIBUTE_KEYS: frozenset[str]            # REQ-V160-DSH-09
error_page(message) -> str                            # every HTML error body
response_too_large_page() -> str                      # API-05
invalid_host_page() -> str                            # SRV-11
esc(value) -> str
```

The last three keep the rule literal: `dashboard_server.py` takes **every** HTML
body it sends — pages, 400, 404, 405, 500, 503 — from here and holds **no HTML
literal of its own**; `error_page` wraps a fixed string.

`dashboard_server.py` calls them for the live pages; `devtools/dashboard.py`
calls them for the static bench report. `T-V160-DSH-02` asserts the two
`usage_section` fragments over one fixture are **byte-identical**.
`devtools/dashboard.py` imports `dashboard_render`, never the reverse
(REQ-V160-TREE-03).

**REQ-V160-DSH-02 (MUST) — offline, no script, no external anything.** Every
page MUST render correctly with the machine's network cable unplugged. There is
**no** `<script>` tag, no `onclick` or any other inline event handler, no
`<link rel="stylesheet">`, no `@import`, no `<img src="http…">`, no `<iframe>`,
no web font, no CDN. Styling is a single inline `<style>` block; charts are
**server-side inline `<svg>`** built as text by `dashboard_render.py`.

**REQ-V160-DSH-03 (MUST) — the three pages plus the index.**

**`/` — usage and cost.** Query `?group=model|day|purpose|scenario&since=<iso-date>`,
defaults `group=model`, `since` absent. Renders: a totals band (calls, errors,
input/output tokens, cached, reasoning, cost, cost basis); the `usage_by` table
for the requested grouping; the **cache-hit share** and **reasoning share**
columns with an explicit `—` where the share is `None` rather than a misleading
`0 %`; the token (`input`, `output`) and duration histograms as inline SVG — **one
chart per returned `Histogram`** (REQ-V160-MET-04), each `<title>` naming its
attribute tuple; the error breakdown by finish reason and by error kind; and a
footer naming the database path's **basename only**, the schema version and the
generation timestamp. The four grouping choices are rendered as four in-page
links that change only the query string.

**`/traces` — the trace list.** Query `?limit=<1..500>&conv=<int>`, defaults
`limit=50`. One row per trace, newest first: timestamp, conversation id, turn id,
root span name, scenario id when present, span count, total duration, status, and
the count of `chat` and `execute_tool` children. `trace_id` is rendered as a link
to `/traces/<trace_id>` and displayed **abbreviated to its first 12 characters**
with the full value in the `title` attribute.

**`/traces/<trace_id>` — one trace.** The span **tree**, indented by depth,
each row carrying span name, kind, duration, status, and the span's **served**
attributes rendered as `key = value` pairs — the serving allowlist of
REQ-V160-DSH-09 and nothing else. Above the tree, an inline-SVG
**gantt**: one bar per span, left edge at
`x = (span.start_ns - root.start_ns) / root_duration_ns`, width
`span.duration_ms * 1e6 / root_duration_ns`, `root_duration_ns` being
`root.duration_ms * 1e6` and a zero-duration root drawing every bar at `x = 0`
rather than dividing; y ordered by `start_ns` then tree order, bars coloured by
kind and outlined in the error colour when `status = "error"`. `ts` is never
used for geometry or ordering. A trace whose root span is
missing renders the orphans as roots with a banner rather than 500-ing.

**`/tools` — tool health.** The `tool_health` table (calls, the five-outcome
split, error rate, p50/p95 duration, longest consecutive repeat run, output
tokens), the `limit_hits` counts as a bar chart, the `summary_health` line, and
the `retry_rate` and `context_pressure` figures. Bench runs appear on all three pages with no
special casing (REQ-V160-TRC-11).

**REQ-V160-DSH-04 (MUST) — charts are SVG text, and legible in both themes.**
`histogram_svg`, `bar_svg` and `gantt_svg` return `<svg>` elements with an
explicit `viewBox`, `width`, `height` and `role="img"`, an `<title>` child as the
accessible name, and a `<desc>` child naming the metric, unit and total count.
Colours come from one named palette defined in `dashboard_render.py`; every
chart also encodes its information in text (axis labels, printed counts), so the
page stays readable with colour removed. A zero-count bucket is drawn as a
zero-height bar with its label present.

**REQ-V160-DSH-05 (MUST) — the static bench report keeps its contract.**
`devtools/dashboard.py`'s CLI is unchanged: positional `bench`, optional
`--compare`, **required** `--out`; exit 0 on success, `EXIT_ERROR` (1) with the
message on stderr for an unreadable document; the same `dashboard: <path>
(<bytes> bytes)` line on stdout. Its existing functions (`load_document` :130,
`scenario_runs` :154, `median_run` :180, `timeline_rows` :198, `tool_breakdown`
:239) stay where they are. The **render** half
(`_esc` :259, `fmt` :263, `_header` :319, `_aggregates` :351, `_cache` :409,
`_bar` :434, `_tools` :439, `_timeline` :473, `_compare` :531, `render` :604) is
what moves behind `dashboard_render.py`; `_esc` becomes a re-export of
`dashboard_render.esc`. `load_document` additionally accepts
`bench_schema ∈ {1, 2}` (REQ-V160-BEN-03).

`docs/assets/dashboard-baseline.html` and `dashboard-v1.3.html` are **frozen**
historical records and are not regenerated (REQ-V160-NG-11); the refactor is
demonstrated by the new `docs/assets/dashboard-v1.6.0.html` (REQ-V160-BEN-06).

**REQ-V160-DSH-06 (MUST) — every value is escaped, once.** All text reaching
HTML goes through `dashboard_render.esc`, which is `html.escape(str(value),
quote=True)` with `None` rendering as `""` — the existing `_esc` semantics
(dashboard.py:259-260). SVG text nodes use the same function. No `str.format`,
f-string or concatenation may place caller data into markup without it;
`T-V160-DSH-04` asserts the rendered bytes carry no unescaped `<`.

**REQ-V160-DSH-07 (MUST) — the content policy, and the canary that proves it.**
Pages and API responses expose **only** aggregates and identifiers:

**Permitted**: tool names, model names, provider names, purpose, finish reasons,
error kinds, outcomes, durations, token counts, cost and cost basis, trace ids,
span ids, parent span ids, scenario ids, bench tags, conversation ids (integers),
turn ids (integers), round and attempt numbers, limit-hit names, timestamps,
`start_ns` (monotonic; no wall-clock or host information),
counts, shares, schema version, and the database file's **basename**.

**Forbidden, without exception**: message text, prompts, system instructions,
tool arguments, tool outputs, file paths taken from tool arguments, URLs taken
from `fetch` arguments, Telegram user ids, Telegram usernames, chat ids, skill
contents, summary contents, `.env` values, the absolute database path, the four
`gen_ai.*` content attributes — **even when `OBS_CAPTURE_CONTENT` is true** —
**`status_message` in any form**, `gen_ai.tool.call.id`,
`tg_agent.tool.fingerprint`, **any span attribute outside
`SERVED_SPAN_ATTRIBUTE_KEYS`**, and the raw `attributes_json` string.
The flag governs what is *stored*; this requirement governs what is *served*, and
there is no configuration that relaxes it. REQ-V160-DSH-09 is the mechanism.

The proof is a **scanning test**, `T-V160-DSH-05`, parametrised over every
route of §8 and §9 — `/` and `/api/usage` once per grouping — **plus the 404
body and the 405 body**.
The fixture database is seeded with `SYNTHETIC-CANARY-DASHBOARD-1` in **six**
places — a `messages.content` row, a `summaries` row, a recorded tool argument,
a span `status_message`, a span content attribute written with
`OBS_CAPTURE_CONTENT` forced true, and a span attribute that is in
`ATTRIBUTE_KEYS` but not in `SERVED_SPAN_ATTRIBUTE_KEYS`
(`tg_agent.tool.fingerprint`) — and the test asserts the canary appears in
no response body, no response header and no log line, with
`OBS_CAPTURE_CONTENT` pinned **false** for the serving process. `T-V160-DSH-06` repeats the sweep with
the flag true for the *writer*.

**REQ-V160-DSH-08 (MUST) — the index is a page, not a redirect.** `/` is the
usage page itself. `/index.html`, `/favicon.ico` and every other unlisted path
are **404** (REQ-V160-SRV-03); there is no redirect, no directory listing and no
static-file serving of any kind. The server owns no filesystem read path other
than the database.

**REQ-V160-DSH-09 (MUST) — the serving DTO; a `spans` row is never served.**
No `spans` row, and no raw `attributes_json`, is serialised, rendered, or passed
to any function of `dashboard_render.py`. `dashboard_render.py` defines the one
gate every span crosses on its way out:

```python
SERVED_SPAN_ATTRIBUTE_KEYS: frozenset[str] = frozenset({
    "gen_ai.operation.name", "gen_ai.provider.name", "gen_ai.request.model",
    "gen_ai.response.model", "gen_ai.response.finish_reasons",
    "gen_ai.usage.input_tokens", "gen_ai.usage.output_tokens",
    "gen_ai.usage.cache_read.input_tokens",
    "gen_ai.usage.reasoning.output_tokens", "gen_ai.conversation.id",
    "gen_ai.tool.name", "gen_ai.agent.name",
    "tg_agent.purpose", "tg_agent.round", "tg_agent.attempt",
    "tg_agent.error_kind", "tg_agent.tool.outcome", "tg_agent.limit_hit",
    "tg_agent.summary.truncated", "tg_agent.cost_usd", "tg_agent.cost_basis",
    "tg_agent.scenario_id", "tg_agent.bench_tag",
})

@dataclass(frozen=True)
class ServedSpan:
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str
    ts: str
    start_ns: int                     # same-trace offsets only
    duration_ms: int
    status: str
    conv_id: int | None
    turn_id: int | None
    attributes: dict[str, object]     # keys ⊆ SERVED_SPAN_ATTRIBUTE_KEYS

def served_span(row_or_mapping) -> ServedSpan: ...   # the ONE constructor
```

`SERVED_SPAN_ATTRIBUTE_KEYS` is `ATTRIBUTE_KEYS` (REQ-V160-TRC-03) minus the
four content attributes, minus `gen_ai.tool.call.id` — a provider-issued string,
not an aggregate — and minus `tg_agent.tool.fingerprint`. `served_span` **drops**
every key outside the set rather than raising, applies REQ-V160-API-05's length
maxima to every string it keeps, and never copies
`status_message`: the field does not exist on `ServedSpan`, so no renderer and
no serialiser can reach it. Conversation and turn ids stay, as integers.

`trace_tree_section`, `gantt_svg` and `/api/traces/<trace_id>` accept
`ServedSpan` only; `devtools/dashboard.py` builds one through the same
constructor from the bench document's parsed `attributes` (REQ-V160-BEN-04), so
REQ-V160-DSH-01's byte-identity property survives. `T-V160-DSH-09` asserts the
set, the dropped keys and the absent field.

---

## 8. JSON endpoints (API)

**REQ-V160-API-01 (MUST) — five endpoints, separate from the pages.** The JSON
API is a distinct route family under `/api/`, sharing the metric functions with
the HTML pages and sharing **no** rendering code with them. A page is never
scraped to produce JSON and JSON is never embedded in a page.

| route | query | returns |
|---|---|---|
| `/api/health` | — | `{"status": "ok", "version": "1.6.0", "schema_version": 4, "spans": <int>, "spans_dropped": <int>, "traces": <int>, "generated_at": "<iso>"}` |
| `/api/usage` | `group`, `since` | `{"group": …, "since": …|null, "rows": [...], "totals": {...}}` |
| `/api/traces` | `limit`, `conv` | `{"limit": …, "conv": …|null, "traces": [...]}` |
| `/api/traces/<trace_id>` | — | `{"trace_id": …, "spans": [...]}` |
| `/api/tools` | `since` | `{"since": …|null, "tools": [...], "limit_hits": {...}, "summary": {...}, "retry_rate": [...], "context_pressure": [...]}` |

**REQ-V160-API-02 (MUST) — semantic-convention keys where one exists.** Inside
`rows` and `spans`, a field that has an OpenTelemetry GenAI name uses that name
verbatim as its JSON key: `gen_ai.request.model`, `gen_ai.provider.name`,
`gen_ai.operation.name`, `gen_ai.response.finish_reasons`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.reasoning.output_tokens`,
`gen_ai.conversation.id`, `gen_ai.tool.name`. A `UsageRow`'s dimensions
(REQ-V160-MET-03) serialise under those names where one exists — `group="model"`
emits **both** `gen_ai.provider.name` and `gen_ai.request.model`, never a fused
string — with `tg_agent.purpose`, `tg_agent.scenario_id` and plain `day` for the
rest, and `key` alongside them as the display label only. `gen_ai.tool.call.id` is **never**
a served key (REQ-V160-DSH-09), and `spans` is an array of `ServedSpan`
objects — never database rows. Fields with
no upstream name are `tg_agent.*` or plain snake_case (`calls`, `errors`,
`cost_usd`, `cost_basis`, `duration_ms`, `start_ns`, `p50_ms`, `p95_ms`,
`trace_id`, `span_id`, `parent_span_id`). A histogram list serialises as an array of
`{"name": …, "unit": …, "attributes": {…}, "boundaries": [...], "counts": [...],
"total": …, "sum": …, "p50": …, "p95": …}`, `attributes` being the sorted pairs
as a JSON object. `T-V160-API-01` asserts the exact key set of each endpoint
against a literal.

`Content-Type: application/json; charset=utf-8`. Output is
`json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`
encoded UTF-8.

**REQ-V160-API-03 (MUST) — every parameter validated, nothing echoed.**

| parameter | rule | on violation |
|---|---|---|
| `group` | member of `{"model", "day", "purpose", "scenario"}` | 400 |
| `since` | matches `^\d{4}-\d{2}-\d{2}$` **and** parses with `datetime.date.fromisoformat` | 400 |
| `limit` | decimal integer, `1 <= n <= 500` | 400 |
| `conv` | decimal integer, `1 <= n <= 2**31-1` | 400 |
| `<trace_id>` | matches `^[0-9a-f]{32}$` | 404 |
| any other query key | unknown keys are **rejected**, not ignored | 400 |

A 400 body is `{"error": "invalid parameter", "parameter": "<name>"}` — the
**name** of the offending parameter, never its **value**; the mutation
`v160-error-echoes-request-input` keeps it out. A duplicated query key
(`?group=model&group=day`) is a 400 naming `group`.

**REQ-V160-API-04 (MUST) — a known trace id that has no spans is 404, not an
empty 200.** `/api/traces/<trace_id>` and `/traces/<trace_id>` return 404 when
`spans_for_trace` yields nothing.

**REQ-V160-API-05 (MUST) — bounded response size, enforced not asserted.** §6's
caps and §8's `limit` ceiling bound the normal case; 2 MiB is enforced. Every
body, JSON and HTML alike, is serialised **into memory first**; when
`len(body) > 2 * 1024 * 1024` the server sends a fixed, content-free **500**
instead — `{"error":"response too large"}` for `/api/*`, and for a page whatever
`dashboard_render.response_too_large_page()` returns, the server writing no HTML
of its own (REQ-V160-DSH-01) — and no fragment of the body, no size,
path or parameter reaches the client or the log beyond one redacted `ERROR` line
naming the route (`T-V160-API-03`). Nothing streams or paginates by cursor.

**Every served string has a maximum**, enforced by REQ-V160-DSH-09's DTO and
marked with a trailing `…`: span, tool, model and provider names ≤ **128**
characters, any served attribute **value** ≤ **256**, a `UsageRow.key` ≤ **128**.
Identifiers are fixed width — `trace_id` 32, `span_id` and `parent_span_id` 16
lower-case hex — and any other shape is dropped, not truncated.

**Spans per trace are bounded** by the constant `MAX_SPANS_PER_TRACE = 64` in
`dashboard_render.py`, a safety bound for a malformed database, never a cap a
legitimate trace can reach: the agent limits (REQ-V160-TRC-10) bound a legitimate
trace at 1 root + `HTTP_ATTEMPT_LIMIT` (9) × 2 failover attempts `chat` +
`TOOL_EXECUTION_LIMIT` (12) `execute_tool` + 2 × 2 summary spans (attempt 1 and
its retry, each with a failover attempt) = **35**. `T-V160-API-03` derives that
maximum from the `agent.py` constants and asserts it is ≤ `MAX_SPANS_PER_TRACE`,
so a change to a limit that crosses the bound fails the suite instead of
silently refusing real traces. `/api/traces/<trace_id>` and `/traces/<trace_id>`
refuse a trace of more than `MAX_SPANS_PER_TRACE` spans with that same fixed 500.
Exceeding any bound is a defect in a cap, never a reason to paginate
(REQ-V160-NG-08).

**REQ-V160-API-06 (MUST) — `/api/health` is the readiness probe and says
nothing else.** It reports liveness, the version string from REQ-V160-VER-01,
the schema version, and three counts — spans, spans dropped by a non-sqlite sink
(REQ-V160-TRC-07), traces. It never reports the database path, the
provider, the model, the configured port, the process id, environment variables or uptime.

---

## 9. HTTP server and process model (SRV)

**REQ-V160-SRV-01 (MUST) — on by default, inside the bot process.**
`uv run --locked python bot.py` starts Telegram polling **and** serves the
dashboard.

Opt-out, two independent switches, either sufficient:

- CLI flag **`--no-dashboard`** (REQ-V160-VER-03), the only flag that combines
  with the default run;
- environment **`DASHBOARD_ENABLED`**, parsed
  `_parse_bool(source, "DASHBOARD_ENABLED", True)` onto
  `Config.dashboard_enabled: bool = True`.

The flag wins over the environment when they disagree, and `/status` says which
switch turned it off.

**REQ-V160-SRV-02 (MUST) — the port, validated at startup.**
`DASHBOARD_PORT` is parsed `_parse_int(source, "DASHBOARD_PORT", 8765, 1024, 65535)`
onto `Config.dashboard_port: int = 8765`. A non-integer or an out-of-range value
raises `ConfigError` at `load_config` time and the bot does not start.

The **bind address is the fixed constant** `DASHBOARD_BIND = "127.0.0.1"` in
`dashboard_server.py`. It is **not** configurable — not by environment, not by
flag, not by a config field. Remote bind, authentication and TLS are NON-GOALs
(REQ-V160-NG-05). The mutation `v160-bind-address-widened` MUST be killed
by `T-V160-SRV-03`.

**REQ-V160-SRV-03 (MUST) — the server surface.**

- `http.server.ThreadingHTTPServer` with `daemon_threads = True`, running in a
  `threading.Thread(daemon=True)` started after `load_config` and before the
  polling loop.
- **`GET` and `HEAD` only.** Every other method — `POST`, `PUT`, `DELETE`,
  `PATCH`, `OPTIONS`, `TRACE`, `CONNECT` and anything unrecognised — is **405**
  with an `Allow: GET, HEAD` header and a fixed body. `HEAD` returns the exact
  headers of the corresponding `GET`, including `Content-Length`, with an empty
  body.
- **Strict path allowlist.** Exactly: `/`, `/traces`, `/tools`, `/api/health`,
  `/api/usage`, `/api/traces`, `/api/tools`, plus the two patterns
  `^/traces/([0-9a-f]{32})$` and `^/api/traces/([0-9a-f]{32})$`. The path is
  compared **after** stripping the query string and **without** any
  normalisation, unquoting or `..` resolution; an unlisted path is 404. `/tools/` with a trailing slash is
  404, not a redirect.
- Request bodies are not read. A request line longer than 8 KiB, or more than
  64 headers, is answered 400 and the connection closed.
- `protocol_version = "HTTP/1.1"` with `Content-Length` always set;
  `server_version`/`sys_version` are overridden to a fixed
  `"tg-agent-bot"` so the response advertises no Python version.
- `BaseHTTPRequestHandler.log_message` is overridden to log through the
  `dashboard` logger at `DEBUG` with the **method and matched route name only** —
  never the raw path, never the query string, never a header value.

**REQ-V160-SRV-04 (MUST) — the security headers, on every response.** Including
404, 405, 400 and 503:

```
Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src data:
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Cache-Control: no-store
```

`default-src 'none'` holds with no relaxation: the inline `<svg>` of
REQ-V160-DSH-02 needs no CSP source of its own.
No cookie is ever set, no `Set-Cookie` header appears, no authentication is
attempted and no session exists. `T-V160-SRV-05` asserts them per status class.

**REQ-V160-SRV-05 (MUST) — nothing but the bot binds a port.**
`bot.py --selftest`, `bot.py --selftest-live`, `devtools/bench.py` and the pytest
suite MUST never construct a listening socket. The server is constructed at
exactly one call site: the default-run branch of `bot.main()`.

1. `tests/conftest.py`'s offline guard is extended to patch `socket.socket.bind`
   so that any bind to an address other than `("127.0.0.1", 0)` raises
   `RuntimeError` naming the address. Tests that genuinely exercise the server
   bind **port 0** and read the assigned port from `server.server_address[1]`.
2. `T-V160-SRV-04` proves the selftest path constructs no server at all.

The mutation `v160-selftest-starts-the-server` MUST be killed by
`T-V160-SRV-04`.

**REQ-V160-SRV-06 (MUST) — the server reads, and only reads.**
`storage.py` gains:

```python
def connect_readonly(db_path: Path) -> sqlite3.Connection
```

which opens `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True,
isolation_level=None, timeout=5.0)`, sets `row_factory = sqlite3.Row` and
`PRAGMA query_only = ON`, and **does not** call `_restrict_permissions` (it
changes no file) and
**does not** set `journal_mode` (a read-only connection cannot). A missing file raises
`sqlite3.OperationalError` rather than creating one; `mode=ro` in the URI form
guarantees that.

The server opens **one read-only connection per request** and closes it in a
`finally:` block. There is **no** cache: no `threading.local()`, no pool, no
module-level handle, nothing to close at shutdown. The per-request lifetime is
also what makes a vanished database observable — on Linux an unlinked file keeps
serving reads through an already-open descriptor, so a cached connection could
never produce the 503. A `sqlite3.Error` at open or query time is answered
**503** with a fixed body, logged once through `redact`.

**REQ-V160-SRV-07 (MUST) — the dashboard never takes the bot down.** Startup is
guarded end to end. A failure to bind (port busy, permission denied), to create
the server, or to start the thread is caught, logged **once** at `ERROR` through
`config.redact()` with the port number and the exception class, and the bot
**continues without the dashboard**. It does not retry, does not pick another
port, and does not exit. `/status` then shows `Dashboard: off (bind failed)`.

Inside a request, an unexpected exception is caught by the handler, logged once
at `ERROR` through `redact`, and answered **500** with a fixed body carrying no
traceback, no exception message and no path. On bot exit the server is shut down
cleanly — `shutdown()` then `server_close()`, joined with a **5 second** timeout;
a thread that does not stop is logged at `WARNING` and abandoned.

**REQ-V160-SRV-08 (MUST) — no SQL is built from request data.** Every value
derived from a query string or a path segment reaches SQLite as a **bound
parameter**. `group` and `since` select between pre-written statements or bind a
value; they never interpolate a column name or a date into SQL text.
`T-V160-SRV-08` monkeypatches the connection's `execute` to record every
`(sql, params)` pair over a full route sweep and proves it.

**REQ-V160-SRV-09 (MUST) — one startup log line, and the `/status` line.** On a
successful start the bot logs exactly one line at `INFO`:

```
dashboard: serving at http://127.0.0.1:<port>/
```

`_render_status` (bot.py:776-803) gains an **eighth and final** line:

- `Dashboard: http://127.0.0.1:<port>/` when serving;
- `Dashboard: off (--no-dashboard)` when the flag disabled it;
- `Dashboard: off (DASHBOARD_ENABLED=false)` when the environment did;
- `Dashboard: off (bind failed)` when REQ-V160-SRV-07's guard fired.

The first seven lines and their order are unchanged, which is why
`tests/test_v1_guardrails.py:1138-1145`'s indexed assertions need no amendment.

**REQ-V160-SRV-10 (MUST) — the server is not a feature of the agent.** No agent
behaviour, no prompt, no tool schema and no tool output depends on whether the
dashboard is running. Running with `--no-dashboard` and running without it MUST
produce identical bot replies and identical database rows for the same input;
`T-V160-SRV-07` proves it.

**REQ-V160-SRV-11 (MUST) — the `Host` header is checked, because loopback bind
is not an origin check.** Binding to `127.0.0.1` stops a remote socket; it does
not stop a browser that a DNS-rebinding page has pointed at `127.0.0.1` while
keeping an attacker origin. CSP hardens what a rendered page may load; it
authenticates nothing inbound. Therefore:

> HTTP/1.1 requests MUST contain exactly one `Host` header equal to
> `127.0.0.1:<actual_port>`; duplicates, other values, userinfo,
> whitespace/control characters and absolute-form request targets receive a
> fixed 400 response. The rejected value is never logged or echoed.

`<actual_port>` is `server.server_address[1]`, so a port-0 test compares against
the assigned port. The check runs **before** routing: a bad `Host` on an
unlisted path is 400, not 404. The body is the fixed `{"error": "invalid host"}`
for `/api/*` and `dashboard_render.invalid_host_page()` elsewhere, both with the four headers
of REQ-V160-SRV-04, neither naming the value; `log_message` records the
rejection as a route name only. `localhost:<port>` is rejected too —
REQ-V160-SRV-09's startup line prints the `127.0.0.1` URL the operator must use.
`T-V160-SRV-10` proves it and kills `v160-host-check-disabled`.

---

## 10. Tool quality (TQ)

Two behaviour changes and six scenarios, both declared benchmark-affecting by
REQ-V160-EC-06 and the reason §11 records a fresh baseline.

**REQ-V160-TQ-01 (MUST) — a truncated summary is never a summary.** Today a summary
response with `finish_reason == "length"` is parsed anyway: `_parse_summary`
returns nothing usable and the turn proceeds with **zero summary rows and no
goal**, uncounted. That is S12's historical flakiness.

The new rule, in `_ask_for_summary` (agent.py:792-817) and its caller:

1. A summary response with `finish_reason == "length"` is **rejected without
   parsing**. It is recorded in `llm_calls` with `purpose = "summary"`,
   `round = 0`, `attempt = 1`, `error_kind = "truncated"`, and the span carries
   `tg_agent.summary.truncated = true`.
2. The call is retried **exactly once**, with the larger budget
   `cfg.llm_summary_max_tokens` (REQ-V160-TQ-02) and otherwise identical inputs.
   The retry is recorded with `attempt = 2`.
3. If the retry also ends with `finish_reason == "length"`, it is recorded with
   `error_kind = "truncated"` and the turn **proceeds without a summary** — the
   user is not blocked and no exception escapes. The failure is counted by
   `metrics.summary_health` and surfaced on `/stats` (REQ-V160-MET-05) and on
   `/tools` (REQ-V160-DSH-03).
4. There is **no second retry**. `error_kind = "truncated"` is a new value in an
   existing free-text column and needs no schema change.

The mutation `v160-truncated-summary-accepted` MUST be killed by
`T-V160-TQ-01`.

**REQ-V160-TQ-02 (MUST) — `LLM_SUMMARY_MAX_TOKENS`, sized against the timeout
budget.** New environment variable, parsed in the existing style:

```python
llm_summary_max_tokens = _parse_int(source, "LLM_SUMMARY_MAX_TOKENS", 1536, 256, 8192)
```

onto `Config.llm_summary_max_tokens: int = 1536`.

**Why 1536.** What must grow is `agent.py:44`'s `SUMMARY_MAX_TOKENS = 512`, not
`LLM_MAX_TOKENS`. `config.py:357`'s `_check_timeout_budget(llm_timeout_s,
llm_max_tokens)` enforces `llm_timeout_s >= 21.1 + 0.093 × tokens`; with
`LLM_MAX_TOKENS` 2048 (config.py:270) and `LLM_TIMEOUT_S` 240.0 the floor is
≈ 211.6 s, ≈ 28 s of headroom. A budget of 2560 would raise it to ≈ 259 s, above
the default timeout, so every deployment that had not raised `LLM_TIMEOUT_S`
would fail to start with a `ConfigError`, breaking REQ-V160-EC-05. **1536** is
three times the starving value, below
`LLM_MAX_TOKENS`'s default, and leaves the floor exactly where it is today.

`_check_timeout_budget` is nevertheless extended to stay honest about what the
process can actually request:

```python
_check_timeout_budget(llm_timeout_s, max(llm_max_tokens, llm_summary_max_tokens))
```

At default configuration `max(2048, 1536) == 2048` and the floor is unchanged. An operator who raises
`LLM_SUMMARY_MAX_TOKENS` above `LLM_MAX_TOKENS` gets the higher floor and a
`ConfigError` naming both variables if `LLM_TIMEOUT_S` is too small for it. The
error message names the variable the operator must raise, not just the floor.

Plumbing: **two** budgets, one keyword being unable to say "512 first, the
configured value on retry" — `summarize_conversation(..., *, max_tokens: int =
SUMMARY_MAX_TOKENS, retry_max_tokens: int = SUMMARY_MAX_TOKENS)`, and
`_ask_for_summary` the same pair. Attempt 1 requests `max_tokens`;
`retry_max_tokens` is requested **only** after `finish_reason == "length"`.
`bot.py` passes `retry_max_tokens=cfg.llm_summary_max_tokens` and nothing else,
so attempt 1 stays at 512 and every existing caller, fake and test keeps today's
behaviour (`T-V160-TQ-02`).

**REQ-V160-TQ-03 (MUST) — the outcome vocabulary is closed.** `agent.py` gains

```python
TOOL_OUTCOMES = ("ok", "error", "budget", "rejected", "refused_repeat")
```

`"ok"` and `"error"` come from `_tool_outcome` (agent.py:574-583), `"budget"`
from the `TOOL_EXECUTION_LIMIT` path (:560), `"rejected"` from the excess-call
path (:569); `"refused_repeat"` is new (REQ-V160-TQ-04). `_record_tool_call`
asserts membership before writing: an unknown outcome raises rather than
landing in the database. `T-V160-TQ-03` covers all five, each also in `metrics.tool_health`.

**REQ-V160-TQ-04 (MUST) — the repeat-failure refusal.** The agent stops in code
a model that repeats an identical failing call.

**Call key.** The refusal is decided **before** the call runs, so its key carries
only pre-execution information:

```
call_key = sha256(tool_name + "\x00" + canonical_arguments).hexdigest()
```

- `tool_name` is `_wire_name(call)` — the vetted name already written to
  `tool_calls.tool`, never the model's raw string (REQ-V12-ID-01 item 4);
- `canonical_arguments` is `json.dumps(parsed_arguments, sort_keys=True,
  separators=(",", ":"), ensure_ascii=False)` when the arguments parse as a JSON
  object, and the raw argument string otherwise. Key order must not change
  `call_key`.

**State.** A `dict[tuple[str, str], int]` scoped to **one user message**, keyed
by `(call_key, normalized_error_class)` and incremented per `outcome = "error"`
call. `normalized_error_class` — that call's error-envelope `"error"` value,
lower-cased, non-alphanumeric runs collapsed to `_`, stripped, truncated to
**64** characters — is **diagnostic only**: the class of a call that has not run
cannot be known. Created with the root span, discarded when it ends; never
persisted, never shared between conversations, never surviving a restart.

**The rule.** `TOOL_REPEAT_REFUSAL_THRESHOLD = 2`. When one `call_key` has
already **failed twice** within the current user message — summed over its error
classes — the third call with that `call_key` is **not executed**. Instead the
agent injects a tool result
that is a fixed, deterministic envelope:

```json
{"error": "refused: this exact tool call already failed twice in this message; report the failure to the user instead of repeating it"}
```

and records the attempt with `outcome = "refused_repeat"`, `duration_ms = 0`,
and the span attribute `tg_agent.tool.fingerprint` set to the **first 16 hex
characters of `call_key`**. The refusal counts toward
`TOOL_EXECUTION_LIMIT` exactly as an execution would.

`/tools` shows the `refused_repeat` count per tool (REQ-V160-DSH-03).

The mutation `v160-fingerprint-threshold-off-by-one` MUST be killed by
`T-V160-TQ-04`.

**Provenance for the risk this manages.** At the v1.3 candidate, scenario S09
moved from 2 tool calls and 5 LLM calls to 4 and 7, and S12 dropped to 0 tool
calls — a quality regression the token totals alone did not show, and what
`max_consecutive_repeats` and `refused_repeat` make visible.

**REQ-V160-TQ-05 (MUST) — six new scenarios, S13…S18.** Appended to
`SCENARIOS` in `devtools/bench_scenarios.py` (list at :148-263), in the existing
style, using the existing `Check` factories (`answer_regex`,
`answer_not_regex`, `answer_max_chars`, `tool_used`, `json_keys`,
`exit_code_seen`, `no_tools`, `summary_exists`) plus the one new factory of
REQ-V160-TQ-06. No existing scenario's `id`, `title`, `turns` or `checks` may
change.

They are **literal**, and this block is the specification — appended verbatim,
in order, to the end of `SCENARIOS`:

```python
    Scenario(
        id="S13",
        title="multi-step-exec",
        turns=[
            "Через exec создай файл calc.py, который печатает сумму целых "
            "чисел от 1 до 100. Затем вторым вызовом exec запусти его через "
            "python3 и назови полученное число.",
        ],
        checks=[tool_used("exec"), answer_regex(r"\b5050\b"), tool_calls_max(4)],
    ),
    Scenario(
        id="S14",
        title="error-recovery",
        turns=[
            "Выполни через exec ровно этот argv: "
            '["python3", "-c", "print(2 ** )"]. В нём синтаксическая ошибка. '
            "Исправь её так, чтобы печаталось 2 в степени 10, перезапусти и "
            "назови результат одним числом.",
        ],
        checks=[
            tool_used("exec"),
            exit_code_seen(nonzero=True),
            answer_regex(r"\b1024\b"),
            tool_calls_max(4),
        ],
    ),
    Scenario(
        id="S15",
        title="big-output-answer",
        turns=[
            "Через exec выведи числа от 1 до 1000, по одному в строке. Вывод "
            "будет обрезан. Всё равно определи, сколько всего строк было "
            "выведено, и назови это число.",
        ],
        checks=[
            tool_used("exec"),
            answer_regex(r"\b1000\b"),
            answer_max_chars(900),
            tool_calls_max(3),
        ],
    ),
    Scenario(
        id="S16",
        title="skill-then-exec",
        turns=[
            "Загрузи скилл host-info и выполни ту команду, которую он "
            "предписывает для версии Python. Назови только номер версии.",
        ],
        checks=[
            tool_used("load_skill"),
            tool_used("exec"),
            answer_regex(r"\b3\.\d+(\.\d+)?\b"),
            tool_calls_max(4),
        ],
    ),
    Scenario(
        id="S17",
        title="fetch-then-exec",
        turns=[
            "Сделай fetch на https://wttr.in/Berlin?format=3, затем через exec "
            "посчитай, сколько символов в полученной строке. Ответь так: "
            "сначала слово Berlin, затем число символов.",
        ],
        checks=[
            tool_used("fetch"),
            tool_used("exec"),
            answer_regex("Berlin|Берлин"),
            answer_regex(r"\b\d{1,4}\b"),
            tool_calls_max(4),
        ],
        network=True,
    ),
    Scenario(
        id="S18",
        title="multi-turn-summary",
        turns=[
            "Запомни: проект называется Vega, дедлайн 3 ноября.",
            "Как называется проект? Ответь одним словом.",
            "Какой дедлайн? Ответь одной строкой.",
            "/new",
        ],
        checks=[
            answer_regex("Vega|Вега", turn=2),
            answer_regex(r"3\s*нояб|11", turn=3),
            summary_exists,
            tool_calls_max(3),
        ],
    ),
```

Facts the block rests on, each measured in the repository:

- **No fixture, setup or cleanup file exists or may be added.** `Scenario` has
  exactly `id`, `title`, `turns`, `checks`, `network` (:104-109). The harness
  gives every run a fresh `sandbox/`, `bot.db` and `audit.jsonl`, wipes
  `.bench/` at the start of `run` and deletes a clean run's directory, so S13,
  S14 and S15 create everything they need inside their own sandbox and nothing
  survives.
- **S16's skill already exists**: `skills/host-info.md`, the one S07 loads. It
  prescribes `["python3", "--version"]`, so the regex matches the version the
  sandbox prints and survives an image bump (REQ-V160-NG-15 forbids one anyway).
  No skill file is created; `skills/` holds `host-info.md` and `weather.md`.
- **S17 reuses S08's network fixture**, the only URL any scenario fetches, on
  the only domain `config.DEFAULT_FETCH_DOMAINS` allows (REQ-V160-NG-12). The
  assertions survive a weather change: `Berlin` is the substring S08 already
  relies on, and the second regex asserts that a character **count** exists,
  never its value. The existing `wttr.in` preflight (bench.py:666-667) — the very
  check S08 uses — MUST **succeed** before the smoke run and again before the
  baseline; a failure stops the run there, so no smoke or baseline document ever
  records S17 in `meta.skipped_scenarios`. The response's HTTP
  status and byte length are recorded in the **report** (REQ-V160-RPT-02.7), not
  in the bench document, whose key sets REQ-V160-BEN-03 freezes.
- **S18's summary precondition is the `/new` turn.** This codebase has no
  automatic summarisation threshold: `summarize_conversation` is reached only
  from `_handle_new` (bot.py:719-724) and `_handle_summary` (:739-746), each
  guarded by `len(load_context_messages(...)) >= 2`. Three answered turns leave
  six context messages, so `/new` summarises; `/new` is not a countable turn,
  which is why `turn=2` and `turn=3` mean what they mean in S12.
- `no_tools` and `summary_exists` are module-level **values**, not factories.
  There is **no** `file_exists` factory and none is added.

**Gate per new scenario**: **3 successes out of 3 repeats** at the default
`--repeats`, with the `tool_calls_max` check green in each. A skip, or fewer
than 3/3, for any of S13…S18 is a **blocking baseline failure**: repair it
before the baseline, or — if it surfaces during T16 — **void the run** and rerun
after the repair. There is no "or a recorded finding" escape anywhere.

**REQ-V160-TQ-06 (MUST) — a tool-call ceiling is a new check kind.** There is
**no** existing field bounding tool calls: `Check` (bench_scenarios.py:42-62) has
`kind`, `turn`, `pattern`, `max_chars`, `tool`, `json_pairs`, `nonzero`, and
`max_chars` is a **character** cap on an answer string. `Scenario`
(:104-111) has `id`, `title`, `turns`, `checks`, `network` and nothing else.
Verified by exhaustive read; anything named `expected_tool_calls_max` does not
exist and must not be invented under that name.

Therefore:

- `Check` gains one field, `max_calls: int = 0` — additive, defaulted, so every
  existing `Check` construction is untouched;
- a new kind `"tool_calls_max"` is added to the kinds tuple (:19-31) and is
  **not** a member of `ANSWER_KINDS` (:36);
- a factory `tool_calls_max(n: int) -> Check` returns
  `Check(kind="tool_calls_max", max_calls=n)` and raises `ValueError` for
  `n < 1`;
- `Scenario.__post_init__` (:112-141) is unchanged: the new check carries
  `turn=None`, which its existing validation already permits;
- **evaluation lives in `bench.py`**, as the module comment at
  `bench_scenarios.py:9-11` requires. The check passes when the number of
  `tool_calls` rows recorded for that scenario run — every outcome included,
  `rejected` and `refused_repeat` among them — is `<= max_calls`.

`T-V160-TQ-05` asserts all four points.

**REQ-V160-TQ-07 (MUST) — the scenario catalogue stays self-validating.**
`_validate_catalog` (bench_scenarios.py:266-274) already rejects duplicate ids at
import; it is extended to reject a `tool_calls_max` check whose `max_calls` is
below the count of distinct `tool_used` checks in the same scenario.

**REQ-V160-TQ-08 (MUST) — the two behaviour changes are individually
switchable in tests, never in production.** `TOOL_REPEAT_REFUSAL_THRESHOLD` and
the truncation retry have **no** environment variable and **no** configuration
flag. Tests exercise them by constructing the agent with scripted responses, not
by disabling them (REQ-V160-NG-09).

---

## 11. Baseline and benchmark (BEN)

**REQ-V160-BEN-01 (MUST) — a fresh baseline is a deliverable of this release.**
Adding S13…S18 changes the bytes of `devtools/bench_scenarios.py`, and
`scenarios_sha256()` (bench.py:195-201) hashes exactly those bytes. Every
document recorded against the old file therefore stops matching
(bench.py:1026-1028). Combined with REQ-V160-EC-06's two behaviour changes, the old baseline is non-comparable by construction.

```bash
uv run --locked python devtools/bench.py run --tag baseline-v1.6.0 --repeats 3 \
  --out .bench/baseline-v1.6.0/baseline-v1.6.0.json
```

All eighteen scenarios, default repeats, provider `lmstudio`, against the
LM Studio instance REQ-V160-PRE-03 resolved. Expected wall clock **≈ 40 minutes**;
expected marginal cost **$0.00** — local inference. The resulting JSON is copied
to `docs/assets/bench/baseline-v1.6.0.json` and **committed**; `.bench/` stays
git-ignored and `docs/assets/bench/*.log` stays git-ignored, exactly as today.

It runs at **T16**, after REQ-V160-BEN-07's two preconditions. The report records
the instrument of REQ-V160-PRE-04, per-scenario successes, the `tool_calls_max`
results for S13…S18, tokens, cost and wall clock (REQ-V160-RPT-02.7); `meta`
carries the locked instrument fields (REQ-V160-BEN-05).

**REQ-V160-BEN-02 (MUST) — the old baseline is informational, and labelled so.**
`docs/assets/bench/baseline-v1.4.json` is **kept** and is re-rendered against the
new one for the S01–S12 subset as an **informational** comparison in the report.
It is **not** a gate, and no verdict, threshold or exit code depends on it. The
comparison's caption states, in the report, that the two documents differ in
`bench_schema`, in `scenarios_sha256`, in the scenario set and in two agent behaviours — a delta is a hint, not a measurement. The
cost/quality gate belongs to v1.7.0 (REQ-V160-NG-02).

**REQ-V160-BEN-03 (MUST) — `bench_schema` 1 → 2, with a readable past.**
`BENCH_SCHEMA` (bench.py:70) becomes **2**, and each run in `runs` gains a
`spans` array alongside its existing `llm_calls` and `tool_calls` arrays.

- `SPAN_ROW_KEYS = frozenset(storage.SPAN_COLUMNS) - {"conv_id",
  "attributes_json"} | {"conv_seq", "attributes"}` — derived as `LLM_ROW_KEYS`
  and `TOOL_ROW_KEYS` are (bench.py:165-166) so it widens with the schema, and
  subtracting `attributes_json` because REQ-V160-BEN-04 emits the parsed object
  under `attributes`. Document and validator therefore agree by construction.
- `REQUIRED_SPAN_ROW_KEYS` is a **literal** tuple, following
  `REQUIRED_LLM_ROW_KEYS` (bench.py:168-182): the required set must not move
  when the schema does. It names **`attributes`**, never `attributes_json`,
  which appears in no key set in `bench.py`.
- `REQUIRED_LLM_ROW_KEYS` itself is **unchanged** — `trace_id` and `span_id` are
  **not** added to it. That is what keeps `tests/test_v14_patch.py`'s
  hand-authored 25-key v1.3-shaped row valid, and that test therefore needs no
  amendment.

`_validate` (bench.py:1012) gains a keyword-only `mode` of `"strict"` (the
default, today's behaviour exactly) or `"informational"`:

| condition | `strict` | `informational` |
|---|---|---|
| `bench_schema` | must equal `BENCH_SCHEMA` | must be in `(1, 2)` |
| `scenarios_sha256` mismatch | `_Invalid`, exit 1 | collected as a **note**, not raised |
| `runs[].spans` | required when schema is 2 | required when schema is 2, skipped when 1 |
| everything else | unchanged | unchanged |

`check_document(document, scenarios=None, *, mode="strict")` keeps its signature
and its default, so every existing caller is unaffected.

- **`bench.py check <path>`** stays strict.
- **`bench.py report --gate …`** stays strict, and still returns
  `EXIT_NOT_COMPARABLE` (2) for a mismatch.
- **`bench.py report` without `--gate`** validates in `informational` mode and,
  when any note was collected, prints to **stderr** before the report:
  `informational comparison: <note>; deltas are indicative, not measured`. It
  then renders and exits 0.

**REQ-V160-BEN-04 (MUST) — the spans travel with the run.** For each scenario
run, the harness collects the `spans` rows whose `trace_id` belongs to that run —
the traces whose root span carries the matching `tg_agent.scenario_id` and
`tg_agent.bench_tag` (REQ-V160-TRC-11) — and serialises them with `conv_id`
replaced by `conv_seq`, exactly as the existing row families are (bench.py:165).
`attributes_json` travels as the **parsed object** under the key `attributes`,
not as an embedded JSON string. Content attributes are absent unless
`OBS_CAPTURE_CONTENT` was true during the run, and the report records which.

**REQ-V160-BEN-05 (MUST) — `meta` records the instrument, and the instrument is
locked.** A version string alone cannot tell two materially different
instruments apart. `meta` (bench.py:671-685, extended by `_cmd_run` at
:2131-2140) gains **six** keys; `LOCKED_META_FIELDS` (bench.py:147-155, ten
entries today) gains those same **six**:

| key | value |
|---|---|
| `git_commit` | `git rev-parse HEAD` at run start — **already in `meta`**, and provenance **outside** `LOCKED_META_FIELDS`: a candidate is always a later commit than its baseline, so locking it would exit `EXIT_NOT_COMPARABLE` on every pair |
| `lmstudio_version` | PRE-04's operator string; `null` off `lmstudio` |
| `served_model_id` | PRE-04's `data[].id`; `null` off `lmstudio` |
| `lmstudio_context_length` | PRE-04's **loaded** length; `null` off `lmstudio`. Not the existing `context_length`, which is `LMSTUDIO_CONTEXT_LENGTH` off `Config` and is locked already |
| `generation_settings` | **purpose-specific**, off the payload paths: `build_payload` (llm/base.py:112-129) sends `tools`/`tool_choice` **only when `tools is not None`** (`agent.py:246` passes `None` on the final round), `_ask_for_summary` (:805) always passes `None` at `SUMMARY_MAX_TOKENS = 512` (agent.py:45). `{"agent":{"temperature":0,"max_tokens":<cfg.llm_max_tokens>,"stream":false,"tool_choice":"auto"},"summary_initial":{"temperature":0,"max_tokens":512,"stream":false},"summary_retry":{"temperature":0,"max_tokens":<cfg.llm_summary_max_tokens>,"stream":false},"provider_defaults":["seed","stop","top_p"]}` — the last names what is sent nowhere |
| `prompt_tools_sha256` | `sha256` of the system prompt concatenated with `json.dumps(<exposed tool schema>, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` |
| `obs_capture_content` | `cfg.obs_capture_content` (REQ-V160-TRC-09) |

`scenarios_sha256`, `config_sha256` and `constants` — the last already carrying
`llm.base.REQUEST_DEFAULTS` verbatim — stay locked as they are. A field that
differs **or that one side omits** makes the pair non-comparable:
`comparability` (bench.py:1291-1320) already returns `"locked meta field
differs: <name>"`, and `report --gate` exits `EXIT_NOT_COMPARABLE` (2).

**A dirty tree refuses a baseline.** `bench.py run` exits `EXIT_ERROR` when
`git status --porcelain` is non-empty and `--tag` begins with `baseline-`;
`git_commit` would otherwise name a commit that is not what ran. Other tags,
`smoke-v160` included, are unaffected. REQ-V160-BEN-02 is untouched: the v1.4
comparison is informational and never passes `--gate`.

**REQ-V160-BEN-06 (MUST) — the static report is regenerated from the new
baseline, inside T16's one commit.** EC-10 gives T16 one commit and TREE-01 both
artefacts in it, so the order is fixed: run the baseline into `.bench/`, copy it
to `docs/assets/bench/baseline-v1.6.0.json`, render from **that copy**

```bash
uv run --locked python devtools/dashboard.py \
  docs/assets/bench/baseline-v1.6.0.json --out docs/assets/dashboard-v1.6.0.html
```

produce REQ-V160-BEN-02's informational S01–S12 comparison, then commit every
T16 artefact together.

**REQ-V160-BEN-07 (MUST) — the baseline is recorded last, over a frozen tree.**
§17 puts the baseline **after** the mutation entries and the re-measured
timeouts (T13), after the clean-context review and every fix it produces (T14),
and after the full offline gates and the LM Studio preflight (T15). **T15 is the
first task permitted to run inference, limited to the fixed preflight and
`smoke-v160`; T16 is the first permitted to record a baseline.** What it records
is a **post-change baseline**, not a before/after pair (EC-06).

Three preconditions, all blocking. T16 does not start until (1) the catalogue
validates — `_validate_catalog` imports cleanly and `bench.py check <path>`
exits 0 on a recorded document; there is no `validate` sub-command, `run`,
`report` and `check` are the three (bench.py:1810-1830); (2) the `wttr.in`
network preflight of REQ-V160-TQ-05 **succeeds**, before the smoke run and again
before the baseline; and (3) one **non-baseline smoke run** executes all six new
scenarios, none skipped:

```bash
uv run --locked python devtools/bench.py run --tag smoke-v160 \
  --only S13,S14,S15,S16,S17,S18 --repeats 1 --out .bench/smoke-v160.json
```

`--only` is one comma-separated string, not a repeated flag (bench.py:1904-1912).
The smoke document is never committed and never a baseline; its non-`null`
`meta.only` makes it non-comparable. A scenario that cannot execute is fixed
here, voiding nothing, because no baseline exists yet.

**After the baseline task, only report and evidence files may change. Any
source, test, config, prompt, scenario, tool schema, model setting or
inference-setting change voids the baseline and requires the complete baseline
run again** — its full ≈ 40 minutes, with the re-run and its trigger reported.

---

## 12. Semantic versioning and the CLI (VER)

**REQ-V160-VER-01 (MUST) — one version, one source.** `pyproject.toml`'s
`project.version` moves from `"0.1.0"` to `"1.6.0"` and is the **single source of
truth**. `bot.py` reads it at call time with the standard library:

```python
def _read_version() -> str:
    path = config.PROJECT_ROOT / "pyproject.toml"
    with path.open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]
```

`importlib.metadata` is **not** an option: `[tool.uv] package = false` means the
project is never installed as a distribution, so `version("tg-agent-bot")` raises
`PackageNotFoundError`. The path is anchored at `config.PROJECT_ROOT`, never `os.getcwd()`. A missing file,
missing `[project]` table or missing `version` key raises `RuntimeError` naming
the path; `--version` then prints it to **stderr** through `config.redact()` and
returns **2**. `--version` prints exactly `tg-agent-bot 1.6.0` — name, space,
version, newline, nothing else. `T-V160-VER-01` compares the printed string
against an independent `tomllib` read, not a literal, and kills the mutation
`v160-version-literal-not-pyproject`.

**REQ-V160-VER-02 (MUST) — the policy.**

| bump | meaning here |
|---|---|
| **MAJOR** | a break in the bot's contract: a command removed or renamed, an environment variable removed or given incompatible semantics, a storage schema change needing manual migration, a tool removed from the exposed set |
| **MINOR** | a spec release — new capability, new commands, new environment variables, an additive schema migration, new scenarios |
| **PATCH** | a fix with no new spec: a defect repaired, a pin moved, a document corrected |

**Historic labels map to SemVer for documentation only.** No retroactive tags
are created and the two existing tags `v1.3` and `v1.3-baseline` stay exactly as
they are:

| historic label | SemVer | note |
|---|---|---|
| v0 | 0.1.0 | the initial spec release |
| v1 | 1.0.0 | first complete agent |
| v1.1 | 1.1.0 | |
| v1.2 | 1.2.0 | |
| v1.3 | 1.3.0 | tags `v1.3`, `v1.3-baseline` exist |
| v1.4 | — | **no release**: RSN-06 STOP, verdict FAIL |
| v1.5 | 1.5.0 | |
| v1.5.1 | 1.5.1 | |
| **this release** | **1.6.0** | |

**REQ-V160-VER-03 (MUST) — the CLI grammar.** `bot.py:61`'s `USAGE` becomes

```
usage: bot.py [--selftest|--selftest-live|--version] [--no-dashboard]
```

and `main(argv)` (bot.py:1306-1321) replaces its two exact-match comparisons
with this grammar, hand-parsed with no `argparse` (the module has none today and
the grammar is four tokens):

| invocation | behaviour |
|---|---|
| *(no arguments)* | the default run: polling **and** the dashboard |
| `--no-dashboard` | the default run with the dashboard suppressed |
| `--selftest` | offline selftest; **binds no port**; exit code unchanged |
| `--selftest-live` | live selftest; **binds no port**; exit code unchanged |
| `--version` | prints `tg-agent-bot <version>` to stdout, exits **0** |
| anything else | prints `USAGE` to stdout, exits **2** |

Rules: `--selftest`, `--selftest-live` and `--version` are **mutually
exclusive** — any two together print `USAGE` and exit 2. **Only**
`--no-dashboard` combines, and only with the default run: `--selftest
--no-dashboard` is an error. A
repeated flag is an error; so is any unknown token or positional argument. Exit
code 2 for a usage error is today's behaviour
(`tests/test_v1_guardrails.py:1397`) and does not change; the asserted usage
**string** does (§15.1).

**REQ-V160-VER-04 (MUST) — the tag is created last, on the evidence-only
commit.** A commit cannot record its own SHA and a tag cannot point at a commit
that does not exist yet, so the order is fixed:

1. **T18 runs every acceptance command** of REQ-V160-ACC-03 against the final
   tree;
2. the **evidence-only commit** lands, touching `docs/reports/*` and nothing
   else. It records `<implementation-tip>`, the replay output, and the
   **intended tag name** `v1.6.0` — never a claim that the tag already exists;
3. the annotated tag is created **on that commit**, and only then:

```bash
git tag -a v1.6.0 -m "tg-agent-bot 1.6.0 at <evidence-commit-sha>"
```

The tag name and target SHA live in the annotated-tag message and in T18's
operator acceptance output; **no further commit records them**, there being none
and none permitted (REQ-V160-ACC-03's freeze). Nothing is pushed, and `v1.3` and
`v1.3-baseline` are never moved or deleted.

**REQ-V160-VER-05 (MUST) — naming from here on.** Specs, reports and prompt
slugs carry three numbers: `docs/spec/spec-v1.6.0.md`,
`docs/reports/report-v1.6.0.md`, `docs/reports/tg-post-v1.6.0.md`,
`docs/prompts/NN-v160-*.md`. Existing two-number filenames are **not** renamed (REQ-V160-NG-16).

**REQ-V160-VER-06 (MUST) — `AGENTS.md` and `README.md` learn the version.**
`README.md` gains the `## Versioning` section (the policy table, the historic
map, `--version`, the tag convention). `AGENTS.md` gains the three new top-level
modules to its project-layout list, the four new environment variables where it
lists configuration, the new gate to its gate section, and the re-measured test
count — each in the same commit as the change it describes, per the spec-sync
rule.

---

## 13. Reporting (RPT)

**REQ-V160-RPT-01 (MUST) — the report carries the ledger row.** REQ-V160-EC-01
forbids the executor to write the lab-root `economics.md`, so
`docs/reports/report-v1.6.0.md` MUST contain a section **"Ledger row
(paste into `economics.md`)"** holding one fenced, ready-to-paste table row
matching the ledger's column order exactly:

```
| Project | Ver | Date | Spec (tokens) | Prompts | First run | Bugs | Tokens ↑/↓ | Cost | Model | Harness |
```

`Ver` is **`1.6.0`**. The row uses the link form
`[tg-agent-bot](https://github.com/axyi/tg-agent-bot)` and every cell is filled
from this run's evidence — no `TBD`, no placeholder. "Spec (tokens)" carries both
the estimate and the measured byte count. The operator pastes it, never the executor.
`checks.py lint-docs` enforces the section's presence and
the cell count (REQ-V15-RPT-03, unchanged).

**REQ-V160-RPT-02 (MUST) — the report.** Beyond the project standard,
`report-v1.6.0.md` carries:

1. the gates table — the six verbatim commands plus every gate of §14, with
   command, profile and exit code;
2. the **measured** test count at HEAD before and after, against the 843 floor;
3. the mutation summary: `mutation-all` entry count, kills and wall clock, and
   the `mutation-v160` subset separately, with the **re-measured** timeouts and
   the arithmetic that produced them (REQ-V160-GATE-02);
4. the committed spec's T0 `sha256`, unchanged at T18 (REQ-V160-PRE-01.1); the
   `.env` interaction record of REQ-V160-EC-04; the `--no-verify` attestation of
   REQ-V160-EC-09, `<base>`,
   `<implementation-tip>`, and `checks.py replay --range <base>..<implementation-tip>`
   output — **the last two recorded by the evidence-only commit, not the
   provisional report** (REQ-V160-ACC-03);
5. per task, whether the RLM rule was applied and to what (REQ-V160-EC-07);
6. **Benchmark-affecting changes**: the two declared in REQ-V160-EC-06, plus any
   discovered, with the disposition of each, and EC-06's statement that this is a
   post-change baseline, not a before/after pair;
7. the baseline: LM Studio **version** (exact string), served **model id**, the
   **loaded** context length, the generation settings actually sent,
   `prompt_tools_sha256`, the `OBS_CAPTURE_CONTENT` state and the repository
   commit SHA (REQ-V160-BEN-05); the inference-preflight result
   (REQ-V160-PRE-04); for S17, the fetched response's **HTTP status and byte
   length** (REQ-V160-TQ-05); the `smoke-v160` result;
   per-scenario successes, `tool_calls_max` results for S13…S18,
   tokens, cost, wall clock, and the informational S01–S12 comparison against
   `baseline-v1.4.json` with its four-reason caption (REQ-V160-BEN-02);
8. the resolved values of §6's two VERIFY markers and the confirmed span-name
   rule `invoke_agent {gen_ai.agent.name}`, with the upstream document version
   and URL, and whether the GenAI conventions were still
   `development`-stability and still in `open-telemetry/semantic-conventions-genai`
   at run time (REQ-V160-PRE-02);
9. the dashboard evidence: the startup log line, the `/status` line, the canary
   sweep result, and the port used;
10. the **intended** tag name `v1.6.0`, recorded by the evidence-only commit as
    an intention and never as an accomplished fact; the tag's target SHA and the
    `git tag -a` message belong to T18's operator acceptance output, not to any
    commit (REQ-V160-VER-04);
11. scanner summary: gitleaks, trivy, semgrep findings and skylos shadow
    findings, each **fixed, not suppressed**; any suppression quoted with the
    code comment citing its REQ id (REQ-V160-GATE-04);
12. fix cycles used against the budget of 5;
13. **Deviations**, per REQ-V12-REP-02, process deviations included; "None" only
    when true.

**REQ-V160-RPT-03 (MUST)** Usage rows are appended per prompt to
`docs/llm-usage.md`'s existing table, never as a headerless fragment.
`docs/reports/tg-post-v1.6.0.md` is **Russian** and **under 1500 characters** by
`wc -m`; the report quotes the count.

**REQ-V160-RPT-04 (MUST)** `AGENTS.md`'s Stack, project layout, gate list and
Benchmark sections, `README.md`'s new sections, and `docs/plan.md`'s milestone
and test count are updated in the same commits as the changes they describe.

---

## 14. Gates

**REQ-V160-GATE-01 (MUST) — the six existing gates, verbatim and in order.**
Restated from `AGENTS.md`; **not one character changes**:

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

Gates 1–4 and 6 are unconditional and offline. Gate 5 requires the §3
preconditions and is executed at **T15** and again at T18, never at T0
(REQ-V160-PRE-04); an unreachable LM Studio is then a **blocked run**. The test count
MUST exceed the number measured at T0 (floor 843); state the
exact number in the report.

**REQ-V160-GATE-02 (MUST) — one new gate, and two re-measured timeouts.**
`config/quality_gates.yaml` gains exactly one gate:

```yaml
  mutation-v160:
    kind: command
    argv: [uv, run, --locked, python, devtools/mutation_check.py, --select, v160-]
    result_mode: exit_status
    blocking: true
    timeout_seconds: <2 x measured, rounded up to the next 10 s>
```

placed in the **`pre-push`** profile, mirroring `mutation-v15` exactly. No
existing gate's `argv`, `result_mode`, `blocking`, `severity` or profile
membership changes.

Two timeouts are **re-measured**, not guessed, per
`config/quality_gates.yaml:202-211` (2× a measured direct run):

- `mutation-v160` — measure `uv run --locked python devtools/mutation_check.py
  --select v160-` on the final tree and set 2× the wall clock;
- `mutation-all` — currently `2600` for 72 entries at ≈ 1273 s measured; this
  release adds at least seven entries **and** grows the test suite, and the gate
  reruns the whole suite once per entry. Re-measure and reset.

**REQ-V160-GATE-03 (MUST) — the profile matrix.** This table is the
**authoritative** rendering of `quality_gates.yaml`'s `profiles:` block, and it
supersedes REQ-V15-GATE-11's table, which becomes a frozen historical record.
`tests/test_v15_standards.py`'s matrix test is repointed at **this** file
(§15.1) and asserts the two agree.

| gate | pre-commit | pre-push | full | note |
|---|:---:|:---:|:---:|---|
| `ruff check` (staged) | yes | — | — | `--force-exclude` |
| `ruff check .` (tree) | — | yes | yes | gate 2 |
| `ruff format --check` | yes | yes | yes | blocking on new files only, shadow elsewhere |
| branch-name check | yes | yes | yes | warn-only on `main` |
| commit-msg checks | own hook | — | via `replay` | REQ-V15-CC-01…03 |
| `gitleaks git --staged` | yes | — | — | staged secrets |
| `gitleaks dir` (tree) | — | yes | yes | tracked set, any severity, not diff-scoped |
| `uv sync --locked` | — | — | yes | gate 1 |
| `pytest` | — | yes | yes | gate 3 |
| `bot.py --selftest` | — | yes | yes | gate 4, offline, binds no port |
| `bot.py --selftest-live` | — | — | yes | gate 5; needs `.env`, Docker, LM Studio |
| `mutation_check.py --select v15-` | — | yes | — | 4 entries |
| `mutation_check.py --select v160-` | — | yes | — | **new**, ≥ 7 entries |
| `mutation_check.py` (all) | — | — | yes | gate 6, timeout re-measured |
| `trivy fs` | — | yes | yes | diff-scoped, HIGH/CRITICAL |
| `semgrep scan` | — | yes | yes | diff-scoped, ERROR |
| `skylos` | — | yes | yes | shadow |
| `install_hooks.py --check` | — | yes | yes | hook chain installed |
| `checks.py doctor` | — | yes | yes | pinned versions |
| `checks.py lint-docs` | — | — | yes | prompts + ledger row |

**REQ-V160-GATE-04 (MUST) — findings are fixed, not suppressed.** Any new
gitleaks, trivy, semgrep or skylos finding introduced by this release is
**fixed**. A suppression — a `# nosemgrep`, an allowlist entry, a `.trivyignore`,
a skylos exclusion — requires a code comment on the suppressing line citing the
REQ id that justifies it, and the report quotes both. `dashboard_server.py` is
the file most likely to draw findings; "it is bound to loopback" is a reason to
write the comment, not to skip it.

**REQ-V160-GATE-05 (MUST) — the dashboard does not slow the hooks.** The
`pre-push` profile's wall clock is measured three times and the median recorded
against the observational 180 s budget (REQ-V15-HOOK-04, unchanged: the budget
moves no gate). If `mutation-v160` pushes the median past it, that is reported as
a number, not fixed by demoting a gate.

Reporting success requires the **`full`** profile green **plus** the six commands
of REQ-V160-GATE-01 run verbatim in their own right; where the two disagree the
verbatim command wins.

### 14.1 Per-task reading map

Navigation aid **and** the authority for REQ-V160-EC-07's file-count threshold;
reading more is never a defect, reading less never releases a requirement. §1
(EC-01…10), §2 (AMEND-01), §4 (TREE-01…03) and §18 (NG-*) bind every task and are
not repeated per line. Sizes are of the v1.5.1 tree.

| T | spec sections | repository files and ranges | delegate? |
|---|---|---|---|
| **T0** | §3, §14 | `AGENTS.md` (6.9 KB), `config/quality_gates.yaml` profiles block (lines 7-31) | no |
| **T1** | §5 (TRC-01…03, -07), §4 | `config.py:118-135` (redact/register_secret), `config.py:455-540` (parse helpers) | no |
| **T2** | §5 (TRC-05, -06, -12), §6 (MET-02) | `storage.py:16-34` (constants, column tuples), `:37-100` (DDL fragments), `:141-216` (schema, migrations, init), `:176-197` (connect, permissions), `:573-592` (turn ids) | **yes** |
| **T3** | §5 (TRC-04, -08, -09, -10, -11) | `agent.py:25-44` (constants), `:245-295` (error path, turn id), `:560-620` (tool recording), `:640-700` (llm recording), `:790-820` (summary) | **yes** |
| **T4** | §6 (MET-01…07) | `metrics.py` (206 lines, whole), `bot.py:776-830` (`/status`, `/stats`) | no |
| **T5** | §7 (DSH-01…09) | `devtools/dashboard.py:259-630` (the render half) | **yes** |
| **T6** | §8 (API-01…06), §9 (SRV-01…11) | `config.py:180-320` (`load_config`), `storage.py:176-197` | no |
| **T7** | §9 (SRV-01, -02, -05, -09), §12 (VER-03) | `bot.py:55-65` (USAGE block), `:1300-1325` (`main`), `:776-803` (`_render_status`), `tests/conftest.py` (39 lines) | no |
| **T8** | §10 (TQ-01…03, -08) | `agent.py:40-46`, `:560-620`, `:790-820`; `config.py:265-275`, `:340-370` | no |
| **T9** | §10 (TQ-04) | `agent.py:520-620` (tool dispatch and recording) | no |
| **T10** | §10 (TQ-05…07) | `devtools/bench_scenarios.py` (274 lines, whole), `devtools/bench.py:1040-1200` (check evaluation) | **yes** |
| **T11** | §11 (BEN-03…05) | `devtools/bench.py:60-90`, `:140-200`, `:600-700`, `:1000-1040`, `:1850-1890` | **yes** |
| **T12** | §12 (VER-01…06), §16 | `pyproject.toml`, `README.md` (env table + Commands), `AGENTS.md`, `docs/plan.md` | **yes** |
| **T13** | §14, §15.4 | `devtools/mutation_check.py` **tail only** (`MUTATIONS` entries and `main()`), `config/quality_gates.yaml:200-235` | **yes** |
| **T14** | §16 (REV-01) | the reviewer's own clean context | n/a |
| **T15** | §3 (PRE-03, PRE-04), §14, §11 (BEN-07) | none — only commands run | no |
| **T16** | §11 (BEN-01, -02, -06, -07) | none — the tree is frozen; only commands run | no |
| **T17** | §13, §16 (ACC-01…03) | this run's own artefacts | no |
| **T18** | §16 (ACC-03), Appendix B | this run's own artefacts | no |

Any task whose actual reading exceeds its map crosses REQ-V160-EC-07 and is
delegated; the report records it either way.

---

## 15. Tests

**REQ-V160-TST-01 (MUST)** New tests live in `tests/test_v160_observability.py`,
`tests/test_v160_dashboard.py` and `tests/test_v160_tool_quality.py` unless
stated otherwise. They are offline and deterministic and touch no Docker daemon,
no network and no `.env` (REQ-V12-OFF-01's `conftest.py` guard, extended by
REQ-V160-SRV-05's bind guard). Server tests bind **port 0** on `127.0.0.1` and
read the assigned port back. Databases are `tmp_path` fixtures. Span and trace
ids are seeded deterministically where a test asserts on them.

**REQ-V160-TST-02 (MUST)** Test-first: each test below is written and observed to
fail **for the right reason** before its implementation exists; the report
records any case where a test passed before its code was written.

### 15.1 Amendments to existing tests (exhaustive)

This list is **complete**; any other existing test that fails means the change
is wrong.

| file:line | change | driven by |
|---|---|---|
| `tests/test_observability.py:431` | `assert storage.SCHEMA_VERSION == 3` → `== 4`; the table loop gains `"spans"` | REQ-V160-TRC-05 |
| `tests/test_observability.py:544` | `assert rows[0]["turn_id"] is None` → `assert rows[0]["turn_id"] == rows[1]["turn_id"] is not None` — the failed attempt now carries its round's turn id | REQ-V160-TRC-08 |
| `tests/test_bench.py:111` | `fake_doc`'s `"bench_schema": 1` → `bench.BENCH_SCHEMA`, so the helper follows the constant instead of pinning a number | REQ-V160-BEN-03 |
| `tests/test_dashboard.py:136` | the `document()` helper's `"bench_schema": 1` → `bench.BENCH_SCHEMA` | REQ-V160-BEN-03 |
| `tests/test_dashboard.py:502` | the parametrised "unreadable document" case `{"bench_schema": 2, …}` → `{"bench_schema": 3, …}`; 2 is now valid and 3 is not | REQ-V160-BEN-03 |
| `tests/test_v1_guardrails.py:1398` | the asserted usage string becomes `usage: bot.py [--selftest|--selftest-live|--version] [--no-dashboard]` | REQ-V160-VER-03 |
| `tests/test_v15_standards.py:1726` | the matrix test reads the committed `docs/spec/spec-v1.6.0.md` instead of `spec-v1.5.md` | REQ-V160-GATE-03 |
| `tests/test_v15_standards.py:1697` | `_GATE_MATRIX_LABEL_TO_NAME` gains `"`mutation_check.py --select v160-`": "mutation-v160"` | REQ-V160-GATE-02 |
| `tests/conftest.py` | the offline guard gains the `socket.socket.bind` restriction of REQ-V160-SRV-05 | REQ-V160-SRV-05 |

**Explicitly NOT amended**, each verified against the test as written:
`tests/test_observability.py:592` (summary rows keep `turn_id is None`,
REQ-V160-TRC-04 item 4); `tests/test_observability.py:738-739` (payloads become
derived, REQ-V160-TRC-06); `tests/test_v14_patch.py:30-60`
(`REQUIRED_LLM_ROW_KEYS` does not move, REQ-V160-BEN-03);
`tests/test_bench.py:1561-1562` and `:1066-1084` (derived from
`LLM_ROW_KEYS`/`TOOL_ROW_KEYS`); `tests/test_v1_guardrails.py:1144` (indexes
`lines[0]`…`lines[5]`; the new line is the eighth, REQ-V160-SRV-09);
`tests/test_storage.py:44`, `tests/test_summary.py:139/147/164` (compare against
`storage.SCHEMA_VERSION`); `tests/test_v15_standards.py:1753-1760` (`--select
v15-` still selects exactly the four `v15-*` entries).

### 15.2 New unit tests — the mechanisms

| id | asserts |
|---|---|
| `T-V160-TRC-01` | `tracing`, `dashboard_render`, `dashboard_server` each resolve to a `.py` file and no same-named package directory exists on `sys.path` |
| `T-V160-TRC-02` | ids: `trace_id` is 32 lower-case hex, `span_id` 16; two spans never share a `span_id`; a nested span inherits the parent's `trace_id` and records the parent's `span_id` |
| `T-V160-TRC-03` | the tree of REQ-V160-TRC-04 for one scripted two-round turn with one tool call: exactly one `invoke_agent` root, two `chat` children, one `execute_tool` child, correct kinds, correct parentage |
| `T-V160-TRC-04` | a failed LLM invocation and each failover attempt each produce their own `chat` span with `status = "error"`; `llm_calls` rows and `chat` spans are in bijection within the trace; a **failing** call yields exactly one `spans` row and one `llm_calls` row in one transaction; with `storage.add_span` monkeypatched to raise, the `llm_calls` row is rolled back with the span and neither is present |
| `T-V160-TRC-05` | `execute_tool` spans and `tool_calls` rows are in bijection, `budget`, `rejected` and `refused_repeat` outcomes included; the same forced-failure case rolls both back |
| `T-V160-TRC-06` | `storage.SPAN_COLUMNS` equals `PRAGMA table_info(spans)`; the `span` log payload's key set equals it too |
| `T-V160-TRC-07` | migration 3 → 4 on a database populated at v3: the `spans` table appears, `llm_calls`/`tool_calls` gain nullable `trace_id`/`span_id`, pre-existing rows survive with `NULL` there, and the version reads 4. Also 1 → 4 and 2 → 4 chained, and idempotence on re-`init_schema` |
| `T-V160-TRC-08` | an unsupported version (0, 5, `"x"`) raises the existing `RuntimeError` naming the version |
| `T-V160-TRC-09` | `set_attribute` with an unlisted key raises `ValueError` naming it; with `OBS_CAPTURE_CONTENT` false the four content keys are **absent** from `attributes_json`; with it true they are present |
| `T-V160-TRC-10` | with `OBS_CAPTURE_CONTENT` true and a registered synthetic secret inside the captured content, `attributes_json` contains the redaction marker and not the secret; each content attribute is ≤ 2000 characters |
| `T-V160-TRC-11` | `status_message` is redacted **then** truncated to 200 characters: a secret straddling the 200-character boundary does not survive |
| `T-V160-TRC-12` | an exception inside a span sets `status = "error"` and **re-raises**; `start_span` called with no `sink` uses `NullSink`; a **non-sqlite** `SpanSink.write` that raises is swallowed, increments `tracing.dropped_spans`, is logged once, and does not mask the body's exception; a `SqliteSpanSink.write` that raises **propagates** |
| `T-V160-TRC-13` | `SqliteSpanSink` writes exactly one row per span end, on the calling thread, on the agent's own connection, inside the same `BEGIN IMMEDIATE` … `COMMIT` as the call row it belongs to; a second `finish()` raises `RuntimeError`, exit never re-finishes, and with every statement recorded **no `BEGIN IMMEDIATE` opens inside another** on any path, the root turn included |
| `T-V160-TRC-14` | with the operation raising **and** `add_span` raising another exception, the **persistence** one escapes; with `BEGIN IMMEDIATE` raising, no bare `ROLLBACK` follows |
| `T-V160-MET-01` | no column of `llm_calls` or `tool_calls` is written and never read: every name from `PRAGMA table_info` appears in `metrics.py` |
| `T-V160-MET-02` | `usage_by` for each of the four groupings over a seeded database, each row populating only its own dimension fields; one model id served by **two** providers yields two rows and `/api/usage?group=model` serialises `gen_ai.provider.name` and `gen_ai.request.model` separately; `group="nope"` raises `ValueError` naming it; `since` excludes older rows and includes the boundary day |
| `T-V160-MET-03` | `cache_hit_share` and `reasoning_share` are `None` — not `0.0` — when no row carries the numerator, and correct when rows do; a mixed-basis group joins bases rather than picking one |
| `T-V160-MET-04` | `error_breakdown` buckets `NULL` finish reason as `"(none)"` and `NULL` error kind as `"ok"`; `error_rate` matches the counted rows |
| `T-V160-MET-05` | `latency_histogram` converts ms → s and places `latency_ms = 1280` in the `1.28` bucket, not the next; bucket count is `len(boundaries) + 1`; the overflow bucket catches a value above the last boundary; a one-model fixture returns a one-element list whose `attributes` holds exactly the three duration keys, sorted |
| `T-V160-MET-06` | `token_histogram(token_type="input"\|"output")` returns one `Histogram` per `(operation, provider, model, token type)` tuple, each `attributes` carrying `gen_ai.token.type` alongside the three duration keys, sorted by key; a two-model fixture yields two histograms; `NULL` dimensions render `"(none)"`; an unknown token type raises |
| `T-V160-MET-07` | `tool_health.max_consecutive_repeats` counts the longest same-tool run **within one turn**, and does not run across a turn or conversation boundary |
| `T-V160-MET-08` | `/stats` and `/api/usage` report the **same** totals for the same database — the one-implementation rule of REQ-V160-MET-01 |
| `T-V160-MET-09` | `limit_hits` counts each constant name at most once per turn and only for the seven of REQ-V160-TRC-10; `MAX_TOOL_CALLS_ACCEPTED` is absent |
| `T-V160-MET-10` | `usage_by` caps at 500 groups with an `"(other)"` remainder row whose totals equal the omitted rows' |
| `T-V160-MET-11` | seeded with 250 distinct `finish_reason` and 250 `error_kind` values, each `error_breakdown` dictionary holds exactly 101 keys — the 100 highest counts, count descending then key ascending — summing to `total`, `error_rate` unchanged |
| `T-V160-DSH-01` | no top-level module imports `devtools`; `devtools/dashboard.py` imports `dashboard_render`; and no string literal in `dashboard_server.py` contains `<` followed by a letter or `/` — every HTML body comes from `dashboard_render` |
| `T-V160-DSH-02` | the same fixture rendered through `dashboard_server` and through `devtools/dashboard.py` yields byte-identical `usage_section` fragments |
| `T-V160-DSH-03` | every route's HTML has zero `script` elements, zero `on*` attributes, no external `href`/`src`, and parses cleanly |
| `T-V160-DSH-04` | a tool name and a model name each containing `<script>`, `"` and `&` are escaped everywhere they appear, HTML and SVG alike. `status_message` is **not** rendered: a canary placed in a span's `status_message` and in a non-served attribute appears in no page and no API response |
| `T-V160-DSH-05` | **the canary sweep** (REQ-V160-DSH-07): the canary seeded in six places appears in no body, header or log line of any of the 14 route cases, 404 and 405 included, with `OBS_CAPTURE_CONTENT` false for the server |
| `T-V160-DSH-06` | the same sweep with content capture **on** for the writer: still absent from every response |
| `T-V160-DSH-07` | `gantt_svg` places and scales bars from `start_ns` offsets against the root duration and orders by `start_ns`, **never** `ts` — a fixture whose `ts` order reverses its `start_ns` order still renders in `start_ns` order; a zero-duration root does not divide; it marks an error span, and emits `role="img"` with `<title>` and `<desc>`; a zero-count histogram bucket is drawn with its label |
| `T-V160-DSH-08` | a trace whose root span is missing renders the orphans with a banner and returns 200, not 500 |
| `T-V160-DSH-09` | `SERVED_SPAN_ATTRIBUTE_KEYS` equals `ATTRIBUTE_KEYS` less the four content keys, `gen_ai.tool.call.id` and `tg_agent.tool.fingerprint`; `ServedSpan` has no `status_message` field; `served_span` on a row whose `attributes_json` carries every one of those keys drops them all and keeps the rest; `trace_tree_section` and `gantt_svg` raise `TypeError` when handed a `sqlite3.Row` |
| `T-V160-API-01` | each endpoint's exact top-level key set against a literal; semconv keys spelled verbatim; JSON is sorted and `ensure_ascii=False` |
| `T-V160-API-02` | `/api/traces/<trace_id>` with an unknown but well-formed id is 404, not an empty 200 |
| `T-V160-API-03` | a body forced over 2 MiB on `/api/usage` and `/` yields the fixed content-free 500, no fragment of it, size or path reaching the response or log; a 65-span trace is refused with that 500 while a 64-span trace serves, and the legitimate maximum derived from the `agent.py` limits (35) is ≤ `MAX_SPANS_PER_TRACE`; a 300-character name and a 400-character attribute value come back truncated to 128 and 256 with `…` |
| `T-V160-SRV-01` | `DASHBOARD_PORT` outside 1024–65535, and a non-integer, each raise `ConfigError` naming the variable; the default is 8765 |
| `T-V160-SRV-02` | `DASHBOARD_ENABLED=false` and `--no-dashboard` each suppress the server; the flag wins over a true environment value |
| `T-V160-SRV-03` | the server binds `127.0.0.1` and nothing else; the bind address is not reachable from any config or environment value |
| `T-V160-SRV-04` | with `socket.socket.bind` patched to raise, `bot.main(["--selftest"])` still returns 0 — no server is constructed on that path |
| `T-V160-SRV-05` | all four security headers on a 200, a 404, a 405 and a 400; `Allow: GET, HEAD` on the 405; no `Set-Cookie` anywhere |
| `T-V160-SRV-06` | an `INSERT` through `connect_readonly` raises; a missing database raises rather than being created; the server answers 503 when the file is absent as the request opens it; with `sqlite3.connect` monkeypatched to count calls, N requests open and close exactly N connections and none is left open after the last response |
| `T-V160-SRV-07` | one scripted turn run with and without the dashboard produces identical `llm_calls`, `tool_calls` and `spans` rows modulo ids and timestamps |
| `T-V160-SRV-08` | across a full route sweep, no executed SQL string contains any request parameter value — every one arrives bound |
| `T-V160-SRV-09` | `/status`'s eighth line for each of the four states; lines 1–7 unchanged |
| `T-V160-SRV-10` | `Host: evil.example.com:<port>`, `Host: 127.0.0.1:<port>@evil`, two `Host` headers, a `Host` carrying a tab, and an absolute-form request target each get 400 with the four headers; the correct `Host` gets 200; the rejected value appears in no body, header or log line |
| `T-V160-TQ-01` | a summary response with `finish_reason == "length"` is rejected, recorded `error_kind = "truncated"` at `attempt = 1`, retried once at `attempt = 2`; a second truncation proceeds without a summary and lands in `summary_health.failed`, as does a row with `error_kind = "timeout"`, while a lone `attempt = 1` truncation does not |
| `T-V160-TQ-02` | with `retry_max_tokens=1536` configured, attempt 1 still requests exactly `SUMMARY_MAX_TOKENS` (512) and only attempt 2 requests 1536; the default of both is unchanged behaviour; `_check_timeout_budget` uses the max of the two budgets and is unchanged at default configuration |
| `T-V160-TQ-03` | each of the five `TOOL_OUTCOMES` is recorded and appears in `tool_health`; an unknown outcome raises before it reaches the database |
| `T-V160-TQ-04` | three identical failing calls: the third is refused, records `outcome = "refused_repeat"` and `duration_ms = 0`, and the injected envelope matches the literal verbatim. Argument key order does not change `call_key`; two failures under **different** error classes still refuse the third call, while the state counts the two `(call_key, class)` pairs apart; it does not survive the user message |
| `T-V160-TQ-05` | `tool_calls_max(0)` raises; the kind is not in `ANSWER_KINDS`; a run with `max_calls + 1` tool rows fails the check and one with exactly `max_calls` passes; refusals count |
| `T-V160-TQ-06` | `_validate_catalog` rejects a scenario whose `tool_calls_max` is below its own `tool_used` count; S13…S18 all import cleanly and ids are unique |
| `T-V160-BEN-01` | `bench.py check` refuses a `bench_schema: 1` document; `report` without `--gate` accepts it and prints the informational banner to stderr; `report --gate` returns `EXIT_NOT_COMPARABLE` |
| `T-V160-BEN-02` | a `scenarios_sha256` mismatch is fatal for `check` and for `report --gate`, and a stderr note for plain `report` |
| `T-V160-BEN-03` | `runs[].spans` round-trips: `attributes` is a parsed object, `conv_id` is replaced by `conv_seq`, `SPAN_ROW_KEYS` equals the document's own key set and holds `attributes`, not `attributes_json` or `conv_id`, and `REQUIRED_SPAN_ROW_KEYS` is enforced only for schema 2 |
| `T-V160-BEN-04` | the six new `meta` keys are present; `LOCKED_META_FIELDS` holds the **six** of REQ-V160-BEN-05 beside the ten it held and **not** `git_commit`; `report --gate` exits `EXIT_NOT_COMPARABLE` when any of the six differs **and** when one side omits it, and 0 on a pair differing only in `git_commit`; `run --tag baseline-x` exits `EXIT_ERROR` on a dirty tree and proceeds on a clean one, while `run --tag smoke-x` proceeds either way |
| `T-V160-VER-01` | `bot.main(["--version"])` prints `tg-agent-bot <v>` where `<v>` equals an independent `tomllib` read of `pyproject.toml`, and returns 0 |
| `T-V160-VER-02` | the CLI grammar table in full: every accepted form, every rejected combination, exit codes 0 and 2, and the exact usage string |

### 15.3 Negative tests — the mechanisms must be able to fail

| id | scenario | expected |
|---|---|---|
| `N1` | `DASHBOARD_PORT=80` (below 1024) and `DASHBOARD_PORT=abc` | `ConfigError` at `load_config`, naming the variable and the range; the bot does not start |
| `N2` | the configured port is already bound when the bot starts | one `ERROR` log through `redact`, the bot **keeps running**, `/status` shows `Dashboard: off (bind failed)`, no retry, no alternative port |
| `N3` | `POST`, `PUT`, `DELETE`, `OPTIONS` and `TRACE` against `/` and `/api/usage` | 405 with `Allow: GET, HEAD`, all four security headers, a fixed body |
| `N4` | `/../etc/passwd`, `/traces/../..`, `/api/usage/../health`, `/tools/`, `/index.html`, `/%2e%2e/` | 404 for each; nothing is unquoted, normalised or resolved; no filesystem access is attempted |
| `N5` | `?group=nope`, `?since=2026-13-45`, `?since=yesterday`, `?limit=0`, `?limit=9999`, `?conv=-1`, `?unknown=1`, `?group=model&group=day` | 400 for each, body naming **only** the parameter name; the offending **value** appears nowhere in the response |
| `N6` | a request whose handler raises an unexpected exception | 500 with a fixed body: no traceback, no exception message, no path; one `ERROR` log through `redact` |
| `N7` | the database file is **missing when the request opens it** (never created, or removed before the request arrives) | 503 with a fixed body, all four security headers; the bot keeps polling; the file is not recreated |
| `N8` | a summary truncated twice, and separately one whose only row carries a non-truncation `error_kind` | the turn completes, no exception escapes, `summary_health.failed` increments in **both**, `/stats` shows it |
| `N9` | `bot.py --selftest --version`, `bot.py --selftest --no-dashboard`, `bot.py --no-dashboard --no-dashboard`, `bot.py extra` | usage printed, exit 2, in every case |
| `N10` | `pyproject.toml` with no `version` key, read by `--version` | `RuntimeError` naming the path, message to stderr through `redact`, exit 2 |

### 15.4 Mutation coverage

**REQ-V160-TST-03 (MUST)** Add **at least seven** `v160-*` entries to
`devtools/mutation_check.py`'s `MUTATIONS` list, each a dict with the existing
five keys (`id`, `path`, `find`, `replace`, `why`), each breaking a security- or
correctness-critical mechanism and killed by a named test:

| id | mutation | killed by |
|---|---|---|
| `v160-bind-address-widened` | `DASHBOARD_BIND = "127.0.0.1"` → `"0.0.0.0"` | `T-V160-SRV-03` |
| `v160-capture-content-default-on` | `_parse_bool(..., "OBS_CAPTURE_CONTENT", False)` → `True` | `T-V160-TRC-09` |
| `v160-content-redact-bypassed` | the content attribute is stored without `config.redact()` | `T-V160-TRC-10` |
| `v160-fingerprint-threshold-off-by-one` | `TOOL_REPEAT_REFUSAL_THRESHOLD = 2` → `3` | `T-V160-TQ-04` |
| `v160-truncated-summary-accepted` | the `finish_reason == "length"` guard is removed | `T-V160-TQ-01` |
| `v160-selftest-starts-the-server` | server construction moves ahead of the selftest branch | `T-V160-SRV-04` |
| `v160-version-literal-not-pyproject` | `_read_version` returns a hard-coded string | `T-V160-VER-01` |
| `v160-readonly-connection-writable` | `mode=ro` → `mode=rw` in `connect_readonly` | `T-V160-SRV-06` |
| `v160-error-echoes-request-input` | the 400 body includes the parameter **value** | `T-V160-DSH-05`, `N5` |
| `v160-host-check-disabled` | the `Host` comparison of REQ-V160-SRV-11 always returns `True` | `T-V160-SRV-10` |

**REQ-V160-TST-04 (MUST)** Every entry's `find` string must match its target file
**exactly once**; `mutation_check.py --list` is run and its output recorded
before the gate is trusted. The whole-tree `ruff format` reformat stays a
NON-GOAL (REQ-V15-NG-04) so existing `find` strings stay valid.

---

## 16. Acceptance, review and report

**REQ-V160-ACC-01 (MUST)** After the `full` profile is green, execute Appendix B
against the repository, the running bot and the recorded baseline. Record pass or
fail per scenario and, per REQ-V12-REP-02, **how** each was driven.

**REQ-V160-ACC-02 (MUST)** Regression check: spec-v1.2's D1 and D2, spec-v1.4's
S01 acceptance and spec-v1.5's freeze properties still hold. No earlier security
posture is weakened; in particular the exec sandbox, the redaction choke points,
the SSRF domain allowlist and the `.env` handling are untouched by this release.

**REQ-V160-ACC-03 (MUST) — the final acceptance run, the frozen tip, and the
freeze.** T17's report cannot be the reported run; the v1.5 machinery applies
unchanged:

- **T17 lands a provisional `report-v1.6.0.md`** carrying every REQ-V160-RPT-02
  item except item 4's `<implementation-tip>` SHA and every T18 artefact. That
  commit's resulting SHA **is**
  `<implementation-tip>`.
- **T18 re-runs against the final tree**: the six verbatim gates of §14,
  `checks.py run --profile full --since <base>`,
  `checks.py replay --range <base>..<implementation-tip>` and Appendix B. It then
  lands **one evidence-only commit** touching `docs/reports/*` and nothing else,
  recording the tip SHA, the replay output, the intended tag name and the
  remaining evidence. That commit is not recursively required to replay against
  itself. **Only after it has landed** is the annotated tag `v1.6.0` created on
  it (REQ-V160-VER-04); the tag is the last action of the run and no commit
  follows it.
- **After the final successful run no source, test or config change is
  permitted.** The one exception is a documentation-only correction of the
  evidence that run produced, which re-runs the `commit-msg` checks, the
  `pre-commit` profile, `lint-docs` and `gitleaks-tree` against the final tree.
  Anything else voids the run and T18 is executed again in full.

**REQ-V160-ACC-04 (MUST)** Failures are fixed and the whole set rerun inside the
**5-cycle** repair budget. Exhausting it means stopping and reporting, not
relaxing a gate, not deleting a test and not lowering a scenario's declared
maximum.

**REQ-V160-REV-01 (MUST)** Code review by the `code-reviewer` subagent
(`.claude/agents/code-reviewer.md`) in a **clean context**, after the gates pass
and before the final report — never self-review in the writing context. Findings
are fixed or waived with a reason in the report; log the review prompt in
`docs/prompts/`. Beyond the standard checklist the reviewer checks:

1. no production module imports anything from `devtools/`, and
   `dashboard_render.py` is the only module emitting HTML;
2. every route, the error routes included, sets all four security headers, and
   no handler writes a request-derived string into a response body;
3. `connect_readonly` is the only path by which the server reaches the database
   and no server code path writes;
4. every content attribute passes through `config.redact()` before storage, and
   no content attribute reaches any response;
5. each mechanism of §15.4 has a mutation entry whose `find` matches once.

---

## 17. Implementation order

**REQ-V160-ORD-01 (MUST)** Work in this order; each task is one prompt and one
commit, with the reading map of §14.1 and the delegation rule of REQ-V160-EC-07.

| T | task | acceptance |
|---|---|---|
| **T0** | Preconditions (§3): `full` profile green, hooks installed, `doctor` green, test count re-measured, docker, port free. **Record `<base>` and the committed spec's `sha256`**, create `docs/prompts/72-go-spec-v1.6.0.md` and the `report-v1.6.0.md` skeleton with its `## Operator inputs` section (LM Studio version, loaded context length, port override) copied verbatim from the `go` request, the served model id excluded (REQ-V160-PRE-04). | every item recorded; `71` is the highest pre-existing prompt and the spec file is present and unchanged; `<base>` written before the first commit; **a version or positive-integer context length missing from the `go` request stops the run here**; any other failure emits the blocker template |
| **T1** | `tracing.py`: `Span`, `SpanKind`, the contextvar tracer, `ATTRIBUTE_KEYS`, `SpanSink`, `NullSink`, `set_run_context`. Tests `T-V160-TRC-01`, `-02`, `-09`, `-11`, `-12`. | those tests green; `ruff check .` green; nothing else imports it yet |
| **T2** | `storage.py`: `SCHEMA_VERSION = 4`, `_SPANS_DDL`, the two new columns, `_MIGRATION_3_TO_4`, the accepted-version tuple, `SPAN_COLUMNS`, `add_span`, `spans_for_trace`, `recent_traces`, `connect_readonly`, derived log payloads. Tests `T-V160-TRC-06`, `-07`, `-08`, `-13`, `T-V160-SRV-06`; amends `tests/test_observability.py:431`. | migration tests green from v1, v2 and v3 databases; `test_obs06` green **unamended** |
| **T3** | `agent.py` wiring: the four span seams, `SqliteSpanSink`, `trace_id`/`span_id` on both row families, the `turn_id` repair, `tg_agent.limit_hit`. Tests `T-V160-TRC-03`, `-04`, `-05`, `-10`, `-14`, `T-V160-MET-09`; amends `tests/test_observability.py:544`. | those tests green; the bijections hold; no other observability test changes |
| **T4** | `metrics.py`: the eight aggregate functions, `Histogram`, `UsageRow`, `ToolHealthRow`, `SummaryHealth`, the caps; `/stats`'s two new lines. Tests `T-V160-MET-01…-08`, `-10`, `-11`. | those tests green; `/stats`'s first eight lines byte-identical in shape |
| **T5** | `dashboard_render.py` and the `devtools/dashboard.py` refactor onto it; its CLI contract unchanged; `bench_schema ∈ {1,2}` accepted. Tests `T-V160-DSH-01`, `-02`, `-03`, `-04`, `-07`, `-09`; amends `tests/test_dashboard.py:136`, `:502`. | the 534-line dashboard suite green but for the two amended lines; the byte-identity test green |
| **T6** | `dashboard_server.py`: routing, the allowlist, method handling, parameter validation, the security headers, the per-request read-only connection, the `Host` check, the JSON API, the error paths. Tests `T-V160-API-01`, `-02`, `-03`, `T-V160-SRV-05`, `-06`, `-08`, `-10`, `T-V160-DSH-05`, `-06`, `-08`, `N3…N7`. | those tests green; the canary sweep green |
| **T7** | `config.py` (four new fields), `bot.py` (CLI grammar, `--version`, `--no-dashboard`, server start/stop, the `/status` line, `USAGE`), `conftest.py` bind guard, `.env.example`. Tests `T-V160-SRV-01`, `-02`, `-03`, `-04`, `-07`, `-09`, `T-V160-VER-01`, `-02`, `N1`, `N2`, `N9`, `N10`; amends `tests/test_v1_guardrails.py:1398`, `tests/conftest.py`. | those tests green; `bot.py --selftest` green with binding patched to raise |
| **T8** | `agent.py` truncated-summary retry + `LLM_SUMMARY_MAX_TOKENS` + `_check_timeout_budget` extension + `TOOL_OUTCOMES`. Tests `T-V160-TQ-01`, `-02`, `-03`, `N8`. | those tests green; the timeout floor unchanged at default configuration |
| **T9** | `agent.py` repeat refusal: `call_key`, per-message state, threshold, the verbatim envelope, `refused_repeat`. Test `T-V160-TQ-04`. | that test green; the envelope matches the literal |
| **T10** | `bench_scenarios.py`: the `tool_calls_max` kind and factory, `max_calls`, the catalogue validation, S13…S18. Tests `T-V160-TQ-05`, `-06`. | those tests green; catalogue imports cleanly; **no existing scenario changed** |
| **T11** | `bench.py`: `BENCH_SCHEMA = 2`, `runs[].spans`, `SPAN_ROW_KEYS`, `REQUIRED_SPAN_ROW_KEYS`, the `mode` parameter, the `check`/`report`/`report --gate` split, `meta.lmstudio_version`/`served_model_id`, the `tool_calls_max` evaluation. Tests `T-V160-BEN-01…-04`; amends `tests/test_bench.py:111`. | those tests green; `REQUIRED_LLM_ROW_KEYS` unchanged; `test_v14_patch` green unamended |
| **T12** | Version and docs: `pyproject.toml` `1.6.0`, `README.md` (Dashboard, Versioning, four env rows, `--version`, `--no-dashboard`, `/status`), `AGENTS.md`, `docs/plan.md`. | `lint-docs` green; the version test green; docs match reality |
| **T13** | `mutation_check.py`: the ten `v160-*` entries; `config/quality_gates.yaml`: the `mutation-v160` gate and both re-measured timeouts; `--list` recorded. | `--select v160-` green; `mutation-all` green inside its new timeout; the matrix test green |
| **T14** | Review (REQ-V160-REV-01) in a clean context; fix or waive findings. **Every source, test and config fix of this run lands here or earlier** — never after T16. | findings closed or waived with reasons |
| **T15** | **Offline gates and the live preflight (REQ-V160-PRE-04)**: gates 1–4 and 6 verbatim plus `checks.py run --profile full --since <base>` with its live member deferred; then resolve LM Studio (PRE-03), run gate 5 `bot.py --selftest-live` and the deferred live member, collect the instrument metadata, run the one-completion inference preflight, and execute the `smoke-v160` run of REQ-V160-BEN-07. | every offline gate green; served model id equals `LMSTUDIO_MODEL`; metadata complete; all six new scenarios executed once |
| **T16** | **Baseline (§11)**: run all 18 scenarios into `.bench/`, copy to `docs/assets/bench/baseline-v1.6.0.json`, render `dashboard-v1.6.0.html` **from that copy**, produce the informational S01–S12 comparison against `baseline-v1.4.json`, then commit every artefact in the task's **one** commit (REQ-V160-BEN-06). **The tree is frozen from here** (REQ-V160-BEN-07). | 3/3 on each new scenario, no skips — a shortfall voids the run (REQ-V160-TQ-05); LM Studio version and model id recorded; ≈ 40 min, $0 |
| **T17** | **Provisional** `report-v1.6.0.md` (RPT-02 minus item 4's tip SHA and T18 artefacts, ledger row included), `tg-post-v1.6.0.md` (RU, < 1500 chars), `docs/llm-usage.md` rows. | `lint-docs` green; `wc -m` recorded; no self-referential SHA claimed |
| **T18** | **Final acceptance (REQ-V160-ACC-03)**: six verbatim gates, `full --since <base>`, `replay --range <base>..<implementation-tip>`, Appendix B; the single evidence-only commit; then the annotated tag `v1.6.0` **on that commit**. | every gate green on the tree that ships; the tag recorded; the freeze begins |

---

## 18. Non-goals for v1.6.0

Implementing any of these is a defect.

| ID | NON-GOAL | why |
|---|---|---|
| REQ-V160-NG-01 | An OTLP exporter, an OpenTelemetry SDK dependency, a collector, or any span export off the box | REQ-V160-TRC-07 ships the **seam**; the exporter is its own release |
| REQ-V160-NG-02 | A reasoning policy, a cost gate or a quality gate against the new baseline | v1.7.0 owns it; gating on an instrument recorded in the same run is circular |
| REQ-V160-NG-03 | Evals, scores, judgements or any quality rating in the UI | scoring needs a rubric this project has not written |
| REQ-V160-NG-04 | Prompt management, prompt versioning, prompt editing or a prompt UI | the prompts live in the repository and are reviewed like code |
| REQ-V160-NG-05 | Authentication, TLS, remote bind, a reverse proxy, CORS, rate limiting on the dashboard | loopback-only is the entire security model |
| REQ-V160-NG-06 | Any framework or new Python dependency: web, template, chart, ORM, YAML, OTel | REQ-V160-EC-01; stdlib plus `httpx` and `python-dotenv` |
| REQ-V160-NG-07 | JavaScript, interactive charts, live refresh, WebSockets, server-sent events | the pages are read-only reports; REQ-V160-DSH-02 |
| REQ-V160-NG-08 | Cursor pagination, streaming responses, a query language, arbitrary filtering | REQ-V160-API-05's caps are the answer to a large database |
| REQ-V160-NG-09 | A feature flag for the truncation retry or the repeat refusal | REQ-V160-TQ-08: the benchmark measures the shipped configuration |
| REQ-V160-NG-10 | O6 routing (`LLM_SUMMARY_MODEL`), tuning `CONTEXT_WINDOW_MESSAGES`, `EXEC_OUTPUT_DEFAULT_CHARS` or `FETCH_INLINE_DEFAULT_CHARS` | REQ-V14-NG-01/-02 stand: measured ceiling −4.6 %, two models do not fit the GPU box |
| REQ-V160-NG-11 | Regenerating `docs/assets/dashboard-baseline.html` or `dashboard-v1.3.html` | they are records of past runs; the refactor is demonstrated by `dashboard-v1.6.0.html` |
| REQ-V160-NG-12 | Changing any existing scenario's `id`, `title`, `turns` or checks; adding a `FETCH_ALLOWED_DOMAINS` entry | the scenario set is the measuring instrument; a new domain is a security change |
| REQ-V160-NG-13 | CI, GitHub Actions, SonarQube, SBOM, commit signing, provenance attestation, dependency-update automation | REQ-V15-NG-02/-03/-05 stand; every gate here is local |
| REQ-V160-NG-14 | Log shipping, metrics push, a time-series database, a second storage backend, or retention/pruning of `spans` | sqlite plus a local page is the whole system; pruning belongs to a release that measures the growth first |
| REQ-V160-NG-15 | Bumping `httpx`, `python-dotenv`, `pytest`, `ruff` or any pinned tool; upgrading Docker or the sandbox image | no requirement here needs one |
| REQ-V160-NG-16 | Retroactive git tags for v0…v1.5, or renaming existing spec/report/prompt files | REQ-V160-VER-02: the mapping is documentation; renaming breaks every `(prompt: …)` reference in the history |

---

## Appendix A — requirement traceability

Every `MUST` appears exactly once. "Verified by" names a test id, a negative
test, a Gherkin scenario or a recorded artefact — never "by inspection".

| Requirement | Source | Verified by |
|---|---|---|
| EC-01 boundary, zero new deps | REQ-V15-EC-01; user decision 1 | `uv.lock` and `pyproject.toml` diffs show no new distribution |
| EC-02 test-first | REQ-V15-EC-02 | the report's per-task "failed first for the right reason" record |
| EC-03 843-test floor, exhaustive §15.1 | `/verify-run` on v1.5.1 | `pytest --collect-only -q` at T0 and T18 |
| EC-04 secrets discipline | REQ-V1/V11/V12/V15-EC-04 | `gitleaks-tree`; the report's `.env` interaction record |
| EC-05 backward compatibility | REQ-V1-EC-05 | `T-V160-TQ-02`; §15.1's unamended-test list |
| EC-06 benchmark-affecting, declared | `AGENTS.md` § Benchmark | the report's "Benchmark-affecting changes"; `baseline-v1.6.0.json` |
| EC-07 RLM rule | lab `AGENTS.md` rule 5; REQ-V15-EC-07 | §14.1's map; the per-task delegation record |
| EC-08 prompt format | REQ-V15-PRM-01 | `checks.py lint-docs`; `E12` |
| EC-09 `--no-verify` ban | REQ-V15-EC-09 | `replay --range <base>..<implementation-tip>`; the attestation sentence |
| EC-10 one prompt one commit, CC | `AGENTS.md` § Commit format | the `commit-msg` hook; `replay` |
| AMEND-01 amendment table | this spec | §15.1's amended and not-amended lists |
| PRE-01 preconditions | REQ-V15-PRE-01 | the T0 record; the blocker template on failure |
| PRE-02 semconv read, nothing installed | semconv-genai, verified 2026-09-04 | the report's resolved VERIFY values; `uv.lock` unchanged |
| PRE-03 LM Studio probe, `sed -i` only | operator's roaming IP; REQ-V160-EC-04 | the report's probe record; `E13` |
| PRE-04 the instrument identified and preflighted before T16 | `bot.py:1273-1283`; user decision 8 | the T0 operator-input block; the T15 record; `E13` |
| TREE-01 new files | this spec | `git status` at T18; the report's tree listing |
| TREE-02 changed files | this spec | the commit diffs; §15.1 |
| TREE-03 module naming, import direction | REQ-V15-TREE-02's `config/` guard | `T-V160-TRC-01`, `T-V160-DSH-01` |
| TRC-01 span record, redact-then-truncate | OTel span model; spec-v1.1 truncation finding | `T-V160-TRC-11` |
| TRC-02 the tracer, `sink` optional, sqlite failures propagate | this spec; the round-1 critique | `T-V160-TRC-02`, `-12` |
| TRC-03 attribute allowlist, fail-closed | semconv-genai attribute names | `T-V160-TRC-09` |
| TRC-04 the span tree | semconv-genai span shapes | `T-V160-TRC-03`, `-04`, `-05`; `E1` |
| TRC-05 schema 3 → 4 | `storage.py:144-216` | `T-V160-TRC-07`, `-08`; `E2` |
| TRC-06 `trace_id`/`span_id` columns, derived payloads | `tests/test_observability.py:738-739` | `T-V160-TRC-06`; `test_obs06` unamended |
| TRC-07 `SpanSink` seam, one transaction per span+row, OTLP as future | user decision 2(a); `storage.py:248-262`, `:291-305` | `T-V160-TRC-13`, `-04`, `-05`, `-14`; REQ-V160-NG-01 |
| TRC-08 recording seams, `turn_id` repair | `agent.py:255-263`, `storage.py:580-584` | `T-V160-TRC-04`; §15.1's `:544` amendment |
| TRC-09 `OBS_CAPTURE_CONTENT` off, redacted, bounded | user decision 9 | `T-V160-TRC-09`, `-10` |
| TRC-10 limit hits on the root span | `agent.py:29-37` | `T-V160-MET-09` |
| TRC-11 bench traced for free | `bench.py` drives `agent.py` | `T-V160-BEN-03`; `E9` |
| TRC-12 storage helpers, bound parameters | `storage.py` style | `T-V160-SRV-08` |
| MET-01 one module | `AGENTS.md` project layout | `T-V160-MET-08` |
| MET-02 revive the dead columns | nine columns written, never read | `T-V160-MET-01` |
| MET-03 the aggregate functions | this spec | `T-V160-MET-02`, `-03`, `-04`, `-07`, `-11` |
| MET-04 histogram names, units, boundaries, one per attribute tuple | semconv-genai metrics VERIFY ×2 | `T-V160-MET-05`, `-06`; the resolved markers |
| MET-05 `/stats` grows compatibly | `bot.py:806-826` | `T-V160-MET-08`; the unamended `/stats` assertions |
| MET-06 summary health, five SQL formulas over rows | REQ-V160-TQ-01; `agent.py:798-801` | `T-V160-TQ-01`; `N8` |
| MET-07 every aggregate bounded | this spec | `T-V160-MET-10`, `-11` |
| DSH-01 one view layer, two callers | user decision 2(c); REQ-V11-NG-06 | `T-V160-DSH-01`, `-02` |
| DSH-02 offline, no script, no CDN | user decision 1; `tests/test_dashboard.py:195` | `T-V160-DSH-03`; `E5` |
| DSH-03 the three pages | user decision 11 | `T-V160-DSH-07`, `-08`; `E4`, `E9` |
| DSH-04 SVG charts legible without colour | this spec | `T-V160-DSH-07` |
| DSH-05 static report contract kept | `devtools/dashboard.py:634-664` | the unchanged CLI tests; `T-V160-DSH-02` |
| DSH-06 escape once, everywhere | `dashboard.py:259-260` | `T-V160-DSH-04` |
| DSH-07 content policy | user decision 5 | `T-V160-DSH-05`, `-06`; `E6` |
| DSH-08 index is a page, no static serving | this spec | `N4` |
| DSH-09 serving DTO, `SERVED_SPAN_ATTRIBUTE_KEYS` | user decision 5; the round-1 critique | `T-V160-DSH-09`; `T-V160-DSH-04`, `-05`; `E4`, `E6` |
| API-01 five endpoints | user decision 11 | `T-V160-API-01` |
| API-02 semconv JSON keys | semconv-genai | `T-V160-API-01` |
| API-03 validation, never echo | this spec | `N5`; `v160-error-echoes-request-input` |
| API-04 unknown trace is 404 | this spec | `T-V160-API-02` |
| API-05 bounded responses, string maxima, `MAX_SPANS_PER_TRACE` ceiling | REQ-V160-MET-07; the round-2 critique | `T-V160-API-03`; `T-V160-MET-10` |
| API-06 health says little | this spec | `T-V160-API-01` |
| SRV-01 on by default, two opt-outs | user decision 3 | `T-V160-SRV-02`; `E3` |
| SRV-02 port validated, bind fixed | user decision 3 | `T-V160-SRV-01`, `-03`; `N1`; `v160-bind-address-widened` |
| SRV-03 server surface, allowlist, methods | user decision 3 | `N3`, `N4`; `T-V160-SRV-05` |
| SRV-04 security headers everywhere | user decision 3 | `T-V160-SRV-05`; `E5` |
| SRV-05 nothing else binds | user decision 3 | `T-V160-SRV-04`; `v160-selftest-starts-the-server`; `E7` |
| SRV-06 one read-only connection per request, closed in `finally` | user decision 4; the round-1 critique | `T-V160-SRV-06`; `N7`; `v160-readonly-connection-writable` |
| SRV-07 never takes the bot down | user decision 3 | `N2`, `N6`; `E8` |
| SRV-08 no SQL from request data | this spec | `T-V160-SRV-08` |
| SRV-09 startup line and `/status` | user decision 3 | `T-V160-SRV-09`; `E3` |
| SRV-10 dashboard is not part of the agent | this spec | `T-V160-SRV-07` |
| SRV-11 `Host` header checked, DNS rebinding | user decision 3; loopback is not an origin check | `T-V160-SRV-10`; `v160-host-check-disabled`; `E5` |
| TQ-01 truncated summary rejected | REL-02, S12 flakiness | `T-V160-TQ-01`; `N8`; `v160-truncated-summary-accepted`; `E10` |
| TQ-02 `LLM_SUMMARY_MAX_TOKENS` sized | `agent.py:44`, `config.py:357`, REQ-V160-EC-05 | `T-V160-TQ-02` |
| TQ-03 closed outcome vocabulary | `agent.py:560-583` | `T-V160-TQ-03` |
| TQ-04 fingerprint refusal | v1.3 candidate S09 2/5 → 4/7, S12 → 0 tools | `T-V160-TQ-04`; `v160-fingerprint-threshold-off-by-one`; `E11` |
| TQ-05 S13…S18, literal | user decision 12; `bench_scenarios.py`, `skills/host-info.md` | `T-V160-TQ-06`; the `smoke-v160` run; the baseline's per-scenario successes |
| TQ-06 `tool_calls_max` is a new kind | measured: no such field exists | `T-V160-TQ-05` |
| TQ-07 catalogue self-validation | `bench_scenarios.py:266-274` | `T-V160-TQ-06` |
| TQ-08 no feature flags | this spec | REQ-V160-NG-09; no such variable in `config.py` |
| BEN-01 fresh baseline | `bench.py:195`, `:1026-1028` | `docs/assets/bench/baseline-v1.6.0.json`; `E13` |
| BEN-02 old baseline informational | user decision 13 | the report's captioned comparison; `T-V160-BEN-01` |
| BEN-03 `bench_schema` 2, readable past | `bench.py:70`, `:1012-1036`, `:1862-1868` | `T-V160-BEN-01`, `-02`, `-03`; §15.1 |
| BEN-04 spans travel with the run | `bench.py:165-166` | `T-V160-BEN-03` |
| BEN-05 `meta` records and locks the instrument | v1.4 recorded no version; `bench.py:147-155`, `:1291-1320` | `T-V160-BEN-04` |
| BEN-06 static report regenerated | REQ-V160-DSH-01 | `docs/assets/dashboard-v1.6.0.html` |
| BEN-07 baseline last, over a frozen tree; smoke run first | REQ-V160-EC-06; the round-1 critique | §17's ordering; the `smoke-v160` document; the report's timeline |
| VER-01 one version source, `tomllib` | `[tool.uv] package = false` | `T-V160-VER-01`; `N10`; `v160-version-literal-not-pyproject` |
| VER-02 the SemVer policy and the map | user decision 6 | `README.md` § Versioning; this table |
| VER-03 the CLI grammar | `bot.py:61`, `:1306-1321` | `T-V160-VER-02`; `N9`; §15.1's `:1398` |
| VER-04 the tag last, on the evidence-only commit | v1.5.1 created no tag | the annotated-tag message; T18's acceptance output; `E14` |
| VER-05 three-number naming | user decision 6 | the file names of this run |
| VER-06 docs learn the version | spec-sync rule | `lint-docs`; the doc diff |
| RPT-01 ledger row in the report | `/verify-run` item 6 vs the repo boundary | `checks.py lint-docs`; `E12` |
| RPT-02 the report's contents | `standards/reporting.md` | `lint-docs`; the review |
| RPT-03 usage rows, RU post < 1500 | REQ-V12-DOC-02 | `wc -m` quoted in the report |
| RPT-04 docs updated in the same commit | spec-sync rule | the commit diffs |
| GATE-01 six verbatim gates | `AGENTS.md` § Gates | the gates table with exit codes |
| GATE-02 one new gate, two re-measured timeouts | `quality_gates.yaml:202-230` | the report's measurements and arithmetic |
| GATE-03 the authoritative matrix | REQ-V15-GATE-11 superseded | `tests/test_v15_standards.py` matrix test, repointed |
| GATE-04 fix, do not suppress | user decision 14 | the scanner summary; the review |
| GATE-05 `pre-push` wall clock observed | REQ-V15-HOOK-04 | the median of three, recorded |
| TST-01 offline, deterministic, port 0 | REQ-V12-OFF-01 | the extended `conftest.py` guard |
| TST-02 fail first, for the right reason | REQ-V160-EC-02 | the per-task record |
| TST-03 ten `v160-*` mutations | REQ-V12-MUT-01 | `mutation_check.py --select v160-` |
| TST-04 each `find` matches once | REQ-V15-TST-02 | `mutation_check.py --list`, recorded |
| ACC-01 Appendix B executed | REQ-V15-ACC-01 | the per-scenario pass/fail record |
| ACC-02 no posture weakened | REQ-V15-ACC-02 | the regression check; `selftest-live` |
| ACC-03 provisional report, frozen tip, freeze | REQ-V15-ACC-03/-04 | the two SHAs and the evidence-only commit |
| ACC-04 five-cycle budget | REQ-V15-EC-01 | the fix-cycle count in the report |
| REV-01 clean-context review, five extra checks | `AGENTS.md` § Review | the review prompt in `docs/prompts/` |
| ORD-01 the task order | this spec | one commit per task, in order |

## Appendix B — acceptance scenarios (Gherkin, written before code)

```gherkin
# E1-E11 run against a temporary database in a tmp_path fixture and, where a
# server is needed, against a ThreadingHTTPServer bound to 127.0.0.1 port 0.
# E12-E14 run against this repository and, for E13, the live LM Studio.
# SAFETY: no live credential is ever used as a test value; the canary
# SYNTHETIC-CANARY-DASHBOARD-1 is the only permitted sentinel.

Scenario: E1 — one user message produces one trace with the right shape
  Given a scripted turn with two LLM rounds and one tool call
  When the turn completes
    Then exactly one invoke_agent span is the root, its gen_ai.conversation.id
       equals the conversation id, and two chat spans and one execute_tool span
       are its children
  And every llm_calls row joins to exactly one chat span by span_id, and every
      tool_calls row to exactly one execute_tool span
  When the same turn's LLM invocation fails instead
  Then exactly one spans row and one llm_calls row are committed together, no
      nested BEGIN IMMEDIATE is opened, and the exception is re-raised

Scenario: E2 — an existing v3 database migrates without losing a row
  Given a database at schema version 3 holding llm_calls and tool_calls rows
  When init_schema runs
    Then the version reads 4, the spans table exists, and every pre-existing row
       survives with NULL trace_id and span_id
  And running init_schema again changes nothing

Scenario: E3 — the dashboard is on by default and says where it is
  Given no DASHBOARD_ENABLED in the environment and no --no-dashboard flag
  When the bot starts
  Then exactly one INFO line reads "dashboard: serving at http://127.0.0.1:<port>/"
  And /status line 8 reads "Dashboard: http://127.0.0.1:<port>/"
  When the bot is restarted with --no-dashboard
  Then no server is listening and /status line 8 reads "Dashboard: off (--no-dashboard)"

Scenario: E4 — a trace opens as a tree and a timeline
  Given a database holding one complete trace
  When GET /traces is requested
  Then the trace is listed with its abbreviated id linking to /traces/<trace_id>
  When that link is followed
  Then the span tree renders every span with kind, duration and status
  And an inline <svg> gantt is present with one bar per span
  And every attribute shown is a member of SERVED_SPAN_ATTRIBUTE_KEYS
  And no status_message, no tool call id and no fingerprint appears
  And no <script> element appears anywhere in the response

Scenario: E5 — every response carries the security headers
  Given the server is running
  When GET /, GET /nope, POST / and GET /api/usage?group=nope are requested
    Then each response carries the four headers REQ-V160-SRV-04 spells out
  And the 405 response carries Allow: GET, HEAD
  And no response carries Set-Cookie
  When the same requests are sent with Host: evil.example.com:<port>, with two
      Host headers, and in absolute form
  Then each is answered 400 with the four headers and the rejected value is
      logged nowhere

Scenario: E6 — the canary never leaves the database
    Given a fixture database seeded with SYNTHETIC-CANARY-DASHBOARD-1 in a
        message, a summary, a recorded tool argument, a span status_message, a
        span content attribute and a non-served span attribute
  And the serving process has OBS_CAPTURE_CONTENT false
  When every route of REQ-V160-DSH-07 is requested, the 404 and 405 included
  Then the canary appears in no response body, no response header and no log line
  When the writing process had OBS_CAPTURE_CONTENT true instead
  Then the canary still appears in no response

Scenario: E7 — the selftest binds nothing
  Given socket.socket.bind is patched to raise
  When bot.py --selftest runs
  Then it exits 0, and the patched bind was never called

Scenario: E8 — a busy port degrades, it does not kill
  Given the configured port is already bound by another process
  When the bot starts
  Then exactly one ERROR line is logged, redacted, naming the port
  And the bot polls normally
  And /status line 8 reads "Dashboard: off (bind failed)"
  And no alternative port is tried

Scenario: E9 — a benchmark run opens in the dashboard as traces
  Given a bench run recorded with --tag baseline-v1.6.0
  When GET /?group=scenario is requested
  Then each of S01…S18 appears as its own row with its own token and cost totals
  When GET /traces is requested
  Then the bench traces are listed with their scenario ids

Scenario: E10 — a starved summary is retried once and never accepted truncated
  Given a summary response whose finish_reason is "length"
  When the turn runs
    Then it is not parsed, its row records error_kind "truncated", and exactly
       one retry is issued with the larger budget
  When the retry is also truncated
  Then the turn completes without a summary, no exception escapes,
       and /stats reports one failed summary

Scenario: E11 — the third identical failing call is refused, not executed
  Given a tool call that fails twice in one message, under two different
      error classes
  When the model issues the same call a third time
    Then the tool is not executed, the outcome is "refused_repeat", duration_ms
       is 0, and the injected result matches the literal envelope
  And reordering the argument keys does not change call_key
  And a fresh user message starts the count again

Scenario: E12 — the report carries a paste-ready ledger row and valid prompts
  Given the run is complete
  When checks.py lint-docs runs
    Then report-v1.6.0.md contains a "Ledger row" section with no placeholder
       cell whose fenced row's cell count matches the ledger header's
  And every prompt file numbered 72 and above — this run's own, 71 predating it
      — has all seven bullets and four blocks

Scenario: E13 — the baseline is recorded against a named, preflighted instrument
  Given every task through T15 is complete and the working tree is clean
  And LM Studio answers at one of the three probed addresses
  And .env was updated by a single-line sed, confirmed by a grep -q that prints
      nothing, and its contents were never emitted
  And the wttr.in preflight succeeded before the smoke run and before the baseline
  When the served model id is read from GET <base>/models
  Then it contains LMSTUDIO_MODEL, and the version and loaded context length are
      the ones the go request supplied and T0 froze
  And the one-completion preflight returns a non-empty assistant message
  And bench.py run --tag smoke-v160 --only S13,S14,S15,S16,S17,S18 --repeats 1
      executes all six scenarios
  When bench.py run --tag baseline-v1.6.0 completes
  Then meta carries every locked instrument field of REQ-V160-BEN-05
  And each of S13…S18 succeeded 3 times out of 3 within its tool_calls_max, none
      skipped — anything less voids the run rather than becoming a finding
  And the document is committed under docs/assets/bench/
  When a source file is then modified
  Then the baseline is void and the whole run is repeated

Scenario: E14 — the tag is created last, on the evidence-only commit
  Given every gate of section 14 is green on the final tree
  When the evidence-only commit lands
  Then it records <implementation-tip>, the replay output and the intended tag
      name v1.6.0, and claims nowhere that the tag exists
  When git tag -a v1.6.0 is then created on that commit
  Then the tag points at the evidence-only commit
  And the tag name and its target SHA appear in the annotated-tag message and in
      the operator acceptance output, and in no further commit
  And git tag -l still shows v1.3 and v1.3-baseline unchanged
  And nothing is pushed
```

## Appendix C — cross-review log

**Rounds 1–3 of 3, termination: `round_limit`** — the lab's stop criterion (a
round without Critical/High findings) was not reached within the round budget;
challenger **OpenAI Codex `gpt-5.6-sol`**, called through the lab debate loop's
cross-review seam with the plan passed by file (the loop wrapper's argv form
cannot carry a plan above 128 KB). 30 findings, 30 accepted, 4 adapted where the
repository or a user decision contradicted the premise.

### Round 1 of at most 3 — against spec-v1.6.0 as committed (9015835); all ten accepted, one adapted

Challenger: the lab's round-1 critique, ten findings, four `Crit` and six `High`.

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R1-1 | Crit | DSH-03, DSH-07, **DSH-09** (new), API-01/-02/-06, `T-V160-DSH-04`/`-05`/`-09` | accepted, adapted | the per-trace routes and the `conv` filter **stay**: "aggregates only" means aggregates *and non-content identifiers*, and the tree-plus-timeline page is the point of the release. A `ServedSpan` DTO behind `SERVED_SPAN_ATTRIBUTE_KEYS` is the only path out — `status_message`, the four content attributes, `gen_ai.tool.call.id`, `tg_agent.tool.fingerprint` and raw `attributes_json` never reach a renderer or a response; conv and turn ids stay as integers. `T-V160-DSH-04` asserts a `status_message` canary instead of rendering one; the sweep seeds six places, not five |
| R1-2 | Crit | TQ-05, BEN-07, `E13` | accepted | S13…S18 written as literal `Scenario(...)` constructions. Repository facts fixed the edges: `Scenario` has no fixture/setup/cleanup field, so state is model-created in the per-run sandbox; S16 uses the existing `skills/host-info.md`; S17 reuses S08's `wttr.in` URL with weather-invariant assertions, recording status and byte length in the report, not the frozen bench document; S18's precondition is `/new` past `_handle_new`'s `>= 2 messages` guard — there is no automatic summariser. A `smoke-v160` run and catalogue validation gate the baseline |
| R1-3 | Crit | BEN-07, BEN-01/-06, EC-06, ORD-01, ACC-03, §14.1 | accepted | §17 reordered: mutations and timeouts (T13) → review and every fix (T14) → offline gates and LM Studio preflight (T15) → baseline (T16) → provisional report (T17) → final acceptance (T18). Nineteen tasks, every citation renumbered; the freeze sentence added verbatim |
| R1-4 | Crit | PRE-01.2, PRE-03, **PRE-04** (new), GATE-01, ORD-01 | accepted | T0 is offline-only; `--selftest-live` and the `full` profile's live member move to T15. Served model id from `GET <base>/models` `data[].id`, the read `bot.py:1273-1283` already performs; version and loaded context length are operator values, a third VERIFY marker covers a possible Bionic 1.1 endpoint, operator wins on disagreement. A one-completion preflight and a model-id match block before the baseline |
| R1-5 | High | MET-02…-07, API-02, DSH-03, `T-V160-MET-05`/`-06` | accepted | `Histogram` gains sorted `attributes`; both histogram functions return a list, one per attribute tuple, capped at 20 with an `"(other)"` fold. `summary_health` gets five SQL formulas over `purpose = 'summary'` **rows** — never turns, those rows being `turn_id = NULL` — with `attempt = 2` uniquely marking TQ-01's retry. `retry_rate` is defined in rows; `output_tokens_est` is `SUM(tool_calls.output_tokens_est)`, making it MET-02's tenth revived column; `/stats`'s "truncated-retried" is `retried` |
| R1-6 | High | VER-04, RPT-02.10, ACC-03, ORD-01 T18, `E14` | accepted | the evidence-only commit lands after every acceptance command and records the tip SHA and the **intended** tag name, never the tag's existence; the annotated tag is then created on it, its name and target SHA living in the tag message and the acceptance output, in no further commit |
| R1-7 | High | SRV-06, `N7`, `T-V160-SRV-06`, ORD-01 T6 | accepted | one `mode=ro` connection per request, closed in `finally`; no `threading.local()`, no cache, nothing to close at shutdown — and the per-request lifetime is what makes a vanished database observable, an unlinked file still serving reads through an open descriptor. `N7` becomes "missing when the request opens it → 503"; the test counts `sqlite3.connect` calls |
| R1-8 | High | **SRV-11** (new), `T-V160-SRV-10`, §15.4, `E5` | accepted | the Host rule verbatim — exactly one `Host` equal to `127.0.0.1:<actual_port>`, everything else 400, the value never logged or echoed — checked before routing, with the new mutation `v160-host-check-disabled` |
| R1-9 | High | TRC-02, TRC-07, API-01/-06, `T-V160-TRC-04`/`-05`/`-12`/`-13` | accepted | `sink: SpanSink \| None = None`, normalised to `NullSink`. Span and call row share one transaction — but there is **no `with conn:` anywhere** in the repository: `storage.connect` is `isolation_level=None` and the idiom is the explicit `BEGIN IMMEDIATE`/`COMMIT`/`ROLLBACK` of `storage.py:248-262`, so the spec requires that. The root span joins `add_tool_turn`'s transaction. `SqliteSpanSink` failures propagate; other sinks stay best-effort and their drops surface as `/api/health`'s `spans_dropped` |
| R1-10 | High | BEN-05, RPT-02.7, `T-V160-BEN-04` | accepted | seven fields join `LOCKED_META_FIELDS`: `git_commit` (already in `meta`, never locked), `lmstudio_version`, `served_model_id`, `lmstudio_context_length`, `generation_settings`, `prompt_tools_sha256`, `obs_capture_content`. Two premises measured false and recorded rather than followed: `context_length` and `scenarios_sha256` are **already** locked, hence a separate key for the *loaded* length. Settings sent are `temperature=0`, `max_tokens`, `stream=false`, `tool_choice="auto"`; `top_p`/`seed`/`stop` are sent nowhere. A dirty tree refuses a `baseline-*` run |

**Round 1: 10 findings, 10 accepted (1 adapted); nothing refused.** Three
requirements added — PRE-04, DSH-09, SRV-11 — and one mutation entry,
`v160-host-check-disabled`.

### Round 2 of at most 3 — against the round-1 spec (eab2ec5); all ten accepted, two adapted

Challenger: the lab's round-2 critique, ten findings, four `Crit` and six `High`.

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R2-1 | Crit | TRC-02, TRC-07, AMEND-01, `T-V160-TRC-04`/`-13` | accepted | one sequence per span owning a call row: `set_error`, `BEGIN IMMEDIATE`, `finish()` (the sole span writer), the call row, `COMMIT`, `finally` re-raise. Exit finishes only what the body did not and a second `finish()` raises; `add_tool_turn` exposes a transaction-body helper, drops `span=`, nests no `BEGIN` |
| R2-2 | Crit | TRC-01/-05/-12, DSH-03/-07/-09, API-02, `T-V160-DSH-07` | accepted | `start_ns INTEGER NOT NULL` persisted through the DDL, `SPAN_COLUMNS`, `add_span` and `ServedSpan`; gantt `x = (span.start_ns - root.start_ns) / root_duration_ns`, ordered by `start_ns`, `ts` display-only. Cross-process comparisons are meaningless and never made |
| R2-3 | Crit | BEN-03, `T-V160-BEN-03` | accepted | the formula verbatim — `frozenset(SPAN_COLUMNS) - {"conv_id", "attributes_json"} \| {"conv_seq", "attributes"}` — and `REQUIRED_SPAN_ROW_KEYS` naming `attributes`; `attributes_json` is now in no key set, so document and validator agree |
| R2-4 | Crit | PRE-01.1, EC-03, TREE-01/-03, ORD-01 T0, §15.1, `E12` | accepted, adapted | measured against the repository: this spec and prompt `71` are **already committed** on `main` (9015835, eab2ec5), so nothing is materialised. PRE-01 expects `71` highest and the spec present, `sha256` recorded at T0 and frozen; T0 creates `72-go-spec-v1.6.0.md`; task prompts run from `73` |
| R2-5 | High | TQ-05, BEN-07, ORD-01 T16, `E13` | accepted | a skip or fewer than 3/3 on any of S13…S18 is a **blocking** baseline failure — repair first, or void the run and rerun; every "or a recorded finding" escape is gone. The `wttr.in` preflight must pass before the smoke run and again before the baseline |
| R2-6 | High | TQ-02, `T-V160-TQ-02` | accepted | two budgets — `max_tokens` for attempt 1, `retry_max_tokens` only after `finish_reason == "length"`; `bot.py` passes `retry_max_tokens=cfg.llm_summary_max_tokens` alone, so attempt 1 stays at 512 |
| R2-7 | High | EC-04, PRE-01.5, PRE-03, `E13` | accepted, adapted | disclosure separated from machine reads per the lab's secrets rule: values never emitted, three reads permitted — `grep -q '^KEY='`, `python-dotenv` loading, the single-line `sed -i` checked by a silent `grep -q`. Any other read is a defect, and a `.env.bak*` copy is one too |
| R2-8 | High | MET-03, API-02, `T-V160-MET-02` | accepted | `UsageRow` gains explicit `provider`, `model`, `purpose`, `scenario`, `day`; each grouping key defined exactly, `group="model"` on the `(provider, model)` **pair**, the API serialising both semconv fields; `key` is the display label only |
| R2-9 | High | API-05, DSH-09, `T-V160-API-03` (new) | accepted | bodies are serialised into memory first and one over 2 MiB becomes a fixed content-free 500; names ≤ 128, attribute values ≤ 256, ids fixed width, truncation marked `…`; spans per trace bounded at `MAX_SPANS_PER_TRACE = 64` (the lab raised the applied 24 after the pass: the legitimate maximum derived from the agent limits is 35 and is asserted ≤ the bound), a longer trace refused with that same 500 |
| R2-10 | High | MET-05, MET-06, `T-V160-TQ-01`, `N8` | accepted | `failed` becomes terminal failures — every non-truncation `error_kind` plus `attempt = 2 AND error_kind = 'truncated'` — the row-based limitation documented and `/stats` reading it that way. The critique's "`T-V160-MET-05/-06`" are **REQ** ids: those tests cover MET-04's histograms and stay untouched, `summary_health` being proved by `T-V160-TQ-01` and `N8` |

**Round 2: 10 findings, 10 accepted (2 adapted); nothing refused.** No new
requirement; one new test, `T-V160-API-03`.

### Round 3 of 3 — against the round-2 spec (cdfb4a1); all ten accepted, one adapted

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R3-1 | Crit | TQ-04 | accepted | `call_key` is pre-execution; the error class only counts for diagnostics |
| R3-2 | Crit | BEN-05 | accepted | `git_commit` stays provenance, not locked — six lock, not seven |
| R3-3 | High | EC-06, BEN-07, RPT-02.6 | accepted | a post-change baseline, no before/after claim; the `AGENTS.md` rule superseded |
| R3-4 | High | TRC-07, `T-V160-TRC-14` (new) | accepted | guarded `ROLLBACK`; the operation failure re-raised after the `try`, not in a masking `finally` |
| R3-5 | High | BEN-05, PRE-04 | accepted | `generation_settings` per purpose — `agent`, `summary_initial` (512), `summary_retry`, `provider_defaults` |
| R3-6 | High | BEN-07 | accepted | verbatim: T15 first runs inference (preflight, `smoke-v160`), T16 first records a baseline |
| R3-7 | High | PRE-04, ORD-01 T0 | accepted, adapted | the operator values arrive in the **`go` request's own text** and block at T0; served model id is `/models` at T15 |
| R3-8 | High | DSH-01, API-05, SRV-11 | accepted | three render functions take every HTML error body, the server none |
| R3-9 | Med | MET-03/-07, `T-V160-MET-11` (new) | accepted | 100 named buckets plus `"(other)"` per dictionary, `total` and `error_rate` surviving the fold |
| R3-10 | Med | BEN-06, ORD-01 T16 | accepted | run, copy, render from the copy, compare, one commit |

**Round 3: 10 accepted (1 adapted); nothing refused, no new REQ.**
