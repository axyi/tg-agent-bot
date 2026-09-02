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
benchmark run again to prove the saving. Acceptance targets, fixed by the
assignment: **cost per successful task −30 % minimum** against the measured
baseline and **success-rate drop ≤ 2 percentage points**.

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
  precondition fails; the spec contradicts itself or AGENTS.md — stop and ask.

---

## 1. Execution contract

Sections 1 of spec-v0, spec-v1, spec-v1.1 and spec-v1.2 apply unless a line
below overrides them.

### 1.1 Conduct

- **REQ-V13-EC-01 (MUST)** Read this whole file before writing code. The
  spec is the contract; where it contradicts itself or AGENTS.md, stop and
  ask instead of choosing.
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
  canaries in tests are synthetic (`OPENROUTER_API_KEY=SYNTHETIC-...`,
  `load_config(env=..., load_env_file=False)`), never a live value.
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
| C1 | `feat: spec-v1.3 stage A — v1.2 carry-over, observability layer, benchmark harness` | sections 5, 6, 7, 8; tests of 11.1–11.4; mutations of 12 tagged A; `docs/prompts/09-go-spec-v1.3.md` and the stage-A subagent prompt logs |
| C2 | `docs: spec-v1.3 baseline benchmark and token audit` | section 9 outputs only: `docs/assets/bench/baseline.json`, `docs/assets/bench/openrouter-smoke.json`, `docs/assets/dashboard-baseline.html`, `docs/reports/bench-baseline.md`, `docs/reports/audit-v1.3.md` |
| C3 | `feat: spec-v1.3 stage C — token-economy optimizations` | section 10; tests of 11.5; mutations of 12 tagged C; README/AGENTS updates tagged C; stage-B/C subagent prompt logs |
| C4 | `docs: spec-v1.3 optimized benchmark, before/after report, Telegram post` | `docs/assets/bench/optimized.json`, `docs/assets/dashboard-v1.3.html`, `docs/reports/bench-v1.3.md`, `docs/reports/report-v1.3.md`, `docs/reports/tg-post-v1.3.md`, `docs/llm-usage.md`, `docs/plan.md`, remaining prompt logs |

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
  steps**. A full run that did not execute all 12 scenarios × 3 repeats (the
  network scenario may be *skipped*, section 7.5, but never *missing*) is not
  a run. The smoke is complete when S02 ran once with `usage` present
  (`prompt_tokens` and `completion_tokens` not `NULL`). A stage whose step
  is incomplete is not done.

### 1.4 Bounded fix loops

- Gates 1–6: at most **3** fix iterations per gate per stage; then stop and
  report.
- Benchmark re-runs: at most **2** extra runs per stage (a run is 36 scenario
  executions). A re-run is allowed only for a harness defect (crash, missing
  usage, wrong skip set) or, in stage D, for the target-miss backlog of
  section 13.4 — never to "try for better numbers".
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
| spec-v1 exec envelope (stdout/stderr capped at `EXEC_MAX_STREAM_BYTES`) | **extended**: the 4096-byte capture cap stays the security ceiling; the model-visible text is additionally compacted (head/tail window, duplicate collapse) with a per-call `max_output_chars` | REQ-V13-TOO-01..04 |
| spec-v1.1 fetch tool (raw body up to `FETCH_MAX_BYTES` inline) | **extended**: HTML→text extraction, inline window `max_chars`, full text saved under the sandbox `fetch/` directory | REQ-V13-TOO-05..09 |
| spec-v1 system prompt text (`SYSTEM_PROMPT`) | **superseded** by the compressed prompt of REQ-V13-PFX-01; the date/time line moves out of the system prompt | REQ-V13-PFX-01, REQ-V13-CCH-01 |
| spec-v1 tool schema descriptions | **superseded** by the compressed descriptions of REQ-V13-PFX-02 (parameters, enums, limits unchanged) | REQ-V13-PFX-02 |
| spec-v1 context assembly (`_assemble_context`: verbatim tool results from the whole window) | **extended**: stale tool results are stubbed at request time, DB unchanged | REQ-V13-HST-01..05 |
| spec-v1 command set `/new /status /summary /model /reload_skills` | **extended** with `/stats` | REQ-V13-OBS-07 |
| spec-v1 `_execute_tool_calls(normalized, *, skills, runner, tools_used, fetcher, audit, on_tool)` | **extended** with keyword-only `conn`, `conv_id`, `turn_id` | REQ-V13-OBS-05 |
| spec-v1.1 `_Capture.snapshot() -> (bytes, truncated)` | **extended** to `(bytes, truncated, fed)` | REQ-V13-TOO-02 |
| spec-v1.1 startup cleanup (`_remove_sandbox_entry`) | **fixed**: the recovery chmod loop never follows symlinks | REQ-V13-CO-01 |
| spec-v1.2 mutation gate (31 mutations) | **extended** to ≥ 43 mutations, all killed | section 12 |
| README "Safety" wording (layer-2 refusal, reap, entries-eat-disk) | **fixed** | REQ-V13-CO-07 |

Everything else in spec-v0 … spec-v1.2 stands.

---

## 3. Preconditions (verify before writing any code)

1. **REQ-V13-PRE-01 (MUST)** Git: `main` at `1ecc35e`, clean tree. Gates 1–4
   and 6 green on the untouched tree (31/31 mutations killed).
