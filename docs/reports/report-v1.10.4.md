# tg-agent-bot v1.10.4 — report skeleton (T0)

The five `v1103-*` mutation entries the v1.10.3 run authored and verified
but stopped before committing, landed; every frozen-list test pin
rewritten to presence, contiguity and order instead of "ends here" (the
defect class that stopped v1.10.3); the single gate 8 that stop route
never reached, run exactly once; the paperwork three stopped runs
(v1.10.1, v1.10.2, v1.10.3) left pending. Spec:
`docs/spec/spec-v1.10.4.md`. `<base>` = `f3ce1a5` (the commit before the
five spec-authoring/handoff commits; `git diff --stat f3ce1a5..HEAD` at
T0 touches only `docs/`, so every `file:line` the spec pins holds
unchanged). Spec `sha256`:
`e6050b826eaf8063e21a9132797816a7c101a3e91d1a9debd3f308424a110f0e`.

This file is filled progressively: T0 (this skeleton), T1 (the frozen-pin
rewrites and repoints), T2 (the five `v1103-*` mutation entries landed),
T3 (the clean-context review), T4 (calibration, gate 6, the live gate
sequence, gate 8), T5 (version bump, paperwork, the evidence commit, the
tag). Sections not yet reached read "not reached: T\<n\>".

## T0 — preflight

`<base>` = `f3ce1a5`. Spec `sha256` as above.

### Exit-status preconditions (EC-04)

- `git diff --exit-code HEAD -- docs/spec/spec-v1.10.4.md` — exit 0
  (committed, unmodified).
- `grep -c '^Status: ready for' docs/spec/spec-v1.10.4.md` — `1`.
- `docs/prompts/227-v1104-spec-authoring.md` and `docs/llm-usage.md` row
  138 present in `HEAD` — both confirmed.
- `pyproject.toml:3` — `1.9.5` (unmoved).
- `git tag -l 'v1.10.*'` — empty (no `v1.10.0`…`v1.10.4` tag).
- `git rev-parse stash@{0}` — `e3c6e3ff3bee60bff183ae056621d4dc984cd5a3`,
  matching MUT-01's pinned id.
- `git diff --stat f3ce1a5 HEAD` — four `docs/` paths only (handoff,
  usage row, prompt 227, the spec itself); no source, test or config file
  differs from `f3ce1a5`, so `f3ce1a5` and the T0 tree are equivalent for
  every `file:line` the spec pins.
