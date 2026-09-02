# tg-agent-bot — implementation specification v1.3 (token economy: observability, audit, optimizations)

This document is the complete contract for **v1.3** on top of the implemented
spec-v1.2 state (commit `1ecc35e`). It is a **delta specification**: spec-v0,
spec-v1, spec-v1.1 and spec-v1.2 remain in force except where a requirement
here explicitly **amends**, **supersedes** or **extends** them (section 2 is
the authoritative amendment table). Everything needed to implement, measure,
test and accept the work is in this file, in the earlier specs, or in files
this spec tells you to change. Do not look for other sources.

Every requirement has a stable `REQ-V13-*` id and is tagged `MUST`,
`SHOULD` or `NON-GOAL`. v1.3 ids never collide with earlier ids. `MUST` =
required for acceptance. `SHOULD` = required unless the report states a
concrete, measured reason it was skipped. `NON-GOAL` = out of scope;
implementing it is a defect, not a bonus.

Target platform: **Linux only**. Language: **Python**. Package manager: **uv**.

Executor model for this run: **claude-opus-5**. This release is not a patch:
it adds a measurement layer, a live benchmark harness, an audit, and a set of
behaviour changes whose value is proven by numbers, not by tests alone. The
difficult parts — deciding what the numbers say, keeping four commits
honest, driving subagents with minimal context — need judgment, so a larger
model is used deliberately.

**What v1.3 is.** Course assignment 5 ("AI Agent Token Audit") applied to
this bot: (1) an observability layer over every LLM call and tool call,
(2) a token audit of the bot on a fixed live benchmark, (3) optimizations
taken from the token-economy lecture and from our own findings, (4) the same
benchmark run again to prove the saving. Assignment targets, checked by the
verdict of section 13.3: **cost per successful task −30 % minimum** against
the measured baseline and **success-rate drop ≤ 2 percentage points**.
Delivery and assignment acceptance are separate: the four commits and the
tags of section 1.2 mark the delivered code either way; the verdict line of
the report (PASS or FAIL, section 13.3) — not the tag — states whether the
assignment target was met.

**What v1.3 also carries.** The open items from the v1.2 audits (`docs/plan.md`
"Carry-over"): one startup-cleanup fix, the coverage tests v1.2 left
untested, a `mutation_check.py` exit-code bug, README wording fixes, and the
llm-usage row for v1.2.

**Reasoning budget for the executor (lecture technique 8, applied to the run
itself).**

- Goal: four green commits (section 1.2) with a measured before/after report.
- Constraints: sections 1, 3, 13 and 15 of this file; AGENTS.md; no new
  dependencies; secrets never printed.
- Acceptance: section 13 gates green at every commit; section 14 report
  complete; section 13.3 verdict recorded honestly whether or not the −30 %
  target was reached.
- Stop conditions: any fix-loop budget in section 1.4 exhausted; a section-3
  precondition fails; the spec contradicts itself or AGENTS.md — stop
  without modifying the tree and emit a report naming the conflicting
  clauses and the observed state (that report is how the executor asks;
  it never picks an interpretation).
  The amendment table (section 2) and the four-commit rule (section 1.2)
  are agreed resolutions of AGENTS.md rules, not contradictions: they never
  trigger this stop condition.

---

## 1. Execution contract

Sections 1 of spec-v0, spec-v1, spec-v1.1 and spec-v1.2 apply unless a line
below overrides them.

### 1.1 Conduct

- **REQ-V13-EC-01 (MUST)** Read this whole file before writing code. The
  spec is the contract; where it contradicts itself or AGENTS.md, stop
  without modifying the tree and emit a report naming the conflicting
  clauses and the observed state — never choose an interpretation (this
  is the "stop and ask" of AGENTS.md performed by an executor that cannot
  wait for an answer). Rows of the section-2 amendment table (including
  the four-commit refinement of "one prompt → one commit") are agreed
  overrides of the earlier text, not contradictions.
- **REQ-V13-EC-02 (MUST)** Test-first per stage: every REQ tagged with a test
  in section 11 gets a failing test before the code that makes it pass.
- **REQ-V13-EC-03 (MUST)** No dependency beyond `httpx` and `python-dotenv`
  (AGENTS.md "Stack"). The observability layer, the benchmark harness, the
  HTML dashboard and the HTML-to-text extractor are **standard library
  only** (`sqlite3`, `json`, `html.parser`, `html`, `re`, `hashlib`,
  `statistics`, `argparse`, `datetime`, `time`).
- **REQ-V13-EC-04 (MUST)** Secrets: `.env` values are never printed, quoted,
  logged, stored in benchmark JSON, dashboards, reports or commits — only
  variable names. Subagents are told never to open `.env`. Redaction
  canaries in tests are synthetic, never a live value: **the one canary
  value used by every v1.3 test is `SYNTHETIC-CANARY-1`**, always injected
  as the value of `OPENROUTER_API_KEY` via
  `load_config(env=..., load_env_file=False)` (the two are written as a
  variable name and a value on purpose — secret scanners flag a
  `NAME=value` pair); `***REDACTED***` is `config.REDACTION` (the
  replacement token), not a canary.
  Model ids (`LMSTUDIO_MODEL`, `OPENROUTER_MODEL`, the price-reference model)
  are **not** secrets and do appear in benchmark metadata and reports;
  base URLs, keys, tokens and Telegram user ids never do.
- **REQ-V13-EC-05 (MUST)** The corpus rule of the lab applies unchanged: no
  course-material content in code, tests, docs, prompts, reports or commits.
- **REQ-V13-EC-06 (MUST)** Docker: only containers carrying this bot's
  `tgexec` label are ever touched (v1.2 REQs unchanged). Never run as root.

### 1.2 Four commits, one prompt

The `go` prompt for this spec produces **exactly four commits on `main`**, in
this order, each self-contained — gates 1–6 green at C1, C3 and C4; gates
1–4 at C2, whose tree differs from C1 only under `docs/` (section 13.1). All
four reference the
same prompt file `docs/prompts/09-go-spec-v1.3.md` in the body. This is a
deliberate, documented refinement of "one prompt → one commit": the
baseline measurement **must be committed on a tree that contains no
optimization code**, otherwise the before/after comparison is not
reproducible from git history. "Never mix results of different prompts"
still holds — all four commits are results of the same prompt.

| # | Commit subject | Content |
|---|---|---|
| C1 | `feat: spec-v1.3 stage A — v1.2 carry-over, observability layer, benchmark harness` | sections 5, 6, 7, 8; tests of 11.1–11.4; mutations of 12 tagged A; of the REQ-V13-PRE-04 variables **only the three pricing ones** (`config.Config` has no stage-C field at C1); `docs/prompts/09-go-spec-v1.3.md` and the stage-A subagent prompt logs |
| C2 | `docs: spec-v1.3 baseline benchmark and token audit` | section 9 outputs only: `docs/assets/bench/baseline.json`, `docs/assets/bench/openrouter-smoke.json`, `docs/assets/dashboard-baseline.html`, `docs/reports/bench-baseline.md`, `docs/reports/bench-openrouter-smoke.md`, `docs/reports/audit-v1.3.md`, and the stage-B prompt log (`docs/prompts/NN-v13-TB1-audit.md`, REQ-V13-EC-13) |
| C3 | `feat: spec-v1.3 stage C — token-economy optimizations` | section 10; tests of 11.5; mutations of 12 tagged C; the stage-C variables of REQ-V13-PRE-04 (each introduced by the task that owns its optimization, section 15); README/AGENTS updates tagged C — the **non-numeric** README sections of REQ-V13-RPT-03 (headline numbers and the `bench-v1.3.md` link do not exist yet); stage-C subagent prompt logs; in the `implemented` / `attempted_removed` states of REQ-V13-RSN-02 the reasoning-probe evidence `docs/assets/bench/reasoning-probe.json` and `docs/reports/bench-reasoning-probe.md` |
| C4 | `docs: spec-v1.3 optimized benchmark, before/after report, Telegram post` | `docs/assets/bench/optimized.json`, `docs/assets/dashboard-v1.3.html`, `docs/reports/bench-v1.3.md`, `docs/reports/report-v1.3.md`, `docs/reports/tg-post-v1.3.md`, `docs/llm-usage.md`, `docs/plan.md`, remaining prompt logs; `README.md` **only** to insert the measured headline numbers and the `docs/reports/bench-v1.3.md` link into the sections C3 created (no other README change in C4) |

- **REQ-V13-EC-07 (MUST)** Immediately after C2 lands, `git diff --stat
  HEAD~1 HEAD` touches only paths under `docs/`; immediately after C3,
  `git diff HEAD~1 HEAD -- devtools/bench_scenarios.py` is empty
  (section 7.6: scenarios are frozen once the baseline exists). Both outputs
  go into the report.
- **REQ-V13-EC-08 (MUST)** Every commit carries the trailers required by the
  lab for `axyi/*` remotes (`Co-Authored-By: Claude Opus 5
  <noreply@anthropic.com>` and the `Claude-Session:` line of the executing
  session). Do not push; the maintainer pushes and opens the compare link.
- **REQ-V13-EC-09 (MUST)** Annotated tags, created as the commits land:
  `v1.3-baseline` on C2, `v1.3` on C4.

### 1.3 Live steps are blocking

- **REQ-V13-EC-10 (MUST)** Gate 5 (`bot.py --selftest-live`) must be
  **fully green** at every commit, including its `lmstudio` check. The v1.2
  exception clause (spec-v1.2 REQ-V12-PRE-01 item 2: "LM Studio unreachable
  → record and proceed") is **withdrawn** for v1.3 and for all later releases.
  If LM Studio is unreachable, stop and report (section 3).
- **REQ-V13-EC-11 (MUST)** The two benchmark runs (section 9 baseline,
  section 13.3 optimized) and the OpenRouter smoke are **blocking contract
  steps**. A **complete run** executes every repeat of every scenario that
  the preflight did not skip (12 scenarios × 3 repeats minus the skipped
  ones, REQ-V13-BEN-11) and records the skip decision explicitly in
  `meta.skipped_scenarios`; skipped repeats produce no `runs[]` entries
  (section 7.4). A file that is aborted (REQ-V13-BEN-05) or lacks a repeat
  of a non-skipped scenario is not a run. The smoke is complete when S02
  ran once and every `llm_calls` row with `error_kind IS NULL` has `usage`
  present (`prompt_tokens` and `completion_tokens` not `NULL`; a failed
  invocation's row is exempt, section 7.4). A stage whose step is
  incomplete is not done.

### 1.4 Bounded fix loops

- Gates 1–6: at most **3** fix iterations per gate per stage; then stop and
  report.
- Benchmark re-runs: at most **2** extra runs per stage (a run is 12 × 3
  scenario executions minus the skipped ones, REQ-V13-EC-11). A re-run is
  allowed only for a harness defect (crash, timeout abort per REQ-V13-BEN-05,
  missing usage, wrong skip set) or a miscalibrated check before C2 (REQ-V13-BEN-12)
  — never to "try for better numbers". There is no tuning loop after C3
  (section 13.4).
- Review findings (section 13.5): one fix round per review, all findings
  addressed or explicitly declined with a reason in the report.

### 1.5 RLM discipline (lab rule 5)

- **REQ-V13-EC-12 (MUST)** The executor's main context does **not** read
  benchmark JSON files, HTML dashboards, or whole source files to "get
  oriented". It reads: this spec, `bench.py` stdout summaries (≤ 40 lines by
  design, section 7.7), generated markdown reports, and subagent summaries.
  Everything else is delegated per the execution plan in section 15; each
  subagent gets a brief of ≤ 8 lines plus the REQ ids it owns, and returns a
  summary, never file dumps.
- **REQ-V13-EC-13 (MUST)** Every subagent brief is logged as its own file
  `docs/prompts/NN-v13-<task-id>-<slug>.md` (numbering continues from 10),
  per AGENTS.md "every prompt sent to an LLM". Review prompts follow the same
  rule.

---

## 2. Amendments to earlier specs — authoritative table

| Earlier requirement | v1.3 action | Where |
|---|---|---|
| spec-v1.2 REQ-V12-PRE-01 item 2 (gate-5 LM Studio exception) | **withdrawn** | REQ-V13-EC-10 |
| AGENTS.md "One prompt → one commit" | **refined**: the v1.3 go prompt yields four sequential commits, all referencing the same prompt file | REQ-V13-EC-07 |
| spec-v1 storage schema v2 | **extended** to v3: `llm_calls`, `tool_calls` tables; migration 2→3 | REQ-V13-OBS-03 |
| spec-v1 `LLMResponse` (content, tool_calls, finish_reason) | **extended** with `usage` and `reasoning_chars` | REQ-V13-OBS-01 |
| spec-v1 `llm/base.py` request body (literal `temperature: 0`, `stream: False`, `tool_choice: "auto"`) | **unchanged values**, lifted into the module constant `REQUEST_DEFAULTS` that the payload builder reads and the benchmark locks in `meta.constants` | section 7.4, REQ-V13-BEN-01 |
| spec-v1 exec envelope (stdout/stderr capped at `EXEC_MAX_STREAM_BYTES`) | **extended**: the 4096-byte capture cap stays the security ceiling; the model-visible text is additionally compacted (head/tail window, duplicate collapse) with a per-call `max_output_chars` | REQ-V13-TOO-01..04 |
| spec-v1.1 fetch tool (raw body up to `FETCH_MAX_BYTES` inline) | **extended**: HTML→text extraction, inline window `max_chars`, full text saved under the sandbox `fetch/` directory | REQ-V13-TOO-05..09 |
| spec-v1 system prompt text (`SYSTEM_PROMPT`) | **superseded** by the compressed prompt of REQ-V13-PFX-01; the date/time line moves out of the system prompt | REQ-V13-PFX-01, REQ-V13-CCH-01 |
| spec-v1 tool schema descriptions | **superseded** by the compressed descriptions of REQ-V13-PFX-02 (parameters, enums, limits unchanged) | REQ-V13-PFX-02 |
| spec-v1 context assembly (`_assemble_context`: verbatim tool results from the whole window) | **extended**: stale tool results are stubbed at request time, DB unchanged | REQ-V13-HST-01..05 |
| spec-v1 command set `/new /status /summary /model /reload_skills` | **extended** with `/stats` | REQ-V13-OBS-07 |
| spec-v1 `_execute_tool_calls(normalized, *, skills, runner, tools_used, fetcher, audit, on_tool)` | **extended** with keyword-only `conn`, `conv_id`, `turn_id` | REQ-V13-OBS-05 |
| spec-v1 `run_agent(*, conn, conv_id, llm, skills, runner, now, sleep, cfg, fetcher, audit, recent_goals, should_stop, on_tool)` and spec-v1 `summarize_conversation(conn, conv_id, llm, cfg)` | **extended** with keyword-only `resolve_cost: CostResolver \| None = None` | REQ-V13-OBS-04, REQ-V13-PRC-02 |
| spec-v1.1 `tools.fetch_url(url, *, allowed_domains, client, resolve, …)` | **extended** with keyword-only `workdir: Path` and `sandbox_max_bytes: int` (the per-run sandbox the full text is saved under); `bot.main()` and the benchmark's `fetcher_factory` supply them | REQ-V13-TOO-06, REQ-V13-BEN-07 |
| spec-v1.1 `_Capture.snapshot() -> (bytes, truncated)` | **extended** to `(bytes, truncated, fed)` | REQ-V13-TOO-02 |
| spec-v1.1 startup cleanup (`_remove_sandbox_entry`) | **fixed**: the recovery chmod loop never follows symlinks | REQ-V13-CO-01 |
| spec-v1.2 mutation gate (31 mutations) | **extended** with the 33 listed v1.3 mutations — final total at least 64, all killed | section 12 |
| README "Safety" wording (layer-2 refusal, reap, entries-eat-disk) | **fixed** | REQ-V13-CO-07 |

Everything else in spec-v0 … spec-v1.2 stands.

---

## 3. Preconditions (verify before writing any code)

1. **REQ-V13-PRE-01 (MUST)** Git: `main` at `1ecc35e`, clean tree. Gates 1–4
   and 6 green on the untouched tree (31/31 mutations killed).
2. **REQ-V13-PRE-02 (MUST)** Live environment: `.env` provisioned;
   `LMSTUDIO_BASE_URL` reachable and `GET /v1/models` lists `LMSTUDIO_MODEL`
   as loaded; `LMSTUDIO_CONTEXT_LENGTH` is set — it is the **configured**
   context length, and that is all the run verifies: whether it equals the
   context the model was actually loaded with is a maintainer precondition
   outside this run's verification (the bot cannot read it and the executor
   does not ask). The benchmark locks the configured value
   (`meta.context_length`, REQ-V13-BEN-01) and the report calls it
   "configured", never a measured server property; Docker
   daemon reachable and `EXEC_DOCKER_IMAGE` pulled; `OPENROUTER_API_KEY`
   valid and `OPENROUTER_MODEL` set (needed for the smoke run only). Run gate
   5 to check all of it. If any check fails: stop and report — do not start
   stage A on a box where stage B cannot run.
3. **REQ-V13-PRE-03 (MUST)** Network for scenario S08 (`wttr.in`) is
   *optional*: unreachable → S08 is skipped in both benchmark runs
   identically (section 7.5). `FETCH_ALLOWED_DOMAINS` must include `wttr.in`
   (the default). Record the outcome in the report.
4. **REQ-V13-PRE-04 (MUST)** New optional environment variables (defaults in
   parentheses; documented in README "Configure" and `.env.example`; all
   validated by `load_config` with the same error style as existing ones).
   Each variable is introduced — `config.Config` field, validation,
   `.env.example` line — by the commit and task named in brackets; a
   variable whose field does not exist in `config.Config` at a commit is
   not parsed there and not in that commit's `.env.example` (the C1
   `Config` has no stage-C field; the benchmark harness records such a
   variable as `null`, REQ-V13-BEN-10):
   - `LLM_PRICE_REF_MODEL` (empty) [C1, TA3] — an OpenRouter model id whose
     `/models` pricing is used as the **reference price** for LM Studio
     calls (section 6.3). Empty → LM Studio cost is `NULL` and the benchmark
     falls back to token-based comparison (section 13.3).
   - `LLM_PRICE_INPUT_USD_PER_MTOK`, `LLM_PRICE_OUTPUT_USD_PER_MTOK` (empty)
     [C1, TA3] — manual fallback prices when `/models` is unreachable; both
     or neither.
   - `EXEC_OUTPUT_DEFAULT_CHARS` (1500), range 200–4096 [C3, TC1] — inline
     window per stream for exec results.
   - `FETCH_INLINE_DEFAULT_CHARS` (5000), range 500–20000 [C3, TC1] — inline
     window for fetch results.
   - `HISTORY_TOOL_STUB` (`on`), `on|off` [C3, TC2] — stale-tool-result
     stubbing (`off` exists for A/B and for the rollback path only).
   - `LLM_SUMMARY_MODEL` (empty) [C3, TC5] — `<provider>:<model>` routing
     for the summary purpose (section 10.6).
   - `LLM_REASONING` (`auto`), `auto|on|off` [C3, TC4] — only in the
     `implemented` state of REQ-V13-RSN-02 (absent in `not_applicable` and
     `attempted_removed`).
5. **REQ-V13-PRE-05 (MUST)** Before relying on any provider field name
   (OpenRouter usage accounting, LM Studio reasoning fields, LM Studio
   thinking switches), verify it against current documentation via the
   context7 tools (`mcp__context7__resolve-library-id` →
   `mcp__context7__query-docs`) or the provider's official docs, and cite the
   page in the report. Never assume a field exists: absent → `NULL`, never a
   guessed value.

---

## 4. Required file tree (delta)