2. **REQ-V13-PRE-02 (MUST)** Live environment: `.env` provisioned;
   `LMSTUDIO_BASE_URL` reachable and `GET /v1/models` lists `LMSTUDIO_MODEL`
   as loaded; `LMSTUDIO_CONTEXT_LENGTH` equals the context length the model is
   loaded with (the maintainer confirms; the bot cannot read it); Docker
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
   validated by `load_config` with the same error style as existing ones):
   - `LLM_PRICE_REF_MODEL` (empty) — an OpenRouter model id whose `/models`
     pricing is used as the **reference price** for LM Studio calls
     (section 6.3). Empty → LM Studio cost is `NULL` and the benchmark falls
     back to token-based comparison (section 13.3).
   - `LLM_PRICE_INPUT_USD_PER_MTOK`, `LLM_PRICE_OUTPUT_USD_PER_MTOK` (empty)
     — manual fallback prices when `/models` is unreachable; both or neither.
   - `EXEC_OUTPUT_DEFAULT_CHARS` (1500), range 200–4096 — inline window per
     stream for exec results (stage C).
   - `FETCH_INLINE_DEFAULT_CHARS` (5000), range 500–20000 — inline window for
     fetch results (stage C).
   - `HISTORY_TOOL_STUB` (`on`), `on|off` — stale-tool-result stubbing
     (stage C; `off` exists for A/B and for the rollback path only).
   - `LLM_SUMMARY_MODEL` (empty) — `<provider>:<model>` routing for the
     summary purpose (stage C, section 10.6).
   - `LLM_REASONING` (`auto`), `auto|on|off` — only if section 10.5 applies.
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
  llm/lmstudio.py             ✎ describe(); reasoning switch only if section 10.5 applies
  llm/openrouter.py           ✎ usage accounting request flag, cache_control, describe()
  llm/failover.py             ✎ describe() of the active client
  llm/pricing.py              ⊕ OpenRouter /models pricing lookup + cost formula
  devtools/bench.py           ⊕ benchmark harness: run / report / check
  devtools/bench_scenarios.py ⊕ the 12 frozen scenarios (Appendix C)
  devtools/dashboard.py       ⊕ static HTML dashboard generator
  devtools/mutation_check.py  ✎ --only exit code; ≥ 12 new mutations
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
  docs/reports/bench-baseline.md, audit-v1.3.md, bench-v1.3.md, report-v1.3.md, tg-post-v1.3.md ⊕
  docs/prompts/09-go-spec-v1.3.md, 10-v13-*.md … ⊕
  docs/llm-usage.md, docs/plan.md, README.md, AGENTS.md, .env.example ✎
  .gitignore                  ✎ `.bench/` (per-run bench directories, REQ-V13-BEN-03)
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
  advisory).
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
    attempt INTEGER NOT NULL,        -- 1-based HTTP attempt within the message
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
    cost_usd REAL, cost_basis TEXT   -- 'provider' | 'openrouter-list' | 'reference:<model>' | 'manual' | NULL
  );
  CREATE TABLE tool_calls (
    id INTEGER PRIMARY KEY,
    conv_id INTEGER NOT NULL REFERENCES conversations(id),
    turn_id INTEGER NOT NULL, tool_call_id TEXT NOT NULL, tool TEXT NOT NULL,
    ts TEXT NOT NULL,
    input_chars INTEGER NOT NULL,        -- len(arguments JSON)
    raw_output_chars INTEGER NOT NULL,   -- before compaction (== output_chars in stage A)
    output_chars INTEGER NOT NULL,       -- what the model was shown
    output_tokens_est INTEGER NOT NULL,  -- estimate_tokens(output)
    duration_ms INTEGER NOT NULL,
    outcome TEXT NOT NULL                -- 'ok' | 'error' | 'rejected' | 'budget'
  );
  ```

- **REQ-V13-OBS-04 (MUST)** `agent.run_agent` records **every**
  `llm.complete` call, including failed ones (`error_kind` set, token
  columns `NULL`, latency measured), via `storage.add_llm_call(...)`.
  `provider`/`model` come from the client actually used: `LLMClient` gains
  a read-only `describe() -> tuple[str, str]` (provider, model);
  `FailoverLLMClient.describe()` reports the client that served the last call.
  `summarize_conversation` records with `purpose='summary'`.
- **REQ-V13-OBS-05 (MUST)** `agent._execute_tool_calls` records every tool
  call via `storage.add_tool_call(...)` — executed, rejected (excess),
  budget-refused — with the outcome, timing (`time.monotonic`), sizes. Its
  signature gains three keyword-only parameters, `conn`, `conv_id` and
  `turn_id` (the value `run_agent` already mints via
  `storage.next_turn_id(conn, conv_id)` for `normalize_tool_calls`); the
  amendment is listed in section 2.
- **REQ-V13-OBS-06 (MUST)** One structured INFO log line per LLM call and
  per tool call, JSON on one line, prefixed `llm_call ` / `tool_call `,
  containing the row's numeric/enum fields and never content, arguments,
  URLs or secrets (goes through `config.redact` anyway). Test: the log line
  parses as JSON and has no `content` key.
- **REQ-V13-OBS-07 (MUST)** New command **`/stats`** (owner-only like the
  others): plain text ≤ 3500 chars, fixed layout (tests assert labels):

  ```
  Stats (this conversation | all time)
  LLM calls: 7 | 143 (errors 0 | 2)
  Tokens in: 21430 | 402118 (cached: n/a | n/a, reasoning: 0 | 0)
  Tokens out: 1204 | 38001
  Est. cost: $0.0123 | $0.4110 (basis: reference:<model>)
  Avg prompt/call: 3061 | 2813; re-sent share: 71% | 68%
  Top tools by output tokens (all time): exec 1812 (78%), fetch 401 (17%), load_skill 110 (5%)
  Last turn: r1 in 2980 out 88 → exec 412 ms; r2 in 3512 out 210 (final)
  ```

  `n/a` where the provider reports nothing; `Est. cost: n/a (no pricing)`
  when no basis exists. `/status` gains one line: `Tokens this conversation:
  in N / out M`.
- **REQ-V13-OBS-08 (MUST)** `metrics.py` (stdlib): pure functions over rows —
  `conversation_stats(conn, conv_id)`, `global_stats(conn)`,
  `resent_tokens(calls) -> (resent, new)`, `top_tools(conn, limit)`,
  `turn_timeline(conn, conv_id, turn_id)`, `context_growth(calls)`. The
  re-sent metric: for calls of one conversation ordered by `id`,
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
  per-million floats); `cost_usd(usage, price) -> float`:
  `(prompt − cached) × in + cached × cached_in + completion × out`, with
  `cached` treated as 0 when `NULL`, and `cached_in = in` when the provider
  publishes no cache price.
- **REQ-V13-PRC-02 (MUST)** Cost basis per call: OpenRouter call with
  `provider_cost_usd` present → `basis='provider'`, that value; else the
  fetched price of the call's model → `basis='openrouter-list'`; LM Studio
  call with `LLM_PRICE_REF_MODEL` set → the fetched price of the reference
  model, `basis='reference:<model>'`; manual env prices →
  `basis='manual'`; otherwise `NULL`. Prices are fetched **once** at bot
  startup and once per benchmark run (stored under `bot_state` key
  `pricing_json` with `fetched_at`; a failed fetch logs a warning and keeps
  the previous value or `NULL` — never blocks startup).
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
    (the provider reported no usage — measurement impossible, stop).
  - `report --baseline A.json [--candidate B.json] [--out PATH] [--gate]` →
    markdown (7.8); with `--gate` exits 1 when the section-13.3 verdict is
    FAIL, 2 when the skip sets differ between the two files.
  - `check <json>` → validates against the schema of 7.4; exit 0/1.
- **REQ-V13-BEN-02 (MUST)** `--provider openrouter` **refuses to run** unless
  `--max-cost-usd` is given, and aborts (exit 4, JSON written with what was
  measured) as soon as the cumulative cost (provider-reported, else
  list-priced) exceeds the cap. `LLM_FAILOVER` is forced to `off` for every
  bench run so the measured provider is the configured one.

### 7.2 Run mechanics

- **REQ-V13-BEN-03 (MUST)** Each *run* (scenario × repeat) gets a fresh
  directory `<PROJECT_ROOT>/.bench/<tag>/<scenario>-<repeat>/` holding three
  **siblings**: `sandbox/` (`EXEC_WORKDIR`), `bot.db` (`DB_PATH`) and
  `audit.jsonl` (`AUDIT_LOG_PATH`). This layout is forced by
  `config._check_sandbox_placement`: `EXEC_WORKDIR` must be a strict
  descendant of `PROJECT_ROOT` and must contain neither the DB, the audit log
  nor `.env` — a `tempfile` directory would be rejected. `.bench/` is added
  to `.gitignore` in C1 and wiped at the start of every `run`. Config comes
  from `.env` via `load_config` with these three paths and `LLM_FAILOVER=off`
  overridden. The harness then does what `main()` does, in the same order:
  `docker_ok` probe, `bot._startup_docker_wiring(cfg, docker_ok)` once per
  run (sandbox cleanup, allowlist check, orphan reap, timeout wrapper,
  empty `resolv.conf`) and a runner built exactly like `main()`'s
  `functools.partial(tools.run_command_docker, workdir=…, image=…,
  docker_ok=…, sandbox_max_bytes=…, wrap_timeout=…, empty_resolv=…)`; the
  real `build_llm_client(cfg, client=…, override=…)` and the real fetcher.
  Telegram is replaced by an in-process recorder object (same duck type as
  `_SelftestTelegram`) — the harness never constructs `TelegramClient` (test
  asserts by monkeypatching the constructor to raise). The run directory is
  removed after its rows were copied into the result.
- **REQ-V13-BEN-04 (MUST)** Turns are driven through `bot.process_update`
  with synthetic updates whose `from.id`/`chat.id` is the first id of
  `ALLOWED_TG_IDS` (never written to the output). Turns of one scenario run
  sequentially in one conversation; `/new` is a turn like any other.
- **REQ-V13-BEN-05 (MUST)** Wall-clock cap per run: 600 s (`--timeout-s`);
  exceeding it marks the run `success=false, failure='timeout'` and the
  harness continues. `should_stop`/signal handling: SIGINT stops after the
  current run and still writes the JSON.
- **REQ-V13-BEN-06 (MUST)** Prefix calibration: once per `run` invocation,
  before the scenarios, one call with the system prompt (skills loaded as
  the bot would), the tool catalog and the user message `ping`,
  `max_tokens=1`, made directly through the LLM client outside `run_agent`,
  so it produces no `llm_calls` row (REQ-V13-OBS-04 covers `run_agent` and
  `summarize_conversation` only); its `LLMResponse.usage.prompt_tokens` is
  stored as `meta.prefix_tokens` and excluded from all scenario totals.
- **REQ-V13-BEN-07 (MUST)** DI for tests: the core is
  `run_bench(scenarios, *, cfg, llm_factory, runner_factory, fetcher,
  telegram_factory, repeats, timeout_s, clock, sleep) -> BenchResult`;
  `main()` only wires real objects. `tests/test_bench.py` runs it with
  `FakeLLM`, `RecordingRunner`, `FakeFetcher` and asserts the JSON shape,
  the checks, the skip logic, the cost cap and the never-Telegram rule.

### 7.3 Scenarios and checks

- **REQ-V13-BEN-08 (MUST)** `devtools/bench_scenarios.py` holds `SCENARIOS:
  list[Scenario]` — exactly the 12 of Appendix C, ids `S01`…`S12`, each
  `Scenario(id, title, turns: list[str], checks: list[Check],
  network: bool)`. Check kinds: `answer_regex(pattern, turn=-1)` (`re.I`,
  `re.S`), `answer_not_regex`, `answer_max_chars(n)`, `tool_used(name)`,
  `no_tools`, `json_keys({...})` (first `{…}` object in the answer parsed;
  values compared), `exit_code_seen(nonzero=True)`, `summary_exists`
  (a `summaries` row with non-empty goal after `/new`). Success = all
  checks pass. `turn=-1` = the last non-command turn unless given.
- **REQ-V13-BEN-09 (MUST)** Scenario texts are Russian (the user talks to
  the bot in Russian; the system prompt is English). Scenarios contain no
  secrets, no course material, no personal data.

### 7.4 Output schema (`bench_schema: 1`)

```
{ "bench_schema": 1,
  "meta": { "tag", "started_at", "finished_at", "git_commit", "provider", "model",
            "context_length", "repeats", "timeout_s", "prefix_tokens",
            "pricing": {"basis", "model", "input_usd_per_mtok", "output_usd_per_mtok",
                        "cached_input_usd_per_mtok", "fetched_at"} | null,
            "skipped_scenarios": ["S08"],
            "env_flags": {"HISTORY_TOOL_STUB", "EXEC_OUTPUT_DEFAULT_CHARS", "FETCH_INLINE_DEFAULT_CHARS",
                          "LLM_REASONING", "LLM_SUMMARY_MODEL", "LLM_FAILOVER", "LLM_MAX_TOKENS"},
            "constants": {"CONTEXT_WINDOW_MESSAGES", "EXEC_MAX_STREAM_BYTES", "FETCH_MAX_BYTES"} },
  "runs": [ { "scenario": "S02", "repeat": 1, "success": true, "failure": null,
              "checks": [{"kind": "answer_regex", "ok": true, "detail": "..."}],
              "answers": ["<redacted final answer per turn>"],
              "llm_calls": [ <llm_calls row as object, minus conv_id> ],
              "tool_calls": [ <tool_calls row as object, minus conv_id> ],
              "totals": {"calls", "prompt_tokens", "completion_tokens", "cached_tokens",
                         "reasoning_tokens", "tool_calls", "tool_output_tokens_est",
                         "latency_ms", "cost_usd", "resent_tokens", "new_tokens",
                         "wall_ms"} } ],
  "summary": { "runs", "skipped", "successes", "success_rate",
               "per_scenario": { "S02": {"success": 3, "of": 3, "median": {<totals keys>}} },
               "totals": {<sums over non-skipped runs>},
               "avg_per_task": {"tokens", "rounds", "tool_calls", "latency_ms"},
               "cost_per_success", "tokens_per_success", "resent_share",
               "cache_hit_rate", "top_tools": [...], "top_turn": {...},
               "context_growth": {"system":…, "tools":…, "user":…, "assistant":…, "tool":…} } }