- Two-path `git stash show -p stash@{0} | git apply --check
  --include='devtools/mutation_check.py'
  --include='config/quality_gates.yaml' -` — exit 0 on the unchanged
  tree. **Id-match route confirmed**; no Appendix D fallback needed at
  T0 (T2 re-runs this check after T1's commit, per MUT-01).

Test-collection floor re-measured: `uv run --locked pytest
--collect-only -q -o addopts="" | grep -c '::'` = **2285** (matches
authoring's count, exit 0). `len(devtools.mutation_check.MUTATIONS) ==
139`. Last prompt at `f3ce1a5`: **227**
(`227-v1104-spec-authoring.md`); this run's own prompts start at **228**.
Last `docs/llm-usage.md` row at `f3ce1a5`: **138** (spec-v1.10.4
authoring itself; this run's rows start at **139**). `doctor` and
`install_hooks.py --check` both green.

### Stage 0 — seven checks, in order (checks 1, 2 and 7 offline, against
the already-synced locked environment)

1. **Configuration check (EC-04's three run values).** `uv run --locked
   python -c` over `load_config()`: `cfg.openrouter_model ==
   "openai/gpt-4.1"` — True; `cfg.llm_judge_model ==
   "openrouter:anthropic/claude-sonnet-5"` — True; `str(cfg.db_path)`
   ends `data/run-v1104.db` — True. PASS.
2. **`OPENROUTER_API_KEY` set.** `bool(openrouter_api_key)` = **True**
   (value never printed). PASS.
3. **Storage preflight (EC-04 precondition 3), offline, before any
   network call.** `cfg.db_path` (`data/run-v1104.db`) did not yet
   exist — a fresh file, so `db_empty=True` by construction (no
   `init_schema` call needed to observe zero counts on an absent file).
   PASS.
4. **Model listings.** `GET https://openrouter.ai/api/v1/models` lists
   `openai/gpt-4.1`; authenticated `GET
   https://openrouter.ai/api/v1/embeddings/models` lists
   `openai/text-embedding-3-small`. Both present. PASS.
5. **One timed plain chat turn** on the production route. Question «Ответь
   одним словом: столица Нидерландов?», elapsed **1.52s** (well under
   `cfg.llm_timeout_s = 600.0s`); no `LLMError`; reply «Амстердам.».
   PASS.
6. **One authenticated embeddings call.** `POST
   https://openrouter.ai/api/v1/embeddings` with
   `model=openai/text-embedding-3-small`, `input=["проверка"]`: status
   200, 1536 floats returned (`== cfg.embedding_dim`). PASS.
7. **One strict-schema judge call**, the two labelled spec-block fences
   (`judge-protocol-1`, `judge-protocol-2`, imported directly from
   `devtools/agent_eval.py` between `# BEGIN SPEC JUDGE PROTOCOL` and
   `# END SPEC JUDGE PROTOCOL`) on the fixed sample, preceded by `assert
   describe_client(judge) != describe_client(chat)`. `describe()` pairs:
   judge `('openrouter', 'anthropic/claude-sonnet-5')`, chat
   `('openrouter', 'openai/gpt-4.1')` — distinct. Parsed reply:
   `{"politeness": 0.7, "accuracy": 1, "conciseness": 1, "reason": "..."}`.
   **No fallback needed** — the primary judge probe
   (`anthropic/claude-sonnet-5`) succeeded on the first call; INS-01's
   `openrouter:openai/gpt-5.6-sol` fallback was never invoked. PASS.
8. **`uv lock --offline` no-op** (`Resolved 25 packages`, no lockfile
   change) and `git diff --exit-code f3ce1a5 -- pyproject.toml uv.lock`
   empty. PASS.

No Stage 0 blocker. The run proceeds past T0.

### Gates 1-5 and 7 on the unchanged tree (gates 6 and 8 not run)

| # | Gate | Exit | Wall / detail |
| --- | --- | --- | --- |
| 1 | `uv sync --locked` | 0 | fast — 25 packages resolved, 23 checked |
| 2 | `ruff check .` | 0 | all checks passed |
| 3 | `pytest` | 0 | exit 0; collection matches the re-measured 2285 floor |
| 4 | `bot.py --selftest` | 0 | `selftest: OK` |
| 5 | `bot.py --selftest-live` | 0 | `live: OK config / OK db / OK docker (29.8.0) / OK telegram / SKIP lmstudio (no route uses it) / OK embeddings / OK openrouter` — all green |
| 6 | `mutation_check.py` | n/a | not run at T0 (GATE-01) |
| 7 | `rag_eval.py` | 0 | `hybrid: recall@5=1.000 mrr=1.000 page_hit_rate=1.000`; `hybrid+rerank: recall@5=1.000 mrr=0.900`; clean on attempt 1, no transient re-invocation needed. Advisory conversation-aware smoke (TOOL-06, context-proof) both **fail** on the one attempt, non-blocking (advisory only, never scored) |
| 8 | `agent_eval.py` | n/a | not run at T0 (GATE-01) |

No repair-budget transient re-invocation used at gate 7 this task (the
first attempt was clean).

### EC-02's T0 inventory

Five-part literal `grep` inventory, run over `tests/` and
`devtools/checks.py` (no AST tooling): (i) the frozen-list patterns
(`tail ==|== _V1[0-9]+_IDS|_IDS = \[|tail\[|len\(mc\.MUTATIONS\)|
len\(MUTATIONS\)|MARKERS\) ==|is now|report-v1\.10\.[0-9]|
spec-v1\.10\.[0-9]|report_path|"1\.9\.5"|1638|120 entries|
v110[0-9]-T<N>` over `tests/`) — **146** raw hits; (ii) the reference
grep (`report_path|_GATE_MATRIX_LABEL_TO_NAME|_parse_gate_matrix|
task-briefs/v1|project\.version|\["version"\]|1638|120 entries` over
`tests/` and `devtools/checks.py`) — **125** raw hits; (iii) the
absence/end-of-list grep (`not in|not any\(|endswith\(|\[-1\]|
(_IDS|ids|labels) == \[` over `tests/` and `devtools/checks.py`) —
**492** raw hits; (v) the deliberately broad pass
(`version|pyproject|uv\.lock|count|entries|task-brief|
report[_-]?path|spec-v|report-v|_IDS|MUTATIONS|labels` over `tests/`
and `devtools/checks.py`) — **1024** raw hits, of which **825** are not
already covered by (i)-(iii).

**Reconciliation, by labelled hit group** (every raw hit falls into
exactly one of these groups; every group is classified):

- **The 16 amendment-table sites (rows 1-14, 12b — spec-v1.10.4.md:93-108).**
  Directly verified by line-range inspection, including the two
  highest-risk patterns (`tail ==` / `_IDS = [`, the exact shape that
  stopped v1.10.3): `tests/test_v1102_gates.py:86` (`assert tail ==
  _V1102_IDS`, inside row 1's `:80-87` range) and
  `tests/test_v1100_gates.py:237,260` (inside row 2's `:226-262`
  range) both confirmed as the sites the amendment table already
  names — no additional `tail ==`/`_IDS = [`/`[-1]`-shaped comparison
  exists anywhere in `tests/` outside the 16 listed sites (checked
  every hit of pattern group (i)'s frozen-list sub-patterns
  individually: `test_v1101_gates.py:266` `_V1101_MUTATION_IDS = [` is
  a static per-release id list used only for gate-config membership
  assertions, not a growing-tail comparison — verified-unaffected
  below; `test_mutation_check.py:163` `_V160_MUTATION_IDS = [` is the
  same shape, also verified-unaffected below).
- **The spec's own "verified unaffected" list (spec-v1.10.4.md:110-118).**
  Confirmed present and untouched at its stated lines:
  `tests/test_v1102_gates.py:28,60,76`; `tests/test_v1103_gates.py:30,
  34,45-52`; `tests/test_v1100_runner.py:576` (a tail over
  `GATE8_DEPENDENCIES`, unrelated to any mutation/version list);
  `tests/test_v1101_gates.py:266-282`; `tests/test_mutation_check.py:132,
  163-185` (prefix filters and lower bounds over the live registry,
  not a frozen tail).
- **Per-profile membership-exclusion checks** (`"mutation-v11NN" not in
  members`, `"agent-eval" not in members` — `tests/test_v1100_gates.py:73,
  113`, `tests/test_v1101_gates.py:242,340`, `tests/test_v1102_gates.py:127`):
  a different semantic from a "list ends here" pin — each asserts a
  *specific, already-fixed* historical label is absent from every
  profile except its own, which stays true forever regardless of what
  a later release appends. Unaffected because the property does not
  reference "the end of the list", only one named element's exclusion.
- **`devtools/checks.py` implementation code** (~60 combined hits
  across parts (ii)/(iii)/(v) — yaml/gate-config parser internals,
  `_validate_one_gate`'s key checks, `_lint_report_delegation`'s own
  cell-shape regexes at `:1643-1684` which this release's
  `T-V1104-PIN-07` exercises but does not edit): none of these are test
  assertions or frozen-list pins — they are the generic mechanism `T-V1104-PIN-07`
  tests through its public function, byte-unchanged this release
  (NG-01). Unaffected because they are production code, not a test
  pin.
- **Module docstring/header citations** (the large cluster of `:1`,
  `:2`-ish hits — `tests/test_v1100_config.py:1`,
  `tests/test_v1102_gates.py:1-4`, `tests/test_v1103_gates.py:3-4,8,12`,
  and dozens more across nearly every `tests/test_v1*.py` file): each
  is a module docstring naming its own governing spec file by number
  (matched incidentally by the `spec-v1\.10\.[0-9]` / `spec-v` /
  `report-v` patterns) — prose, not an executable assertion. Unaffected.
- **`tests/test_v1103_lint.py`'s `report_path`/`delegation_record`
  fixture literals** (15 hits, e.g. `:165,177,197,263,297,357,372,387`):
  spot-checked at `:102-115` and `:165-180` — these construct synthetic
  `report_path: "docs/reports/report-v1.10.3.md"` / `delegation_record`
  gate dicts as **test fixtures** to exercise `_lint_report_delegation`
  and `_run_lint_docs` generically (a frozen predecessor test file,
  `REQ-V190-EC-03`); none assert anything about *this* release's live
  `config/quality_gates.yaml`. Unaffected.
- **Frozen predecessor version tests** (`tests/test_v180_version.py`
  through `tests/test_v194_version.py`, each pinning its own historical
  git blob read — `git show v1.8.0:pyproject.toml` etc.): unaffected
  per `REQ-V190-EC-03`, no amendment expected; `tests/test_v195_version.py`
  is row 15's amendment site (T5 only).
- **The generic `not in` / `endswith(` / broad-pass sprawl** (the
  remaining ~1150 combined raw hits across ~90 distinct test modules
  with no frozen-list, pin, version or gate-matrix semantics —
  `tests/test_v160_dashboard.py`, `test_tool_output.py`, `test_agent.py`,
  `test_v180_conversations.py`, `test_v190_commands.py`,
  `test_v170_reasoning.py`, `test_bench.py`, `test_docker.py`,
  `test_summary.py`, `test_observability.py`, `test_config.py` and
  similar — per-file counts confirmed by grouping the raw grep output
  by file): generic membership/suffix assertions on business-logic
  values (a secret not appearing in output, a key absent from a dict, a
  filename not ending in a given suffix) — none reference a release-id
  list, a mutation count, a version literal, or a gate-matrix label.
  Unaffected because the pattern match is on an English word
  (`count`/`entries`/`version`) or a generic Python idiom (`not in`),
  not on release-list semantics — exactly the false-positive volume
  part (v)'s own text predicts.

**Reconciliation result: no hit falls outside the 16-row amendment
table, the spec's verified-unaffected list, or the labelled groups
above.** No unclassified hit survived T0 (ERR-01 row 14). No second
`tail ==`/`_IDS = [`/frozen-equality site exists beyond the 16 the
spec's table already names — specifically re-checked because an
unlisted fourth pin of exactly this shape (`tests/test_v1102_gates.py:80-87`)
is what stopped v1.10.3.

**EC-02 amendment table: no new rows.** The spec's 16-row table plus
this T0 inventory together remain the exhaustive authorized set;
nothing outside it was found.

### Delegation record (T0)

- T0 | delegated: no | to: — (commands only) | brief: — | map vs actual: matches §10.1

Executor model: `claude-sonnet-5`.

## T1 — not reached: T1

## T2 — not reached: T2

## T3 — not reached: T3

## T4 — not reached: T4

## T5 — not reached: T5

## Operator inputs

- **Run configuration (EC-04), source `.env` (operator-prepared ahead of
  `go`, never read directly by the executor — only through
  `load_config()`):** `OPENROUTER_MODEL=openai/gpt-4.1`,
  `LLM_JUDGE_MODEL=openrouter:anthropic/claude-sonnet-5`,
  `DB_PATH=data/run-v1104.db`.
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
- **Stash identity (MUT-01):** `git rev-parse stash@{0}` =
  `e3c6e3ff3bee60bff183ae056621d4dc984cd5a3`, matching the pinned id;
  id-match route confirmed at T0 (post-T1 re-check at T2).

## Gate-7 attempt log

| task | attempt | exit | facts (i)/(ii)/(iii) | outcome |
| --- | --- | --- | --- | --- |
| T0 | 1 | 0 | n/a (exit 0) | PASS, clean on the first attempt, no re-invoke needed |

## `docs/reports/tg-post-v1.10.4.md`

Not reached: written at T5.

## Ledger row (paste into `economics.md`)

Not reached: the run has not bumped `pyproject.toml` yet (T5) and has not
stopped early. Filled at close (T5 on green, or the stop route's stage
if the run halts earlier).
