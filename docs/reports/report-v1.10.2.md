# tg-agent-bot v1.10.2 — report skeleton (T0)

Closes the prompt gap gate 8 of v1.10.1 exposed, makes the gate-8 verdict
report every violated clause and every tool call, widens two
adjacency-blind marker families with fixture proof, and ships the
paperwork two stopped runs (v1.10.0, v1.10.1) never reached. Spec:
`docs/spec/spec-v1.10.2.md`. `<base>` = `ccab5d7` (the commit before the
five spec-authoring/handoff commits; `git diff --stat ccab5d7..HEAD` at T0
touches only `docs/`, so every `file:line` the spec pins holds unchanged).
Spec `sha256`:
`eb97888030a9e3ac3679d0a06c348c61efa66b53007b49430a8720c03ca72024`.

This file is filled progressively: T0 (this skeleton), T1 (PRM-02's
before/after table), T2 (dataset `sha256`s), T5 (the mutation/gate-6
record and the one live gate-8 run and its tables), T6 (version bump,
provisional report), T7 (final evidence-only commit). Sections not yet
reached read "not reached: T\<n\>".

## T0 — preflight

`<base>` = `ccab5d7`. Spec `sha256` as above. Test-collection floor
re-measured: `uv run --locked pytest --collect-only -q -o addopts="" |
grep -c '::'` = **2035** (2034 passed + 1 skipped, matches
`report-v1.10.1.md:608-609`). `len(MUTATIONS) == 133`. Last prompt at
`ccab5d7`: **211** (`211-v1102-spec-authoring.md`); this run's own prompts
start at 212. Last `docs/llm-usage.md` row at `ccab5d7`: **123**
(spec-v1.10.2 authoring itself; this run's rows start at 124, per the
spec's own header — the T0 acceptance table's "last usage row 122" is
stale authoring-time text, superseded by the header's "continues at row
124").

### Stage 0 — seven checks, in order (checks 1, 2 and 7 offline, against the
already-synced locked environment)