```

- **REQ-V13-BEN-10 (MUST)** `answers` pass through `config.redact` with the
  live config's secrets before being written; a synthetic-canary test proves
  a secret in an answer never reaches the JSON. `meta.env_flags` holds the
  keys listed above (effective values, defaults included) and nothing else —
  no other environment key is ever serialized (test). `LLM_REASONING` is
  present only when section 10.5 applies (REQ-V13-RSN-01); otherwise the
  allowlist has six keys and the test asserts six.

### 7.5 Skipping

- **REQ-V13-BEN-11 (MUST)** Before the scenarios, a preflight resolves and
  HEADs `https://wttr.in/` (5 s timeout). Failure → every `network: true`
  scenario is `skipped` (all repeats), listed in `meta.skipped_scenarios`,
  excluded from every denominator. `report` with two files whose skip sets
  differ exits 2 with a one-line reason: the comparison would be unfair.

### 7.6 Frozen scenarios

- **REQ-V13-BEN-12 (MUST)** From C2 onward `bench_scenarios.py` is frozen
  (REQ-V13-EC-07). If the baseline shows a scenario whose checks are
  *miscalibrated* (fails in all 3 repeats while the answer is visibly
  correct), the fix happens **before** C2, is documented in
  `bench-baseline.md`, and the baseline is re-run (counts against 1.4).

