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
(`uv run --locked pytest --collect-only -q`, reported 2026-09-04 at HEAD
`859d12d`). The executor **re-measures at HEAD** at T0 and records the number;
if it differs, the measured number is the floor. No test may be deleted; tests
may be modified **only** where §15.1 lists them, and that list is exhaustive. A
change making an unlisted test fail means the change is wrong — stop and
reconsider, do not edit the test.

**REQ-V160-EC-04 (MUST)** Secrets discipline unchanged (REQ-V1/V11/V12/V15-EC-04):
credential **values** are never printed, logged, committed or quoted in `docs/`;
presence checks are by key **name** only; tests use the synthetic sentinel
pattern. `.env`, `data/`, `sandbox/`, `*.db` and `exec_audit.jsonl` are never
opened, printed or quoted by any task of this run. The one permitted touch of
`.env` is REQ-V160-PRE-03's single-line `sed -i` rewrite of `LMSTUDIO_BASE_URL`,
which never reads or prints the file.

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

Both are declared **before** implementation; §11 discharges the obligation by
recording a **fresh baseline** (`baseline-v1.6.0.json`) per REQ-V160-BEN-01
and -02. A **cost or quality gate** against that baseline is **not** part of
this release (REQ-V160-NG-02).

If a *further* benchmark-affecting change is proposed or discovered at any
point: (1) stop the task that proposed it; (2) record it and its trigger in the
report under "Benchmark-affecting changes"; (3) either drop it and hand it to
v1.7.0, or fold it in **before** the baseline recording task (T13). Recording
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

1. **Repository**: branch `main`, clean tree, HEAD at the delivered v1.5.1
   (`docs/spec/spec-v1.5.md`, `docs/reports/report-v1.5.md` and
   `docs/reports/report-v1.5.1.md` present; `docs/prompts/70-v151-advisor-followup.md`
   is the highest-numbered prompt file). **Record the starting HEAD SHA as
   `<base>`** in the report before the first commit — it is the lower bound of
   every `--since` and `replay --range` in this run.
2. **The `full` profile green before anything changes**:
   `python3 devtools/checks.py run --profile full --since <base>` exits 0, and
   the six verbatim gates of §14 exit 0 in their own right. An already-red gate
   is a blocker, not something to fix silently here. Gate 5's `lmstudio` check is
   **not** excused — an unreachable LM Studio blocks the run.
3. **Test count re-measured** at HEAD: `uv run --locked pytest --collect-only -q`.
   Record the number; it is the floor of REQ-V160-EC-03.
4. **Hooks**: `python3 devtools/install_hooks.py --check` exits 0 and
   `python3 devtools/checks.py doctor` exits 0 against the six pinned tools.
5. **Credentials**: the git-ignored `.env` exists with the keys spec-v1.2 §3.3
   lists, plus `LMSTUDIO_BASE_URL`. Presence **by key name only**; never create,
   overwrite, print or scan it (REQ-V160-EC-04).
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

`.env` is never read, printed, `cat`-ed, diffed or quoted; `sed -i` is the whole
of the permitted interaction. If no address answers, the run stops at T13 with
the blocker template — the code tasks T1–T12 do not need LM Studio and are not
blocked by it.

LM Studio is now **Bionic 1.1.x** on the operator's host. The executor records
the **exact** version string and the **exact served model id** — read from the
LM Studio HTTP API and from the operator's `## Operator inputs` section — into
`docs/reports/report-v1.6.0.md` and into `meta` of the recorded baseline. This supersedes REQ-V15-DEP-06's "not inspected" escape.

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
docs/prompts/71-v160-spec-authoring.md  # this spec's authoring prompt (lab session)
docs/prompts/72-go-spec-v1.6.0.md  # the `go` prompt
docs/prompts/72-v160-*.md …        # one per task of §17
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
`metrics` and `storage`. `T-V160-DSH-01` asserts it by static inspection of the module source.

**Prompt numbering.** `docs/prompts/70-v151-advisor-followup.md` closes
the v1.5.1 cycle and exists before this run starts; `70` missing at T0 is a
precondition failure. This run's `go` prompt is
therefore `72-go-spec-v1.6.0.md` (`71-v160-spec-authoring.md` is the lab's
authoring prompt for this spec) and per-task prompts continue from `73` as
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
| `start_ns` | `int` | `time.monotonic_ns()` at start, for duration only |
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
start_span(name, kind, *, sink, attributes=None, conv_id=None,
           turn_id=None, trace_id=None) -> ContextManager[MutableSpan]
new_trace_id() -> str
new_span_id() -> str
```

`start_span` is a `contextlib.contextmanager`. On entry it mints a `span_id`,
takes `parent_span_id` and `trace_id` from `current_span()` when one exists —
otherwise starting a new trace with `trace_id or new_trace_id()` — sets the
`contextvars.ContextVar` and yields a `MutableSpan` handle carrying
`set_attribute(key, value)`, `add_limit_hit(name)` and `set_error(exc_or_kind)`.
On exit it resets the contextvar **through the token returned by `set`**, never
by assigning `None`, stamps `end_ns`, resolves `status`, and calls
`sink.write(span)` exactly once.

An exception leaving the block sets `status = "error"` and `status_message =
redact(f"{type(exc).__name__}: {exc}")` and is **re-raised**. A `sink.write` that raises is caught, logged once at
`WARNING` through `redact`, and never masks the body's exception
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
│   └── (attempts of one invocation share the span; a failover retry is a new span)
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
    duration_ms     INTEGER NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    status_message  TEXT,
    attributes_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans (trace_id, id);
CREATE INDEX IF NOT EXISTS idx_spans_conv  ON spans (conv_id, id);
```

`attributes_json` is a JSON **object**, never an array and never `null`; an
empty attribute set is `"{}"`.

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

The future second implementation — an `OtlpHttpSpanSink` batching spans as
OTLP/HTTP JSON and `POST`ing them to a collector with `httpx`, a serialiser over
the same `Span` objects — is a **NON-GOAL** here (REQ-V160-NG-01).

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
         name, kind, ts, duration_ms, status, status_message,
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

**REQ-V160-MET-02 (MUST) — revive the dead columns.** Nine columns have been
written since v1.3 and read by nothing: `llm_calls.attempt`, `.ts`, `.provider`,
`.model`, `.total_tokens`, `.messages_n`, `.finish_reason`, and
`tool_calls.ts`, `.outcome`. This release makes each of them load-bearing:

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

**REQ-V160-MET-03 (MUST) — the aggregate functions.** Exactly these, with these
names and these return shapes:

```python
usage_by(conn, *, group, since=None) -> list[UsageRow]
error_breakdown(conn, *, since=None) -> ErrorBreakdown
latency_histogram(conn, *, since=None) -> Histogram
token_histogram(conn, *, token_type, since=None) -> Histogram
tool_health(conn, *, since=None) -> list[ToolHealthRow]
limit_hits(conn, *, since=None) -> dict[str, int]
retry_rate(conn, *, since=None) -> tuple[int, int]
context_pressure(conn, *, since=None) -> tuple[float, int]
```

- `group` ∈ `{"model", "day", "purpose", "scenario"}`; anything else raises
  `ValueError` naming the value. `"scenario"` groups by the root span's
  `tg_agent.scenario_id` and reports rows only for traces that carry one, plus
  a single `"(none)"` row for the rest.
- `since` is a `datetime.date` or `None`; when given, rows with
  `ts < since.isoformat()` are excluded. The comparison is lexicographic on the
  fixed-width ISO-8601 UTC strings `storage.utc_now_iso()` already writes.
- `UsageRow` is a frozen dataclass: `key`, `calls`, `errors`, `input_tokens`,
  `output_tokens`, `cached_tokens`, `reasoning_tokens`, `cost_usd`,
  `cost_basis`, `cache_hit_share`, `reasoning_share`. `cache_hit_share` is
  `cached_tokens / input_tokens` over rows where both are non-`NULL`, and is
  `None` — not `0.0` — when no row qualifies. `reasoning_share` is
  `reasoning_tokens / output_tokens` under the same rule. `cost_basis` is
  the set of distinct bases in the group, joined by `", "`.
- `ErrorBreakdown` carries `by_finish_reason: dict[str, int]`,
  `by_error_kind: dict[str, int]`, `total: int`, `error_rate: float`. A `NULL`
  `finish_reason` is bucketed as `"(none)"`; a `NULL` `error_kind` is bucketed as
  `"ok"`.
- `ToolHealthRow`: `tool`, `calls`, `ok`, `error`, `budget`, `rejected`,
  `refused_repeat`, `error_rate`, `p50_ms`, `p95_ms`, `max_consecutive_repeats`,
  `output_tokens_est`. `max_consecutive_repeats` is the longest run of
  consecutive `tool_calls` rows naming the same tool **within one `turn_id` of
  one conversation**, ordered by `id` (REQ-V160-TQ-04).
- `retry_rate` returns `(invocations_with_attempt_gt_1, total_invocations)`.
- `context_pressure` returns `(mean_messages_n, max_messages_n)` over
  `purpose = 'agent'` rows.

**REQ-V160-MET-04 (MUST) — histograms carry the OpenTelemetry metric contract.**
The **names, units and bucket boundaries** are taken

| metric | name | unit | attributes |
|---|---|---|---|
| operation duration | `gen_ai.client.operation.duration` | `s` | `gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model` |
| token usage | `gen_ai.client.token.usage` | `{token}` | the same three, plus **required** `gen_ai.token.type` ∈ `{input, output}` |

`Histogram` is a frozen dataclass: `name`, `unit`, `boundaries: tuple[float, ...]`,
`counts: tuple[int, ...]` of length `len(boundaries) + 1` (the last is the
overflow bucket), `total: int`, `sum: float`, `p50`, `p95`. Bucket `i` counts
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

Both lines are **appended**, so `/stats`'s existing indexed assertions keep
passing, and both are built from `metrics.error_breakdown` and
`metrics.summary_health`, never from their own SQL.

**REQ-V160-MET-06 (MUST) — summary health is counted.** `metrics.py` gains
`summary_health(conn, *, since=None) -> SummaryHealth` with fields `attempts`,
`ok`, `truncated`, `retried`, `failed`. `truncated` counts `llm_calls` rows with
`purpose = 'summary'` and `error_kind = 'truncated'`; `failed` counts turns where
the retry was also truncated (REQ-V160-TQ-01). `/tools` renders it.