1. **Configuration check (CFG-01) + export proof (EC-04).** `uv run
   --offline --locked python -c` over `load_config()`:
   `llm_provider="openrouter"`, `llm_judge_model="openrouter:openai/gpt-4.1"`,
   `openrouter_model="openai/gpt-4.1-mini"` — judge distinct from chat
   model. `cfg.db_path` ends `data/run-v1102.db` (asserted). `bool
   (openrouter_api_key) = True`. Export proof:
   `LLM_JUDGE_MODEL=openrouter:openai/gpt-4.1-mini uv run --offline
   --locked python -c '...load_config().llm_judge_model'` printed
   `openrouter:openai/gpt-4.1-mini` (the exported value, not `.env`'s).
   PASS.
2. **Storage preflight (EC-04 precondition 3), offline, before any network
   call.** Opened `cfg.db_path` (`data/run-v1102.db`, already present —
   set by the operator ahead of `go`, schema-initialised, no documents)
   via `storage.connect`, `storage.init_schema(conn, embedding_dim=1536,
   embedding_model="openai/text-embedding-3-small")`, then
   `storage.document_count_all(conn) = 0` and `SELECT COUNT(*) FROM
   chunks` `= 0`; `conversations`/`messages`/`llm_calls`/`tool_calls` also
   `0`. Printed `db_empty=True`. PASS.
3. **Model listings.** `GET https://openrouter.ai/api/v1/models` lists
   `openai/gpt-4.1-mini`; authenticated `GET
   https://openrouter.ai/api/v1/embeddings/models` lists
   `openai/text-embedding-3-small`. Both present. PASS.
4. **One timed plain chat turn** on the production route. Question «Ответь
   одним словом: столица Нидерландов?», elapsed **2.932s** (well under
   `cfg.llm_timeout_s`); no `LLMError`. `describe() = ('openrouter',
   'openai/gpt-4.1-mini')`. PASS.
5. **One authenticated embeddings call.** `POST
   https://openrouter.ai/api/v1/embeddings` with
   `model=openai/text-embedding-3-small`, `input=["проверка"]`: status
   200, 1536 floats returned (`== cfg.embedding_dim`). PASS.
6. **One strict-schema judge call**, the two labelled spec-block fences
   (`judge-protocol-1`, `judge-protocol-2`, copied verbatim from
   `spec-v1.10.0.md` §7/§8, already pinned source-to-source by
   `T-V1100-JDG-08`) on the fixed sample. Parsed reply: `{"politeness": 1,
   "accuracy": 1, "conciseness": 1, "reason": "..."}`. `describe()` pairs
   as in check 1, unequal. No fallback needed (EC-01 disallows it this
   release regardless). PASS.
7. **`uv lock --offline` no-op** (`Resolved 25 packages`, no lockfile
   change) and `git diff --stat ccab5d7 -- pyproject.toml uv.lock` empty.
   PASS.

No Stage 0 blocker. The run proceeds past T0.

### Gates 1-5 and 7 on the unchanged tree (gates 6 and 8 not run)

| # | Gate | Exit | Wall / detail |
| --- | --- | --- | --- |
| 1 | `uv sync --locked` | 0 | fast — 25 packages resolved, 23 checked |
| 2 | `ruff check .` | 0 | all checks passed |
| 3 | `pytest` | 0 | 19.04s, 2034 passed / 1 skipped (matches re-measured floor) |
| 4 | `bot.py --selftest` | 0 | `selftest: OK` |
| 5 | `bot.py --selftest-live` | 0 | `live: OK config / OK db / OK docker (29.8.0) / OK telegram / SKIP lmstudio (no route uses it) / OK embeddings / OK openrouter` — all green, no v1.10.1-style expected red this release (GATE-01) |
| 6 | `mutation_check.py` | n/a | not run at T0 (GATE-01) |
| 7 | `rag_eval.py` | 0 | `hybrid: recall@5=1.000 mrr=1.000`; `hybrid+rerank: recall@5=1.000 mrr=0.900`; advisory conversation-aware smoke (TOOL-06, context-proof) both **fail**, non-blocking per NG-07 (unchanged since v1.10.1 T4) — `gate-7: PASS` |
| 8 | `agent_eval.py` | n/a | not run at T0 (GATE-01) |

`doctor`: `[PASS] doctor: all tools at pin, hooks installed`. Hooks:
`install_hooks.py --check`: `hooks installed correctly`.

Neither gate spends the 3-cycle repair budget — no Stage 0 exception was
needed this release, everything green on the first try.

### EC-02's T0 inventory

`grep -rn` over `tests/` for the literals `800`, `736`, `fifteen`, `== 15`,
`1.9.5`, `len(MUTATIONS)`, `v1101-` (tail pins), `report_path`, and the
stdout-format literals `FAIL `, `reply: `, `CASE `, `TOOLS `; the
plain/escaped `rg -n 'spec-v1(?:\\)?\.10(?:\\)?\.1|report-v1(?:\\)?\.10
(?:\\)?\.1' tests`; and `grep -rnw` for the five symbols `INJ_MARKERS`,
`HAL_MARKERS`, `MUTATIONS`, `PROMPT_LIMIT`, `SYSTEM_PROMPT`. Every hit
reconciled against EC-02's exhaustive amendment table
(spec-v1.10.2.md:113-129).

**Reviewed and matching the table** (no amendment needed beyond what's
already listed): `tests/test_prefix.py:31`, `tests/test_v190_tool.py:394`
(`800`); `tests/test_v1101_prompt.py:42` (`736`; the docstring mention at
`:8` is historical prose about what v1.10.1 T4/T5 originally asserted,
stays accurate as history, no pin); `tests/test_v1100_red_team.py:318-338,
371-388`, `tests/test_v1101_red_team.py:406-411` (`fifteen`/`== 15`;
`tests/test_v191_rerank_contract.py:27`'s `_RERANK_TIMEOUT_S == 15.0` is
an unrelated numeric coincidence; `tests/test_v1100_red_team.py:81`'s
`len(CHECKED_STEPS) == 15` is on the "verified unaffected" list); every
`1.9.5` hit outside `tests/test_v195_version.py:18-22` is either a
synthetic, arbitrary version string in `tests/test_v1100_runner.py`'s
`dependency_diff_is_version_only` fixture (:600, :610 — illustrative, not
a pin) or historical-comment prose (`tests/test_v190_agents.py:133,
283-284`, `tests/test_v170_bench.py:322`, `tests/test_routing.py:323`);
`tests/test_v1101_gates.py:311`'s `len(MUTATIONS)` is a comment, the live
assertion is `:343-356` (already listed); every other `v1101-` hit in
`tests/test_v1101_gates.py` is that file's own v1101-scoped mutation
subset test, correctly out of this release's scope;
`tests/test_v190_agents.py:290`, `tests/test_v170_bench.py:327` (already
listed `report_path` sites); no `FAIL `/`reply: `/`CASE `/`TOOLS `
stdout-literal pins exist yet in `tests/` (the CASE/TOOLS shape is new to
this release; `tests/test_v1101_runner.py:204`'s substring on the legacy
`FAIL` line is on the "verified unaffected" list); `INJ_MARKERS`/
`HAL_MARKERS` referenced only in `tests/test_v1100_red_team.py` and
`tests/test_v1101_red_team.py`, all generic (index `[14]`, disjointness,
invariant loops) or already-listed exact-list/count pins; `MUTATIONS`
referenced generically (`>= 28`, full iteration, `startswith` filters) in
`tests/test_v13_carryover.py`, `tests/test_mutation_check.py`,
`tests/test_v15_standards.py:1851` — no hardcoded total anywhere outside
the already-listed sites; `PROMPT_LIMIT` only in `tests/test_prefix.py`
(listed); `SYSTEM_PROMPT` additionally used generically in
`tests/test_v1100_runner.py:39,740-742,1216` and
`tests/test_v1101_runner.py:34,158,197,227,256,304,474,498` (building the
real prompt for a scripted runner, or picking any line over 30 chars as a
synthetic "leaked" line) — unaffected by content changes, no pin.

**EC-02 amendment table (one hit outside the spec's list, closed here,
before T1):**

| file:line | literal | why the list missed it | to be fixed |
| --- | --- | --- | --- |
| `tests/test_v1101_gates.py:254-256` (`test_lint_docs_report_path_repointed_to_v1101`) | `assert config["gates"]["lint-docs"]["report_path"] == "docs/reports/report-v1.10.1.md"` | `RPT-01`'s amendment list named only `tests/test_v170_bench.py:316-331` and `tests/test_v190_agents.py:279-291` as `report_path` pins; this third, v1101-scoped test also hardcodes the value and will break the moment T3 repoints `config/quality_gates.yaml`'s `report_path` to v1.10.2 | rename to name v1.10.2 (matching the T3 pattern of the other two sites) and re-pin the literal to `docs/reports/report-v1.10.2.md`, at T3 |

### Delegation record (T0)

T0 — not delegated — *commands only* (§12.1's exemption: the seven Stage 0
checks and gates 1–5+7 are commands whose redacted output goes into this
skeleton; the storage preflight is an offline one-liner over existing
`storage`/`config` APIs that writes no source or tracked repository file;
the skeleton, prompt file and EC-02 inventory are prose no gate compiles,
imports or runs). Executor model: `claude-sonnet-5`. Map vs actual:
matches §12.1 exactly.

## Operator inputs

- **Run configuration (CFG-01), source `.env` (operator-prepared ahead of
  `go`, never read directly by the executor — only through
  `load_config()`):** `LLM_PROVIDER=openrouter`,
  `OPENROUTER_MODEL=openai/gpt-4.1-mini`, `LMSTUDIO_BASE_URL`/
  `LMSTUDIO_MODEL` empty, `EMBEDDING_BASE_URL=https://openrouter.ai/api/v1`,
  `EMBEDDING_MODEL=openai/text-embedding-3-small`, `EMBEDDING_DIM=1536`,
  `LLM_JUDGE_MODEL=openrouter:openai/gpt-4.1`, `DB_PATH=data/run-v1102.db`.
- **Chat client `describe()`:** `('openrouter', 'openai/gpt-4.1-mini')`
- **Judge client `describe()`:** `('openrouter', 'openai/gpt-4.1')`
- **Embedder route:** `openrouter` / `openai/text-embedding-3-small` /
  1536 — fixed all release (EC-04, NG-01; no instrument switch permitted)
- **Stage 0 check-6 fallback used:** no
- **REV-04 embedder switch (Stage B″):** not permitted this release (NG-01);
  not reached
- **T5 gate-6 procedural deviation (operator decision, 2026-09-17):**
  `GATE-02`'s literal stage→write-tree→gate6→commit order is unexecutable
  against the pre-existing v1.9.3 dirty-tree guard
  (`devtools/mutation_check.py:1983-2016`), which unconditionally compares
  every `MUTATIONS` path's working-tree bytes against the committed `HEAD`
  blob regardless of `--select`, and `devtools/mutation_check.py` is
  itself already a target path of seven existing entries. The operator
  chose: commit the six `v1102-*` entries and the `mutation-all`
  count/anchor edit first (the v1.10.1 T6a precedent, commits
  `4830039`→`8098aa7`), then run the `--select v1102-` calibration and the
  full gate-6 run on the already-clean, committed tree. `git write-tree`/
  `HEAD^{tree}` equality then holds trivially by construction; R3-8's
  substantive intent (catching a hook rewriting a file between intent and
  commit) is preserved because the assertion still runs, just against a
  tree that is, by this point, already the committed one.

## Gate-7 attempt log

| task | attempt | exit | facts (i)/(ii)/(iii) | outcome |
| --- | --- | --- | --- | --- |
| T0 | 1 | 0 | n/a (exit 0) | scheduled run, no re-invoke needed |

## T1 — not reached

## T2 — not reached

## T3 — not reached

## T4 — not reached

## T5 — not reached

## T6 — not reached

## T7 — not reached

## Ledger row (paste into `economics.md`)

Provisional — filled in full at T6/T7.

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | 1.9.5 (provisional; bumped to 1.10.2 at T6 on green) | 2026-09-17 | TBD | TBD | TBD | TBD | TBD | TBD | claude-sonnet-5 | Claude Code |
```