### 7.7 Console summary (what the main context reads)

- **REQ-V13-BEN-13 (MUST)** `run` prints at most 40 lines: header (tag,
  provider, model, repeats, prefix_tokens, pricing basis), one line per
  scenario (`S02 arith  3/3  prompt 8.9k  out 0.4k  cost $0.0123  wall 41s`),
  totals, success rate, cost/success, tokens/success, re-sent share, skipped
  list, output path. Nothing else.

### 7.8 Report markdown

- **REQ-V13-BEN-14 (MUST)** `report` renders: meta table; per-scenario table
  (success, median prompt/out/cached/reasoning tokens, median latency,
  median cost) — with `--candidate`, the same columns for both plus
  absolute and relative deltas; totals with deltas; the four audit answers
  computed from the data (most expensive tool by output tokens; most
  expensive turn/round; fastest-growing context category; re-sent share);
  prefix share (`prefix_tokens × calls / Σprompt`); cache hit rate or `n/a`;
  and, with `--candidate`, the section-13.3 verdict block.

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
  tools called — for the median-cost run of every scenario), `#compare`
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
  --max-cost-usd 0.50` — proves the usage/cost/cached parsing against a
  provider that reports them (or documents that it does not).
- **REQ-V13-AUD-02 (MUST)** Baseline sanity: success rate < 70 % → stop, look
  at the failing checks (7.6), decide, document; do not proceed to
  optimizations on a benchmark that mostly fails.
- **REQ-V13-AUD-03 (MUST)** `docs/reports/bench-baseline.md` = `report
  --baseline baseline.json` output plus the OpenRouter smoke table.
  `docs/assets/dashboard-baseline.html` = `dashboard.py baseline.json`.
- **REQ-V13-AUD-04 (MUST)** `docs/reports/audit-v1.3.md`, written by a
  subagent from `bench-baseline.md` (not from the JSON), answering the
  assignment's audit questions with the computed numbers: the most expensive
  tool and turn; the fastest-growing context category; re-sent tokens (share
  and absolute, with the "100k input → 27k new" style example from the
  data); prefix share; reasoning share; per-scenario token sinks; then a
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
  int, error_context: bool = False) -> str`, deterministic:
  1. strip ANSI escape sequences;
  2. collapse runs of ≥ 3 identical consecutive lines into one line followed
     by ` [×N]`;
  3. if `len(text) ≤ max_chars` return it; otherwise keep the first 40 % of
     the budget (whole lines) and the last 60 % (whole lines) joined by a
     marker line `[… N chars / M lines omitted …]`;
  4. with `error_context=True`, if the last line matching
     `(?i)\b(error|traceback|exception|failed|fatal)\b` would fall inside
     the omitted region, the tail window starts 20 lines before that line
     (the head shrinks accordingly; the budget is respected).
  Redaction happens **before** compaction (existing v1.1 order); after any
  cut, `strip_secret_fragment` runs on the cut boundaries so a partial
  secret never survives (test with a synthetic canary straddling a cut).
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
  `(bytes, truncated, fed)`. The window operates on the captured head only
  (first `4096 + headroom` bytes): output beyond the capture cap is gone
  before compaction, which `truncated` tells the model. The schema's
  `max_output_chars` description tells the model the default and the
  maximum.