```
tg-agent-bot/
  agent.py                    ✎ call recording, context stubbing, prefix, reasoning switch
  bot.py                      ✎ /stats, carry-over fix, tool-call recording hook
  config.py                   ✎ new env vars (REQ-V13-PRE-04)
  metrics.py                  ⊕ aggregates over llm_calls/tool_calls (shared by /stats, bench, dashboard)
  storage.py                  ✎ schema v3, llm_calls/tool_calls writers and readers
  tools.py                    ✎ compact_output, html_to_text, fetch save-to-sandbox, schema text
  llm/__init__.py             ✎ build_llm_client: summary-model routing (RTE-01)
  llm/base.py                 ✎ Usage dataclass, usage parsing, reasoning fields, latency, describe()
  llm/lmstudio.py             ✎ describe(); reasoning switch only in the RSN-02 `implemented` state
  llm/openrouter.py           ✎ usage accounting request flag, cache_control, describe()
  llm/failover.py             ✎ describe() of the active client
  llm/pricing.py              ⊕ OpenRouter /models pricing lookup + cost formula
  devtools/bench.py           ⊕ benchmark harness: run / report / check
  devtools/bench_scenarios.py ⊕ the 12 frozen scenarios (Appendix C)
  devtools/dashboard.py       ⊕ static HTML dashboard generator
  devtools/mutation_check.py  ✎ --only exit code; the 33 listed v1.3 mutations (total ≥ 64)
  tests/test_v13_carryover.py ⊕ section 5
  tests/test_observability.py ⊕ section 6
  tests/test_pricing.py       ⊕ section 6.3
  tests/test_bench.py         ⊕ section 7
  tests/test_dashboard.py     ⊕ section 8
  tests/test_tool_output.py   ⊕ section 10.1 (exec compaction, fetch text)
  tests/test_history_stub.py  ⊕ section 10.2
  tests/test_prefix.py        ⊕ sections 10.3, 10.4
  tests/test_routing.py       ⊕ section 10.6 (and 10.5 if implemented)
  tests/fixtures/bench/       ⊕ two small bench JSON fixtures for report/dashboard tests
  docs/assets/bench/          ⊕ baseline.json, openrouter-smoke.json, optimized.json
  docs/assets/dashboard-baseline.html, dashboard-v1.3.html ⊕
  docs/reports/bench-baseline.md, bench-openrouter-smoke.md, audit-v1.3.md, bench-v1.3.md, report-v1.3.md, tg-post-v1.3.md ⊕
  docs/prompts/09-go-spec-v1.3.md, 10-v13-*.md … ⊕
  docs/llm-usage.md, docs/plan.md, README.md, AGENTS.md, .env.example ✎
  .gitignore                  ✎ `.bench/` (per-run bench directories, REQ-V13-BEN-03), `docs/assets/bench/*.log` (REQ-V13-BEN-13)
```

---

## 5. Carry-over from the v1.2 audits (stage A)

- **REQ-V13-CO-01 (MUST)** `bot._remove_sandbox_entry`: the top-level
  `entry.is_symlink()` guard already exists; the hole is the recovery loop
  `for path in failed_paths: os.chmod(path, stat.S_IRWXU)`, which **follows
  symlinks**. A sandbox directory with mode `0o555` whose child is a symlink
  to a bot-owned file outside the sandbox makes `rmtree`'s first pass fail on
  the child, and the loop then chmods the *target*. Fix: skip
  `os.path.islink(path)` entries in that loop (a symlink never needs a mode
  change; unlinking it only needs its parent directory's mode, which the
  loop fixes). Test: sandbox dir `0o555` containing a symlink to an outside
  file of mode `0o644` — after startup cleanup the entry is gone and the
  target's mode and content are unchanged (`try/finally` restores modes).
- **REQ-V13-CO-02 (MUST)** Test the `owner=owner_key()` binding of the
  orphan reap: with two containers labelled with different owner keys (fake
  docker CLI), only the one whose owner label equals this process's
  `owner_key()` is reaped.
- **REQ-V13-CO-03 (MUST)** Test `resolve`'s late binding in
  `_startup_docker_wiring` / `_check_allowlist_resolution`: with
  `resolve=None` the function looked up **at call time** is used —
  monkeypatching `socket.getaddrinfo` after import is observed.
- **REQ-V13-CO-04 (MUST)** Test `resolve_host`'s `OSError`-only catch: an
  `OSError` from the resolver yields the "unresolvable" outcome; a
  non-`OSError` exception propagates unchanged.
- **REQ-V13-CO-05 (MUST)** Test the INF-01 clauses of `_ensure_empty_resolv`
  separately: (a) a file owned by a different uid (monkeypatched `st_uid`)
  is rejected/recreated; (b) `st_nlink != 1` is rejected; (c) the open uses
  `O_NONBLOCK` — a FIFO at the path does not hang the call (test with a
  timeout guard) and is rejected.
- **REQ-V13-CO-06 (MUST)** `devtools/mutation_check.py --only <unknown-id>`
  exits **1** with `unknown mutation id: <id>` on stderr (today it silently
  runs nothing). Test via subprocess with `--list` semantics untouched.
- **REQ-V13-CO-07 (MUST)** README fixes: the layer-2 refusal wording, the
  orphan-reap description, and the "sandbox entries consume disk" note, as
  listed in `docs/plan.md` v1.3 carry-over. `docs/llm-usage.md` v1.2 row:
  replace `not computed` by the ≈ $33.11 figure with the note that it was
  measured after the fact from the local transcript.
- **REQ-V13-CO-08 (MUST)** The chmod-000 tests (v1.2 quota tests) restore
  permissions in `try/finally` so an assertion failure never leaves an
  unreadable temp dir behind.

---

## 6. Observability layer (stage A)

The layer answers the assignment's per-call and per-tool-call schema exactly
and never stores message content.

### 6.1 Usage and reasoning fields on the response

- **REQ-V13-OBS-01 (MUST)** `llm/base.py`: new frozen dataclass
  `Usage(prompt_tokens: int | None, completion_tokens: int | None,
  total_tokens: int | None, cached_tokens: int | None,
  reasoning_tokens: int | None, provider_cost_usd: float | None)`.
  `LLMResponse` gains `usage: Usage | None` and `reasoning_chars: int`
  (default 0). `parse_response` fills them from the OpenAI-compatible
  `usage` object: `prompt_tokens`, `completion_tokens`, `total_tokens`,
  `prompt_tokens_details.cached_tokens`,
  `completion_tokens_details.reasoning_tokens`, and — OpenRouter usage
  accounting — `usage.cost`; each missing → `None`, never 0. A non-integer
  where an integer is expected → `None` (not a malformed response: usage is
  advisory). Stage A also **asks** for the accounting: every OpenRouter
  request body carries `usage: {"include": true}` (field name verified per
  REQ-V13-PRE-05; request-shape test in section 11.2), so that the B2 smoke
  (REQ-V13-AUD-01) can rely on `usage` rows from C1 on — the flag is an
  observability prerequisite, not a stage-C optimization. LM Studio
  requests are unchanged.
- **REQ-V13-OBS-02 (MUST)** Reasoning text: if the message carries
  `reasoning_content` or `reasoning` (string), its length is
  `reasoning_chars`. If `content` contains `<think>…</think>` blocks, they
  are **removed from `content`** (the user never sees them; today they would
  be delivered) and their length is added to `reasoning_chars`. Test both
  paths and the no-reasoning path. This is a correctness fix and belongs to
  stage A, so the baseline already includes it.
- **REQ-V13-OBS-03 (MUST)** Storage schema **v3**: `SCHEMA_VERSION = 3`,
  migration 2→3 creates the two tables below (idempotent; a v2 fixture DB
  migrates without touching existing rows; test).

  ```sql
  CREATE TABLE llm_calls (
    id INTEGER PRIMARY KEY,
    conv_id INTEGER NOT NULL REFERENCES conversations(id),
    turn_id INTEGER,                 -- assistant turn produced by this call; NULL for summary / failed
    purpose TEXT NOT NULL CHECK (purpose IN ('agent', 'summary')),
    round INTEGER NOT NULL,          -- agent loop round (1-based); 0 for summary
    attempt INTEGER NOT NULL,        -- run_agent's `attempts` counter after increment: the 1-based
                                     -- ordinal of the llm.complete invocation within the message
    ts TEXT NOT NULL,                -- ISO-8601 UTC, request start
    provider TEXT NOT NULL, model TEXT NOT NULL,
    prompt_tokens INTEGER, completion_tokens INTEGER, total_tokens INTEGER,
    cached_tokens INTEGER, reasoning_tokens INTEGER,    -- NULL = not reported
    reasoning_chars INTEGER NOT NULL DEFAULT 0,
    prompt_chars INTEGER NOT NULL,
    prompt_chars_by_role TEXT NOT NULL,   -- JSON {"system":n,"tools":n,"user":n,"assistant":n,"tool":n}
    messages_n INTEGER NOT NULL, tools_exposed INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL, finish_reason TEXT,
    tool_calls_n INTEGER NOT NULL DEFAULT 0,
    error_kind TEXT,                 -- NULL on success; LLMError.kind otherwise
    cost_usd REAL, cost_basis TEXT   -- 'provider' | 'openrouter-list' | 'openrouter-list-stale' |
                                     -- 'reference:<model>' | 'reference-stale:<model>' | 'manual' | NULL
                                     -- (the two stale forms per REQ-V13-PRC-02)
  );
  CREATE TABLE tool_calls (
    id INTEGER PRIMARY KEY,
    conv_id INTEGER NOT NULL REFERENCES conversations(id),
    turn_id INTEGER NOT NULL, tool_call_id TEXT NOT NULL, tool TEXT NOT NULL,
    ts TEXT NOT NULL,
    input_chars INTEGER NOT NULL,        -- len(arguments JSON)
    raw_output_chars INTEGER NOT NULL,   -- stream/text chars before compaction (REQ-V13-TOO-03; == output_chars in stage A)
    output_chars INTEGER NOT NULL,       -- the same measure after compaction (what the model was shown)
    output_tokens_est INTEGER NOT NULL,  -- estimate_tokens(output)
    duration_ms INTEGER NOT NULL,
    outcome TEXT NOT NULL                -- 'ok' | 'error' | 'rejected' | 'budget'
  );
  ```

- **REQ-V13-OBS-04 (MUST)** `agent.run_agent` records **one row per
  `llm.complete` invocation** it makes, including failed ones (`error_kind`
  set, token columns `NULL`, latency measured around the invocation), via
  `storage.add_llm_call(...)`. The unit is the invocation, not the HTTP
  request: `run_agent`'s own retries are separate invocations (separate
  rows, `attempt` 1, 2, …), whereas a fallback performed *inside* one
  invocation by `FailoverLLMClient` is not a separate row — the row carries
  the outcome of the invocation and the client that served it.
  `provider`/`model` come from `LLMClient.describe() -> tuple[str, str]`
  (provider, model), a new read-only method, read **after** the invocation;
  `FailoverLLMClient.describe()` reports the client that served the last
  call. `summarize_conversation` records with `purpose='summary'`,
  `round 0`, `attempt 1`. Both functions gain the keyword-only parameter
  `resolve_cost: CostResolver | None = None` (REQ-V13-PRC-02): after each
  invocation the row's `cost_usd`/`cost_basis` are whatever
  `resolve_cost(provider, model, usage)` returns; `None` (the pytest
  default, and a bot with no price source) stores `NULL`/`NULL` — the
  recording code never fetches, reads `bot_state` or computes prices
  itself. Tests: a stub resolver's return lands in the row; `None` →
  `NULL`; the resolver is called with the `describe()` values read after
  the invocation.
- **REQ-V13-OBS-05 (MUST)** `agent._execute_tool_calls` records every tool
  call via `storage.add_tool_call(...)` — executed, rejected (excess),
  budget-refused — with the outcome, timing (`time.monotonic`), sizes. Its
  signature gains three keyword-only parameters, `conn`, `conv_id` and
  `turn_id` (the value `run_agent` already mints via
  `storage.next_turn_id(conn, conv_id)` for `normalize_tool_calls`); the
  amendment is listed in section 2.
- **REQ-V13-OBS-06 (MUST)** One structured INFO log line per LLM call and
  per tool call, JSON on one line, prefixed `llm_call ` / `tool_call `,
  whose keys are **every column of the stored row** — for `llm_call` the
  `llm_calls` columns of 7.1 (`id`, `conv_id`, `turn_id`, `purpose`,
  `round`, `attempt`, `ts`, `provider`, `model`, `prompt_tokens`,
  `completion_tokens`, `total_tokens`, `cached_tokens`, `reasoning_tokens`,
  `reasoning_chars`, `prompt_chars`, `prompt_chars_by_role` as a nested
  object, `messages_n`, `tools_exposed`, `latency_ms`, `finish_reason`,
  `tool_calls_n`, `error_kind`, `cost_usd`, `cost_basis`), for `tool_call`
  the `tool_calls` columns (`id`, `conv_id`, `turn_id`, `tool_call_id`,
  `tool`, `ts`, `input_chars`, `raw_output_chars`, `output_chars`,
  `output_tokens_est`, `duration_ms`, `outcome`) — and never content,
  arguments, URLs or secrets (goes through `config.redact` anyway;
  `conv_id` is the local database id, not a Telegram id). Test: the log
  line parses as JSON, its key set equals the table's column set, and it
  has no `content` key.
- **REQ-V13-OBS-07 (MUST)** New command **`/stats`** (owner-only like the
  others): plain text ≤ 3500 chars, fixed layout (tests assert labels):

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

  `n/a` where the provider reports nothing. The basis label is computed
  **per side** from the distinct non-null `cost_basis` values of the rows
  summed on that side: exactly one → that value; several → `mixed`; none
  → that side's cost reads `n/a (no pricing)` (test: three fixture
  databases — one basis, two bases, no basis). `/status` gains one line:
  `Tokens this conversation: in N / out M`.
- **REQ-V13-OBS-08 (MUST)** `metrics.py` (stdlib): pure functions over rows —
  `conversation_stats(conn, conv_id)`, `global_stats(conn)`,
  `resent_tokens(calls) -> (resent, new)`, `top_tools(conn, limit)`,
  `turn_timeline(conn, conv_id, turn_id)`, `context_growth(calls)`. The
  re-sent metric: for calls of one conversation ordered by `id` (in a
  benchmark file: one `conv_seq` group, section 7.4),
  `new_1 = prompt_1`, `new_i = max(0, prompt_i − prompt_{i−1})`,
  `resent_i = prompt_i − new_i`; `resent_share = Σresent / Σprompt`. Calls
  with `prompt_tokens IS NULL` are skipped. `/stats`, `bench.py report` and
  `dashboard.py` all use these functions — one implementation.

### 6.2 What is deliberately not stored

- **REQ-V13-OBS-09 (MUST)** No message content, tool arguments, tool output,
  URLs or Telegram ids in `llm_calls`/`tool_calls`, log lines, dashboards or
  benchmark JSON *except* the benchmark's redacted final answers (needed for
  the checks; section 7.4).

### 6.3 Pricing and cost

- **REQ-V13-PRC-01 (MUST)** `llm/pricing.py`: `Price(input_usd_per_mtok,
  output_usd_per_mtok, cached_input_usd_per_mtok | None, source: str,
  fetched_at: str)`; `fetch_openrouter_prices(client, model_ids) ->
  dict[str, Price]` from `GET https://openrouter.ai/api/v1/models` (field
  names verified per REQ-V13-PRE-05; per-token strings converted to
  per-million floats); `cost_usd(usage, price) -> float | None`:
  `(prompt − cached) × in + cached × cached_in + completion × out`, with
  `cached` treated as 0 when `NULL`, and `cached_in = in` when the provider
  publishes no cache price; returns `None` (never 0.0, never raises) when
  `prompt_tokens` or `completion_tokens` is `None` — a failed call or a
  provider that reports partial usage stores `cost_usd = NULL` (test: each
  of the two fields missing → `None`; both present with `cached = None` →
  the formula).
- **REQ-V13-PRC-02 (MUST)** Cost basis per call, **strict precedence — the
  first available wins**: (1) OpenRouter call with `provider_cost_usd`
  present → `basis='provider'`, that value; (2) a price fetched **in this
  process** for the call's model (OpenRouter call → `basis='openrouter-list'`;
  LM Studio call with `LLM_PRICE_REF_MODEL` set → the reference model's
  price, `basis='reference:<model>'`); (3) manual env prices
  (`LLM_PRICE_INPUT_USD_PER_MTOK`/`LLM_PRICE_OUTPUT_USD_PER_MTOK`, both
  required, non-negative) → `basis='manual'`; (4) the previously persisted
  fetched price (`bot_state.pricing_json`, its own `fetched_at`) →
  `basis='openrouter-list-stale'` / `'reference-stale:<model>'`; (5)
  otherwise `NULL`. Manual prices therefore override a stale persisted
  price but never a fresh fetch. Prices are fetched **once** at bot startup
  and once per `bench.py run` CLI invocation — never per scenario-repeat
  (stored under `bot_state` key `pricing_json` with `fetched_at`; a failed
  fetch logs a warning and falls through to (3) and (4) — never blocks
  startup). **The path from the fetch to the recording point is one
  explicit interface**, so TA2 and TA3 cannot invent two, and it is split
  so that the sequential order TA2 → TA3 (section 15) has no forward
  dependency: the **type** lives with `Usage` in `llm/base.py` (TA2) —
  `CostResolver = Callable[[str, str, Usage | None], tuple[float | None,
  str | None]]`, `(provider, model, usage) -> (cost_usd, cost_basis)` —
  and the **implementation** lives in `llm/pricing.py` (TA3):
  `make_resolver(cfg, snapshot: dict[str, Price] | None, *, snapshot_basis:
  str | None, stale: dict | None) -> CostResolver`, a pure closure over the
  values above that implements the precedence (1)–(5) per call; it holds
  no global state and performs no I/O. TA2 ships the threading with the
  `None` default and stub resolvers in its tests (REQ-V13-OBS-04), so its
  suite is green before `llm/pricing.py` exists; TA3 then adds
  `make_resolver` and the **single** `bot.py` wiring — the startup fetch,
  the `bot_state` persist, building the resolver once and passing it to
  `run_agent`/`summarize_conversation` — nobody else touches that path.
  `bench.py run` builds it once per CLI invocation from the snapshot it
  also writes to `meta.pricing`; both hand it down as the keyword-only
  `resolve_cost` of `run_agent` and `summarize_conversation`
  (REQ-V13-OBS-04, section 2). Because the
  snapshot lives in the resolver and not in a database, the fresh
  per-scenario DBs of REQ-V13-BEN-03 price every call through step (2)
  with the same snapshot. Tests: one per precedence step, with the
  next-lower source present to prove the ordering (all through
  `make_resolver`, no network).
- **REQ-V13-PRC-03 (MUST)** Reference-priced costs are always labelled as
  estimates in `/stats`, reports and dashboards ("reference price of
  `<model>` on OpenRouter as of `<date>`; local inference is free").

---

## 7. Benchmark harness (stage A)

Pytest cannot measure tokens (all LLM traffic is faked), so measurement is a
separate, live, deterministic-as-possible harness.

### 7.1 CLI

- **REQ-V13-BEN-01 (MUST)** `devtools/bench.py` with subcommands:
  - `run --tag <tag> [--repeats N=3] [--only <id>[,<id>]] [--provider
    lmstudio|openrouter] [--timeout-s N=600] [--max-cost-usd X] [--out PATH]`
    → writes
    `docs/assets/bench/<tag>.json` (or `--out`) and prints the ≤ 40-line
    summary of 7.7. Exit 0 when every non-skipped run completed (success or
    checked failure); 1 on a harness error; 3 when a run had `usage_missing`
    (a **completed** invocation — an `llm_calls` row with `error_kind IS
    NULL` — reported no usage: measurement impossible, stop; failed
    invocations are exempt, section 7.4).
  - `report --baseline A.json [--candidate B.json] [--out PATH] [--gate]` →
    markdown (7.8); with `--gate` exits 1 when the section-13.3 verdict is
    FAIL, 2 when the two files are not comparable: any of the **locked meta
    fields** `provider`, `model`, `context_length`, `repeats`, `timeout_s`,
    `scenarios_sha256`, `skipped_scenarios`, `constants`, `config_sha256`
    differs (the one-line reason names the field), or the two `env_flags`
    objects violate the treatment rule of REQ-V13-BEN-03 (the reason names
    the key). `pricing` may differ — it is the price snapshot — and the
    `env_flags` and `pricing` of both files are printed side by side in the
    report.
  - `check <json>` → validates against the schema **and the field contract**
    of 7.4 (types, nullability, every `runs[].totals` and `summary` value
    recomputed from the embedded rows) **and the run set**: with
    `SCENARIOS` imported from `devtools/bench_scenarios.py` (whose bytes
    must hash to `meta.scenarios_sha256`, else exit 1 — a file produced
    from another scenario set cannot be validated), `runs[]` holds exactly
    one entry per (scenario ∈ `SCENARIOS` ∖ `meta.skipped_scenarios`,
    repeat ∈ 1..`meta.repeats`) — an omitted pair, a duplicate or an
    unknown id is exit 1 — `meta.skipped_scenarios` ⊆ the ids with
    `network: true`, and `summary.per_scenario` has exactly the
    non-skipped ids as keys. A harness defect that drops a scenario from
    both files is therefore caught by `check`, never by eye. Exit 0 valid;
    1 schema, run-set or arithmetic
    mismatch; 2 `meta.aborted` present (REQ-V13-BEN-05); 3 `usage_missing`
    or invalid token counts — any `llm_calls` row with a negative token
    column or `cached_tokens > prompt_tokens`, or a successful run with an
    `llm_calls` row that has `error_kind IS NULL` **and** a `NULL`
    `prompt_tokens` or `completion_tokens` (rows with `error_kind` set are
    exempt — sections 7.4 and 13.3). `report` runs the same validation on
    both files before comparing and exits with the same code.
- **REQ-V13-BEN-02 (MUST)** `--provider openrouter` **refuses to run** unless
  `--max-cost-usd` is given, and aborts (exit 4, JSON written with what was
  measured and `meta.aborted = "cost_cap"`) as soon as the cumulative cost
  (provider-reported, else list-priced) exceeds the cap; the cap is
  enforced inside `run_bench` through its `max_cost_usd` argument
  (REQ-V13-BEN-07), checked after every run. `LLM_FAILOVER` is
  forced to `off` for every bench run so the measured provider is the
  configured one (the full list of pinned variables is in REQ-V13-BEN-03).

### 7.2 Run mechanics

- **REQ-V13-BEN-03 (MUST)** Each *run* (scenario × repeat) gets a fresh
  directory `<PROJECT_ROOT>/.bench/<tag>/<scenario>-<repeat>/` holding three
  **siblings**: `sandbox/` (`EXEC_WORKDIR`), `bot.db` (`DB_PATH`) and
  `audit.jsonl` (`AUDIT_LOG_PATH`). This layout is forced by
  `config._check_sandbox_placement`: `EXEC_WORKDIR` must be a strict
  descendant of `PROJECT_ROOT` and must contain neither the DB, the audit log
  nor `.env` — a `tempfile` directory would be rejected. `.bench/` is added
  to `.gitignore` in C1 and wiped at the start of every `run`. Config comes
  from `.env` via `load_config` with these three paths overridden **and the
  treatment pinned by the harness**, so a maintainer's `.env` cannot alter
  what is measured: `LLM_FAILOVER=off`, `LLM_SUMMARY_MODEL=""` (routing is
  never benchmarked, section 10.6) and every stage-C variable of
  REQ-V13-PRE-04 set to its PRE-04 default whenever its `config.Config`
  field exists at that commit (`HISTORY_TOOL_STUB=on`,
  `EXEC_OUTPUT_DEFAULT_CHARS=1500`, `FETCH_INLINE_DEFAULT_CHARS=5000`,
  `LLM_REASONING=auto`); a variable whose field does not exist is neither
  set nor read. Only provider, model, URLs, keys, ids, timeouts and the
  pricing variables come from `.env`. `report --gate` enforces the pair
  this produces: exit 2 unless `LLM_FAILOVER` is `"off"` and
  `LLM_SUMMARY_MODEL` is `""` in both files, `LLM_MAX_TOKENS` is equal, and
  every stage-C key is `null` on the baseline side and equal to its PRE-04
  default on the candidate side (`LLM_REASONING`: `"auto"` or `null`); a
  later spec comparing two optimized trees amends this rule. The harness
  then does what `main()` does, in the same order:
  `docker_ok` probe, `bot._startup_docker_wiring(cfg, docker_ok)` once per
  run (sandbox cleanup, allowlist check, orphan reap, timeout wrapper,
  empty `resolv.conf`) and a runner built exactly like `main()`'s
  `functools.partial(tools.run_command_docker, workdir=…, image=…,
  docker_ok=…, sandbox_max_bytes=…, wrap_timeout=…, empty_resolv=…)`; the
  real `build_llm_client(cfg, client=…, override=…)` and the real fetcher
  built **per run** by the factory `main()` wires — the
  `functools.partial(tools.fetch_url, allowed_domains=…, client=…,
  resolve=tools.resolve_host)` of `bot.main()` plus
  `workdir=cfg.exec_workdir, sandbox_max_bytes=cfg.exec_sandbox_max_bytes`
  of that run's `cfg` (REQ-V13-TOO-06, REQ-V13-BEN-07).
  Telegram is replaced by an in-process recorder object (same duck type as
  `_SelftestTelegram`) — the harness never constructs `TelegramClient` (test
  asserts by monkeypatching the constructor to raise). The run directory is
  removed after its rows were copied into the result (an aborted run's
  directory stays, REQ-V13-BEN-05).
- **REQ-V13-BEN-04 (MUST)** Turns are driven through `bot.process_update`
  with synthetic updates whose `from.id`/`chat.id` is the first id of
  `ALLOWED_TG_IDS` (never written to the output). Turns of one scenario run
  sequentially in one conversation; `/new` is a turn like any other (it
  opens a new conversation, i.e. the next `conv_seq` group of the embedded
  rows, section 7.4).
- **REQ-V13-BEN-05 (MUST)** Wall-clock cap per run: 600 s (`--timeout-s`),
  deliberately above the sum of the per-operation timeouts a run can hit
  (LLM HTTP timeout × `HTTP_ATTEMPT_LIMIT` × rounds, exec timeout × tool
  calls), so a run that reaches it is a harness defect, not a slow model.
  Mechanism: `run_bench` executes each run's turns in a worker thread
  (`threading.Thread(daemon=True)`) and waits with `join(timeout_s)`.
  Connection ownership: the worker opens the run's SQLite connection
  itself (`storage.connect` called **inside** the thread — `sqlite3`
  connections are bound to the thread that created them), every
  `storage.add_llm_call` / `add_tool_call` commits immediately (the
  connection's existing autocommit, `isolation_level=None`), and the main
  thread never touches that connection: to copy the rows — after a normal
  completion as well as on timeout — it opens its own **read-only**
  connection (`sqlite3.connect(f"file:{db}?mode=ro", uri=True)`), reads
  the committed rows, closes it. A
  thread stuck in a blocking call cannot be cancelled, so on timeout the
  benchmark takes one **abort path**: the run is recorded as
  `success=false, failure='timeout'` with the rows the worker had
  committed so far (a snapshot — the worker is abandoned, never joined
  again), no
  further run is started, `run_bench` returns the `BenchResult` with
  `meta.aborted = "timeout:<scenario>-<repeat>"`, and the CLI `main()`
  writes the JSON, reaps every `tgexec`-labelled container with
  `bot._reap_orphaned_containers()` and ends with `os._exit(4)` — the only
  way to end a process whose daemon thread may be blocked, and what stops
  spending; the aborted run's directory is left in place for inspection
  (git-ignored `.bench/`, wiped by the next `run`). In-process callers of
  `run_bench` (the tests) receive the aborted result while the worker is
  abandoned; the test's `FakeLLM` sets its `threading.Event` in teardown so
  the thread exits. `check` and `report` reject a file with `meta.aborted`
  set (exit 2, reason `aborted run`): an aborted file is a diagnostic,
  never a comparison side; the re-run counts against 1.4 (harness defect).
  SIGINT (`KeyboardInterrupt` raised in the main thread during `join`)
  takes the **same abort path immediately** — it does not wait for the
  current run: that run is recorded as `success=false,
  failure='harness_error'` with its rows so far, `meta.aborted = "sigint"`,
  no further run, reap, `os._exit(4)`. Tests: a `FakeLLM` whose `complete`
  blocks on a `threading.Event`, `timeout_s=0.2`, two scenarios →
  `run_bench` returns after the first with `aborted` set and one run
  recorded, the second scenario never started; `join` monkeypatched to
  raise `KeyboardInterrupt` once → `meta.aborted == "sigint"`, one run
  recorded with `failure='harness_error'`, the second never started;
  a `FakeLLM` that completes its first call and blocks on the second →
  the aborted run's JSON holds exactly the one `llm_calls` row committed
  before the block (snapshot = committed rows only).
- **REQ-V13-BEN-06 (MUST)** Prefix calibration: once per `run` invocation,
  before the scenarios, one call with the system prompt (skills loaded as
  the bot would), the tool catalog and the user message `ping`,
  `max_tokens=1`, made directly through the LLM client outside `run_agent`,
  so it produces no `llm_calls` row (REQ-V13-OBS-04 covers `run_agent` and
  `summarize_conversation` only); its `LLMResponse.usage.prompt_tokens` is
  stored as `meta.prefix_tokens` and excluded from all scenario totals.
- **REQ-V13-BEN-07 (MUST)** DI for tests: the core is
  `run_bench(scenarios, *, cfg, llm_factory, runner_factory,
  fetcher_factory, telegram_factory, repeats, timeout_s, clock, sleep,
  network_preflight, max_cost_usd=None) -> BenchResult` —
  `fetcher_factory: Callable[[Config], Fetcher]` is called once per run
  inside the worker with that run's `cfg` (whose `exec_workdir` is the
  run directory), like `runner_factory`, so every fetch of a run saves
  under that run's sandbox (REQ-V13-TOO-06); `network_preflight:
  Callable[[], bool]` is the REQ-V13-BEN-11 probe (`True` = network
  reachable; `main()` passes the real wttr.in HEAD), `max_cost_usd: float
  | None` the REQ-V13-BEN-02 cap; `main()` only wires real objects.
  `tests/test_bench.py` runs it with `FakeLLM`, `RecordingRunner`,
  `fetcher_factory=lambda cfg: FakeFetcher()` and asserts the JSON shape,
  the factory being called with each run's `cfg` (distinct `exec_workdir`
  per run), the checks, the skip logic
  (`network_preflight=lambda: False` → S08 skipped, `lambda: True` →
  executed), the cost cap (`max_cost_usd=0.01` with a `FakeLLM` reporting
  `provider_cost_usd` → `meta.aborted == "cost_cap"`) and the
  never-Telegram rule.

### 7.3 Scenarios and checks

- **REQ-V13-BEN-08 (MUST)** `devtools/bench_scenarios.py` holds `SCENARIOS:
  list[Scenario]` — exactly the 12 of Appendix C, ids `S01`…`S12`, each
  `Scenario(id, title, turns: list[str], checks: list[Check],
  network: bool)`. Check kinds: `answer_regex(pattern, turn=-1)` (`re.I`,
  `re.S`), `answer_not_regex`, `answer_max_chars(n)`, `tool_used(name)`,
  `no_tools`, `json_keys({...})` (first `{…}` object in the answer parsed;
  values compared), `exit_code_seen(nonzero=True)`, `summary_exists`
  (a `summaries` row with non-empty goal after `/new`). Success = all
  checks pass. `turn` addresses a **user turn, one-based, counting only
  non-command turns** (turns starting with `/` are not counted): in a
  scenario `["a", "/new", "b", "c"]` turn 1 = `a`, 2 = `b`, 3 = `c`;
  `turn=-1` (default) = the last non-command turn. Loading `SCENARIOS`
  validates every check's `turn` against the scenario's non-command turn
  count (`ValueError` otherwise; test with an out-of-range turn) — Appendix
  C's S09 `turn=2`/`turn=3` and S12 `turn=2` follow this rule.
- **REQ-V13-BEN-09 (MUST)** Scenario texts are Russian (the user talks to
  the bot in Russian; the system prompt is English). Scenarios contain no
  secrets, no course material, no personal data.

### 7.4 Output schema (`bench_schema: 1`)

```
{ "bench_schema": 1,
  "meta": { "tag", "started_at", "finished_at", "git_commit", "provider", "model",
            "context_length", "repeats", "timeout_s", "prefix_tokens",
            "scenarios_sha256",   // sha256 of the bytes of devtools/bench_scenarios.py
            "pricing": {"basis", "model", "input_usd_per_mtok", "output_usd_per_mtok",
                        "cached_input_usd_per_mtok", "fetched_at"} | null,
            "skipped_scenarios": ["S08"],
            "env_flags": {"HISTORY_TOOL_STUB", "EXEC_OUTPUT_DEFAULT_CHARS", "FETCH_INLINE_DEFAULT_CHARS",
                          "LLM_REASONING", "LLM_SUMMARY_MODEL", "LLM_FAILOVER", "LLM_MAX_TOKENS"},
                          // always exactly these 7 keys; value = effective Config value, or null when
                          // the Config field does not exist at this commit (REQ-V13-BEN-10)
            "config_sha256",      // hash of the non-treatment, non-secret Config fields (table below)
            "constants": {"CONTEXT_WINDOW_MESSAGES", "EXEC_MAX_STREAM_BYTES", "FETCH_MAX_BYTES",
                          "ROUND_LIMIT", "TOOL_ROUND_LIMIT", "TOOL_EXECUTION_LIMIT", "HTTP_ATTEMPT_LIMIT",
                          "REQUEST_DEFAULTS": {"temperature": 0, "stream": false, "tool_choice": "auto"}} },
                          // REQUEST_DEFAULTS = the request-control literals llm/base.py sends with every
                          // request body, read from that module (table below) — a change there is a
                          // different treatment and makes `report --gate` exit 2
  "runs": [ { "scenario": "S02", "repeat": 1, "success": true,
              "failure": null | "checks" | "timeout" | "harness_error" | "usage_missing" | "cost_cap",
              "checks": [{"kind": "answer_regex", "ok": true, "detail": "<reason code, ≤ 120 chars, never an answer excerpt>"}],
              "answers": ["<redacted final answer per turn>"],
              "llm_calls": [ <llm_calls row as object, minus conv_id, plus conv_seq> ],
              "tool_calls": [ <tool_calls row as object, minus conv_id, plus conv_seq> ],
              "totals": {"calls", "failed_calls", "prompt_tokens", "completion_tokens", "cached_tokens",
                         "reasoning_tokens", "tool_calls", "tool_output_tokens_est",
                         "latency_ms", "cost_usd", "resent_tokens", "new_tokens",
                         "wall_ms"} } ],
  "summary": { "runs", "skipped", "successes", "success_rate",
               "per_scenario": { "S02": {"success": 3, "of": 3, "median": {<same keys as runs[].totals>}} },
               "totals": {<same keys as runs[].totals, summed over runs[]>},
               "avg_per_task": {"tokens", "rounds", "tool_calls", "latency_ms"},
               "cost_per_success", "tokens_per_success", "resent_share",
               "cache_hit_rate", "top_tools": [...], "top_turn": {...},
               "context_growth": {"system":…, "tools":…, "user":…, "assistant":…, "tool":…} } }
```

Normative field contract (the schema above is the shape; this table is the
arithmetic `bench.py check` enforces and `report` relies on — one table,
one implementation). "Run" below always means an entry of `runs[]`.

| Field | Type | Definition |
|---|---|---|
| `meta.aborted` | string \| absent | present only on an aborted file (REQ-V13-BEN-05); `check`/`report` exit 2 when present |
| `meta.env_flags` | object | exactly the seven keys of the schema, always present; each value is the effective `config.Config` value of that variable (defaults included, REQ-V13-BEN-03 pins apply) or `null` when the field does not exist at `meta.git_commit` (REQ-V13-BEN-10) |
| `meta.config_sha256` | string | `hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()` where `fields` maps every `config.Config` field name to its value **except** the secrets (`telegram_bot_token`, `openrouter_api_key`), the identifiers (`allowed_tg_ids`, `telegram_bot_name`), the location (`lmstudio_base_url`), every `Path` field (`exec_workdir`, `db_path`, `audit_log_path` — per run) and the treatment fields (`llm_failover`, `llm_summary_model`, `history_tool_stub`, `exec_output_default_chars`, `fetch_inline_default_chars`, `llm_reasoning`, whichever exist); `frozenset` values are serialized as sorted lists; a secret is never serialized, not even hashed. Tests: the canary value and the Telegram id do not change the hash, `llm_max_tokens` does; two fixtures differing only in `config_sha256` make `report --gate` exit 2 |
| `meta.constants` | object | the seven module constants by name, plus `REQUEST_DEFAULTS` = `llm.base.REQUEST_DEFAULTS` verbatim — the dict of request-control values every client sends in the request body (today the literals `temperature: 0`, `stream: False`, and `tool_choice: "auto"` when tools are present, lifted into that one module-level constant in C1 so the harness records what the client actually sends; `max_tokens` is `Config.llm_max_tokens`, already pinned equal by `env_flags`). Sampling or request-control drift between B1 and D1 is thereby a locked-field mismatch (exit 2), not a hidden treatment. No new control is added: the values are recorded, not made configurable |
| `meta.pricing` | object \| null | the price snapshot resolved once per run by steps 2–4 of REQ-V13-PRC-02 (step 1, the provider-reported cost, is per call and never a snapshot); `null` when no basis exists (step 5). Keys: `basis` ∈ `openrouter-list` \| `reference:<model>` \| `openrouter-list-stale` \| `reference-stale:<model>` \| `manual`; `model` = the priced model (the OpenRouter model, or the `LLM_PRICE_REF_MODEL` reference), `null` for `manual`; `input_usd_per_mtok`, `output_usd_per_mtok` floats ≥ 0, required; `cached_input_usd_per_mtok` float ≥ 0 or `null` (`null` for `manual` and when the list carries none); `fetched_at` ISO-8601 UTC of the fetch (the persisted timestamp for the `-stale` forms), `null` for `manual`. `check` validates types and nullability per basis |
| `runs[]` | array | exactly one entry per **executed** (scenario, repeat) pair, in execution order; skipped scenarios (REQ-V13-BEN-11) produce **no** entry; a failed or timed-out run **is** an entry (`success=false`). `check` enforces the set, not just the shape: the (scenario, repeat) pairs are exactly `(SCENARIOS ∖ meta.skipped_scenarios) × 1..meta.repeats` — omission, duplicate or unknown scenario id → exit 1 (REQ-V13-BEN-01) |
| `runs[].llm_calls[].conv_seq`, `runs[].tool_calls[].conv_seq` | int | replaces the row's `conv_id`: the 1-based ordinal of that `conv_id` among the run's conversations in order of first appearance (the `/new` turn of Appendix C S12 starts ordinal `+1`); assigned by the harness while copying the rows — never a Telegram or database identifier |
| `runs[].success` | bool | all checks `ok` and `failure` null |
| `runs[].failure` | string \| null | null on success; else the first applicable of `harness_error`, `timeout`, `usage_missing`, `cost_cap`, `checks` |
| `runs[].totals.calls` | int | number of `llm_calls` rows of the run, failed invocations included |
| `runs[].totals.failed_calls` | int | number of the run's `llm_calls` rows with `error_kind IS NOT NULL` — the failed invocations of REQ-V13-OBS-04, whose token columns are legitimately `NULL` and count as 0 in every Σ below; a `NULL` `prompt_tokens` or `completion_tokens` on a row with `error_kind IS NULL` is `usage_missing` (REQ-V13-BEN-01, section 13.3) |
| `runs[].totals.{prompt,completion,cached,reasoning}_tokens` | int | Σ of the column over the run's `llm_calls` rows, NULL counted as 0 |
| `runs[].totals.cost_usd` | float \| null | Σ of non-null `cost_usd`; null when every row's `cost_usd` is null |
| `runs[].totals.tool_calls` | int | number of `tool_calls` rows of the run |
| `runs[].totals.tool_output_tokens_est` | int | Σ `output_tokens_est` over the run's `tool_calls` rows |
| `runs[].totals.latency_ms` | int | Σ `latency_ms` over `llm_calls` rows |
| `runs[].totals.{resent,new}_tokens` | int | Σ over the run's `conv_seq` groups of `resent_tokens(calls)` / `new_tokens(calls)` (REQ-V13-OBS-08) applied to that group's `llm_calls` rows ordered by `id` — a `/new` turn resets the arithmetic because it starts a new group; `check` recomputes per group |
| `runs[].totals.wall_ms` | int | wall-clock of the run from first turn sent to last answer received (or to the timeout) |
| `summary.runs` | int | `len(runs)` |
| `summary.skipped` | int | `len(meta.skipped_scenarios) × meta.repeats` |
| `summary.successes` | int | count of runs with `success=true` |
| `summary.success_rate` | float | `successes / runs`; `0.0` when `runs == 0` |
| `summary.per_scenario[S].success`, `.of` | int, int | successes and executed runs of scenario S (`of == repeats` on a complete file) |
| `summary.per_scenario[S].median[k]` | number \| null | median over S's runs of `totals[k]` (`statistics.median`: even count → mean of the two middle values); null keys (`cost_usd`) are dropped before the median, null when nothing remains |
| `summary.totals[k]` | as `runs[].totals[k]` | Σ over runs of `totals[k]`; `cost_usd` null when null in every run |
| `summary.avg_per_task.tokens` | float | `(Σprompt_tokens + Σcompletion_tokens) / runs` |
| `summary.avg_per_task.rounds` | float | (number of `llm_calls` rows with `purpose = 'agent'` and `error_kind IS NULL` over all runs) `/ runs` |
| `summary.avg_per_task.tool_calls` | float | `summary.totals.tool_calls / runs` |
| `summary.avg_per_task.latency_ms` | float | `summary.totals.latency_ms / runs` |
| `summary.cost_per_success` | float \| null | `summary.totals.cost_usd / successes`; null when `cost_usd` is null or `successes == 0` |
| `summary.tokens_per_success` | float \| null | `(Σprompt_tokens + Σcompletion_tokens) / successes`; null when `successes == 0` |
| `summary.resent_share` | float | `Σresent_tokens / Σprompt_tokens`; `0.0` when `Σprompt_tokens == 0` |
| `summary.cache_hit_rate` | float \| null | `Σcached_tokens / Σprompt_tokens` when at least one `llm_calls` row has non-null `cached_tokens`; else null (rendered `n/a`) |
| `summary.top_tools` | array | `[{"name", "calls", "output_tokens_est"}]` per distinct tool name over all `tool_calls` rows, sorted by `output_tokens_est` desc, then `name` |
| `summary.top_turn` | object \| null | the `llm_calls` row with the maximum `prompt_tokens` (first in execution order on ties) as `{"scenario", "repeat", "turn", "round", "prompt_tokens"}`; null when no rows |
| `summary.context_growth[role]` | float | mean over runs of (`prompt_chars_by_role[role]` at the run's last `purpose='agent'` call − at its first); a run with fewer than two agent calls contributes 0 |

All divisions are float; every `avg_per_task` value is `0.0` when
`runs == 0`. `check` verifies each `summary` value against a recomputation
from `runs[]` (exit 1 on mismatch, REQ-V13-BEN-01), as it verifies
`runs[].totals` against the embedded rows.

- **REQ-V13-BEN-10 (MUST)** Before the JSON is written, **every string value
  in the whole document** (not only `answers`: `checks[].detail`, error
  texts, tool names, meta values) passes a recursive walk that applies
  `config.redact` with the live config's secrets and then replaces the
  decimal form of every id in `ALLOWED_TG_IDS` with `[tg-id]`. `checks[].detail`
  is a bounded reason code produced by the check (`pattern not found`,
  `3 of 4 keys matched`, `1800 > 1500 chars`), never an excerpt of the
  answer. Tests: a synthetic canary in an answer, the same canary in a
  provider error message (`FakeLLM` raising `LLMError` whose text contains
  it), and the first allowed Telegram id — none reaches the JSON text.
  `meta.env_flags` holds **exactly the seven keys** of the 7.4 schema in
  every file, at every commit: the value is the effective `config.Config`
  value (defaults included, harness pins of REQ-V13-BEN-03 applied) when
  the field exists at that commit, else `null` — so a C1 baseline carries
  `null` for every stage-C key and `LLM_REASONING` is `null` in the
  `not_applicable` and `attempted_removed` states of REQ-V13-RSN-02. No
  other environment key is ever serialized; the test asserts the key set
  is exactly these seven.

### 7.5 Skipping

- **REQ-V13-BEN-11 (MUST)** Before the scenarios, `run_bench` calls its
  `network_preflight` callable (REQ-V13-BEN-07); the real one, wired by
  `main()`, resolves and HEADs `https://wttr.in/` (5 s timeout) and
  returns `False` on any exception. `False` → every `network: true`
  scenario is `skipped` (all repeats): listed in `meta.skipped_scenarios`,
  counted in `summary.skipped`, and **absent from `runs[]`** — a skip is
  never a run state, so skipped repeats are outside every sum and
  denominator by construction (section 7.4). The preflight decision is
  always recorded (`meta.skipped_scenarios` is `[]` when nothing was
  skipped). `report` with two files whose skip sets differ exits 2 with a
  one-line reason: the comparison would be unfair.

### 7.6 Frozen scenarios

- **REQ-V13-BEN-12 (MUST)** From C2 onward `bench_scenarios.py` is frozen
  (REQ-V13-EC-07). If the baseline shows a scenario whose checks are
  *miscalibrated* (fails in all 3 repeats while the answer is visibly
  correct), the fix is folded into C1 by amending it (REQ-V13-AUD-02
  branch a), documented in `bench-baseline.md`, and the baseline is re-run
  (counts against 1.4). The AUD-02 decision is taken right after B1 and
  **before** B2, so the OpenRouter smoke runs once, on the final C1 tree.

### 7.7 Console summary (what the main context reads)

- **REQ-V13-BEN-13 (MUST)** `run` prints at most 40 lines: header (tag,
  provider, model, repeats, prefix_tokens, pricing basis), one line per
  scenario (`S02 arith  3/3  prompt 8.9k  out 0.4k  cost $0.0123  wall 41s`),
  totals, success rate, cost/success, tokens/success, re-sent share, skipped
  list, output path. Nothing else — the limit applies to the **complete
  console stream, stdout and stderr together**. The per-call INFO records
  of REQ-V13-OBS-06 (`llm_call `/`tool_call `, hundreds per run) are
  therefore not allowed on the console: `bench.py run` configures logging
  itself — root level INFO, a single `FileHandler` on
  `<output dir>/<tag>.log` (next to the JSON, git-ignored via
  `docs/assets/bench/*.log`), no stream handler — before the first
  scenario, and restores nothing (it is a one-shot CLI). The log file is a
  diagnostic for the maintainer; no requirement reads it and the main
  context never opens it (REQ-V13-EC-12). Tests: a CLI-level run with the
  fakes and INFO logging active produces ≤ 40 console lines in total
  (captured `capsys` out + err) and a `.log` file containing `llm_call `
  lines.

### 7.8 Report markdown

- **REQ-V13-BEN-14 (MUST)** `report` renders these sections, with these
  exact headings, in this order (with `--candidate` every table shows both
  files' values plus absolute and relative deltas). The report is the
  **only** data source of the stage-B/D writers (TB1, TD1 read markdown,
  never JSON — section 15), so every number a downstream requirement needs
  is a named cell here:
  - `## Meta` — the locked meta fields, `config_sha256`, `constants`,
    `prefix_tokens`, `pricing` and `env_flags` side by side.
  - `## Per scenario` — one row per scenario: success `k/n` and the
    **median of every `runs[].totals` key** (`prompt_tokens`,
    `completion_tokens`, `cached_tokens`, `reasoning_tokens`, `resent_tokens`,
    `new_tokens`, `tool_calls`, `tool_output_tokens_est`, `latency_ms`,
    `wall_ms`, `cost_usd`, `calls`, `failed_calls`).
  - `## Totals` — `summary.totals` in full plus `success_rate`,
    `cost_per_success`, `tokens_per_success`, `resent_share`, prefix share
    (`prefix_tokens × calls / Σprompt`), cache hit rate or `n/a`.
  - `## Totals by purpose` — `calls`, `prompt_tokens`, `completion_tokens`
    for the `agent` rows and the `summary` rows separately (the baseline
    `summary` row is the input of REQ-V13-RTE-02).
  - `## Audit` — the four answers computed from the data: most expensive
    tool by output tokens; most expensive turn/round (`top_turn`);
    fastest-growing context category (`context_growth`); re-sent share.
  - `## Reasoning` — computed over *all* `llm_calls` rows (medians hide
    single calls): `reasoning observed: yes|no` (yes iff any row has
    `reasoning_tokens > 0` or `reasoning_chars > 0`), `max reasoning_tokens:
    N`, `max reasoning_chars: N`, `Σ reasoning_tokens: N`, `reasoning share:
    Σreasoning_tokens / Σcompletion_tokens` (or `n/a (chars only: N)` when
    no row has `reasoning_tokens` and some have `reasoning_chars`), then
    the same five values split by the `tools_exposed` column on two
    further lines — `tool-exposed calls: calls: N, reasoning observed:
    yes|no, …` (rows with `tools_exposed = 1`) and `tools-withheld calls:
    calls: N, …` (rows with `tools_exposed = 0`), where `calls: N` counts
    the rows of that group with `error_kind IS NULL` (so `calls: 0` says
    the group was never exercised) — the deterministic input of the O5
    decisions (REQ-V13-RSN-01 reads the overall line, REQ-V13-RSN-02 the
    `tool-exposed calls` line, REQ-V13-AUD-04 all three).
  - `## Latency` — median `latency_ms` **per LLM call** over all rows, and
    per purpose (`agent`, `summary`).
  - `## Failures` — one row per run with `success = false` (per file):
    scenario, repeat, `failure`, the failing check kinds with their
    `detail` reason codes, and the run's `answers` joined with ` ⏎ ` and
    truncated to 300 characters (already redacted per REQ-V13-BEN-10;
    the scenarios of REQ-V13-BEN-09 touch no course material or secrets);
    `none` when every run succeeded. This is the **calibration evidence** of
    REQ-V13-AUD-02: the main context judges "visibly correct answer, wrong
    check" from this section alone, never from the JSON (REQ-V13-EC-12).
  - `## Verdict` — with `--candidate`, the section-13.3 verdict block.
  Consumer map: REQ-V13-AUD-02 → Failures; REQ-V13-AUD-04 → Audit,
  Reasoning, Per scenario, Totals;
  REQ-V13-RTE-02 → Totals by purpose (`summary` row); REQ-V13-RPT-01 O1 →
  Totals (`tool_output_tokens_est`), O2 → Per scenario (`resent_tokens`,
  `prompt_tokens`) on every scenario with more than one non-command user
  turn (Appendix C), O3 → Latency, O4 → Meta (`prefix_tokens`). Tests: the
  report of a fixture file contains every heading above; a fixture with
  one failed run renders that run's scenario, repeat, check kind and reason
  code under `## Failures` and truncates a 400-character answer to 300; a
  fixture with no failed run renders `none` there.

---

## 8. Dashboard (stage A)

- **REQ-V13-DSH-01 (MUST)** `devtools/dashboard.py <bench.json>
  [--compare other.json] --out <file.html>` writes **one self-contained HTML
  file**: inline CSS, no JavaScript required for reading, no external
  resources (test greps for `http://`/`https://` in `src=`/`href=` and for
  `<script src`), sections with ids `#aggregates` (calls, tokens in/out/
  cached/reasoning, latency, cost, success rate, cost per success, and the
  per-task averages the assignment asks for: tokens, rounds, tool calls,
  latency per run — the schema's `avg_per_task`), `#cache` (cache hit rate or n/a, re-sent share, prefix share), `#tools`
  (tool breakdown by output tokens and by time, as CSS bars with numbers),
  `#timeline` (per run: rounds as rows — prompt/completion tokens, latency,
  tools called — for the **median run** of every scenario: its runs sorted
  ascending by `totals.cost_usd`, or by `totals.prompt_tokens +
  totals.completion_tokens` when any run's `cost_usd` is null, stable on
  execution order, element at index `n // 2`; fixture test for both keys
  and for a tie), `#compare`
  (present only with `--compare`: side-by-side totals and per-scenario
  deltas). Input is benchmark JSON only; live-bot figures come from `/stats`.
- **REQ-V13-DSH-02 (MUST)** Test with the two fixtures of section 4
  (`tests/fixtures/bench/`): output parses with `html.parser`, contains the
  four ids without `--compare` and all five with it, the per-task averages
  and the totals match the fixture summaries.

---

## 9. Baseline benchmark and audit (stage B, commit C2)

- **REQ-V13-AUD-01 (MUST)** On the C1 tree, with gate 5 green:
  `uv run --locked python devtools/bench.py run --tag baseline --repeats 3`
  (background process; the main context reads only the 40-line summary).
  Then `--provider openrouter --only S02 --repeats 1 --tag openrouter-smoke
  --max-cost-usd 0.50` — proves **live usage and cost accounting** against
  a provider that reports them (`prompt_tokens`, `completion_tokens`,
  `cost_basis = provider` or `openrouter-list`). The smoke is complete
  only under REQ-V13-EC-11 (both usage fields present); missing usage →
  exit 3, stop and report — there is no "document that it does not"
  branch. Cached-token parsing is proven by the request/response fixture
  tests of section 11.2, not by the smoke: a single S02 call need not hit
  the provider's cache, so `cached_tokens` is reported live only when the
  provider supplies it and the smoke makes no claim about it either way.
- **REQ-V13-AUD-02 (MUST)** Baseline sanity: success rate < 70 % → look at
  the failing checks before C2 — the evidence is the `## Failures`
  section of `bench-baseline.md` (REQ-V13-BEN-14: failing check kinds,
  reason codes and the redacted answers, truncated), the only input the
  main context reads for this decision (REQ-V13-EC-12) — and take exactly
  one of two branches, documented in `bench-baseline.md`: (a) a check is
  *miscalibrated*
  (REQ-V13-BEN-12: the answer is visibly correct, the check wrong) → fix
  the check **inside C1** (`git commit --amend --no-edit`; nothing is
  pushed and no tag exists before C2, REQ-V13-EC-08/09), re-run the C1
  gates, re-run B1
  (counts against 1.4; `baseline.json.meta.git_commit` then names the
  amended C1), then continue — no scenario code ever lands in C2
  (REQ-V13-EC-07); (b) the model
  genuinely fails the scenario → keep the checks, commit C2 as is, and
  continue to C3/C4 with the honest verdict of section 13.3 (a low baseline
  makes the quality gate harder, never waives it). There is no third branch
  and no early termination: the four-commit contract of 1.2 holds.
- **REQ-V13-AUD-03 (MUST)** Two generated, never hand-edited files:
  `docs/reports/bench-baseline.md` = the verbatim output of `bench.py
  report --baseline docs/assets/bench/baseline.json --out
  docs/reports/bench-baseline.md`, and `docs/reports/bench-openrouter-smoke.md`
  = the verbatim output of the same command on
  `docs/assets/bench/openrouter-smoke.json` (a one-run file renders the
  same sections, REQ-V13-BEN-14; its `## Meta` shows `pricing.basis`, its
  `## Totals` the provider-reported usage and the cache hit rate). No
  "smoke table" is composed by hand — the main context never reads the
  JSON (REQ-V13-EC-12). `docs/assets/dashboard-baseline.html` =
  `dashboard.py baseline.json`.
- **REQ-V13-AUD-04 (MUST)** `docs/reports/audit-v1.3.md`, written by a
  subagent from `bench-baseline.md` (not from the JSON), answering the
  assignment's audit questions with the computed numbers: the most expensive
  tool and turn; the fastest-growing context category; re-sent tokens (share
  and absolute, with the "100k input → 27k new" style example from the
  data); prefix share; reasoning share and the `reasoning observed` / max
  values of the report's reasoning block (REQ-V13-BEN-14 — the O5 decision
  input; the audit names O5 only as `not_applicable` or `applicable —
  pending validation`, REQ-V13-RSN-01); per-scenario token sinks; then a
  **ranked list of hypotheses** for stage C with an expected saving each,
  mapped to section 10 REQ ids, and an explicit statement of which
  section-10 optimizations the data does **not** justify (e.g. 10.5 when no
  reasoning was observed). Every number cites the table it came from.

---

## 10. Optimizations (stage C, commit C3)

All optimizations are behaviour changes proven by tests (section 11.5) and
measured by the optimized run (section 13.3). Each maps to lecture
techniques (Appendix A). The set below is the contract; the audit may
re-rank them, never drop a `MUST`.

### 10.1 Token-aware tool output (lecture 4, 11, 14, 17) — O1

- **REQ-V13-TOO-01 (MUST)** `tools.compact_output(text: str, *, max_chars:
  int, error_context: bool = False) -> str`, deterministic. The algorithm
  below is normative — fixtures are byte-exact against it:

  ```text
  ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")   # CSI sequences only
  MARKER_RESERVE = 50                                  # chars kept for the marker line
  ERROR_RE = re.compile(r"(?i)\b(error|traceback|exception|failed|fatal)\b")

  1. text = ANSI_RE.sub("", text)
  2. lines = text.split("\n")            # a trailing "\n" yields a final "" line, kept
     collapse every run of ≥ 3 identical consecutive lines into the single
     line f"{line} [×{N}]"; text = "\n".join(lines)
  3. if len(text) <= max_chars: return text
  4. budget      = max_chars - MARKER_RESERVE        # max_chars ≥ 200 by contract
     head_budget = budget * 40 // 100
     tail_budget = budget - head_budget
     cost(line)  = len(line) + 1                     # the newline that joins it
     head = longest prefix of `lines` with Σcost ≤ head_budget   (whole lines; may be empty)
     tail = longest suffix of `lines[len(head):]` with Σcost ≤ tail_budget (may be empty)
  5. if error_context: let e = index of the LAST line matching ERROR_RE;
     if e exists and lines[e] is inside the omitted region (len(head) ≤ e < len(lines) - len(tail)):
         start = max(0, e - 20)
         tail  = lines[start:]; drop lines from the FRONT of tail until Σcost(tail) ≤ budget
         head  = longest prefix of lines[:start] with Σcost ≤ budget - Σcost(tail)
  6. omitted = lines[len(head) : len(lines) - len(tail)]
     marker  = f"[… {len(chr(10).join(omitted))} chars / {len(omitted)} lines omitted …]"
     if head or tail: return "\n".join(head + [marker] + tail)
  7. fallback (a single line longer than both windows — head and tail empty):
     return text[:head_budget] + marker + text[-tail_budget:]     # marker inline, no newlines
  ```

  Invariant (asserted by a property test over random inputs with
  `max_chars ∈ [200, 4096]`): `len(result) ≤ max_chars` always. Proof
  sketch: step 6 yields `Σcost(head) + Σcost(tail) + len(marker) ≤ budget +
  len(marker)`, step 7 yields `head_budget + tail_budget + len(marker)`; the
  marker is 29 fixed chars plus the digits of the two counts, i.e. ≤ 50 for
  any input below 10^10 chars (exec streams are ≤ 4096 bytes). Rounding is
  integer floor everywhere; character counts are Python `len` on `str`
  (code points), not bytes.
  Redaction happens **before** compaction (existing v1.1 order), so the
  input of `compact_output` contains no complete secret; what a cut can
  still expose is a *proper prefix* of a registered secret that the source
  printed incompletely (e.g. a truncated key at the end of a log line).
  Therefore, after any cut (steps 4–7), `config.strip_secret_fragment`
  (v1.2: removes from the end of a text the longest trailing proper prefix,
  ≥ `SECRET_FRAGMENT_MIN` = 8 chars, of a registered secret) is applied to
  the **head part** — the joined `head` lines in step 6, `text[:head_budget]`
  in step 7 — before the marker is appended, **and** to the end of the
  assembled result (defence in depth: the tail part ends where the source
  ended, and the producers — `_finalize_stream` and REQ-V13-TOO-09 —
  already strip at their own truncation points, so for real input the
  second application is a no-op; it is there so that `compact_output`
  alone never emits a trailing fragment whatever its caller did). The tail
  part begins at a line boundary in step 6 and at an arbitrary character
  offset in step 7; a cut *start* cannot expose a prefix of a secret (the
  input holds no complete secret, and a trailing fragment is handled by
  the end-strip), so the tail's start needs no stripping.
  `len(result) ≤ max_chars` still holds (stripping only shortens). Tests
  (boundary contract, exact): a synthetic canary registered as the only
  secret; (a) input with **no** complete canary whose head window's last
  line is `token=` + the canary's first 10 characters, followed by enough
  filler lines to force a cut → the result's head ends with `token=`
  followed by the marker line, the rest byte-exact per the algorithm;
  (b) fallback-mode input (one line longer than `max_chars`, step 7) that
  ends in `key=` + the canary's first 12 characters → the result ends
  with `key=` (fragment stripped) and is otherwise byte-exact per step 7.
- **REQ-V13-TOO-02 (MUST)** exec: the 4096-byte capture cap per stream
  stays. After capture and redaction, each stream is passed through
  `compact_output(max_chars=min(requested, 4096), error_context=exit_code
  != 0)` where `requested` is the tool argument `max_output_chars` (integer,
  200–4096) or `EXEC_OUTPUT_DEFAULT_CHARS`. The existing `truncated` flag
  keeps its meaning (the 4096-byte capture cap was hit; asserted by v1
  tests). The envelope gains `compacted: bool` (the head/tail window or the
  duplicate collapse changed the text) and `stdout_bytes_total`,
  `stderr_bytes_total`: the **true** byte count the process produced, from
  `_Capture._fed`, exposed by extending `snapshot()` to
  `(bytes, truncated, fed)`. The window operates on exactly the retained
  capture buffer (the existing 4096-byte cap per stream, no headroom):
  output beyond the capture cap is gone before compaction, which
  `truncated` tells the model. The schema's `max_output_chars` description
  tells the model the default and the maximum.
- **REQ-V13-TOO-03 (MUST)** Output size is measured on the **stream text**,
  at one canonical point per tool, never on the serialized envelope:
  - exec: `raw_output_chars` = `len(redacted stdout) + len(redacted stderr)`
    as decoded from the retained capture buffers, before `compact_output`;
    `output_chars` = the same sum after `compact_output` (what the envelope
    carries);
  - fetch: `raw_output_chars` = `chars_total` (the full extracted, redacted
    text); `output_chars` = `len(text)` of the inline excerpt;
  - load_skill: both = `len(output)` (REQ-V13-TOO-10).
  In stage A (before O1) both columns equal the length of the model-facing
  text (exec: redacted stdout + stderr; fetch: the v1.2 `body`; load_skill:
  output), so `raw_output_chars == output_chars` for every row.
  The audit trail (JSONL) keeps the existing fields; it does not need the
  raw text.
- **REQ-V13-TOO-04 (MUST)** Duplicate collapse and head/tail are visible in
  the model-facing text only; nothing about the security caps, the
  timeout, the exit-code mapping (v1.2 REQs) changes. Tests: byte-exact
  expected outputs for a 200-line duplicate log, a 5000-line numeric
  output, a traceback at the end of a long stderr, ANSI-coloured output
  (`compact_output` unit tests feed text directly; envelope tests stay under
  the 4096-byte capture cap so the collapse is observable end to end).
- **REQ-V13-TOO-05 (MUST)** Fetch, HTML → text: when the response
  `Content-Type` is `text/html` (or the body starts with `<!doctype html`/
  `<html` case-insensitively), the body is converted with a stdlib
  `html.parser.HTMLParser` subclass: `script`, `style`, `noscript`,
  `template`, `svg` subtrees dropped; block-level tags (`p, div, br, li, tr,
  h1–h6, pre, blockquote, section, article, header, footer, nav, table`)
  become newlines; entities decoded; runs of whitespace collapsed (newlines
  preserved, at most two in a row); `<title>` kept as the first line.
  Non-HTML text bodies pass through unchanged; binary bodies (`Content-Type`
  neither `text/*` nor `application/json`/`+json`/`xml`) yield
  `{"error": "unsupported content type: <type>"}` and no file.
- **REQ-V13-TOO-06 (MUST)** Fetch saves the **full extracted text** (already
  redacted, ≤ `FETCH_MAX_BYTES`) to `<EXEC_WORKDIR>/fetch/<sha256(url)[:16]>.txt`
  **only when `truncated` is true** — the inline `text` already holds
  everything otherwise, and an untruncated fetch writes nothing (no file
  under `fetch/`, `"saved_to": null, "save_error": null`). The save is
  subject to the quota (fail-closed scan of v1.2: if the write would exceed
  `EXEC_SANDBOX_MAX_BYTES`, the file is not written and the envelope says
  `"saved_to": null, "save_error": "sandbox quota"`). The directory name is
  fixed; the file name is derived only from the hash — no path component
  comes from the model. `tools.fetch_url` learns where the sandbox is
  through two new keyword-only parameters, `workdir: Path` and
  `sandbox_max_bytes: int` (section 2); `bot.main()` adds
  `workdir=cfg.exec_workdir, sandbox_max_bytes=cfg.exec_sandbox_max_bytes`
  to its existing `functools.partial(tools.fetch_url, …)`, and the
  benchmark's `fetcher_factory` (REQ-V13-BEN-07) builds the same partial
  per run from that run's `cfg`. The sandbox contents are model-controlled (the
  container runs as the host uid and may create `fetch` or
  `fetch/<hash>.txt` as a symlink before the fetch), so the write is
  **fail-closed and never follows a link**, in the style of
  `bot._ensure_empty_resolv`:
  1. `root_fd = os.open(workdir, O_RDONLY | O_DIRECTORY | O_NOFOLLOW)`;
  2. `os.mkdir("fetch", 0o700, dir_fd=root_fd)` (`FileExistsError` is fine);
  3. `fetch_fd = os.open("fetch", O_RDONLY | O_DIRECTORY | O_NOFOLLOW,
     dir_fd=root_fd)`; `fstat` must show `S_ISDIR` and `st_uid == os.getuid()`;
  4. the write never reuses a pre-existing inode (a hard link inside
     `fetch/` to a bot-owned file outside the sandbox would otherwise be
     truncated by `O_TRUNC` before any check could run):
     `os.unlink(name, dir_fd=fetch_fd)` ignoring `FileNotFoundError` only
     (removes the directory entry, never the linked data), then
     `fd = os.open(name, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0o644,
     dir_fd=fetch_fd)`; `fstat` must show `S_ISREG`, `st_nlink == 1`,
     `st_uid == os.getuid()`; then write and close. No `O_TRUNC` anywhere.
  Any `OSError` (including `ELOOP` from `O_NOFOLLOW`, `EEXIST` from
  `O_EXCL`, `EISDIR` from the unlink) or failed check at any step →
  nothing is written, `"saved_to": null, "save_error": "refused"` (the
  fetched text is still returned inline). A pre-existing symlink **at the
  target name** is not refused but **replaced**: step 4's `unlink` removes
  the link entry (never its target) and `O_CREAT | O_EXCL | O_NOFOLLOW`
  creates a fresh regular file in its place — the outside data is never
  opened. Tests (all with a truncating fetch): a symlinked `fetch/`
  directory pointing outside the sandbox is refused (`ELOOP` at step 3),
  the link target stays untouched and the outside temp directory stays
  empty; a symlinked `fetch/<hash>.txt` pointing at a temp file outside
  the sandbox is replaced — afterwards `os.lstat` of the name shows
  `S_ISREG`, the outside file is byte-identical, and `saved_to` is the
  path; a **hard link** `fetch/<hash>.txt` to a temp file outside the
  sandbox (`os.link`, same filesystem) → the save lands in a fresh inode,
  the outside file is byte-identical afterwards and its `st_nlink` is back
  to 1; a regular save round-trips and a second save of the same URL
  replaces the file; an untruncated fetch leaves `fetch/` absent or empty.
- **REQ-V13-TOO-07 (MUST)** Fetch envelope of a **successful text
  response** (an HTTP response whose body was extracted per REQ-V13-TOO-05,
  whatever the status code) — exactly these keys, always all
  present, in this order: `{"url", "status", "content_type", "chars_total",
  "returned_chars", "truncated", "saved_to": "fetch/<hash>.txt" | null,
  "save_error": null | "sandbox quota" | "refused", "text": "<first
  max_chars of the text>"}` with `max_chars` = tool argument (500–20000) or
  `FETCH_INLINE_DEFAULT_CHARS`. The pair (`saved_to`, `save_error`) has
  exactly three shapes: `truncated` false → `(null, null)` (nothing is
  written, REQ-V13-TOO-06); `truncated` true and the save succeeded →
  `("fetch/<hash>.txt", null)`; `truncated` true and the save failed →
  `(null, "sandbox quota" | "refused")`. They are never both non-null.
  Every other outcome — malformed URL, disallowed domain, redirect limit,
  transport failure, unsupported content type (REQ-V13-TOO-05) — keeps the
  v1.2 shape `{"error": "<reason>"}` with no other key, and no file is
  written; the exact-envelope test of section 11.5 covers the success
  shape, a second test asserts the error shape has the single key `error`.
  The tool description tells the model: to search the rest, run
  `exec(["grep", "-n", "<pattern>", "fetch/<hash>.txt"])` (fetch once,
  process locally — lecture 11).
- **REQ-V13-TOO-08 (MUST)** Startup cleanup (`_clean_sandbox_at_start`)
  treats `fetch/` like any other sandbox entry (removed; one new test).
  `/new` does not touch the sandbox today and this spec does not change
  that; the quota (REQ-V13-TOO-06) bounds what `fetch/` can accumulate.
- **REQ-V13-TOO-09 (MUST)** Redaction order for fetch is unchanged (redact →
  cut → strip fragment, the same head-part boundary contract as
  REQ-V13-TOO-01); the saved file contains redacted text only. Tests: a
  synthetic canary in a fixture HTML body is absent from the inline text
  and from the saved file; a canary prefix at the inline cut is stripped.
- **REQ-V13-TOO-10 (MUST)** `load_skill` output is not compacted (skills are
  reference material and small); test asserts byte-equality.

### 10.2 Request-time compaction of stale tool results (lecture 1, 3, 12) — O2

- **REQ-V13-HST-01 (MUST)** In `_assemble_context`, every `tool`-role
  message that belongs to a turn **older than the current user message**
  (i.e. not produced during this `run_agent` invocation) is replaced, **in
  the request only**, by a stub JSON string:
  `{"stub": true, "tool": "exec", "exit_code": 0, "chars": 3512,
  "sha256_16": "…", "head": "<first 120 chars of the original>"}` for exec;
  `{"stub": true, "tool": "fetch", "url": "…", "saved_to": "fetch/….txt",
  "chars": N}` for fetch; `{"stub": true, "tool": "load_skill", "name":
  "…"}` for superseded skill loads. The tool name and arguments are resolved
  by matching the tool message's `tool_call_id` against the `tool_calls` of
  the nearest preceding assistant message; no match → generic stub
  `{"stub": true, "tool": "unknown", "chars": N, "sha256_16": "…", "head":
  "…"}`. The DB rows are untouched (audit trail, `/summary` and the
  summarizer keep the full text).
- **REQ-V13-HST-02 (MUST)** Exception: the **most recent** `load_skill`
  result per skill name inside the window is kept verbatim (the model must
  keep following the skill across turns).
- **REQ-V13-HST-03 (MUST)** Assistant messages (including their
  `tool_calls` arguments) and user messages are never stubbed.
- **REQ-V13-HST-04 (MUST)** The token budget of `_assemble_context` is
  computed on the stubbed messages; `CONTEXT_WINDOW_MESSAGES` is unchanged.
  `HISTORY_TOOL_STUB=off` disables stubbing only: every tool-role message is
  passed verbatim and the assembled list equals the un-stubbed assembly
  (test compares against `_assemble_context` with stubbing bypassed — not
  against a v1.2 payload, which C3's prompt changes alter anyway).
- **REQ-V13-HST-05 (MUST)** `llm_calls.prompt_chars_by_role.tool` reflects
  the stubbed sizes; `metrics.context_growth` therefore shows the effect.

### 10.3 Byte-stable prefix and provider caching (lecture 6) — O3

- **REQ-V13-CCH-01 (MUST)** The system prompt is **byte-identical for every
  call of a conversation while its inputs are unchanged** — the inputs are
  the recent goals (`GOALS_BLOCK`, which change only between conversations)
  and the loaded skill catalog (which changes only on `/reload_skills`, the
  one explicit invalidation event): the `Current date and time` line leaves
  the system prompt; at request-assembly time the string `(now: YYYY-MM-DD
  HH:MM UTC)` is appended as the last line of the **most recent user
  message** (stored content unchanged). Tests: two `run_agent` invocations
  with different `now` produce identical system messages and identical
  `tools` JSON, and the user message carries the `now`; after
  `/reload_skills` with a changed skill catalog the system prompt differs
  exactly in the skill lines and is again stable across the next two calls.
- **REQ-V13-CCH-02 (MUST)** Message and tool ordering is stable across rounds.
  This is the existing v1 loop structure made explicit, not a new
  constraint: `run_agent` calls `_assemble_context` **once** per
  invocation, before the round loop, and the loop only appends to that
  list (assistant tool-call messages, tool results, the empty-repair and
  final system messages) — no eviction, truncation or re-assembly happens
  between rounds, so the properties below hold by construction and the
  tests pin them. Two separate properties, tested separately within one
  `run_agent` invocation: (a) the serialized **message list** of round *n*
  is a prefix-extension of round *n−1*'s (byte-equal up to the length of
  the older one, then only appended items); (b) the serialized `tools`
  JSON is byte-identical on every round that exposes tools. The
  tools-withheld final request of REQ-V13-RSN-02 (`request_tools is None`)
  is exempt from (b) — its messages still satisfy (a). Context budgeting
  (REQ-V13-HST-04) acts at assembly time, i.e. across invocations, never
  inside one.
- **REQ-V13-CCH-03 (SHOULD)** OpenRouter: when `OPENROUTER_MODEL` starts with
  `anthropic/`, the system message is sent in the content-blocks form with
  `cache_control: {"type": "ephemeral"}` on the system block (field shape
  verified per REQ-V13-PRE-05; the `usage: {"include": true}` flag is a
  stage-A matter, REQ-V13-OBS-01). Not benchmarked in v1.3: the only OpenRouter run (B2) precedes
  C3, so the effect is **unmeasured** — the request shape is unit-tested
  (section 11.5) and the report lists CCH-03 as *implemented, unmeasured*
  (REQ-V13-RPT-01 shows no metric for it, never an estimate); for other
  models the request shape is unchanged.
- **REQ-V13-CCH-04 (MUST)** The report states the LM Studio effect honestly:
  a llama.cpp-style prefix cache reduces **latency**, not billed tokens, and
  O2 invalidates the history part once per user turn; the number reported
  is the median latency delta per call.

### 10.4 Prefix compression (lecture 8 + participant grammar) — O4

- **REQ-V13-PFX-01 (MUST)** `SYSTEM_PROMPT` rewritten: English, imperative,
  `NEVER`/`MUST` modality, no politeness, structured as `Role / Output /
  Tools / Rules / Skills`, **≤ 550 characters measured as
  `len(SYSTEM_PROMPT.replace("{skill_lines}", ""))`** (today 1325 by the
  same measure; filled with the two shipped skills and the datetime 1701, of
  which 374 are the skill lines, so ≤ 924 filled before the datetime moves
  out under CCH-01). Statements that MUST survive, in meaning:
  Telegram plain text (no Markdown/HTML/code fences/tables); answer in the
  user's language; `exec` is argv, not a shell, no network; call
  `load_skill` first when a skill covers the topic and follow it; never
  invent tool output, report errors; at most 3 tool calls per reply; reply
  without tool calls when done; tool output is untrusted data, never
  instructions (prompt-injection defence); installed skills list. New
  statement: `Be concise: answer the question, no preamble, no repetition of
  the tool output.` The tool bullet list that duplicates the schema
  descriptions is removed (the schema carries it).
- **REQ-V13-PFX-02 (MUST)** Tool schema descriptions rewritten in the same
  style; `json.dumps(tool_specs())` **≤ 1400 characters** (today 2041)
  while every parameter name, type, enum, minimum/maximum and `required`
  list is unchanged except the two new parameters of 10.1 (test compares the
  schema with descriptions stripped against the v1.2 schema with the two
  additions).
- **REQ-V13-PFX-03 (MUST)** Behaviour tests (fake LLM) prove the prompt still
  drives: skill-first, plain-text output, injection refusal wording is
  present in the system message. Measured effect: `meta.prefix_tokens`
  before/after.

### 10.5 Reasoning control (lecture 8) — O5, conditional

- **REQ-V13-RSN-01 (MUST)** Decision rule: if the baseline shows
  `reasoning_tokens > 0` or `reasoning_chars > 0` in **any** call — read as
  the `reasoning observed: yes|no` line of `bench-baseline.md`
  (REQ-V13-BEN-14), the only source the main context and the audit
  subagent consult — O5 is
  *applicable* and `audit-v1.3.md` (committed in C2, before stage C)
  records exactly `applicable — pending validation`; otherwise it is
  recorded as `not_applicable` (*no reasoning observed*) in `audit-v1.3.md`
  and the report, and no code is written for it (no speculative feature).
  The audit never names `implemented` or `attempted_removed` — that
  decision is made in stage C (REQ-V13-RSN-02) and named in
  `report-v1.3.md`.
- **REQ-V13-RSN-02 (MUST, when applicable)** `LLM_REASONING=auto|on|off`:
  `auto` disables thinking on every call whose request carries tools
  (`agent.py`: `expose_tools` true, `request_tools` non-empty) and leaves
  the model default on the tools-withheld call the loop makes when
  `expose_tools` is false (`FINAL_INSTRUCTION` appended, `request_tools is
  None`) and on the summary call (`purpose='summary'`). The rule uses
  request-time state only: a tool-exposed call that happens to return the
  final answer is still a "tool round". `off` disables everywhere; `on`
  never disables. The mechanism is the one the model's
  documentation specifies (e.g. `chat_template_kwargs: {"enable_thinking":
  false}` or a `/no_think` soft switch appended to the last user message at
  request time), verified per REQ-V13-PRE-05. Whether the mechanism
  works is decided **before C3 is committed**, by one bounded live probe
  that TC4 runs on the stage-C working tree: `bench.py run --only S05
  --repeats 1 --tag reasoning-probe` (S05 is a one-turn scenario with a
  tool round, Appendix C) followed by `bench.py report --baseline
  docs/assets/bench/reasoning-probe.json --out
  docs/reports/bench-reasoning-probe.md`; both files are C3 content
  (section 1.2) and are the evidence. The state is read from that
  markdown only, and the probe must have **exercised** the mechanism
  before it can prove anything: the probe is *conclusive* iff `## Per
  scenario` shows S05 as `1/1` (its `tool_used("exec")` check passed) and
  the `## Reasoning` line `tool-exposed calls:` shows `calls: 1` or more
  (REQ-V13-BEN-14 splits the figures by `tools_exposed` and counts the
  successful rows of each group). A conclusive probe decides:
  `tool-exposed calls: … reasoning observed: no` → `implemented`; `yes` →
  `attempted_removed`. An inconclusive probe (S05 failed, or `calls: 0`)
  is re-run **once**; still inconclusive → `attempted_removed` with the
  reason `probe inconclusive` in `report-v1.3.md` — never `implemented`
  on the strength of an unexercised path. `attempted_removed` means the
  knob is
  **not shipped** — the C3 tree carries no `LLM_REASONING` (no `Config`
  field, no validation, no tests, no README/`.env.example` line), the
  probe report and the context7 citation document the attempt in
  `report-v1.3.md`. D1 then **confirms** the `implemented` state through
  the same block of `bench-v1.3.md`; when D1 nevertheless shows reasoning
  on tool-exposed calls, the state stays `implemented`, the report says
  `implemented — not confirmed by D1 (reasoning on N tool-exposed calls)`
  and no code changes (section 13.4). O5 therefore ends in exactly one
  of three states: `not_applicable` (REQ-V13-RSN-01: no reasoning
  observed), `implemented`, or `attempted_removed`; `audit-v1.3.md` (C2)
  names only `not_applicable` or `applicable — pending validation`, the
  final state is named in `report-v1.3.md`. The `LLM_REASONING` variable
  — its `load_config` validation (REQ-V13-PRE-04), its tests and its
  README/`.env.example` lines — exists **only in the `implemented`
  state**; in the other two states none of them exists in the C3 tree and
  the fixed `LLM_REASONING` key of `meta.env_flags` (REQ-V13-BEN-10) holds
  `null`.

### 10.6 Model routing by purpose (lecture 7) — O6, configuration only

The maintainer's constraint: only one model fits the GPU box; switching
models per call means load/unload (tens of seconds) and is not viable.
Therefore routing is implemented as configuration that the maintainer can
enable when a second model or a cheap cloud model is available, and it is
**not** enabled during the v1.3 benchmark. Decision record: keeping O6 as
config-only scope is the maintainer's explicit choice (spec cross-review,
Appendix D: its removal was demanded in five of seven rounds and refused
each time) — it is the lecture-7 technique
the assignment lists, covered at the cost of one env var, one client
constructor branch and their tests; it is not a candidate for removal
during execution.

- **REQ-V13-RTE-01 (MUST)** `LLM_SUMMARY_MODEL=<provider>:<model>` routes
  `summarize_conversation` to that client (built with the same
  `httpx.Client`, `LLM_FAILOVER` semantics unchanged for the main client,
  none for the summary client). Validation: provider ∈ {lmstudio,
  openrouter} and configured, else `ConfigError`. `llm_calls.model` shows the
  routed model. Tests with fakes: the summary goes to the routed client; the
  agent loop does not.
- **REQ-V13-RTE-02 (MUST)** The report has a "Routing" paragraph: what is
  implemented, why it was not benchmarked (memory constraint), how to enable
  it, and the baseline `purpose='summary'` token total the routing would
  affect (from `bench-baseline.md`). The saving estimate `summary tokens ×
  (reference price − cheap-model price)` is computed **only** when
  `LLM_SUMMARY_MODEL` is configured and its price is present in the pricing
  snapshot (REQ-V13-PRC-01); otherwise the paragraph states
  `estimate: n/a — no candidate model configured` and lists the inputs a
  future estimate needs. No price is invented.

### 10.7 Techniques judged not applicable (recorded, not implemented)

- Semantic cache (lecture 10): needs embeddings → dependency; NON-GOAL.
- Smart git diff (13), AgentHandoff (15), batch processing (16): no such
  workload in this bot; NON-GOAL.
- Memory split (2) and loop caps (8): already implemented in v1/v1.1
  (structured summaries, ROUND/TOOL limits) — counted, not re-done.
- Tokenizer-accurate budget (`estimate_tokens` calibrated from observed
  `prompt_chars/prompt_tokens`): affects how much history fits, not tokens
  billed; deferred to v1.4 (`docs/plan.md`).

---

## 11. Tests

Baseline: 326 tests (`pytest --collect-only` at `1ecc35e`). v1.3 adds
**≥ 70** tests; final count ≥ 396. All new
tests are offline (conftest `no_network`, `no_dns` unchanged), use synthetic
secrets only, and never spawn Docker, network clients, or application
executables; Python subprocesses are allowed only for CLI exit-code tests
(`bench.py`, `dashboard.py`, `mutation_check.py --only`, REQ-V13-CO-06),
run with `sys.executable` against fixture files.

### 11.1 `tests/test_v13_carryover.py` — section 5
One test per REQ-V13-CO-01…06 (CO-05 = three tests).

### 11.2 `tests/test_observability.py` — sections 6.1–6.2
Usage parsing (full, partial, absent, non-integer); `<think>` stripping and
`reasoning_content`; every OpenRouter request body carries
`usage: {"include": true}` and no LM Studio request body does (OBS-01);
schema v3 fresh + migration from a v2 fixture; one
`llm_calls` row per `llm.complete` invocation including a failed one
(`attempt` 1, 2 on a `run_agent` retry; one row with the fallback's
provider/model on an in-invocation failover); `tool_calls`
rows for executed/rejected/budget outcomes; `describe()` on all three
clients; log lines are JSON without content and their key set equals the
table's column set (OBS-06); `/stats` layout, `n/a` branches and the
per-side basis label (one basis, `mixed`, `n/a (no pricing)`);
`resolve_cost` (a stub resolver's `(cost, basis)` lands in the row; `None`
→ `NULL`/`NULL`; called with the post-invocation `describe()` values —
OBS-04); `/status`
token line; `metrics.resent_tokens` on a hand-computed
sequence (including a window drop → clamped at 0); `context_growth`.

### 11.3 `tests/test_pricing.py` — section 6.3
`/models` parsing from a fixture (mock transport), per-token → per-million,
cost formula with/without cached price, `cost_usd` → `None` when
`prompt_tokens` or `completion_tokens` is missing, basis precedence — one test per
PRC-02 step, all through `make_resolver(...)` with no network (provider over fresh list,
fresh list over manual, manual over stale persisted, stale over `NULL`),
startup fetch failure is non-fatal and falls through, `bot_state`
persistence, manual prices rejected when negative or half-configured;
every `cost_basis` form of PRC-02 (both stale forms included) is accepted
by storage and rendered by `/stats` and the report.

### 11.4 `tests/test_bench.py`, `tests/test_dashboard.py` — sections 7–8
Scenario schema validation (12 scenarios, unique ids, checks well-formed,
out-of-range `turn` rejected, no `answer_regex` pattern contains the
two-character sequence `\|`); each check kind against crafted answers,
including one-based non-command `turn` addressing; `run_bench` with fakes
produces a schema-valid JSON (`check` passes); `check` recomputes every
`runs[].totals` and `summary` value of the 7.4 table (a fixture with one
tampered `summary` value → exit 1; negative tokens / `cached >
prompt` → exit 3; `meta.aborted` → exit 2); skip logic with a failing
preflight (no `runs[]` entries for S08, `summary.skipped == 3`,
`meta.skipped_scenarios == ["S08"]`, `[]` when nothing skipped);
`report` deltas on the two fixtures; `--gate` exit codes (pass / fail /
each locked meta field differing → 2, incl. `scenarios_sha256`,
`skipped_scenarios` and `config_sha256`; the BEN-03 treatment rule —
`LLM_FAILOVER` not `"off"`, `LLM_SUMMARY_MODEL` non-empty, a stage-C key
non-null on the baseline side or off its default on the candidate side →
2); `config_sha256` invariants (canary value and Telegram id do not change
it, `llm_max_tokens` does); two fixtures differing only in
`constants.REQUEST_DEFAULTS.temperature` → `report --gate` exit 2, and
`run` records `llm.base.REQUEST_DEFAULTS` verbatim; gate cost recomputed
with the baseline
snapshot (a candidate fixture with a cheaper `meta.pricing` but identical
tokens does not pass); literal quality gate (one lost run at 36 → FAIL;
3/3 → 1/3 → FAIL even with a compensating gain); `usage_missing`
rejection of a file whose successful run has a NULL-usage row with
`error_kind IS NULL`, while a file whose only NULL-usage row has
`error_kind` set passes `check` and reports `totals.failed_calls == 1`;
per-run timeout with a blocking FakeLLM (`timeout_s=0.2`, two scenarios:
first recorded as `failure='timeout'`, second never started,
`meta.aborted` set, the CLI exits 4 with `os._exit` monkeypatched to
record its argument); `join` raising `KeyboardInterrupt` once →
`meta.aborted == "sigint"`, `failure='harness_error'`; `meta.env_flags` is
exactly the seven keys with `null` for absent fields; report headings of
BEN-14 all present, `Totals by purpose` and `Latency` values recomputed;
report's reasoning block (`reasoning observed: yes` from a single nonzero
call among zeros, max values, share, and the `tool-exposed` /
`tools-withheld` split lines from rows differing only in
`tools_exposed`); `conv_seq` (an S12-shaped fake run: rows after `/new`
carry `conv_seq == 2`, `totals.resent_tokens` is the sum over the two
groups — a fixture computing it over the flat row list is rejected by
`check` with exit 1); `meta.pricing` validation (`manual` with `model`
and `fetched_at` null passes; `openrouter-list` with `fetched_at` null →
exit 1; a negative rate → exit 1); the run set (`check` on a fixture
with S07 omitted from `runs[]` and `summary.per_scenario` while every
sum is self-consistent → exit 1; a duplicated (S03, repeat 2) → exit 1;
an unknown id `S99` → exit 1; `skipped_scenarios: ["S01"]` on a
non-network scenario → exit 1; a `meta.scenarios_sha256` that does not
match `devtools/bench_scenarios.py` → exit 1); the `failed_calls`
warning line present iff the candidate's count exceeds the baseline's;
the conservative cost gate (a fixture pair where the candidate's plain
figure is 0.65 × baseline but, with its `failed_calls` charged at its
mean successful-call cost, 0.74 × baseline → `FAIL`, exit 1, both
candidate figures printed; the same pair with `failed_calls = 0` →
`PASS`); `fetcher_factory` called once per run with that run's `cfg`
(distinct `exec_workdir` values recorded); OpenRouter
refusal without cap and abort over cap (`meta.aborted = "cost_cap"`,
`max_cost_usd=0.01`); the timeout snapshot holding exactly the rows
committed before the block; Telegram constructor never called; synthetic
canary in answer / provider error and the first allowed Telegram id
never in JSON; console summary ≤ 40 lines; dashboard sections/no
external resources/numbers; `#timeline` median-run selection by cost,
by tokens when a cost is null, and on a tie.

### 11.5 Stage C files — section 10
`tests/test_tool_output.py`: REQ-V13-TOO-01…10 (byte-exact fixtures against
the TOO-01 algorithm; `len(result) ≤ max_chars` property test; canary
prefix at the head cut and at the end of a fallback-mode result (TOO-01
boundary contract, tests (a) and (b)); exact envelope key set and order of TOO-07 in all three
(`saved_to`, `save_error`) shapes — a truncated fetch saved (path, null),
an untruncated fetch (null, null) with no file under `fetch/`, a refused
save (null, "refused"); quota-refused save (null, "sandbox quota");
symlinked `fetch/` dir refused with the link target untouched; symlinked
target file replaced by a regular file (`lstat` `S_ISREG`, outside file
byte-identical, `saved_to` set); hard-linked target: fresh inode, outside
file byte-identical, `st_nlink` back to 1; error outcomes — transport
failure and binary type
— return the single-key `{"error"}` shape and write no file; `fetch/`
hash name only). `tests/test_history_stub.py`: HST-01…05 (request has stubs for
old turns, verbatim for the current one; latest skill kept; DB unchanged;
`off` equals the un-stubbed assembly, tool messages verbatim; budget on
stubs).
`tests/test_prefix.py`: CCH-01…03, PFX-01…03 (size limits, mandatory
statements present, schema equality modulo descriptions, `now` in the user
message, `/reload_skills` as the only invalidation of the byte-stable
prompt, Anthropic cache_control shape). `tests/test_routing.py`: RTE-01
(and RSN-02 when applicable).

### 11.6 Existing tests
Amend only what the changed system prompt and tool schemas break
(assertions on exact prompt text/tool description text) and what the
`<think>` stripping affects; list every amended test in the report.

---

## 12. Mutation gate

`devtools/mutation_check.py` gains the **33** mutations listed below (20
tagged A, 13 tagged C; with the 31 of v1.2 the final total is at least 64
— every summary of this gate elsewhere in the spec means exactly this
list, never a smaller threshold), all killed. Tagged A (stage A) or C
(stage C):

| id | tag | mutation | killed by |
|---|---|---|---|
| v13-usage-parse-none | A | `parse_response` ignores `usage` | 11.2 |
| v13-cached-tokens-dropped | A | `cached_tokens` always `None` | 11.2 |
| v13-think-not-stripped | A | `<think>` blocks left in content | 11.2 |
| v13-llm-call-not-recorded-on-error | A | failed calls skip `add_llm_call` | 11.2 |
| v13-resent-formula | A | `new_i = prompt_i` (re-sent always 0) | 11.2 |
| v13-cost-drops-output | A | cost formula omits completion tokens | 11.3 |
| v13-cost-none-as-zero | A | `cost_usd` returns `0.0` instead of `None` on missing usage | 11.3 |
| v13-bench-gate-threshold | A | `--gate` threshold 30 → 0 | 11.4 |
| v13-bench-skipset-ignored | A | report ignores differing skip sets | 11.4 |
| v13-bench-scenario-hash-ignored | A | report ignores differing `scenarios_sha256` | 11.4 |
| v13-bench-candidate-pricing | A | gate costs use each file's own `meta.pricing` | 11.4 |
| v13-bench-quality-minus-one | A | quality gate allows `successes − 1` | 11.4 |
| v13-bench-redact-detail | A | recursive redaction skips `checks[].detail` | 11.4 |
| v13-bench-turn-zero-based | A | positive `turn` indexes user turns zero-based | 11.4 |
| v13-bench-timeout-continues | A | timeout marks the run and starts the next scenario | 11.4 |
| v13-bench-check-trusts-summary | A | `check` skips the recomputation of `summary` | 11.4 |
| v13-usage-missing-ignores-failed | A | `check` rejects rows with `error_kind` set as `usage_missing` | 11.4 |
| v13-openrouter-cap-ignored | A | cap check removed | 11.4 |
| v13-symlink-chmod | A | `islink` skip in the `failed_paths` chmod loop removed | 11.1 |
| v13-only-typo-exit0 | A | `--only` unknown id exits 0 | 11.1 |
| v13-compact-keeps-head-only | C | tail window dropped | 11.5 |
| v13-dedup-threshold | C | collapse runs of ≥ 2 instead of ≥ 3 | 11.5 |
| v13-fragment-after-cut | C | `strip_secret_fragment` not applied after the cut | 11.5 |
| v13-fetch-script-kept | C | `script` subtree text kept | 11.5 |
| v13-fetch-save-path | C | file name uses the URL path instead of the hash | 11.5 |
| v13-fetch-dir-follows-symlink | C | `O_NOFOLLOW` dropped from the `fetch/` directory open | 11.5 (symlinked dir) |
| v13-fetch-save-reuses-inode | C | `unlink` + `O_EXCL` replaced by `O_TRUNC` on the target open | 11.5 (hard link) |
| v13-fetch-save-always | C | file written on an untruncated fetch too | 11.5 (short page) |
| v13-compact-over-budget | C | `MARKER_RESERVE` not subtracted from the budget | 11.5 |
| v13-stub-current-turn | C | current-turn tool results stubbed too | 11.5 |
| v13-stub-skill-latest | C | latest `load_skill` stubbed | 11.5 |
| v13-now-in-system | C | date/time line back in the system prompt | 11.5 |
| v13-routing-agent-too | C | routed client used for the agent loop | 11.5 |

Mutation ids, `--list`, `--only` semantics as in v1.2.

---

## 13. Gates, benchmark steps and acceptance

### 13.1 Gates (verbatim, AGENTS.md)

```bash
uv sync --locked
uv run --locked ruff check .
uv run --locked pytest
uv run --locked python bot.py --selftest
uv run --locked python bot.py --selftest-live
uv run --locked python devtools/mutation_check.py
```

All six exit 0 at C1, C3 and C4 (C2 changes docs only, but run 1–4 anyway).
Gate 5 fully green (REQ-V13-EC-10). The gate table of `report-v1.3.md`
(REQ-V13-RPT-01) has one row per commit; each row records the gates as run
on the tree **about to be committed**. For C4 the procedure is a fixed
two-pass sequence: (1) write every C4 file, with the gate table's C4 row
holding the literal placeholder `_pending_`; (2) run the six gates; (3)
replace the placeholder with the results of (2) and `git add` every C4
file; (4) re-run the six gates **without changing any file**; (5) when
(4) is all green, commit — the tree tested in (4) is byte-for-byte the
tree committed. The row is labelled `C4 (staged tree)` and records the
pass of (2) with the note `confirmed by an unchanged re-run`. A red gate
in (4) counts as one iteration of the section-1.4 fix loop and restarts
the sequence at (1). (No claim is made that gates never read `docs/` —
`bench.py` defaults to `docs/assets/bench/`; the re-run is what makes the
recorded results true for the committed tree.)

### 13.2 Benchmark steps (blocking, not permanent gates)

| step | when | command |
|---|---|---|
| B1 | after C1 gates | `bench.py run --tag baseline --repeats 3` |
| B2 | after B1 and the REQ-V13-AUD-02 decision | `bench.py run --provider openrouter --only S02 --repeats 1 --tag openrouter-smoke --max-cost-usd 0.50` |
| CP | stage C, only when REQ-V13-RSN-01 applies, before the C3 commit | `bench.py run --only S05 --repeats 1 --tag reasoning-probe` then `bench.py report --baseline docs/assets/bench/reasoning-probe.json --out docs/reports/bench-reasoning-probe.md` (REQ-V13-RSN-02; one scenario, not a section-1.4 run; at most one repeat of the pair when the first probe is inconclusive) |
| D1 | after C3 gates | `bench.py run --tag optimized --repeats 3` |
| D2 | after D1 | `bench.py report --baseline docs/assets/bench/baseline.json --candidate docs/assets/bench/optimized.json --gate --out docs/reports/bench-v1.3.md` |

Both full runs use the same `LMSTUDIO_MODEL` and context length, and the
harness — not the maintainer's `.env` — fixes the treatment
(REQ-V13-BEN-03). "Same configuration" is machine-checked, not asserted:
the harness records the comparison basis in `meta`, and `report --gate`
enforces it (REQ-V13-BEN-01): exit 2 when `provider`, `model`,
`context_length`, `repeats`, `timeout_s`, `scenarios_sha256`,
`skipped_scenarios`, `constants` or `config_sha256` (the hash of every
behaviour-affecting, non-secret `Config` field outside the treatment,
section 7.4) differ, or when the `env_flags` pair is not the expected
baseline/candidate treatment (stage-C keys `null` on the baseline side,
PRE-04 defaults on the candidate side; `LLM_FAILOVER=off`,
`LLM_SUMMARY_MODEL=""`, equal `LLM_MAX_TOKENS` on both). The only
differences a fair comparison expects are the stage-C treatment itself
and `pricing.fetched_at` — and the report prints both files' `env_flags`
and `pricing` side by side so the reader sees exactly what changed.

D2's exit code is captured explicitly (`rc=$?` — never left to fail-fast
shell semantics) and read as follows: **0 (PASS) and 1 (FAIL) both mean
the step completed** — execution continues to C4 with that verdict; **2
(not comparable) and 3 (`usage_missing`) are harness defects** — D1 is
re-run within the section-1.4 budget when a re-run can fix the cause,
otherwise (or once the budget is exhausted) the executor stops and
reports per section 3, and no C4 is produced. The same reading applies
to B1/B2 (`run` exit 4 = aborted, a harness defect).

### 13.3 Verdict

- Primary metric: **cost per successful task** =
  `Σ cost_usd / successes` (reference-priced for LM Studio). Cost gate:
  `candidate ≤ 0.70 × baseline`.
- **One price snapshot for both sides.** `report` does not trust the
  `cost_usd` columns of the two files for the gate: it recomputes every
  run's cost on both sides from the `llm_calls` token columns with
  `cost_usd(usage, price)` (REQ-V13-PRC-01) using the **baseline file's
  `meta.pricing`** — the snapshot committed in C2 — so a list-price change
  between B1 and D1 can neither create nor hide a saving. The candidate's
  own `meta.pricing` is printed next to it for information only; the
  verdict block names the snapshot (`model`, `fetched_at`). `check` (and
  `report` before comparing) rejects a file in which any successful run has
  an `llm_calls` row with `error_kind IS NULL` and a `NULL` `prompt_tokens`
  or `completion_tokens`, or any row with a negative token count or
  `cached_tokens > prompt_tokens` (exit 3, `usage_missing`,
  REQ-V13-BEN-01): a partially or inconsistently priced sum is never
  compared. Failed invocations (`error_kind` set, token columns `NULL` by
  REQ-V13-OBS-04) are exempt: they cost nothing measurable, count as 0 in
  every sum, and are reported as `failed_calls` (section 7.4) so a run
  with a transient retry stays comparable instead of invalidating the
  file. The verdict block prints `failed_calls` of both sides; when the
  candidate's count exceeds the baseline's it adds the line `warning:
  failed_calls rose N → M — the cost of failed invocations is unmeasured`
  (on the LM Studio path a failed invocation returns no usage and is not
  billed, and a retry that changed a task's outcome is already visible to
  the quality gate). What **is** gated is a conservative bound that keeps
  failed invocations from silently lowering the candidate's figure. One
  normative formula, with `B` the baseline file and `C` the candidate
  file, `successes_X = summary.successes`, `failed_X =
  summary.totals.failed_calls`, `Σcost_X` the recomputed sum above and
  `mean_ok_X = Σcost_X / (summary.totals.calls − failed_X)` (the mean cost
  of a successful invocation of that side; `0` when the divisor is `0`):
  `B_plain = Σcost_B / successes_B`; `C_plain = Σcost_C / successes_C`;
  `C_conservative = (Σcost_C + failed_C × mean_ok_C) / successes_C`. The
  cost gate requires **both** `C_plain ≤ 0.70 × B_plain` (the headline)
  and `C_conservative ≤ 0.70 × B_plain`; with `failed_C = 0` the two
  candidate figures are equal. No conservative figure is computed for the
  baseline. The verdict block prints `B_plain`, `C_plain` and
  `C_conservative` with these labels and `failed_B`/`failed_C` next to
  them. Test (section 11.4): a fixture pair where the plain gate passes
  and the conservative gate fails → `FAIL`, exit 1.
- Quality gate, literal: `success_rate(candidate) ≥ success_rate(baseline)
  − 0.02` where `success_rate = successes / runs` (skipped repeats are not
  runs, section 7.4). At the
  benchmark's resolution (33–36 runs, one flipped run = 2.8–3.0 pp) this
  means the candidate may lose **no** run net; the report prints the delta
  in pp next to the assignment's 2 pp headline with this resolution note.
  Additionally (also gated): no scenario loses more than one repeat
  (3/3 → 1/3 fails even when another scenario gains — a compensated
  aggregate must not hide a broken scenario). Any regressed run is
  investigated and documented.
- Verdict PASS = cost gate and quality gate both pass. `successes == 0` in
  either file → FAIL, exit 1, reason `no successful runs` (never a division
  by zero). At D1 the checks are frozen (REQ-V13-BEN-12), so a candidate
  below the AUD-02 floor is not re-calibrated: the quality gate alone
  decides, and the regressed runs are documented (REQ-V13-AUD-02 branch b).
- When the baseline has no pricing basis (`meta.pricing` is `null`): the
  primary metric is **tokens per successful task** (`prompt + completion`)
  on both sides, same thresholds; the report says so.
- Secondary (reported, not gated): prompt tokens, completion tokens,
  re-sent share, prefix tokens, median latency per call, tool output tokens,
  per-scenario deltas, cache hit rate (OpenRouter smoke only).

### 13.4 Target miss

There is no tuning loop: after C3 no code, test or configuration default
changes (C4 is docs and benchmark artifacts only, section 1.2), and D1 is
re-run only for a harness defect (section 1.4). If D2 says FAIL, C4 is
still produced with the honest FAIL verdict, the analysis of why, and a
**ranked list of untried levers for v1.4** with the expected effect of
each, derived from the two benchmark tables (candidates the executor must
evaluate, not apply: `EXEC_OUTPUT_DEFAULT_CHARS` 1500 → 1000,
`FETCH_INLINE_DEFAULT_CHARS` 5000 → 3000, `CONTEXT_WINDOW_MESSAGES` 30 →
20). The assignment grades the audit and the method, not only the number;
a FAIL with a clear cause is a valid deliverable, a PASS obtained by
re-running until the numbers fit is not.

### 13.5 Review

Two clean-context reviews by the `code-reviewer` subagent (prompt logged):
after stage A (before B1 — a harness defect found later costs a re-run) and
after stage C (before D1). Findings fixed in the same stage's commit.

---

## 14. Deliverables and documentation

- **REQ-V13-RPT-01 (MUST)** `docs/reports/report-v1.3.md` per
  `standards/reporting.md`: gate table per commit; both benchmark summaries;
  the verdict; the **combined** before/after cost delta (the only causal
  claim — O1–O4 are enabled together, there are no ablation runs, NG-05);
  per-optimization **observed supporting metric** (a table: optimization →
  its own metric → before → after; O1 `tool_output_tokens_est`, O2
  `resent_tokens`/`prompt_tokens` on multi-turn scenarios, O3 median
  `latency_ms` only, O4 `prefix_tokens`; O5 applicable or not; O6 not
  benchmarked, why) with the explicit label "attribution is non-causal:
  each metric is consistent with its optimization, not proof of it";
  amended tests list; review findings and fixes;
  fix-loop iterations used; LM Studio model and context length; pricing
  basis and date; skipped scenarios; executor token usage (prompts,
  tokens, cost — from `docs/llm-usage.md` as REQ-V13-RPT-06 fills it,
  `unknown` cells included).
- **REQ-V13-RPT-02 (MUST)** `docs/reports/tg-post-v1.3.md` per AGENTS.md
  (Russian, < 1500 chars, executor model named, link). v1.1 and v1.2 were
  never posted, so this post covers **v1 → v1.3 as one story**: one line per
  version (what changed, tests count, executor model), then the v1.3
  headline numbers (cost per task before → after, success rate before →
  after, re-sent share) and the cumulative token/cost line of RPT-07 with
  its caveat. The per-version detail stays in the report; the post links it.
- **REQ-V13-RPT-07 (MUST)** `report-v1.3.md` has a section **"Cumulative:
  v1 → v1.3"** built only from files in this repository — `docs/spec/`,
  `docs/reports/report-v1*.md`, `docs/llm-usage.md` — with two tables:
  (a) per version: spec (REQ count, size), what was delivered (one line),
  executor model, tests after the run, gates, bugs found by review / fixed,
  prompts; (b) per version: tokens in/out and cost, copied from the `Σ` rows
  of `docs/llm-usage.md` **verbatim including "unknown" and "not computed"
  cells** — never re-estimated or back-filled; where a cell is not
  computed, the table says so and a note names the lab ledger
  (`economics.md`, outside this repository) as the place where the
  maintainer records measured values. A final line gives the total over
  the computed cells only, labelled as a lower bound.
- **REQ-V13-RPT-03 (MUST)** README: new sections "Observability" (`/stats`,
  what is recorded, log lines, pricing env vars, the estimate caveat),
  "Benchmark" (how to run, what the JSON and the report contain, how to
  regenerate the dashboard), "Token economy" (what v1.3 changed and the
  headline before/after with a link to `docs/reports/bench-v1.3.md`),
  updated "Configure" table, "Commands" (`/stats`), "The fetch tool"
  (text extraction, `fetch/` files, `max_chars`), "Limits"
  (`max_output_chars`), plus the carry-over fixes of REQ-V13-CO-07.
  Split across commits (1.2): C3 writes every section with the "Token
  economy" numbers as the literal placeholder `_measured in C4_` and no
  link; C4 replaces exactly that placeholder with the measured headline
  (cost/success before → after, −N %, success-rate delta in pp) and the
  link — the only README change C4 makes (test: none; verified by the
  `git diff HEAD -- README.md` output captured in step (1) of section
  13.1 right after the README edit — i.e. the working tree against C3,
  which is what C4 will commit — and quoted in `report-v1.3.md`; the
  post-commit `git diff HEAD~1 HEAD -- README.md` would be the same diff
  but cannot be quoted before C4 exists).
- **REQ-V13-RPT-04 (MUST)** AGENTS.md: project layout gains `metrics.py`,
  `llm/pricing.py`, `devtools/`; gate paragraph states gate 5 must be fully
  green (LM Studio reachable); a "Benchmark" section with the two commands
  and the rule that a behaviour change touching tokens must be accompanied
  by a benchmark run before/after.
- **REQ-V13-RPT-05 (MUST)** `docs/plan.md`: v1.3 marked done with the
  headline numbers; v1.4 candidates: tokenizer-accurate budget, routing
  enabled when a second model is available, streaming, semantic cache if a
  dependency is ever allowed.
- **REQ-V13-RPT-06 (MUST)** `docs/llm-usage.md`: rows for the v1.3 run
  (per stage if the harness reports them separately) and the corrected v1.2
  row (REQ-V13-CO-07). **Source of the executor numbers:** the executor has
  no API to its own session usage; it fills each cell from what its harness
  displays (a usage/cost line or `/cost`-style summary, if any) and writes
  the literal `unknown` in every cell it cannot observe — never an
  estimate, never a number without a named source (the row's note column
  says where the value came from). Prompt counts are always known (the
  files in `docs/prompts/`). The measured tokens/cost of the whole run are
  filled in **after** the run by the maintainer from the lab's session
  transcripts (`tools/session-usage.py`, outside this repository) and
  recorded in `economics.md`; RPT-07 copies whatever the table says. The
  AGENTS.md instruction to add "an estimate at public API prices" applies
  to the Telegram post only, where it stays labelled as an estimate.

---

## 15. Execution plan (RLM)

Sequential by default: one subagent at a time in the working tree. Parallel
only where file ownership is disjoint **and** each agent has its own
worktree (AGENTS.md "Parallel agent work"); the executor decides, the
report says what was parallel. Every brief: ≤ 8 lines + REQ ids + the
file list it owns + "return a ≤ 15-line summary; never paste files; never
open `.env`". The main context runs gates and benchmark commands itself
(background Bash), reads only summaries.

| id | stage | task (owned files) | returns |
|---|---|---|---|
| TA1 | A | carry-over: REQ-V13-CO-01…08 (`bot.py` `_remove_sandbox_entry`, `devtools/mutation_check.py`, `tests/test_v13_carryover.py`, v1.2 quota tests, README wording, llm-usage v1.2 row) | tests added/passing, files touched |
| TA2 | A | observability core: OBS-01…09 (`llm/base.py` incl. the `CostResolver` type next to `Usage`, `llm/*.py` `describe()`, `storage.py` v3, `agent.py` recording — threads the keyword-only `resolve_cost` of REQ-V13-PRC-02 through `run_agent`/`summarize_conversation` with the `None` default, tested with stub resolvers, no dependency on `llm/pricing.py`; `metrics.py`, `bot.py` `/stats` + `/status` line only, `tests/test_observability.py`) — runs **before** TA3 | schema, row counts, test count |
| TA3 | A | pricing: PRC-01…03 (`llm/pricing.py` incl. `make_resolver` against the TA2 type, `config.py` — the three pricing variables, the only REQ-V13-PRE-04 variables C1 introduces, `bot.py` **pricing wiring only** — startup fetch, `bot_state` persist, building the resolver once and passing it to `run_agent`/`summarize_conversation`, `tests/test_pricing.py`, `.env.example`) — includes the context7 verification of `/models` and usage-accounting field names; runs **after** TA2 | verified field names + doc citation |
| TA4 | A | bench harness: BEN-01…14 (`devtools/bench.py`, `devtools/bench_scenarios.py`, `tests/test_bench.py`, `tests/fixtures/bench/`) | CLI summary sample, test count |
| TA5 | A | dashboard: DSH-01…02 (`devtools/dashboard.py`, `tests/test_dashboard.py`) | sections implemented |
| TA6 | A | mutations tagged A (`devtools/mutation_check.py`) | ids added, all killed |
| TA7 | A | review (code-reviewer, clean context) of stage A | findings list |
| TA8 | A | fix findings of TA7 | what changed |
| — | A | main: gates 1–6, commit **C1** | — |
| — | B | main: B1, the AUD-02 decision from `## Failures`, B2 (background), `report` for both JSON files (REQ-V13-AUD-03), `dashboard.py` | 40-line summaries |
| TB1 | B | audit writer: AUD-04 from `bench-baseline.md` (plus `bench-openrouter-smoke.md` for the provider-usage statement) | the audit file |
| — | B | main: commit **C2**, tag `v1.3-baseline` | — |
| TC1 | C | O1: TOO-01…10 (`tools.py`, `config.py`, `tests/test_tool_output.py`) | fixtures, sizes before/after on fixtures |
| TC2 | C | O2: HST-01…05 (`agent.py` `_assemble_context`, `config.py` `HISTORY_TOOL_STUB`, `storage.py` reader if needed, `tests/test_history_stub.py`) | payload example sizes |
| TC3 | C | O3 + O4: CCH-01…04, PFX-01…03 (`agent.py` prompt/prefix, `tools.py` `tool_specs` descriptions, `llm/openrouter.py`, `tests/test_prefix.py`, amended existing tests) | char counts before/after |
| TC4 | C | O5 if RSN-01 applies (`agent.py`, `llm/lmstudio.py`, `config.py`, tests) — includes the context7 verification and the REQ-V13-RSN-02 reasoning probe (reads only `bench-reasoning-probe.md`; on `attempted_removed` strips the knob again before returning) | mechanism + state (`implemented` / `attempted_removed`) + evidence |
| TC5 | C | O6: RTE-01 (`llm/__init__.py`, `config.py`, `agent.py` summary path, `tests/test_routing.py`) | wiring summary |
| TC6 | C | mutations tagged C | ids added, all killed |
| TC7 | C | review (code-reviewer) of stage C | findings |
| TC8 | C | fix findings of TC7 | what changed |
| TC9 | C | docs: RPT-03, RPT-04 (README, AGENTS.md, `.env.example`) | sections touched |
| — | C | main: gates 1–6, commit **C3** | — |
| — | D | main: D1 (background), D2, `dashboard.py --compare`; on FAIL the 13.4 target-miss analysis (documentation only) | summaries + verdict |
| — | D | main: the README step of REQ-V13-RPT-03 — replace the `_measured in C4_` placeholder with the headline from `bench-v1.3.md` and the link, then capture `git diff HEAD -- README.md` (step (1) of section 13.1); that diff output is an **input** of TD1 — TD1 never edits README | the diff text |
| TD1 | D | report writer: RPT-01, RPT-05, RPT-06, RPT-07 from the two `bench-*.md` files, gate outputs, the README diff captured above, and `docs/reports/report-v1*.md` + `docs/llm-usage.md` (never from JSON; never touches README) | the report |
| TD2 | D | Telegram post: RPT-02 from `report-v1.3.md` | the post |
| — | D | main: commit **C4**, tag `v1.3` | — |

TC1, TC2 and TC3 all touch `agent.py`/`tools.py`; run them sequentially
unless worktrees are used. Task ids (`TA*`, `TB*`, `TC*`, `TD*`) are distinct
from commit ids (C1–C4) and benchmark steps (B1, B2, D1, D2).

---

## 16. Non-goals for v1.3

- **REQ-V13-NG-01 (NON-GOAL)** Any new dependency (embeddings, tokenizers,
  web frameworks, plotting libraries).
- **REQ-V13-NG-02 (NON-GOAL)** Runtime model switching with load/unload on
  the single-model box.
- **REQ-V13-NG-03 (NON-GOAL)** Streaming responses; a live web dashboard
  server; Prometheus/OTel exporters.
- **REQ-V13-NG-04 (NON-GOAL)** Changing the security posture of exec/fetch
  (caps, timeouts, allowlist, redaction order) beyond what section 10.1
  states.
- **REQ-V13-NG-05 (NON-GOAL)** Editing benchmark scenarios after C2, or
  cherry-picking repeats: all raw runs are committed. Per-optimization
  ablation runs (one benchmark per O1–O4 toggle): two full runs are the
  budget; attribution stays non-causal (REQ-V13-RPT-01).
- **REQ-V13-NG-06 (NON-GOAL)** LLM-based summarization/compaction of tool
  output (lecture 3 says: deterministic first; LLM compaction is the last
  resort and is not needed here).

---

## Appendix A — traceability

### A.1 Assignment 5 requirements → REQs

| Assignment item | REQs |
|---|---|
| Per-call logging: timestamp, agent/task id, model, input/output/cached/reasoning tokens, latency, cost, turn number | OBS-01…04, PRC-01…03 (`conv_id` = task id in the bot; `scenario`+`repeat` = task id in the bench; `agent_id` is constant for this single-agent bot and therefore not stored — stated, not forgotten) |
| Per-tool-call: name, input size, output size, output tokens, duration | OBS-05 |
| Dashboard: aggregates, cache hit rate, expensive-tool breakdown, per-run timeline | DSH-01…02, OBS-07 (`/stats`) |
| Audit: most expensive tool/turn, fastest-growing context, re-sent tokens | OBS-08, BEN-14, AUD-04 |
| ≥ 3 optimizations | TOO (O1), HST (O2), PFX (O4) mandatory; CCH (O3), RSN (O5), RTE (O6) |
| Benchmark before/after, −30 % cost/task, ≤ 2 pp success drop | BEN-*, AUD-01, 13.2–13.4 |
| Deliverables: dashboard + before/after report + PR | DSH-01, RPT-01…02, EC-08…09 (compare link between `v1.2`-state and `v1.3`) |

### A.2 Lecture techniques → disposition

| # | Technique | v1.3 |
|---|---|---|
| 1 | Context search before LLM | HST-01 (stubs carry `head`/`saved_to`; the model re-reads locally) |
| 2 | Memory split (JSON state) | already in v1.1 (structured summaries); counted |
| 3 | Compaction: deterministic → structured → LLM | TOO-01, HST-01 (deterministic + structured; LLM compaction NG-06) |
| 4 | Token-aware tool output (`maxTokens`) | TOO-02, TOO-07 |
| 5 | Code instead of LLM | metrics/report/dashboard are code; bench checks are code |
| 6 | Prompt/KV caching, stable prefix | CCH-01…04 |
| 7 | Model routing | RTE-01…02 (config-only; not benchmarked — memory constraint) |
| 8 | Reasoning limits, structured prompt, caps | PFX-01, RSN-01…02, existing loop caps |
| 9 | Fewer turns, minimal subagent briefs | section 15 (the run itself); PFX-01 "be concise" |
| 10 | Semantic cache | NG-01 |
| 11 | Fetch once → process locally | TOO-06…07 |
| 12 | Don't resend unchanged content (SHA256) | HST-01 (`sha256_16` in stubs) |
| 13 | Smart git diff | n/a — no git workload |
| 14 | Smart test results | TOO-01 error-context window (same idea for exec output) |
| 15 | AgentHandoff structure | n/a — single agent |
| 16 | Batch processing | n/a |
| 17 | Compression without LLM (drop INFO, collapse dupes, ±20 lines) | TOO-01 |
| 18 | Cost observability, cost per successful task | OBS-*, PRC-*, 13.3 |
| — | Participant materials: format controls length, NEVER/MUST, English, no politeness | PFX-01…02 |

### A.3 Carry-over → REQs

`_remove_sandbox_entry` → CO-01; owner binding → CO-02; late binding →
CO-03; OSError-only → CO-04; INF-01 clauses → CO-05; `--only` typo → CO-06;
README + llm-usage → CO-07; chmod-000 hygiene → CO-08.

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

Secrets in these scenarios are **synthetic canaries**; never a live value.

```gherkin
Feature: usage is recorded for every LLM call
  Scenario: a successful tool round
    Given a FakeLLM that answers with one exec tool call and usage {prompt 900, completion 40}
    When run_agent handles one user message
    Then llm_calls has one row with purpose 'agent', round 1, prompt_tokens 900, completion_tokens 40
    And prompt_chars_by_role has keys system, tools, user, assistant, tool
  Scenario: a failed llm.complete invocation is recorded and retried by run_agent
    Given a FakeLLM that raises LLMError(kind='http', retryable=True) once, then answers
    When run_agent handles one user message
    Then llm_calls has two rows with attempt 1 and 2, the first with error_kind 'http' and NULL token columns
  Scenario: a failover inside one invocation is one row
    Given a FailoverLLMClient whose primary has failure_counts at FAILOVER_THRESHOLD − 1, raises LLMError once more, and whose fallback answers
    When run_agent handles one user message
    Then llm_calls has one row with attempt 1, provider and model of the fallback client (describe() after the invocation)

Feature: think blocks never reach the user
  Scenario: LM Studio returns inline thinking
    Given a response whose content is "<think>plan</think>Answer"
    When parse_response runs
    Then content is "Answer" and reasoning_chars is 4

Feature: /stats
  Scenario: no pricing basis
    Given a conversation with two recorded calls and no pricing in bot_state
    When the owner sends /stats
    Then the reply contains "Est. cost: n/a (no pricing)" and "LLM calls: 2 |"

Feature: benchmark harness never talks to Telegram
  Scenario: TelegramClient constructor is patched to raise
    When run_bench executes one scenario with fakes
    Then no exception is raised and the recorder holds the final answer

Feature: benchmark secrets
  Scenario: synthetic canary in an answer
    Given config whose OPENROUTER_API_KEY value is SYNTHETIC-CANARY-1 (load_env_file=False)
    And a FakeLLM whose final answer contains that value
    When run_bench writes its JSON
    Then the JSON text does not contain "SYNTHETIC-CANARY-1"
  Scenario: canary in a provider error and a Telegram id
    Given the same config with ALLOWED_TG_IDS containing 123456789
    And a FakeLLM raising LLMError whose message contains "SYNTHETIC-CANARY-1" and "123456789"
    When run_bench writes its JSON
    Then the JSON text contains neither string and checks[].detail is a reason code

Feature: benchmark timeout
  Scenario: a run blocks forever
    Given a FakeLLM whose complete() waits on a threading.Event that is never set
    And run_bench with timeout_s 0.2 and two scenarios
    When the run is executed
    Then the first run is recorded with success false and failure "timeout" within 1 s
    And the second scenario is never started, the JSON is written with meta.aborted "timeout:S01-1"
    And the run directory of S01-1 is left in place
    And the CLI reaps tgexec-labelled containers and exits 4 via os._exit, and bench.py check on that file exits 2
  Scenario: SIGINT during a run
    Given run_bench with two scenarios and join monkeypatched to raise KeyboardInterrupt once
    When the run is executed
    Then the first run is recorded with success false and failure "harness_error"
    And meta.aborted is "sigint", the second scenario is never started, and the CLI exits 4

Feature: report gate
  Scenario: skip sets differ
    Given baseline skipped S08 and candidate skipped nothing
    When bench.py report --gate runs
    Then it exits 2
  Scenario: scenario file changed between runs
    Given baseline and candidate with different meta.scenarios_sha256
    When bench.py report --gate runs
    Then it exits 2 and the reason names scenarios_sha256
  Scenario: −30 % reached with equal success
    Given baseline cost_per_success 0.100 and candidate 0.065, success rates equal
    When bench.py report --gate runs
    Then the verdict is PASS and exit code 0
  Scenario: one lost run fails the literal quality gate
    Given 36 runs each, baseline 34 successes and candidate 33, cost −40 %
    When bench.py report --gate runs
    Then the verdict is FAIL with reason "success rate −2.8 pp > 2 pp" and exit code 1
  Scenario: cheaper list price does not count as a saving
    Given identical llm_calls token columns in both files and a candidate meta.pricing 50 % cheaper
    When bench.py report --gate runs
    Then costs are recomputed with the baseline snapshot, the delta is 0 % and the verdict is FAIL

Feature: exec output compaction
  Scenario: 200 identical INFO lines then a traceback
    Given exec stdout of 200 lines "INFO heartbeat ok" (3600 B, under the 4096 B capture cap) and a ZeroDivisionError traceback on stderr, exit code 1
    When the envelope is built with max_output_chars 1500
    Then stdout contains "INFO heartbeat ok [×200]"
    And stderr contains "ZeroDivisionError" and no "[… " marker between "Traceback" and the last line
  Scenario: a secret prefix at the head cut
    Given a synthetic canary is the only registered secret
    And the redacted input holds no complete canary, its head window's last line is "token=" + the canary's first 10 characters, and filler lines force a cut
    When compact_output runs
    Then the head part ends with "token=" immediately before the marker line
    And no fragment of the canary of 8 or more characters is present

Feature: fetch saves text once
  Scenario: HTML page, truncated
    Given a FakeFetcher returning text/html with <script>, <style>, a <title> and 3000 chars of text
    When fetch runs with max_chars 500
    Then the envelope text starts with the title, contains no script text, truncated is true
    And saved_to is "fetch/<16 hex>.txt", save_error is null and that file exists in the sandbox
  Scenario: short page, nothing to save
    Given a FakeFetcher returning 300 chars of text
    When fetch runs with max_chars 500
    Then truncated is false, saved_to is null, save_error is null and no file exists under fetch/
  Scenario: quota refuses the save
    Given the sandbox usage already at EXEC_SANDBOX_MAX_BYTES and a truncating fetch
    When fetch runs
    Then saved_to is null and save_error is "sandbox quota" and the inline text is still returned
  Scenario: a symlinked fetch directory is refused
    Given <EXEC_WORKDIR>/fetch is a symlink to a temp directory outside the sandbox and a truncating fetch
    When fetch runs
    Then saved_to is null, save_error is "refused" and the temp directory stays empty
  Scenario: a symlinked target file is replaced, its target untouched
    Given <EXEC_WORKDIR>/fetch/<hash>.txt is a symlink to a temp file outside the sandbox and a truncating fetch
    When fetch runs
    Then saved_to is "fetch/<hash>.txt", lstat of that name is a regular file, and the temp file content is unchanged
  Scenario: a hard-linked target file never reaches the outside inode
    Given <EXEC_WORKDIR>/fetch/<hash>.txt is a hard link to a temp file outside the sandbox and a truncating fetch
    When fetch runs
    Then saved_to is "fetch/<hash>.txt", the temp file content is byte-identical and its st_nlink is 1
  Scenario: an error outcome keeps the single-key shape
    Given the transport raises a connection error
    When fetch runs
    Then the envelope is {"error": "<reason>"} with no other key and no file exists under fetch/

Feature: stale tool results are stubbed in the request only
  Scenario: second user turn
    Given a conversation whose first turn produced an exec result of 3000 chars
    When run_agent handles the second user message
    Then the request's tool message for turn 1 is a stub JSON with "stub": true and sha256_16
    And the messages table still holds the 3000-char result
    And with HISTORY_TOOL_STUB=off every tool message is verbatim, equal to the un-stubbed assembly
  Scenario: skill loads survive
    Given turn 1 loaded skill "weather"
    When turn 2 is assembled
    Then the load_skill result for "weather" is verbatim in the request

Feature: byte-stable prefix
  Scenario: two turns, two timestamps
    When run_agent runs at now=A and later at now=B in the same conversation
    Then both requests have identical system messages and identical tools JSON
    And the last user message of the second request ends with "(now: B)"

Feature: routing
  Scenario: summary goes to the routed client
    Given LLM_SUMMARY_MODEL=lmstudio:small-fake and two FakeLLMs
    When /new triggers summarization
    Then the summary call was served by the routed client and the agent calls by the main client
```

---

## Appendix C — the 12 frozen benchmark scenarios

Turns are sent verbatim (Russian). `network` is `false` unless stated.
Inside this table `\|` is only the markdown escape of the cell separator:
every `answer_regex` argument is a Python regex in which those are plain
`|` alternations — the S03 literal is `r"\b3\b|три"`, the S01 literal is
`r"exec|команд|скилл|skill|fetch|python"`. A backslash-pipe never appears
in `bench_scenarios.py`; the loading test of REQ-V13-BEN-08 asserts that no
pattern contains the two-character sequence `\|` (as a Python string).

| id | title | turns | checks |
|---|---|---|---|
| S01 | greet | «Привет! Что ты умеешь? Ответь кратко.» | `no_tools`; `answer_regex("exec\|команд\|скилл\|skill\|fetch\|python")`; `answer_max_chars(900)` |
| S02 | arith | «Посчитай 17*23+5, используя python через exec, и дай только число.» | `tool_used("exec")`; `answer_regex(r"\b396\b")` |
| S03 | file-roundtrip | «Создай файл notes.txt с тремя строками: alpha, beta, gamma. Затем выведи, сколько строк в файле, и назови это число.» | `tool_used("exec")`; `answer_regex(r"\b3\b\|три")` |
| S04 | error-explain | «Выполни python-скрипт, который импортирует модуль foo_bar_baz_qux, и объясни в одной фразе, почему он упал.» | `tool_used("exec")`; `exit_code_seen(nonzero=True)`; `answer_regex("ModuleNotFoundError\|foo_bar_baz_qux\|не найден\|not found\|не установлен")` |
| S05 | big-output | «Выполни через exec этот python-код без изменений: import random; random.seed(7); [print(random.randint(1, 1000)) for _ in range(5000)] — и назови первое напечатанное число.» | `tool_used("exec")`; `answer_regex(r"\b332\b")` (the first line is inside the 4096-byte capture head and is knowable only from the output: CPython `seed(7)` → 332) |
| S06 | noisy-log | «Запусти python-скрипт: 200 раз печатает строку 'INFO heartbeat ok', затем вычисляет 1/0. Объясни причину падения одной фразой.» | `tool_used("exec")`; `answer_regex("ZeroDivisionError\|делен\|на ноль\|zero")` |
| S07 | skill | «Используй скилл host-info и расскажи, что он сообщает о системе.» | `tool_used("load_skill")`; `answer_regex(".{40,}")` |
| S08 | fetch-weather (`network: true`) | «Какая сейчас погода в Берлине? Используй fetch на https://wttr.in/Berlin?format=3 и ответь одной строкой.» | `tool_used("fetch")`; `answer_regex("Berlin\|Берлин\|°")` |
| S09 | multi-turn | (1) «Создай файл data.csv со строками: name,score / ann,10 / bob,20 / cid,30 / dan,40 / eve,50» (2) «Посчитай через python среднее значение score из data.csv.» (3) «А какое там максимальное значение score? Ответь одним числом.» | `answer_regex(r"\b30\b", turn=2)`; `answer_regex(r"\b50\b", turn=3)` |
| S10 | knowledge | «Объясни в двух предложениях, что такое KV-cache в LLM.» | `no_tools`; `answer_regex("KV\|кэш\|кеш\|cache")`; `answer_max_chars(900)` |
| S11 | json | «Верни строго JSON-объект с ключами a и b, где a=1, b=2. Без пояснений.» | `no_tools`; `json_keys({"a": 1, "b": 2})` |
| S12 | summary | (1) «Запомни: проект называется Orion, дедлайн 15 октября.» (2) «Что я просил запомнить? Одной строкой.» (3) `/new` | `answer_regex("Orion", turn=2)`; `summary_exists` |

Success rate denominators exclude skipped scenarios (S08 when the network
preflight fails). Repeats: 3 each → 36 runs (33 with S08 skipped).

---

## Appendix D — spec cross-review log

`━━━ CHECKPOINT: debate, rounds=7, termination=round_limit, cross_review=codex, gate=pass ━━━`

The spec was cross-reviewed before `go` by an independent challenger —
OpenAI Codex `gpt-5.6-sol` through the lab's `debate-loop.sh` (the plan
text is sanitized before it leaves the machine; termination is decided
deterministically from the diff hash, `--max 7`). Every round's critique
was verified against the spec text and, where it made a claim about the
code, against the v1.2 tree before anything was edited.

| round | findings | applied | refused | notable |
|---|---|---|---|---|
| 1 | 16 | 16 | 0 | literal quality gate (≤ 2 pp); locked comparison meta; one price snapshot for both sides; fetch symlink hardening; wall-clock timeout semantics |
| 2 | 15 | 14 | 1 (O6) | C3/C4 documentation ordering; gate results per commit; precise bench schema for `check`/`report`; turn indexing; skipped-scenario semantics |
| 3 | 12 | 10 | 2 (O6; one sanitizer artifact, not a spec defect) | Appendix C regexes; AUD-02 recalibration inside the four-commit contract; fetch write sequence; O5 request-time rule |
| 4 | 12 | 12 (2 partial) | 0 | C4 two-pass gate procedure; retries are separate invocations; treatment pinned by the harness (`env_flags`), not `.env`; report writers read markdown, never JSON |
| 5 | 12 | 11 (1 partial) | 1 (O6) | O5 probe before C3; arithmetic across `/new` (`conv_seq`); `run_bench` DI interface; FAIL vs harness-defect exit codes; `failed_calls` |
| 6 | 10 | 9 (2 partial) | 1 (O6) | run-set validation; `usage: {include: true}` moved to stage A; `resolve_cost` interface; `fetcher_factory`; configured vs actual context length |
| 7 | 12 | 11 | 1 (O6) | `## Failures` calibration evidence; TA2 → TA3 order; probe conclusiveness; one conservative-cost formula; `REQUEST_DEFAULTS` locked; INFO logs off the console |

Refused on purpose, every time it was raised: removing O6 (section 10.6,
REQ-V13-RTE-01/02). The challenger's argument — unmeasured scope that
cannot contribute to the 30 % target — is correct as far as it goes; the
maintainer's decision is that the lecture-7 technique stays covered as
configuration on a box where a second model does not fit into GPU memory
(load/unload per call is not viable), and the spec records it as
config-only, disabled in both benchmark runs. Round 7's finding 1
(CCH-02 "impossible under eviction") was refuted by the code — assembly
runs once per invocation — and answered by making that structure explicit
rather than by weakening the requirement.

Codex kept producing findings of decreasing weight up to the round limit
and never issued `PLAN APPROVED`; termination by `round_limit` is the
documented outcome for that case. One local fault occurred in round 6:
the wrapper passes the plan as a single argv string and the spec had
grown past the kernel's per-argument limit (`Argument list too long`,
`MAX_ARG_STRLEN`) — a fault of the caller, not a Codex outage. It was
fixed without modifying the lab scripts, through the wrapper's documented
`CODEX_CMD` seam: an exported shell function that writes the prompt to a
file and calls the API from there. Rounds 6 and 7 ran through that seam
with `cross_review=codex`.

---

## Appendix E — execution deltas (written during the v1.3 run)

Four clauses of this spec turned out to be inconsistent with the code they
describe or with each other. AGENTS.md ("spec drift") requires the delta to
land in the same commit as the behaviour, so each is recorded here with the
resolution the executor applied. Every one was found before the baseline
benchmark; none changes a target, a gate threshold or the four-commit
contract. The executor never chose between readings where a reading was
available — each entry names the clause that survives and why.

### E.1 REQ-V13-CO-02 — the example sentence is inverted (stage A)

The requirement reads: "with two containers labelled with different owner keys
(fake docker CLI), only the one whose owner label equals this process's
`owner_key()` is reaped."

`tools.owner_key()` returns `f"{pid}-{start_ticks}"` — a **per-process** tag.
spec-v1.2 REQ-V12-ORP-02, still in force (§2: "Everything else in spec-v0 …
spec-v1.2 stands"), requires the opposite and is already pinned by
`test_t_v12_orp_02_three_containers`: a container labelled by a **still-live**
bot process is left alone, "so starting a second instance can no longer kill
the first one's running exec".

**Resolution.** The normative instruction of CO-02 is its first clause — "Test
the `owner=owner_key()` binding of the orphan reap" — and that is what was
implemented (the binding plus the reap discrimination). The illustrative
sentence is a defect: following it literally would regress REQ-V12-ORP-02 and
reintroduce the v1.1 fault it fixed. REQ-V12-ORP-02 survives unchanged.

### E.2 REQ-V13-BEN-01 run-set validation vs REQ-V13-AUD-03 / REQ-V13-RSN-02

BEN-01 makes `check` — and therefore `report`, which runs the same validation —
reject any file whose `runs[]` is not exactly
`(SCENARIOS ∖ meta.skipped_scenarios) × 1..meta.repeats`. But AUD-03 (MUST)
requires `docs/reports/bench-openrouter-smoke.md` to be the verbatim output of
`bench.py report` on a file produced with `--only S02 --repeats 1`, and states
that "a one-run file renders the same sections"; RSN-02 (MUST) requires the
same for `docs/assets/bench/reasoning-probe.json`. Under the literal rule
neither required file can exist. `meta.skipped_scenarios` cannot absorb the
difference — BEN-01 constrains it to ids with `network: true`.

**Resolution.** `run` records the selection as **`meta.only`**: the sorted list
of selected scenario ids, or `null` for a full run. `check` validates the run
set against `(SCENARIOS ∩ meta.only ∖ skipped) × 1..repeats` when `only` is
non-null and against the spec's literal set when it is `null`;
`summary.per_scenario` keys must equal the same set; omission, duplicate and
unknown id remain exit 1. `meta.only` joins the **locked** meta fields of
REQ-V13-BEN-01, so a `--only` file can never be gated against a full one
(differing → exit 2, reason names `only`). B1 and D1 both carry `null`, so the
two files the verdict compares are validated by the spec's literal rule and
BEN-01's stated purpose — "a harness defect that drops a scenario from both
files is therefore caught by `check`, never by eye" — is preserved exactly.

`meta.only` is an additional required key of the §7.4 schema; a document
missing it fails `check` with `meta.only is missing`.

### E.3 REQ-V13-BEN-14 — `tools_exposed = 1` does not match the stored column

§7.8 splits the `## Reasoning` figures into "rows with `tools_exposed = 1`" and
"rows with `tools_exposed = 0`". The column stores a **count**
(`agent.py`: `tools_exposed = len(tools) if tools else 0`, i.e. 3 for a normal
agent round with the shipped catalog), parallel to `messages_n`, beside which
§6.1 lists it. Under the literal `= 1` the tool-exposed group is empty on every
real run: `## Reasoning` would always render `tool-exposed calls: calls: 0`,
and REQ-V13-RSN-02 — which is conclusive only when that line shows `calls: 1`
or more — would force O5 to `attempted_removed` on a false reading. The
`tools-withheld` line worked only by accident, the final tools-withheld request
setting `request_tools = None` → 0.

**Resolution.** The column keeps its count semantics; the split reads
**`tools_exposed > 0`** for tool-exposed and **`tools_exposed == 0`** for
tools-withheld. `calls: N` still counts the rows of that group with
`error_kind IS NULL`, so the RSN-02 conclusiveness rule is unchanged in
meaning. The test that covered the split was rewritten to use production-shaped
values (3 and 0) and to assert the rendered counts — it previously passed with
the production path dead.

### E.4 REQ-V13-BEN-02 — the cost-cap refusal is keyed on the effective provider

BEN-02 says "`--provider openrouter` **refuses to run** unless `--max-cost-usd`
is given". The harness sets `LLM_PROVIDER` only when `--provider` was passed,
so on a box whose `.env` selects OpenRouter a plain
`bench.py run --tag baseline` would have run 36 live scenarios with no cap and
`run_bench`'s cap check disabled.

**Resolution.** The refusal is keyed on the **effective** provider
(`cfg.llm_provider == "openrouter"`), evaluated after the config is built and
before anything is spent or written. This strictly widens the protection BEN-02
asks for; the flag path behaves exactly as specified.