**REQ-V160-MET-07 (MUST) — every aggregate is bounded.** No function of §6 may
return an unbounded list. `usage_by` caps at **500** groups and reports a
`"(other)"` row carrying the remainder; `tool_health` caps at **50** tools;
`recent_traces` is capped by its `limit` parameter, itself bounded by
REQ-V160-API-03.

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
trace_tree_section(spans) -> str
gantt_svg(spans, *, width) -> str
tool_health_section(rows, *, summary) -> str
compare_section(baseline, candidate) -> str
esc(value) -> str
```

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
`0 %`; the two token histograms (`input`, `output`) and the duration histogram as
inline SVG; the error breakdown by finish reason and by error kind; and a footer
naming the database path's **basename only**, the schema version, and the
generation timestamp. The four grouping choices are rendered as four in-page
links that change only the query string.

**`/traces` — the trace list.** Query `?limit=<1..500>&conv=<int>`, defaults
`limit=50`. One row per trace, newest first: timestamp, conversation id, turn id,
root span name, scenario id when present, span count, total duration, status, and
the count of `chat` and `execute_tool` children. `trace_id` is rendered as a link
to `/traces/<trace_id>` and displayed **abbreviated to its first 12 characters**
with the full value in the `title` attribute.

**`/traces/<trace_id>` — one trace.** The span **tree**, indented by depth,
each row carrying span name, kind, duration, status, and the span's allowlisted
attributes rendered as `key = value` pairs — with the four content attributes
**excluded unconditionally** (REQ-V160-DSH-07). Above the tree, an inline-SVG
**gantt**: one horizontal bar per span, x-axis scaled to the root span's
duration, y ordered by start time then by tree order, bars coloured by kind and
outlined in the error colour when `status = "error"`. A trace whose root span is
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
counts, shares, schema version, and the database file's **basename**.

**Forbidden, without exception**: message text, prompts, system instructions,
tool arguments, tool outputs, file paths taken from tool arguments, URLs taken
from `fetch` arguments, Telegram user ids, Telegram usernames, chat ids, skill
contents, summary contents, `.env` values, the absolute database path, and the
four `gen_ai.*` content attributes — **even when `OBS_CAPTURE_CONTENT` is true**.
The flag governs what is *stored*; this requirement governs what is *served*, and
there is no configuration that relaxes it.

The proof is a **scanning test**, `T-V160-DSH-05`, parametrised over every
route of §8 and §9 — `/` and `/api/usage` once per grouping — **plus the 404
body and the 405 body**.
The fixture database is seeded with `SYNTHETIC-CANARY-DASHBOARD-1` in **five**
places — a `messages.content` row, a `summaries` row, a recorded tool argument,
a span `status_message` and a span content attribute written with
`OBS_CAPTURE_CONTENT` forced true — and the test asserts the canary appears in
no response body, no response header and no log line, with
`OBS_CAPTURE_CONTENT` pinned **false** for the serving process. `T-V160-DSH-06` repeats the sweep with
the flag true for the *writer*.

**REQ-V160-DSH-08 (MUST) — the index is a page, not a redirect.** `/` is the
usage page itself. `/index.html`, `/favicon.ico` and every other unlisted path
are **404** (REQ-V160-SRV-03); there is no redirect, no directory listing and no
static-file serving of any kind. The server owns no filesystem read path other
than the database.

---

## 8. JSON endpoints (API)

**REQ-V160-API-01 (MUST) — five endpoints, separate from the pages.** The JSON
API is a distinct route family under `/api/`, sharing the metric functions with
the HTML pages and sharing **no** rendering code with them. A page is never
scraped to produce JSON and JSON is never embedded in a page.

| route | query | returns |
|---|---|---|
| `/api/health` | — | `{"status": "ok", "version": "1.6.0", "schema_version": 4, "spans": <int>, "traces": <int>, "generated_at": "<iso>"}` |
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
`gen_ai.conversation.id`, `gen_ai.tool.name`, `gen_ai.tool.call.id`. Fields with
no upstream name are `tg_agent.*` or plain snake_case (`calls`, `errors`,
`cost_usd`, `cost_basis`, `duration_ms`, `p50_ms`, `p95_ms`, `trace_id`,
`span_id`, `parent_span_id`). Histograms serialise as
`{"name": …, "unit": …, "boundaries": [...], "counts": [...], "total": …,
"sum": …, "p50": …, "p95": …}`. `T-V160-API-01` asserts the exact key set of
each endpoint against a literal.

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

**REQ-V160-API-05 (MUST) — bounded response size.** Every endpoint's response is
bounded by §6's caps and §8's `limit` ceiling; no endpoint may stream, paginate
by cursor, or return more than **2 MiB**. Exceeding the bound is a defect in a
cap, not a reason to add pagination (REQ-V160-NG-08).

**REQ-V160-API-06 (MUST) — `/api/health` is the readiness probe and says
nothing else.** It reports liveness, the version string from REQ-V160-VER-01,
the schema version, and two counts. It never reports the database path, the
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

The server holds **one connection per serving thread**, created lazily in a
`threading.local()` and closed at shutdown. A `sqlite3.OperationalError` at request time — a missing or
unreadable database — is answered **503** with a fixed body and logged once
through `redact`.

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

**Why 1536.** The value that must grow is `agent.py:44`'s
`SUMMARY_MAX_TOKENS = 512`, not `LLM_MAX_TOKENS`. `config.py:357`'s
`_check_timeout_budget(llm_timeout_s, llm_max_tokens)` enforces
`llm_timeout_s >= 21.1 + 0.093 × tokens`; with `LLM_MAX_TOKENS` defaulting to
2048 (config.py:270) and `LLM_TIMEOUT_S` to 240.0 the floor is ≈ 211.6 s, with
≈ 28 s of headroom. A summary budget of 2560 would raise the floor to ≈ 259 s —
above the default timeout — so every deployment that had not raised
`LLM_TIMEOUT_S` would fail to start with a `ConfigError`, breaking
REQ-V160-EC-05. **1536** is three times the starving value, below
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

Plumbing: `summarize_conversation` and `_ask_for_summary` gain a keyword-only
`max_tokens: int = SUMMARY_MAX_TOKENS`, so every existing caller, fake and test
keeps today's behaviour; `bot.py` passes `cfg.llm_summary_max_tokens` for the
**retry** only (`T-V160-TQ-02`).

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

**Fingerprint.** For a tool call that produced `outcome = "error"`:

```
fingerprint = sha256(
    tool_name + "\x00" + normalized_error_class + "\x00" + canonical_arguments
).hexdigest()
```

- `tool_name` is `_wire_name(call)` — the vetted name already written to
  `tool_calls.tool`, never the model's raw string (REQ-V12-ID-01 item 4);
- `normalized_error_class` is derived from the tool's JSON error envelope: the
  value of its `"error"` key, lower-cased, with every run of non-alphanumeric
  characters collapsed to a single `_`, stripped, and truncated to **64**
  characters;
- `canonical_arguments` is `json.dumps(parsed_arguments, sort_keys=True,
  separators=(",", ":"), ensure_ascii=False)` when the arguments parse as a JSON
  object, and the raw argument string otherwise. Key order must not change the
  fingerprint.

**State.** A `dict[str, int]` scoped to **one user message**, created when the
root span is created and discarded when it ends. It is never persisted, never
shared between conversations, and never survives a restart.

**The rule.** `TOOL_REPEAT_REFUSAL_THRESHOLD = 2`. When a call's fingerprint has
already **failed twice** within the current user message, the third call with
that fingerprint is **not executed**. Instead the agent injects a tool result
that is a fixed, deterministic envelope:

```json
{"error": "refused: this exact tool call already failed twice in this message; report the failure to the user instead of repeating it"}
```

and records the attempt with `outcome = "refused_repeat"`, `duration_ms = 0`,
and the span attribute `tg_agent.tool.fingerprint` set to the fingerprint's
**first 16 hex characters**. The refusal counts toward
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

| id | title | shape | checks |
|---|---|---|---|
| **S13** | `multi-step-exec` | two dependent `exec` calls: write a file computing a value, then run a second command that consumes the first's output | `tool_used("exec")`, `answer_regex` on the final number, `tool_calls_max(4)` |
| **S14** | `error-recovery` | a first `exec` that fails **by construction** (a deliberate syntax error in the requested snippet); the model must diagnose, fix and re-run | `tool_used("exec")`, `exit_code_seen(nonzero=True)`, `answer_regex` on the corrected result, `tool_calls_max(4)` |
| **S15** | `big-output-answer` | a command whose output exceeds the tool-output cap; the agent must still answer the question about it | `tool_used("exec")`, `answer_regex` on the derived figure, `answer_max_chars(900)`, `tool_calls_max(3)` |
| **S16** | `skill-then-exec` | `load_skill` followed by an `exec` that applies what the skill said | `tool_used("load_skill")`, `tool_used("exec")`, `answer_regex`, `tool_calls_max(4)` |
| **S17** | `fetch-then-exec` | `fetch` from **`wttr.in`** — the one domain `config.DEFAULT_FETCH_DOMAINS` allows and S08 already uses — then an `exec` computing something from the fetched text | `tool_used("fetch")`, `tool_used("exec")`, `answer_regex`, `tool_calls_max(4)`, **`network=True`** |
| **S18** | `multi-turn-summary` | three user turns, then the summary must exist and carry a goal | `answer_regex` on turns 2 and 3, `summary_exists`, `tool_calls_max(3)` |

**Gate per new scenario**: **3 successes out of 3 repeats** at the default
`--repeats`, and the `tool_calls_max` check green in each. A new scenario that
cannot reach 3/3 on the recorded baseline is reported as a finding and its
declared maximum is re-examined.

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

The report records the LM Studio version and served model id, the context
length, per-scenario successes, the `tool_calls_max` results for S13…S18, tokens,
cost and wall clock (REQ-V160-RPT-02.7); `meta` carries the same version and model
id (REQ-V160-BEN-05).

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

- `SPAN_ROW_KEYS = frozenset(storage.SPAN_COLUMNS) - {"conv_id"} | {"conv_seq"}`,
  derived exactly as `LLM_ROW_KEYS` and `TOOL_ROW_KEYS` are (bench.py:165-166),
  so it widens with the schema.
- `REQUIRED_SPAN_ROW_KEYS` is a **literal** tuple, following
  `REQUIRED_LLM_ROW_KEYS` (bench.py:168-182): the required set must not move
  when the schema does.
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

**REQ-V160-BEN-05 (MUST) — `meta` records the instrument.** `meta` (bench.py:671-685)
gains two keys, `lmstudio_version` and `served_model_id`, both strings, both
`null` when the provider is not `lmstudio`. They join `LOCKED_META_FIELDS`
(bench.py:147-155) so that `report --gate` refuses to compare two runs taken against different LM Studio versions.

**REQ-V160-BEN-06 (MUST) — the static report is regenerated from the new
baseline.** At T13, after the baseline lands:

```bash
uv run --locked python devtools/dashboard.py \
  docs/assets/bench/baseline-v1.6.0.json --out docs/assets/dashboard-v1.6.0.html