- **REQ-V13-TOO-03 (MUST)** `tool_calls.raw_output_chars` = envelope length
  before compaction; `output_chars` = after. The audit trail (JSONL) keeps
  the existing fields; it does not need the raw text.
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
  through the same ownership/permission path the sandbox uses for its own
  files, subject to the quota (fail-closed scan of v1.2: if the write would
  exceed `EXEC_SANDBOX_MAX_BYTES`, the file is not written and the envelope
  says `"saved_to": null, "save_error": "sandbox quota"`). The directory name
  is fixed; the file name is derived only from the hash — no path component
  comes from the model.
- **REQ-V13-TOO-07 (MUST)** Fetch envelope: `{"url", "status",
  "content_type", "chars_total", "returned_chars", "truncated", "saved_to":
  "fetch/<hash>.txt" | null, "text": "<first max_chars of the text>"}` with
  `max_chars` = tool argument (500–20000) or `FETCH_INLINE_DEFAULT_CHARS`.
  The tool description tells the model: to search the rest, run
  `exec(["grep", "-n", "<pattern>", "fetch/<hash>.txt"])` (fetch once,
  process locally — lecture 11).
- **REQ-V13-TOO-08 (MUST)** Startup cleanup (`_clean_sandbox_at_start`)
  treats `fetch/` like any other sandbox entry (removed; one new test).
  `/new` does not touch the sandbox today and this spec does not change
  that; the quota (REQ-V13-TOO-06) bounds what `fetch/` can accumulate.
- **REQ-V13-TOO-09 (MUST)** Redaction order for fetch is unchanged (redact →
  cut → strip fragment); the saved file contains redacted text only. Test
  with a synthetic canary in a fixture HTML body.
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
  call of a conversation**: the `Current date and time` line leaves the
  system prompt; at request-assembly time the string `(now: YYYY-MM-DD
  HH:MM UTC)` is appended as the last line of the **most recent user
  message** (stored content unchanged). Recent goals (`GOALS_BLOCK`) stay in
  the system prompt (they change only between conversations). Test: two
  `run_agent` invocations with different `now` produce identical system
  messages and identical `tools` JSON; the user message carries the `now`.
