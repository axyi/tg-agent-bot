# tg-agent-bot v1.10.3 — report skeleton (T0)

A stronger model under test (`openai/gpt-4.1`) and a judge from another
vendor (`anthropic/claude-sonnet-5`), an `exec` guard as defense in
depth, the two marker misses of v1.10.2 closed (HAL-02's noun-before-«нет»
order, INJ-04's «недоступен»), the delegation-record bullet made a
`lint-docs` rule, and the paperwork three stopped runs (v1.10.0,
v1.10.1, v1.10.2) never reached. Spec: `docs/spec/spec-v1.10.3.md`.
`<base>` = `636a281` (the commit before the five spec-authoring/handoff
commits; `git diff --stat 636a281..HEAD` at T0 touches only `docs/`, so
every `file:line` the spec pins holds unchanged). Spec `sha256`:
`682d95dc5f73b0ba25646e4a7b9df3d703f6b4b4952c0eea03e511deb12525ca`.

This file is filled progressively: T0 (this skeleton), T1 (the exec
guard), T2 (the marker widenings, the two dataset `sha256`s), T3 (the
delegation-record lint), T4 (paperwork), T5 (the clean-context review),
T6 (mutations, the live gate-8 run and its tables), T7 (version bump,
final evidence-only commit). Sections not yet reached read "not
reached: T\<n\>".

## T0 — preflight

`<base>` = `636a281`. Spec `sha256` as above. Test-collection floor
re-measured: `uv run --locked pytest --collect-only -q -o addopts="" |
grep -c '::'` = **2170** (2169 passed + 1 skipped). `len(MUTATIONS) ==
139`. Last prompt at `636a281`: **219** (`219-v1103-spec-authoring.md`);
this run's own prompts start at 220. Last `docs/llm-usage.md` row at
`636a281`: **130** (spec-v1.10.3 authoring itself; this run's rows start
at 131).

### Stage 0 — seven checks, in order (checks 1, 2 and 7 offline, against
the already-synced locked environment)