```

The output is committed.

**REQ-V160-BEN-07 (MUST) — no benchmark runs before the tree is final.** T13 is the
last implementation task before review. If any code, prompt, tool
schema or scenario changes after T13, the baseline is re-recorded and the cost
of the re-run is reported.

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

**REQ-V160-VER-04 (MUST) — the tag, and when it is created.** After **every**
gate of §14 is green on the final tree and the report has landed, the executor
creates the annotated tag:

```bash
git tag -a v1.6.0 -m "tg-agent-bot 1.6.0"
```

Not before. The report records the tag name and the SHA it points
at. Nothing is pushed, and the existing tags `v1.3` and `v1.3-baseline` are never
moved or deleted.

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
4. the `--no-verify` attestation of REQ-V160-EC-09, `<base>`,
   `<implementation-tip>`, and `checks.py replay --range <base>..<implementation-tip>`
   output — **the last two recorded by the evidence-only commit, not the
   provisional report** (REQ-V160-ACC-03);
5. per task, whether the RLM rule was applied and to what (REQ-V160-EC-07);
6. **Benchmark-affecting changes**: the two declared in REQ-V160-EC-06, plus any
   discovered, with the disposition of each;
7. the baseline: LM Studio **version** (exact string) and served **model id**,
   context length, per-scenario successes, `tool_calls_max` results for S13…S18,
   tokens, cost, wall clock, and the informational S01–S12 comparison against
   `baseline-v1.4.json` with its four-reason caption (REQ-V160-BEN-02);
8. the resolved values of §6's two VERIFY markers and the confirmed span-name
   rule `invoke_agent {gen_ai.agent.name}`, with the upstream document version
   and URL, and whether the GenAI conventions were still
   `development`-stability and still in `open-telemetry/semantic-conventions-genai`
   at run time (REQ-V160-PRE-02);
9. the dashboard evidence: the startup log line, the `/status` line, the canary
   sweep result, and the port used;
10. the tag `v1.6.0` and the SHA it points at (REQ-V160-VER-04);
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
preconditions; an unreachable LM Studio is a **blocked run**. The test count
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
| **T5** | §7 (DSH-01…08) | `devtools/dashboard.py:259-630` (the render half) | **yes** |
| **T6** | §8 (API-01…06), §9 (SRV-01…10) | `config.py:180-320` (`load_config`), `storage.py:176-197` | no |
| **T7** | §9 (SRV-01, -02, -05, -09), §12 (VER-03) | `bot.py:55-65` (USAGE block), `:1300-1325` (`main`), `:776-803` (`_render_status`), `tests/conftest.py` (39 lines) | no |
| **T8** | §10 (TQ-01…03, -08) | `agent.py:40-46`, `:560-620`, `:790-820`; `config.py:265-275`, `:340-370` | no |
| **T9** | §10 (TQ-04) | `agent.py:520-620` (tool dispatch and recording) | no |
| **T10** | §10 (TQ-05…07) | `devtools/bench_scenarios.py` (274 lines, whole), `devtools/bench.py:1040-1200` (check evaluation) | **yes** |
| **T11** | §11 (BEN-03…05) | `devtools/bench.py:60-90`, `:140-200`, `:600-700`, `:1000-1040`, `:1850-1890` | **yes** |
| **T12** | §12 (VER-01…06), §16 | `pyproject.toml`, `README.md` (env table + Commands), `AGENTS.md`, `docs/plan.md` | **yes** |
| **T13** | §11 (BEN-01, -02, -06, -07), §3 (PRE-03) | none — the tree is final; only commands run | no |
| **T14** | §14, §15.4 | `devtools/mutation_check.py` **tail only** (`MUTATIONS` entries and `main()`), `config/quality_gates.yaml:200-235` | **yes** |
| **T15** | §16 (REV-01) | the reviewer's own clean context | n/a |
| **T16** | §13, §16 (ACC-01…03) | this run's own artefacts | no |
| **T17** | §16 (ACC-03), Appendix B | this run's own artefacts | no |

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
| `tests/test_v15_standards.py:1726` | the matrix test reads `docs/spec/spec-v1.6.0.md` instead of `spec-v1.5.md` | REQ-V160-GATE-03 |
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
| `T-V160-TRC-04` | a failed LLM invocation and each failover attempt each produce their own `chat` span with `status = "error"`; `llm_calls` rows and `chat` spans are in bijection within the trace |
| `T-V160-TRC-05` | `execute_tool` spans and `tool_calls` rows are in bijection, `budget`, `rejected` and `refused_repeat` outcomes included |
| `T-V160-TRC-06` | `storage.SPAN_COLUMNS` equals `PRAGMA table_info(spans)`; the `span` log payload's key set equals it too |
| `T-V160-TRC-07` | migration 3 → 4 on a database populated at v3: the `spans` table appears, `llm_calls`/`tool_calls` gain nullable `trace_id`/`span_id`, pre-existing rows survive with `NULL` there, and the version reads 4. Also 1 → 4 and 2 → 4 chained, and idempotence on re-`init_schema` |
| `T-V160-TRC-08` | an unsupported version (0, 5, `"x"`) raises the existing `RuntimeError` naming the version |
| `T-V160-TRC-09` | `set_attribute` with an unlisted key raises `ValueError` naming it; with `OBS_CAPTURE_CONTENT` false the four content keys are **absent** from `attributes_json`; with it true they are present |
| `T-V160-TRC-10` | with `OBS_CAPTURE_CONTENT` true and a registered synthetic secret inside the captured content, `attributes_json` contains the redaction marker and not the secret; each content attribute is ≤ 2000 characters |
| `T-V160-TRC-11` | `status_message` is redacted **then** truncated to 200 characters: a secret straddling the 200-character boundary does not survive |
| `T-V160-TRC-12` | an exception inside a span sets `status = "error"` and **re-raises**; a `SpanSink.write` that raises is swallowed, logged once, and does not mask the body's exception |
| `T-V160-TRC-13` | `SqliteSpanSink` writes exactly one row per span end, on the calling thread, on the agent's own connection |
| `T-V160-MET-01` | no column of `llm_calls` or `tool_calls` is written and never read: every name from `PRAGMA table_info` appears in `metrics.py` |
| `T-V160-MET-02` | `usage_by` for each of the four groupings over a seeded database; `group="nope"` raises `ValueError` naming it; `since` excludes older rows and includes the boundary day |
| `T-V160-MET-03` | `cache_hit_share` and `reasoning_share` are `None` — not `0.0` — when no row carries the numerator, and correct when rows do; a mixed-basis group joins bases rather than picking one |
| `T-V160-MET-04` | `error_breakdown` buckets `NULL` finish reason as `"(none)"` and `NULL` error kind as `"ok"`; `error_rate` matches the counted rows |
| `T-V160-MET-05` | `latency_histogram` converts ms → s and places `latency_ms = 1280` in the `1.28` bucket, not the next; bucket count is `len(boundaries) + 1`; the overflow bucket catches a value above the last boundary |
| `T-V160-MET-06` | `token_histogram(token_type="input"|"output")` uses the token boundaries and carries `gen_ai.token.type`; an unknown token type raises |
| `T-V160-MET-07` | `tool_health.max_consecutive_repeats` counts the longest same-tool run **within one turn**, and does not run across a turn or conversation boundary |
| `T-V160-MET-08` | `/stats` and `/api/usage` report the **same** totals for the same database — the one-implementation rule of REQ-V160-MET-01 |
| `T-V160-MET-09` | `limit_hits` counts each constant name at most once per turn and only for the seven of REQ-V160-TRC-10; `MAX_TOOL_CALLS_ACCEPTED` is absent |
| `T-V160-MET-10` | `usage_by` caps at 500 groups with an `"(other)"` remainder row whose totals equal the omitted rows' |
| `T-V160-DSH-01` | no top-level module imports `devtools`; `devtools/dashboard.py` imports `dashboard_render` |
| `T-V160-DSH-02` | the same fixture rendered through `dashboard_server` and through `devtools/dashboard.py` yields byte-identical `usage_section` fragments |
| `T-V160-DSH-03` | every route's HTML has zero `script` elements, zero `on*` attributes, no external `href`/`src`, and parses cleanly |
| `T-V160-DSH-04` | a tool name, model name and status message each containing `<script>`, `"` and `&` are escaped everywhere they appear, HTML and SVG alike |
| `T-V160-DSH-05` | **the canary sweep** (REQ-V160-DSH-07): the canary seeded in five places appears in no body, header or log line of any of the 14 route cases, 404 and 405 included, with `OBS_CAPTURE_CONTENT` false for the server |
| `T-V160-DSH-06` | the same sweep with content capture **on** for the writer: still absent from every response |
| `T-V160-DSH-07` | `gantt_svg` scales bars to the root duration, marks an error span, and emits `role="img"` with `<title>` and `<desc>`; a zero-count histogram bucket is drawn with its label |
| `T-V160-DSH-08` | a trace whose root span is missing renders the orphans with a banner and returns 200, not 500 |
| `T-V160-API-01` | each endpoint's exact top-level key set against a literal; semconv keys spelled verbatim; JSON is sorted and `ensure_ascii=False` |
| `T-V160-API-02` | `/api/traces/<trace_id>` with an unknown but well-formed id is 404, not an empty 200 |
| `T-V160-SRV-01` | `DASHBOARD_PORT` outside 1024–65535, and a non-integer, each raise `ConfigError` naming the variable; the default is 8765 |
| `T-V160-SRV-02` | `DASHBOARD_ENABLED=false` and `--no-dashboard` each suppress the server; the flag wins over a true environment value |
| `T-V160-SRV-03` | the server binds `127.0.0.1` and nothing else; the bind address is not reachable from any config or environment value |
| `T-V160-SRV-04` | with `socket.socket.bind` patched to raise, `bot.main(["--selftest"])` still returns 0 — no server is constructed on that path |
| `T-V160-SRV-05` | all four security headers on a 200, a 404, a 405 and a 400; `Allow: GET, HEAD` on the 405; no `Set-Cookie` anywhere |
| `T-V160-SRV-06` | an `INSERT` through `connect_readonly` raises; a missing database raises rather than being created; the server answers 503 for a missing database |
| `T-V160-SRV-07` | one scripted turn run with and without the dashboard produces identical `llm_calls`, `tool_calls` and `spans` rows modulo ids and timestamps |
| `T-V160-SRV-08` | across a full route sweep, no executed SQL string contains any request parameter value — every one arrives bound |
| `T-V160-SRV-09` | `/status`'s eighth line for each of the four states; lines 1–7 unchanged |
| `T-V160-TQ-01` | a summary response with `finish_reason == "length"` is rejected, recorded `error_kind = "truncated"` at `attempt = 1`, retried once at `attempt = 2`; a second truncation proceeds without a summary and is counted |
| `T-V160-TQ-02` | the first summary attempt requests 512 tokens and the retry requests `cfg.llm_summary_max_tokens`; the default is 1536; `_check_timeout_budget` uses the max of the two budgets and is unchanged at default configuration |
| `T-V160-TQ-03` | each of the five `TOOL_OUTCOMES` is recorded and appears in `tool_health`; an unknown outcome raises before it reaches the database |
| `T-V160-TQ-04` | three identical failing calls: the third is refused, records `outcome = "refused_repeat"` and `duration_ms = 0`, and the injected envelope matches the literal verbatim. Argument key order does not change the fingerprint; a different error class does not match; the state does not survive the user message |
| `T-V160-TQ-05` | `tool_calls_max(0)` raises; the kind is not in `ANSWER_KINDS`; a run with `max_calls + 1` tool rows fails the check and one with exactly `max_calls` passes; refusals count |
| `T-V160-TQ-06` | `_validate_catalog` rejects a scenario whose `tool_calls_max` is below its own `tool_used` count; S13…S18 all import cleanly and ids are unique |
| `T-V160-BEN-01` | `bench.py check` refuses a `bench_schema: 1` document; `report` without `--gate` accepts it and prints the informational banner to stderr; `report --gate` returns `EXIT_NOT_COMPARABLE` |
| `T-V160-BEN-02` | a `scenarios_sha256` mismatch is fatal for `check` and for `report --gate`, and a stderr note for plain `report` |
| `T-V160-BEN-03` | `runs[].spans` round-trips: `attributes` is a parsed object, `conv_id` is replaced by `conv_seq`, and `REQUIRED_SPAN_ROW_KEYS` is enforced only for schema 2 |
| `T-V160-BEN-04` | `meta.lmstudio_version` and `meta.served_model_id` are present, and are members of `LOCKED_META_FIELDS` so `report --gate` refuses a mismatched pair |
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
| `N7` | the database file is deleted while the server runs | 503 with a fixed body; the bot keeps polling; the file is not recreated |
| `N8` | a summary that is truncated twice in a row | the turn completes, no exception escapes, `summary_health.failed` increments, `/stats` shows it |
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
freeze.** T16's report cannot be the reported run; the v1.5 machinery applies
unchanged:

- **T16 lands a provisional `report-v1.6.0.md`** carrying every REQ-V160-RPT-02
  item except item 4's `<implementation-tip>` SHA and every T17 artefact. That
  commit's resulting SHA **is**
  `<implementation-tip>`.
- **T17 re-runs against the final tree**: the six verbatim gates of §14,
  `checks.py run --profile full --since <base>`,
  `checks.py replay --range <base>..<implementation-tip>` and Appendix B. It then
  creates the tag `v1.6.0` (REQ-V160-VER-04) and lands **one evidence-only
  commit** touching `docs/reports/*` and nothing else, recording the tip SHA, the
  replay output, the tag SHA and the remaining evidence. That commit is not
  recursively required to replay against itself.
- **After the final successful run no source, test or config change is
  permitted.** The one exception is a documentation-only correction of the
  evidence that run produced, which re-runs the `commit-msg` checks, the
  `pre-commit` profile, `lint-docs` and `gitleaks-tree` against the final tree.
  Anything else voids the run and T17 is executed again in full.

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
| **T0** | Preconditions (§3): `full` profile green, hooks installed, `doctor` green, test count re-measured, docker, port free. **Record `<base>`** and create the `report-v1.6.0.md` skeleton with its `## Operator inputs` section (LM Studio version, served model id, port override). | every item recorded; `<base>` written before the first commit; a failure emits the blocker template |
| **T1** | `tracing.py`: `Span`, `SpanKind`, the contextvar tracer, `ATTRIBUTE_KEYS`, `SpanSink`, `NullSink`, `set_run_context`. Tests `T-V160-TRC-01`, `-02`, `-09`, `-11`, `-12`. | those tests green; `ruff check .` green; nothing else imports it yet |
| **T2** | `storage.py`: `SCHEMA_VERSION = 4`, `_SPANS_DDL`, the two new columns, `_MIGRATION_3_TO_4`, the accepted-version tuple, `SPAN_COLUMNS`, `add_span`, `spans_for_trace`, `recent_traces`, `connect_readonly`, derived log payloads. Tests `T-V160-TRC-06`, `-07`, `-08`, `-13`, `T-V160-SRV-06`; amends `tests/test_observability.py:431`. | migration tests green from v1, v2 and v3 databases; `test_obs06` green **unamended** |
| **T3** | `agent.py` wiring: the four span seams, `SqliteSpanSink`, `trace_id`/`span_id` on both row families, the `turn_id` repair, `tg_agent.limit_hit`. Tests `T-V160-TRC-03`, `-04`, `-05`, `-10`, `T-V160-MET-09`; amends `tests/test_observability.py:544`. | those tests green; the bijections hold; no other observability test changes |
| **T4** | `metrics.py`: the eight aggregate functions, `Histogram`, `UsageRow`, `ToolHealthRow`, `SummaryHealth`, the caps; `/stats`'s two new lines. Tests `T-V160-MET-01…-08`, `-10`. | those tests green; `/stats`'s first eight lines byte-identical in shape |
| **T5** | `dashboard_render.py` and the `devtools/dashboard.py` refactor onto it; its CLI contract unchanged; `bench_schema ∈ {1,2}` accepted. Tests `T-V160-DSH-01`, `-02`, `-03`, `-04`, `-07`; amends `tests/test_dashboard.py:136`, `:502`. | the 534-line dashboard suite green but for the two amended lines; the byte-identity test green |
| **T6** | `dashboard_server.py`: routing, the allowlist, method handling, parameter validation, the security headers, the per-thread read-only connection, the JSON API, the error paths. Tests `T-V160-API-01`, `-02`, `T-V160-SRV-05`, `-06`, `-08`, `T-V160-DSH-05`, `-06`, `-08`, `N3…N7`. | those tests green; the canary sweep green |
| **T7** | `config.py` (four new fields), `bot.py` (CLI grammar, `--version`, `--no-dashboard`, server start/stop, the `/status` line, `USAGE`), `conftest.py` bind guard, `.env.example`. Tests `T-V160-SRV-01`, `-02`, `-03`, `-04`, `-07`, `-09`, `T-V160-VER-01`, `-02`, `N1`, `N2`, `N9`, `N10`; amends `tests/test_v1_guardrails.py:1398`, `tests/conftest.py`. | those tests green; `bot.py --selftest` green with binding patched to raise |
| **T8** | `agent.py` truncated-summary retry + `LLM_SUMMARY_MAX_TOKENS` + `_check_timeout_budget` extension + `TOOL_OUTCOMES`. Tests `T-V160-TQ-01`, `-02`, `-03`, `N8`. | those tests green; the timeout floor unchanged at default configuration |
| **T9** | `agent.py` fingerprint refusal: fingerprint, per-message state, threshold, the verbatim envelope, `refused_repeat`. Test `T-V160-TQ-04`. | that test green; the envelope matches the literal |
| **T10** | `bench_scenarios.py`: the `tool_calls_max` kind and factory, `max_calls`, the catalogue validation, S13…S18. Tests `T-V160-TQ-05`, `-06`. | those tests green; catalogue imports cleanly; **no existing scenario changed** |
| **T11** | `bench.py`: `BENCH_SCHEMA = 2`, `runs[].spans`, `SPAN_ROW_KEYS`, `REQUIRED_SPAN_ROW_KEYS`, the `mode` parameter, the `check`/`report`/`report --gate` split, `meta.lmstudio_version`/`served_model_id`, the `tool_calls_max` evaluation. Tests `T-V160-BEN-01…-04`; amends `tests/test_bench.py:111`. | those tests green; `REQUIRED_LLM_ROW_KEYS` unchanged; `test_v14_patch` green unamended |
| **T12** | Version and docs: `pyproject.toml` `1.6.0`, `README.md` (Dashboard, Versioning, four env rows, `--version`, `--no-dashboard`, `/status`), `AGENTS.md`, `docs/plan.md`. | `lint-docs` green; the version test green; docs match reality |
| **T13** | **Baseline (§11)**: resolve LM Studio (PRE-03), record `baseline-v1.6.0.json` with all 18 scenarios, commit it, render `dashboard-v1.6.0.html`, produce the informational S01–S12 comparison against `baseline-v1.4.json`. | 3/3 on each new scenario or a recorded finding; LM Studio version and model id recorded; ≈ 40 min, $0 |
| **T14** | `mutation_check.py`: the nine `v160-*` entries; `config/quality_gates.yaml`: the `mutation-v160` gate and both re-measured timeouts; `--list` recorded. | `--select v160-` green; `mutation-all` green inside its new timeout; the matrix test green |
| **T15** | Review (REQ-V160-REV-01) in a clean context; fix or waive findings. | findings closed or waived with reasons |
| **T16** | **Provisional** `report-v1.6.0.md` (RPT-02 minus item 4's tip SHA and T17 artefacts, ledger row included), `tg-post-v1.6.0.md` (RU, < 1500 chars), `docs/llm-usage.md` rows. | `lint-docs` green; `wc -m` recorded; no self-referential SHA claimed |
| **T17** | **Final acceptance (REQ-V160-ACC-03)**: six verbatim gates, `full --since <base>`, `replay --range <base>..<implementation-tip>`, Appendix B; tag `v1.6.0`; the single evidence-only commit. | every gate green on the tree that ships; the tag recorded; the freeze begins |

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
| EC-03 843-test floor, exhaustive §15.1 | `/verify-run` on v1.5.1 | `pytest --collect-only -q` at T0 and T17 |
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
| TREE-01 new files | this spec | `git status` at T17; the report's tree listing |
| TREE-02 changed files | this spec | the commit diffs; §15.1 |
| TREE-03 module naming, import direction | REQ-V15-TREE-02's `config/` guard | `T-V160-TRC-01`, `T-V160-DSH-01` |
| TRC-01 span record, redact-then-truncate | OTel span model; spec-v1.1 truncation finding | `T-V160-TRC-11` |
| TRC-02 the tracer, contextvars | this spec | `T-V160-TRC-02`, `-12` |
| TRC-03 attribute allowlist, fail-closed | semconv-genai attribute names | `T-V160-TRC-09` |
| TRC-04 the span tree | semconv-genai span shapes | `T-V160-TRC-03`, `-04`, `-05`; `E1` |
| TRC-05 schema 3 → 4 | `storage.py:144-216` | `T-V160-TRC-07`, `-08`; `E2` |
| TRC-06 `trace_id`/`span_id` columns, derived payloads | `tests/test_observability.py:738-739` | `T-V160-TRC-06`; `test_obs06` unamended |
| TRC-07 `SpanSink` seam, OTLP as future | user decision 2(a) | `T-V160-TRC-13`; REQ-V160-NG-01 |
| TRC-08 recording seams, `turn_id` repair | `agent.py:255-263`, `storage.py:580-584` | `T-V160-TRC-04`; §15.1's `:544` amendment |
| TRC-09 `OBS_CAPTURE_CONTENT` off, redacted, bounded | user decision 9 | `T-V160-TRC-09`, `-10` |
| TRC-10 limit hits on the root span | `agent.py:29-37` | `T-V160-MET-09` |
| TRC-11 bench traced for free | `bench.py` drives `agent.py` | `T-V160-BEN-03`; `E9` |
| TRC-12 storage helpers, bound parameters | `storage.py` style | `T-V160-SRV-08` |
| MET-01 one module | `AGENTS.md` project layout | `T-V160-MET-08` |
| MET-02 revive the dead columns | nine columns written, never read | `T-V160-MET-01` |
| MET-03 the aggregate functions | this spec | `T-V160-MET-02`, `-03`, `-04`, `-07` |
| MET-04 histogram names, units, boundaries | semconv-genai metrics VERIFY ×2 | `T-V160-MET-05`, `-06`; the resolved markers |
| MET-05 `/stats` grows compatibly | `bot.py:806-826` | `T-V160-MET-08`; the unamended `/stats` assertions |
| MET-06 summary health | REQ-V160-TQ-01 | `T-V160-TQ-01`; `N8` |
| MET-07 every aggregate bounded | this spec | `T-V160-MET-10` |
| DSH-01 one view layer, two callers | user decision 2(c); REQ-V11-NG-06 | `T-V160-DSH-01`, `-02` |
| DSH-02 offline, no script, no CDN | user decision 1; `tests/test_dashboard.py:195` | `T-V160-DSH-03`; `E5` |
| DSH-03 the three pages | user decision 11 | `T-V160-DSH-07`, `-08`; `E4`, `E9` |
| DSH-04 SVG charts legible without colour | this spec | `T-V160-DSH-07` |
| DSH-05 static report contract kept | `devtools/dashboard.py:634-664` | the unchanged CLI tests; `T-V160-DSH-02` |
| DSH-06 escape once, everywhere | `dashboard.py:259-260` | `T-V160-DSH-04` |
| DSH-07 content policy | user decision 5 | `T-V160-DSH-05`, `-06`; `E6` |
| DSH-08 index is a page, no static serving | this spec | `N4` |
| API-01 five endpoints | user decision 11 | `T-V160-API-01` |
| API-02 semconv JSON keys | semconv-genai | `T-V160-API-01` |
| API-03 validation, never echo | this spec | `N5`; `v160-error-echoes-request-input` |
| API-04 unknown trace is 404 | this spec | `T-V160-API-02` |
| API-05 bounded responses | REQ-V160-MET-07 | `T-V160-MET-10` |
| API-06 health says little | this spec | `T-V160-API-01` |
| SRV-01 on by default, two opt-outs | user decision 3 | `T-V160-SRV-02`; `E3` |
| SRV-02 port validated, bind fixed | user decision 3 | `T-V160-SRV-01`, `-03`; `N1`; `v160-bind-address-widened` |
| SRV-03 server surface, allowlist, methods | user decision 3 | `N3`, `N4`; `T-V160-SRV-05` |
| SRV-04 security headers everywhere | user decision 3 | `T-V160-SRV-05`; `E5` |
| SRV-05 nothing else binds | user decision 3 | `T-V160-SRV-04`; `v160-selftest-starts-the-server`; `E7` |
| SRV-06 read-only connection | user decision 4 | `T-V160-SRV-06`; `N7`; `v160-readonly-connection-writable` |
| SRV-07 never takes the bot down | user decision 3 | `N2`, `N6`; `E8` |
| SRV-08 no SQL from request data | this spec | `T-V160-SRV-08` |
| SRV-09 startup line and `/status` | user decision 3 | `T-V160-SRV-09`; `E3` |
| SRV-10 dashboard is not part of the agent | this spec | `T-V160-SRV-07` |
| TQ-01 truncated summary rejected | REL-02, S12 flakiness | `T-V160-TQ-01`; `N8`; `v160-truncated-summary-accepted`; `E10` |
| TQ-02 `LLM_SUMMARY_MAX_TOKENS` sized | `agent.py:44`, `config.py:357`, REQ-V160-EC-05 | `T-V160-TQ-02` |
| TQ-03 closed outcome vocabulary | `agent.py:560-583` | `T-V160-TQ-03` |
| TQ-04 fingerprint refusal | v1.3 candidate S09 2/5 → 4/7, S12 → 0 tools | `T-V160-TQ-04`; `v160-fingerprint-threshold-off-by-one`; `E11` |
| TQ-05 S13…S18 | user decision 12 | `T-V160-TQ-06`; the baseline's per-scenario successes |
| TQ-06 `tool_calls_max` is a new kind | measured: no such field exists | `T-V160-TQ-05` |
| TQ-07 catalogue self-validation | `bench_scenarios.py:266-274` | `T-V160-TQ-06` |
| TQ-08 no feature flags | this spec | REQ-V160-NG-09; no such variable in `config.py` |
| BEN-01 fresh baseline | `bench.py:195`, `:1026-1028` | `docs/assets/bench/baseline-v1.6.0.json`; `E13` |
| BEN-02 old baseline informational | user decision 13 | the report's captioned comparison; `T-V160-BEN-01` |
| BEN-03 `bench_schema` 2, readable past | `bench.py:70`, `:1012-1036`, `:1862-1868` | `T-V160-BEN-01`, `-02`, `-03`; §15.1 |
| BEN-04 spans travel with the run | `bench.py:165-166` | `T-V160-BEN-03` |
| BEN-05 `meta` records the instrument | v1.4 recorded no version | `T-V160-BEN-04` |
| BEN-06 static report regenerated | REQ-V160-DSH-01 | `docs/assets/dashboard-v1.6.0.html` |
| BEN-07 no benchmark before the tree is final | REQ-V160-EC-06 | §17's ordering; the report's timeline |
| VER-01 one version source, `tomllib` | `[tool.uv] package = false` | `T-V160-VER-01`; `N10`; `v160-version-literal-not-pyproject` |
| VER-02 the SemVer policy and the map | user decision 6 | `README.md` § Versioning; this table |
| VER-03 the CLI grammar | `bot.py:61`, `:1306-1321` | `T-V160-VER-02`; `N9`; §15.1's `:1398` |
| VER-04 the tag, after the gates | v1.5.1 created no tag | the recorded tag and SHA; `E14` |
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
| TST-03 nine `v160-*` mutations | REQ-V12-MUT-01 | `mutation_check.py --select v160-` |
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
  And no <script> element appears anywhere in the response

Scenario: E5 — every response carries the security headers
  Given the server is running
  When GET /, GET /nope, POST / and GET /api/usage?group=nope are requested
    Then each response carries the four headers REQ-V160-SRV-04 spells out
  And the 405 response carries Allow: GET, HEAD
  And no response carries Set-Cookie

Scenario: E6 — the canary never leaves the database
    Given a fixture database seeded with SYNTHETIC-CANARY-DASHBOARD-1 in a
        message, a summary, a recorded tool argument, a span status_message and
        a span content attribute
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
  Given a tool call that fails with the same error class twice in one message
  When the model issues the same call a third time
    Then the tool is not executed, the outcome is "refused_repeat", duration_ms
       is 0, and the injected result matches the literal envelope
  And reordering the argument keys does not change the fingerprint
  And a fresh user message starts the count again

Scenario: E12 — the report carries a paste-ready ledger row and valid prompts
  Given the run is complete
  When checks.py lint-docs runs
    Then report-v1.6.0.md contains a "Ledger row" section with no placeholder
       cell whose fenced row's cell count matches the ledger header's
  And every prompt file numbered 71 and above has all seven bullets and four
      blocks

Scenario: E13 — the baseline is recorded against a named instrument
  Given LM Studio answers at one of the three probed addresses
  And .env was updated by a single-line sed and never read
  When bench.py run --tag baseline-v1.6.0 completes
  Then meta carries the exact LM Studio version and served model id
  And each of S13…S18 succeeded 3 times out of 3 within its tool_calls_max
  And the document is committed under docs/assets/bench/

Scenario: E14 — the tag is created last
  Given every gate of section 14 is green on the final tree
  And the evidence-only commit has landed
  When git tag -a v1.6.0 is created
  Then the report records the tag name and the SHA it points at
  And git tag -l still shows v1.3 and v1.3-baseline unchanged
  And nothing is pushed
```

## Appendix C — cross-review log

*filled after cross-review*