- **REQ-V13-CCH-02 (MUST)** Message and tool ordering is stable across rounds
  (test: the request of round *n* is a prefix-extension of round *n−1*'s
  request within one invocation, comparing serialized messages).
- **REQ-V13-CCH-03 (SHOULD)** OpenRouter: when `OPENROUTER_MODEL` starts with
  `anthropic/`, the system message is sent in the content-blocks form with
  `cache_control: {"type": "ephemeral"}` on the system block; the OpenRouter
  request also sets `usage: {"include": true}` (REQ-V13-PRE-05 verification
  of both). Effect measured by `cached_tokens` in the smoke run; for other
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
  `reasoning_tokens > 0` or `reasoning_chars > 0` in **any** call, O5 is
  implemented; otherwise it is recorded as *not applicable — no reasoning
  observed* in `audit-v1.3.md` and the report, and no code is written for
  it (no speculative feature).
- **REQ-V13-RSN-02 (MUST, when applicable)** `LLM_REASONING=auto|on|off`:
  `auto` disables thinking for **tool rounds** (rounds where tools are
  exposed) and leaves the model default for the final round; `off` disables
  everywhere; `on` never disables. The mechanism is the one the model's
  documentation specifies (e.g. `chat_template_kwargs: {"enable_thinking":
  false}` or a `/no_think` soft switch appended to the last user message at
  request time), verified per REQ-V13-PRE-05 and **proven** by
  `reasoning_tokens = 0`/`reasoning_chars = 0` on those rounds in the
  optimized run. If no documented mechanism works, O5 is reported as
  attempted-and-not-effective with the evidence, and `LLM_REASONING` is
  removed again (not left as a dead knob).

### 10.6 Model routing by purpose (lecture 7) — O6, configuration only

The maintainer's constraint: only one model fits the GPU box; switching
models per call means load/unload (tens of seconds) and is not viable.
Therefore routing is implemented as configuration that the maintainer can
enable when a second model or a cheap cloud model is available, and it is
**not** enabled during the v1.3 benchmark.

- **REQ-V13-RTE-01 (MUST)** `LLM_SUMMARY_MODEL=<provider>:<model>` routes
  `summarize_conversation` to that client (built with the same
  `httpx.Client`, `LLM_FAILOVER` semantics unchanged for the main client,
  none for the summary client). Validation: provider ∈ {lmstudio,
  openrouter} and configured, else `ConfigError`. `llm_calls.model` shows the
  routed model. Tests with fakes: the summary goes to the routed client; the
  agent loop does not.
- **REQ-V13-RTE-02 (MUST)** The report has a "Routing" paragraph: what is
  implemented, why it was not benchmarked (memory constraint), how to enable
  it, and the expected saving computed from baseline summary tokens ×
  (reference price − cheap-model price).

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
secrets only, and never spawn Docker or real processes.

### 11.1 `tests/test_v13_carryover.py` — section 5
One test per REQ-V13-CO-01…06 (CO-05 = three tests).

### 11.2 `tests/test_observability.py` — sections 6.1–6.2
Usage parsing (full, partial, absent, non-integer); `<think>` stripping and
`reasoning_content`; schema v3 fresh + migration from a v2 fixture; one
`llm_calls` row per `complete` call including a failed call; `tool_calls`
rows for executed/rejected/budget outcomes; `describe()` on all three
clients; log lines are JSON without content; `/stats` layout and `n/a`
branches; `/status` token line; `metrics.resent_tokens` on a hand-computed
sequence (including a window drop → clamped at 0); `context_growth`.

### 11.3 `tests/test_pricing.py` — section 6.3
`/models` parsing from a fixture (mock transport), per-token → per-million,
cost formula with/without cached price, basis selection for the four cases,
startup fetch failure is non-fatal, `bot_state` persistence.

### 11.4 `tests/test_bench.py`, `tests/test_dashboard.py` — sections 7–8
Scenario schema validation (12 scenarios, unique ids, checks well-formed);
each check kind against crafted answers; `run_bench` with fakes produces a
schema-valid JSON (`check` passes); skip logic with a failing preflight;
`report` deltas on the two fixtures; `--gate` exit codes (pass / fail /
skip-set mismatch → 2); OpenRouter refusal without cap and abort over cap;
Telegram constructor never called; synthetic canary never in JSON; console
summary ≤ 40 lines; dashboard sections/no external resources/numbers.

### 11.5 Stage C files — section 10
`tests/test_tool_output.py`: REQ-V13-TOO-01…10 (byte-exact fixtures;
canary across a cut; quota-refused save; binary type refused; `fetch/` hash
name only). `tests/test_history_stub.py`: HST-01…05 (request has stubs for
old turns, verbatim for the current one; latest skill kept; DB unchanged;
`off` equals the un-stubbed assembly, tool messages verbatim; budget on
stubs).
`tests/test_prefix.py`: CCH-01…03, PFX-01…03 (size limits, mandatory
statements present, schema equality modulo descriptions, `now` in the user
message, Anthropic cache_control shape). `tests/test_routing.py`: RTE-01
(and RSN-02 when applicable).

### 11.6 Existing tests
Amend only what the changed system prompt and tool schemas break
(assertions on exact prompt text/tool description text) and what the
`<think>` stripping affects; list every amended test in the report.