1. **Configuration check (EC-04's three run values).** `uv run --locked
   python -c` over `load_config()`: `cfg.openrouter_model ==
   "openai/gpt-4.1"` — True; `cfg.llm_judge_model ==
   "openrouter:anthropic/claude-sonnet-5"` — True; `str(cfg.db_path)`
   ends `data/run-v1103.db` — True. PASS.
2. **`OPENROUTER_API_KEY` set.** `bool(openrouter_api_key)` = **True**
   (value never printed). PASS.
3. **Storage preflight (EC-04 precondition 3), offline, before any
   network call.** `cfg.db_path` (`data/run-v1103.db`) did not yet exist
   — a fresh file, so `db_empty=True` by construction (no `init_schema`
   call needed to observe zero counts on an absent file). PASS.
4. **Model listings.** `GET https://openrouter.ai/api/v1/models` lists
   `openai/gpt-4.1`; authenticated `GET
   https://openrouter.ai/api/v1/embeddings/models` lists
   `openai/text-embedding-3-small`. Both present. PASS.
5. **One timed plain chat turn** on the production route. Question «Ответь
   одним словом: столица Нидерландов?», elapsed **0.81s** (well under
   `cfg.llm_timeout_s = 600.0s`); no `LLMError`. PASS.
6. **One authenticated embeddings call.** `POST
   https://openrouter.ai/api/v1/embeddings` with
   `model=openai/text-embedding-3-small`, `input=["проверка"]`: status
   200, 1536 floats returned (`== cfg.embedding_dim`). PASS.
7. **One strict-schema judge call**, the two labelled spec-block fences
   (`judge-protocol-1`, `judge-protocol-2`, byte-equal to the slice of
   `devtools/agent_eval.py` between `# BEGIN SPEC JUDGE PROTOCOL` and
   `# END SPEC JUDGE PROTOCOL`, per `T-V1100-JDG-08`) on the fixed
   sample, preceded by `assert describe_client(judge) !=
   describe_client(chat)`. `describe()` pairs: judge
   `('openrouter', 'anthropic/claude-sonnet-5')`, chat `('openrouter',
   'openai/gpt-4.1')` — distinct. Parsed reply: `{"politeness": 1,
   "accuracy": 1, "conciseness": 1, "reason": "..."}`. **No fallback
   needed** — the primary judge probe (`anthropic/claude-sonnet-5`)
   succeeded on the first call; INS-01's `openrouter:openai/gpt-5.6-sol`
   fallback was never invoked. PASS.
8. **`uv lock --offline` no-op** (`Resolved 25 packages`, no lockfile
   change) and `git diff --stat 636a281 -- pyproject.toml uv.lock`
   empty. PASS.

No Stage 0 blocker. The run proceeds past T0.

### Gates 1-5 and 7 on the unchanged tree (gates 6 and 8 not run)

| # | Gate | Exit | Wall / detail |
| --- | --- | --- | --- |
| 1 | `uv sync --locked` | 0 | fast — 25 packages resolved, 23 checked |
| 2 | `ruff check .` | 0 | all checks passed |
| 3 | `pytest` | 0 | 22.70s, 2169 passed / 1 skipped (matches re-measured floor) |
| 4 | `bot.py --selftest` | 0 | `selftest: OK` |
| 5 | `bot.py --selftest-live` | 0 | `live: OK config / OK db / OK docker (29.8.0) / OK telegram / SKIP lmstudio (no route uses it) / OK embeddings / OK openrouter` — all green |
| 6 | `mutation_check.py` | n/a | not run at T0 (GATE-01) |
| 7 | `rag_eval.py` | 2 then 0 | attempt 1: `hybrid: recall@5=1.000 mrr=1.000`, one item's rerank failed transiently (`rerank returned no usable order`, HTTP 429 retries exhausted) — the permitted-capture shape of `REQ-V1102-GATE-01`'s transient rule; re-invoked once (of ≤2 allowed). Attempt 2: clean, `hybrid+rerank: recall@5=1.000 mrr=0.900`, `gate-7: PASS`. Advisory conversation-aware smoke (TOOL-06, context-proof) both **fail** on both attempts, non-blocking (advisory only, never scored) |
| 8 | `agent_eval.py` | n/a | not run at T0 (GATE-01) |

`doctor` and hooks not separately re-checked at T0 beyond the gate run above.

One repair-budget-free transient re-invocation used at gate 7 (1 of the
≤2 allowed under `REQ-V1102-GATE-01`'s transient rule) — not a repair
cycle, per that rule's own accounting.

### EC-02's T0 inventory

`grep -rn` over `tests/` for `800`, `736`, `fifteen`, `sixteen`,
`seventeen`, `== 16`, `== 17`, `1.9.5`, `len(MUTATIONS)`, `v1101-`,
`v1102-`, `report_path`, `FAIL `, `reply: `, `CASE `, `TOOLS `, `gpt-4.1`,
`printenv`, `delegation`, `report-v1.10.2`, `is now`, `all prompts and
the report ledger row pass`; the plain/escaped `rg -n
'spec-v1(?:\\)?\.10(?:\\)?\.2|report-v1(?:\\)?\.10(?:\\)?\.2' tests`; and
`grep -rnw` for `INJ_MARKERS`, `HAL_MARKERS`, `MUTATIONS`,
`EXTRA_KEYS_BY_GATE`, `_validate_exec_arguments`, `_run_lint_docs`. Every
hit reconciled against EC-02's 19-row amendment table
(spec-v1.10.3.md:99-119) and the verified-unaffected list (:121-135).

**Five labelled hit lists:**

- **Allowed-key sets** (`EXTRA_KEYS_BY_GATE` / `_BUILTIN_KEYS`-style
  pins): 2 hits, both definition/usage sites in `devtools/checks.py`
  (`:337` dict definition, `:470` lookup), no test hardcodes this set
  directly — the generic key-shape test (`tests/test_v15_standards.py:
  503-535`) is on the verified-unaffected list. `_BUILTIN_KEYS`: 0 hits.
- **`.env.example` model literals** (`gpt-4.1-mini`, `openai/gpt-4.1`):
  2 hits — `tests/test_v1100_config.py:148` (table row 1, INS-01's
  amendment site) and `tests/test_v1102_docs.py:99` (verified
  unaffected, the v1.10.1 row stays).
  `.env.example`'s own values are never printed here (key names only).
- **`report_path` consumers**: hits across `tests/test_v1101_gates.py`,
  `tests/test_v1102_gates.py`, `tests/test_v170_bench.py`,
  `tests/test_v190_agents.py`, `tests/test_v15_standards.py:1823`, plus
  doc-header/spec-name mentions in `tests/test_v1102_docs.py`,
  `tests/test_v1102_red_team.py`, `tests/test_v1102_prompt.py`,
  `tests/test_v1102_runner.py`, `tests/test_v1100_gates.py:229` — all
  fall inside table rows 6-10 or are already-noted unaffected mentions.
  Three coincidental hits at `test_v15_standards.py:1021-1039` (an
  unrelated local variable name for a scanner-findings tmp path)
  excluded as irrelevant.
- **Mutation totals and tail pins**: `len(mc.MUTATIONS)` comparisons at
  `tests/test_v1101_gates.py:358`, `tests/test_v1102_gates.py:128` (both
  dynamic/regex-extracted, no hardcoded total, table row 16); tail-order
  checks at `tests/test_v1100_gates.py:228-256` (table row 15) and
  `tests/test_v1102_gates.py:63-70` (the v1102-round predecessor of the
  same mechanism, out of this release's amendment scope). Literal `139`
  appears only as comments in `config/quality_gates.yaml` — non-test,
  out of the table's scope.
- **Live-version reads**: `tests/test_v195_version.py:2,5,10,18-22`
  (table row 19, VER-01's amendment site); `tests/test_v194_version.py`
  and `tests/test_v180_version.py` are frozen predecessors per
  `REQ-V190-EC-03`, no amendment expected; `tests/test_routing.py:323`
  is an unrelated historical comment; `tests/test_v1100_runner.py:600,
  610` is a synthetic diff-text fixture inside
  `dependency_diff_is_version_only`'s test data, not a real version pin.

**Reconciliation result: no hit falls outside the 19-row table or the
verified-unaffected list.** Every table row was located at or within its
stated line range, still reading its pre-amendment value (expected at
T0 — nothing has been amended yet). Every verified-unaffected entry was
confirmed present and untouched. `printenv` and `delegation` returned
zero hits in `tests/` (expected — neither feature exists yet). One
documentation-quality observation, not a gap: `tests/test_v1102_gates.py:
54-55` (a v1102-presence check inside `_GATE_MATRIX_LABEL_TO_NAME` that
GATE-03's T4 append leaves untouched) is functionally the same class as
its already-listed neighbour `:60` but isn't itself cited in the
verified-unaffected prose — no amendment or repair cycle needed, since
GATE-03 only appends a new label after the v1102 one.

**EC-02 amendment table: no new rows.** The spec's 19-row table plus this
T0 inventory together remain the exhaustive authorized set; nothing
outside it was found.

### Delegation record (T0)

- T0 | delegated: no | to: — (commands only) | brief: — | map vs actual: matches §13.1

Executor model: `claude-sonnet-5`.

## T1 — not reached: T1

## T2 — not reached: T2

## T3 — not reached: T3

## T4 — not reached: T4

## T5 — not reached: T5

## T6 — not reached: T6

## T7 — not reached: T7

## Operator inputs

- **Run configuration (EC-04), source `.env` (operator-prepared ahead of
  `go`, never read directly by the executor — only through
  `load_config()`):** `OPENROUTER_MODEL=openai/gpt-4.1`,
  `LLM_JUDGE_MODEL=openrouter:anthropic/claude-sonnet-5`,
  `DB_PATH=data/run-v1103.db`.
- **Chat client `describe()`:** `('openrouter', 'openai/gpt-4.1')`
- **Judge client `describe()`:** `('openrouter', 'anthropic/claude-sonnet-5')`
- **Embedder route:** `openrouter` / `openai/text-embedding-3-small` /
  1536 — fixed all release (NG-01; no instrument switch permitted)
- **Stage 0 check-6 fallback used:** no — the primary judge
  (`anthropic/claude-sonnet-5`) passed the strict-schema probe on the
  first call.
- **Judge ≠ chat identity pairs (INS-01):** primary —
  `('openrouter', 'anthropic/claude-sonnet-5')` ≠ `('openrouter',
  'openai/gpt-4.1')`; fallback not used, no second pair.

## Gate-7 attempt log

| task | attempt | exit | facts (i)/(ii)/(iii) | outcome |
| --- | --- | --- | --- | --- |
| T0 | 1 | 2 | (i) capture ends with `gate-7: FAIL rerank did not run for every answerable item:` followed by exactly one item line `'Какие суточные положены за командировку по России?': rerank_attempted=True rerank_succeeded=False rerank_failure='rerank returned no usable order'`; (ii) same-attempt metrics block `hybrid: recall@5=1.000` at/above the floor; (iii) no `Traceback`/`ConfigError`/other `gate-7: FAIL …` line outside the item line, exactly one `rerank did not run` line | transient, permitted capture — re-invoked (1 of ≤2 allowed) |
| T0 | 2 | 0 | n/a (exit 0) | PASS, no further re-invoke needed |

## `docs/reports/tg-post-v1.10.3.md`

Not reached: written at T7.

## Ledger row (paste into `economics.md`)

Not reached: the run has not bumped `pyproject.toml` yet (T7) and has not
stopped early. Filled at close (T7 on green, or the stop route's stage
if the run halts earlier).