---

## 12. Mutation gate

`devtools/mutation_check.py` gains **≥ 12** mutations (total ≥ 43), all
killed. Tagged A (stage A) or C (stage C):

| id | tag | mutation | killed by |
|---|---|---|---|
| v13-usage-parse-none | A | `parse_response` ignores `usage` | 11.2 |
| v13-cached-tokens-dropped | A | `cached_tokens` always `None` | 11.2 |
| v13-think-not-stripped | A | `<think>` blocks left in content | 11.2 |
| v13-llm-call-not-recorded-on-error | A | failed calls skip `add_llm_call` | 11.2 |
| v13-resent-formula | A | `new_i = prompt_i` (re-sent always 0) | 11.2 |
| v13-cost-drops-output | A | cost formula omits completion tokens | 11.3 |
| v13-bench-gate-threshold | A | `--gate` threshold 30 → 0 | 11.4 |
| v13-bench-skipset-ignored | A | report ignores differing skip sets | 11.4 |
| v13-openrouter-cap-ignored | A | cap check removed | 11.4 |
| v13-symlink-chmod | A | `islink` skip in the `failed_paths` chmod loop removed | 11.1 |
| v13-only-typo-exit0 | A | `--only` unknown id exits 0 | 11.1 |
| v13-compact-keeps-head-only | C | tail window dropped | 11.5 |
| v13-dedup-threshold | C | collapse runs of ≥ 2 instead of ≥ 3 | 11.5 |
| v13-fragment-after-cut | C | `strip_secret_fragment` not applied after the cut | 11.5 |
| v13-fetch-script-kept | C | `script` subtree text kept | 11.5 |
| v13-fetch-save-path | C | file name uses the URL path instead of the hash | 11.5 |
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
Gate 5 fully green (REQ-V13-EC-10).

### 13.2 Benchmark steps (blocking, not permanent gates)

| step | when | command |
|---|---|---|
| B1 | after C1 gates | `bench.py run --tag baseline --repeats 3` |
| B2 | after B1 | `bench.py run --provider openrouter --only S02 --repeats 1 --tag openrouter-smoke --max-cost-usd 0.50` |
| D1 | after C3 gates | `bench.py run --tag optimized --repeats 3` |
| D2 | after D1 | `bench.py report --baseline docs/assets/bench/baseline.json --candidate docs/assets/bench/optimized.json --gate --out docs/reports/bench-v1.3.md` |

Both full runs use the **same** `LMSTUDIO_MODEL`, context length and
`.env` (the harness records them; `report` refuses (exit 2) when
`meta.model` or `meta.context_length` differ).

### 13.3 Verdict

- Primary metric: **cost per successful task** =
  `Σ cost_usd / successes` (reference-priced for LM Studio). Cost gate:
  `candidate ≤ 0.70 × baseline`.
- Quality gate, stated at the benchmark's resolution: with 33–36 runs one
  flipped run is already 2.8–3.0 pp, so the assignment's "≤ 2 pp" cannot be
  measured literally. `--gate` implements: `successes(candidate) ≥
  successes(baseline) − 1` **and** no scenario loses more than one repeat
  (3/3 → 2/3 tolerated, 3/3 → 1/3 not). Any regressed run is investigated
  and documented in the report. The report prints the success-rate delta in
  pp next to the assignment's 2 pp headline, with this resolution note.
- Verdict PASS = cost gate and quality gate both pass. `successes == 0` in
  either file → FAIL, exit 1, reason `no successful runs` (never a division
  by zero); the AUD-02 sanity floor (< 70 % → stop and look) applies to D1
  as well as to B1.
- When no pricing basis exists (`cost_usd` all `NULL`): the primary metric
  is **tokens per successful task** (`prompt + completion`), same
  thresholds; the report says so.
- Secondary (reported, not gated): prompt tokens, completion tokens,
  re-sent share, prefix tokens, median latency per call, tool output tokens,
  per-scenario deltas, cache hit rate (OpenRouter smoke only).

### 13.4 Target miss

If D2 says FAIL, apply — in this order, one per re-run, at most the two
re-runs of 1.4 — the levers below, each a config-default change with a
test update, and document each attempt: (1) `EXEC_OUTPUT_DEFAULT_CHARS`
1500 → 1000; (2) `FETCH_INLINE_DEFAULT_CHARS` 5000 → 3000; (3)
`CONTEXT_WINDOW_MESSAGES` 30 → 20. Still FAIL → C4 is still produced, with
the honest FAIL verdict and the analysis of why (the assignment grades the
audit and the method, not only the number).

### 13.5 Review

Two clean-context reviews by the `code-reviewer` subagent (prompt logged):
after stage A (before B1 — a harness defect found later costs a re-run) and
after stage C (before D1). Findings fixed in the same stage's commit.

---

## 14. Deliverables and documentation

- **REQ-V13-RPT-01 (MUST)** `docs/reports/report-v1.3.md` per
  `standards/reporting.md`: gate table per commit; both benchmark summaries;
  the verdict; per-optimization measured effect (a table: optimization →
  metric → before → after → delta; O3 latency-only; O5 applicable or not;
  O6 not benchmarked, why); amended tests list; review findings and fixes;
  fix-loop iterations used; LM Studio model and context length; pricing
  basis and date; skipped scenarios; executor token usage (prompts,
  tokens, cost).
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
  row (REQ-V13-CO-07).

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
| TA2 | A | observability core: OBS-01…09 (`llm/base.py`, `llm/*.py` `describe()`, `storage.py` v3, `agent.py` recording, `metrics.py`, `bot.py` `/stats` + `/status` line, `tests/test_observability.py`) | schema, row counts, test count |
| TA3 | A | pricing: PRC-01…03 (`llm/pricing.py`, `config.py` env vars, `bot.py` startup fetch, `tests/test_pricing.py`, `.env.example`) — includes the context7 verification of `/models` and usage-accounting field names | verified field names + doc citation |
| TA4 | A | bench harness: BEN-01…14 (`devtools/bench.py`, `devtools/bench_scenarios.py`, `tests/test_bench.py`, `tests/fixtures/bench/`) | CLI summary sample, test count |
| TA5 | A | dashboard: DSH-01…02 (`devtools/dashboard.py`, `tests/test_dashboard.py`) | sections implemented |
| TA6 | A | mutations tagged A (`devtools/mutation_check.py`) | ids added, all killed |
| TA7 | A | review (code-reviewer, clean context) of stage A | findings list |
| TA8 | A | fix findings of TA7 | what changed |
| — | A | main: gates 1–6, commit **C1** | — |
| — | B | main: B1, B2 (background), `report`, `dashboard.py` | 40-line summaries |
| TB1 | B | audit writer: AUD-04 from `bench-baseline.md` | the audit file |
| — | B | main: commit **C2**, tag `v1.3-baseline` | — |
| TC1 | C | O1: TOO-01…10 (`tools.py`, `config.py`, `tests/test_tool_output.py`) | fixtures, sizes before/after on fixtures |
| TC2 | C | O2: HST-01…05 (`agent.py` `_assemble_context`, `config.py` `HISTORY_TOOL_STUB`, `storage.py` reader if needed, `tests/test_history_stub.py`) | payload example sizes |
| TC3 | C | O3 + O4: CCH-01…04, PFX-01…03 (`agent.py` prompt/prefix, `tools.py` `tool_specs` descriptions, `llm/openrouter.py`, `tests/test_prefix.py`, amended existing tests) | char counts before/after |
| TC4 | C | O5 if RSN-01 applies (`agent.py`, `llm/lmstudio.py`, `config.py`, tests) — includes the context7 verification | mechanism + evidence plan |
| TC5 | C | O6: RTE-01 (`llm/__init__.py`, `config.py`, `agent.py` summary path, `tests/test_routing.py`) | wiring summary |
| TC6 | C | mutations tagged C | ids added, all killed |
| TC7 | C | review (code-reviewer) of stage C | findings |
| TC8 | C | fix findings of TC7 | what changed |
| TC9 | C | docs: RPT-03, RPT-04 (README, AGENTS.md, `.env.example`) | sections touched |
| — | C | main: gates 1–6, commit **C3** | — |
| — | D | main: D1 (background), D2, `dashboard.py --compare`, optional 13.4 loop | summaries + verdict |
| TD1 | D | report writer: RPT-01, RPT-05, RPT-06, RPT-07 from the two `bench-*.md` files, gate outputs and `docs/reports/report-v1*.md` + `docs/llm-usage.md` (never from JSON) | the report |
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
  cherry-picking repeats: all raw runs are committed.
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
  Scenario: a failed HTTP attempt is recorded
    Given a FakeLLM that raises LLMError(kind='http', retryable=True) once, then answers
    When run_agent handles one user message
    Then llm_calls has two rows, the first with error_kind 'http' and NULL token columns

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
    Given config with OPENROUTER_API_KEY=SYNTHETIC-CANARY-1 (load_env_file=False)
    And a FakeLLM whose final answer contains that value
    When run_bench writes its JSON
    Then the JSON text does not contain "SYNTHETIC-CANARY-1"

Feature: report gate
  Scenario: skip sets differ
    Given baseline skipped S08 and candidate skipped nothing
    When bench.py report --gate runs
    Then it exits 2
  Scenario: −30 % reached with equal success
    Given baseline cost_per_success 0.100 and candidate 0.065, success rates equal
    When bench.py report --gate runs
    Then the verdict is PASS and exit code 0

Feature: exec output compaction
  Scenario: 200 identical INFO lines then a traceback
    Given exec stdout of 200 lines "INFO heartbeat ok" (3600 B, under the 4096 B capture cap) and a ZeroDivisionError traceback on stderr, exit code 1
    When the envelope is built with max_output_chars 1500
    Then stdout contains "INFO heartbeat ok [×200]"
    And stderr contains "ZeroDivisionError" and no "[… " marker between "Traceback" and the last line
  Scenario: a secret straddles the cut
    Given redaction produced text where a canary would be split by the head/tail cut
    When compact_output runs
    Then neither fragment of the canary is present

Feature: fetch saves text once
  Scenario: HTML page
    Given a FakeFetcher returning text/html with <script>, <style> and a <title>
    When fetch runs with max_chars 500
    Then the envelope text starts with the title, contains no script text
    And saved_to is "fetch/<16 hex>.txt" and that file exists in the sandbox
  Scenario: quota refuses the save
    Given the sandbox usage already at EXEC_SANDBOX_MAX_BYTES
    When fetch runs
    Then saved_to is null and save_error is "sandbox quota" and the inline text is still returned

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
