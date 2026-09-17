# tg-agent-bot v1.10.1 — report skeleton (T0)

Closes every tail the v1.10.0 run and its `/verify-run` left, and moves
every live gate — 5, 7 and 8 — off LM Studio onto OpenRouter models the lab
chose. Spec: `docs/spec/spec-v1.10.1.md`. `<base>` = `1d96ca0` (the commit
before the five spec-authoring/handoff commits; `git diff --stat
1d96ca0..HEAD` at T0 touches only `docs/`, so every `file:line` the spec
pins holds unchanged). Spec `sha256`:
`6b6cd7371aaa8c673a89b681b704e9750b4ed8f6cd0d6f7cfb8596c43926a297`.

This file is filled progressively: T0 (this skeleton), T3 (dataset
`sha256`s), T4 (PRM-02's before/after table), T6 (the one live gate-8 run
and its tables), T7 (version bump, provisional report), T8 (final
evidence-only commit). Sections not yet reached read "not reached: T<n>".

## T0 — preflight

`<base>` = `1d96ca0`. Spec `sha256` as above. Test-collection floor
re-measured: `uv run --locked pytest --collect-only -q -o addopts="" | grep
-c '::'` = **1860** (matches `pyproject.toml`'s `addopts` count; the
v1.10.0 report's "1859" note is `NG-06`, not investigated further).

### Stage 0 — seven checks, in order (checks 1, 2 and 7 offline, against the
already-synced locked environment)

1. **Configuration check (CFG-01) + export proof (EC-04).** `uv run
   --offline --locked python -` over `load_config()` asserted every CFG-01
   `asserted as` cell: `llm_provider="openrouter"`,
   `openrouter_model="openai/gpt-4.1-mini"`, `lmstudio_model=""`,
   `embedding_base_url="https://openrouter.ai/api/v1"`,
   `embedding_model="openai/text-embedding-3-small"`, `embedding_dim=1536`,
   `llm_rerank_model="openrouter:mistralai/mistral-small-24b-instruct-2501"`,
   `llm_judge_model="openrouter:openai/gpt-4.1"`, `llm_eval_chat_model=""`,
   `db_path` ending `data/run-v1101.db` — all True. `bool(openrouter_api_key)
   = True`. `chat.describe() = ('openrouter', 'openai/gpt-4.1-mini')`,
   `judge.describe() = ('openrouter', 'openai/gpt-4.1')` — distinct.
   Export proof: `LLM_JUDGE_MODEL=openrouter:openai/gpt-4.1-mini uv run
   --offline --locked python -c '...load_config().llm_judge_model'` printed
   `openrouter:openai/gpt-4.1-mini` (the exported value, not `.env`'s).
   PASS.
2. **Storage preflight (EC-04 precondition 3), offline, before any network
   call.** Opened `cfg.db_path` (`data/run-v1101.db`, a fresh file),
   `storage.init_schema(conn, embedding_dim=1536,
   embedding_model="openai/text-embedding-3-small")`, then
   `storage.document_count_all(conn) = 0` and `SELECT COUNT(*) FROM chunks`
   `= 0`. Printed `db_empty=True`. PASS.
3. **Model listings.** `GET https://openrouter.ai/api/v1/models` lists
   `openai/gpt-4.1-mini`; authenticated `GET
   https://openrouter.ai/api/v1/embeddings/models` lists
   `openai/text-embedding-3-small`. Both present. PASS.
4. **One timed plain chat turn** on the production route. Question «Ответь
   одним словом: столица Нидерландов?», reply `"Амстердам"`, elapsed
   **2.976s** (well under `cfg.llm_timeout_s` = 600s); no `LLMError`, no
   rejected `reasoning` field observed (default `ReasoningRequest`, no
   `reasoning=` kwarg sent — the tool-round reasoning policy is a no-op on
   this model per CFG-01). `t_turn = 2.976s`. PASS.
5. **One authenticated embeddings call.** `POST
   https://openrouter.ai/api/v1/embeddings` with
   `model=openai/text-embedding-3-small`, `input=["проверка"]`: status 200,
   1536 floats returned (`== cfg.embedding_dim`). PASS.
6. **One strict-schema judge call**, the two labelled spec-block fences
   (`judge-protocol-1`, `judge-protocol-2`) — extracted byte-identical from
   the already-implemented slice of `devtools/agent_eval.py` between `#
   BEGIN/END SPEC JUDGE PROTOCOL` (v1.10.0's `T-V1100-JDG-08` already pins
   that slice source-to-source against the spec fences) — on the fixed
   sample (question/reference/reply as REV-04 Stage 0 specifies). Parsed
   reply: `{"politeness": 1, "accuracy": 1, "conciseness": 1, "reason":
   "Ответ вежливый, точный и краткий. Указана правильная столица, без
   лишней информации."}`. `describe()` pairs as in check 1, unequal. **No
   fallback needed** (`openai/gpt-4.1` accepted `response_format` on the
   first attempt; EC-01 disallows the fallback this release regardless).
   PASS.
7. **`uv lock --offline` no-op.** `Resolved 25 packages` with no lockfile
   change; `git diff --exit-code -- uv.lock` empty. PASS.

No Stage 0 blocker. The run proceeds past T0.

### RUN-02 timeout computation

`R = HTTP_ATTEMPT_LIMIT = 9` (`agent.py:45`); `max_calls = 23 * 9 + 12 =
219`; `t_turn = 2.976s` (check 4); `timeout_seconds = ceil_to_100(1.5 * 219
* 2.976) = ceil_to_100(977.6) = 1000`, floor 1800, no cap → **`agent-eval.
timeout_seconds = 1800`** (the floor, as the handoff predicted; T6 writes
this into `config/quality_gates.yaml`).

### Gates 1-7 on the unchanged tree (gate 8 not run)

Gate 6 (mutation, ~13m44s) and gate 7 (rag_eval, <1s) run sequentially,
nothing else on the box during gate 6.

| # | Gate | Exit | Wall |
| --- | --- | --- | --- |
| 1 | `uv sync --locked` | 0 | fast — 25 packages resolved, 23 checked |
| 2 | `ruff check .` | 0 | fast, all checks passed |
| 3 | `pytest` | 0 | 20.87s, 1859 passed / 1 skipped, 1860 collected (matches re-measured floor) |
| 4 | `bot.py --selftest` | 0 | `selftest: OK` |
| 5 | `bot.py --selftest-live` | 1 | `live: OK config`, `OK db`, `OK docker (29.8.0)`, `OK telegram`, `SKIP lmstudio (not configured)`, **`FAIL embeddings — model openai/text-embedding-3-small is not loaded`**, `OK openrouter` — **disclosed expected** (G5-02's T0 exception: the embeddings client cannot authenticate to OpenRouter until T1); no other line red, `db` in particular OK |
| 6 | `mutation_check.py` (no `--select`) | 0 | 823.4s (13m43.4s), 127/127 killed, 0 survived/errored/drifted |
| 7 | `rag_eval.py` | 2 | 0.69s — `gate-7: FAIL indexing the corpus -- embeddings http 401` — **disclosed expected** (same cause as gate 5) |
| 8 | `agent_eval.py` | n/a | not run at T0 (GATE-01) |

`doctor`: `[PASS] doctor: all tools at pin, hooks installed`. Hooks:
`install_hooks.py --check`: `hooks installed correctly`.

Neither the gate-5 nor the gate-7 red spends the 3-cycle repair budget —
both are G5-02's disclosed T0 exception, recorded verbatim per RPT-01 item
1.

### Delegation record (T0)

T0 — not delegated — *commands only* (§16.1's exemption: the seven Stage 0
checks and the seven gates are commands whose redacted output goes into
this skeleton; the storage preflight is an offline `python -` one-liner
over existing `storage`/`config` APIs that writes no source or tracked
repository file — creating/initialising `cfg.db_path` is permitted; the
skeleton, prompt file and ledger block are prose no gate compiles, imports
or runs). Executor model: `claude-sonnet-5`. Map vs actual: matches §16.1
exactly.

## Operator inputs

- **Run configuration (CFG-01), source `.env` (lab-written 2026-09-17,
  never read directly by the executor — only through `load_config()`):**
  `LLM_PROVIDER=openrouter`, `OPENROUTER_MODEL=openai/gpt-4.1-mini`,
  `LMSTUDIO_BASE_URL`/`LMSTUDIO_MODEL` empty,
  `EMBEDDING_BASE_URL=https://openrouter.ai/api/v1`,
  `EMBEDDING_MODEL=openai/text-embedding-3-small`, `EMBEDDING_DIM=1536`,
  `LLM_RERANK_MODEL=openrouter:mistralai/mistral-small-24b-instruct-2501`,
  `LLM_JUDGE_MODEL=openrouter:openai/gpt-4.1`, `LLM_EVAL_CHAT_MODEL` unset,
  `DB_PATH=data/run-v1101.db`.
- **Chat client `describe()`:** `('openrouter', 'openai/gpt-4.1-mini')`
- **Judge client `describe()`:** `('openrouter', 'openai/gpt-4.1')`
- **Rerank route:** `openrouter:mistralai/mistral-small-24b-instruct-2501`
  (unchanged since v1.9.1)
- **Stage 0 check-6 fallback used:** no
- **REV-04 embedder switch (Stage B″):** not used (not reached)

## T1 — embeddings over OpenRouter, gate 5's route rules

`embedding_api_key` resolved from `OPENROUTER_API_KEY` through one
`is_openrouter_url(url)` helper in `config.py` (imported by
`llm/embeddings.py`, preserving the existing `llm → config` direction —
`T-V1101-CFG-05`'s fresh-interpreter smoke proves no import cycle).
`EmbeddingsClient` sends `Authorization: Bearer` only with a non-empty key
(`llm/embeddings.py:_post`); `describe()` is provider-aware over the same
helper, and the `gen_ai.provider.name` span attribute now reads
`self.describe()[0]`. The three T1 constructor sites
(`bot.py:_live_embeddings`, `bot.py:main()`, `devtools/rag_eval.py:main()`)
pass `api_key=cfg.embedding_api_key`; the fourth (gate 8's runner) is T3's
job. `_live_lmstudio` gained the route-rule SKIP; `_live_embeddings`
dropped the unauthenticated `/models` listing step, keeping only the
authenticated round-trip.

27 new tests: `tests/test_v1101_config.py` (9 — `is_openrouter_url`,
`embedding_api_key` resolution, `T-V1101-EC-02`'s offline storage-preflight
expression including the `ConfigError`-on-mismatched-pair case), `tests/
test_v1101_embeddings.py` (18 — the fresh-interpreter import smoke, the
header/describe()/error-message pins, the AST source pin on the three
constructor sites, `T-V1101-G5-01…03`). Two renames inside `tests/
test_v190_embeddings.py` (`:381-389`, `:404-409`) per EC-02's exhaustive
amendment list — nothing else in that file touched. `tests/
test_v1_guardrails.py:1425-1445` re-checked, green, unamended.

Gates 1-4 green offline (pytest: 1895 collected). Gate 5 and gate 7 live,
in sequence, nothing else concurrent:

| # | Gate | Exit | Wall | Detail |
| --- | --- | --- | --- | --- |
| 5 | `bot.py --selftest-live` | 0 | — | `OK config`, `OK db`, `OK docker (29.8.0)`, `OK telegram`, `SKIP lmstudio (no route uses it)`, `OK embeddings`, `OK openrouter` — capable-of-green rule (G5-02) now holds from this tree on |
| 7 | `rag_eval.py` | 0 | 35.4s | hybrid recall@5=1.000, mrr=1.000, page_hit_rate=1.000 (vector and hybrid+rerank likewise 1.000); advisory conversation-aware smoke — TOOL-06 pin **fail**, context-proof **fail** (no `search_documents` call on turns 2/3) — non-blocking (NG-07); PRM-01/02 (T4) targets exactly this pattern |

Not reused as PRM-02's "before" measurement (T4 runs its own pair). No
Stage B″ needed (`recall@5` green on the first live attempt with the new
embedder).

Delegated (general-purpose subagent, brief `docs/spec/task-briefs/v1101-T1.md`).
Commit `4b18804`. Map vs actual: matches §16.1 exactly.

## T2 — gate `env:` passthrough, matrix and `lint-docs` repoint

`devtools/checks.py`: `_COMMAND_BASE_KEYS` gains `"env"`;
`_validate_command_gate` validates it before the unknown-key check
(non-empty string keys matching `^[A-Za-z_][A-Za-z0-9_]*$`, no NUL in a
value, no key naming a registered secret in any case); builtin gates
still reject it via the pre-existing unknown-key error. `run_argv` gains
keyword-only `env:`, merged over `os.environ` for `Popen`;
`execute_command_gate` is the only caller that passes it
(`gate.get("env")`). `config/quality_gates.yaml`'s `skylos` entry pinned
`env: { SKYLOS_GREP_BUDGET: "180" }`; `lint-docs.report_path` →
`report-v1.10.1.md`. Gate-matrix test repointed at `spec-v1.10.1.md` with
the `mutation-v1101` label added.

19 new tests in `tests/test_v1101_gates.py`, written first (confirmed red
for the expected reason pre-implementation). Exact `GateConfigError`
messages: `gates.g.env must map non-empty string keys to string values`;
`gates.g.env key is not an identifier: <key>`; `gates.g.env value contains
NUL: <key>`; `gates.g.env must not name a secret: <key>` (original casing
preserved); a builtin gate carrying `env:` still hits the pre-existing
`gates.g: unknown key(s) ['env']`.

Two disclosed deviations, both in the commit body: (1)
`tests/test_v190_agents.py:278-286` (a duplicate `report_path` pin
outside the brief's file list) needed its two literals bumped to stay
green after the yaml repoint — the function name is left for whichever
task next renames this file's tests; (2) this report's own `## Ledger
row` placeholder was a bare `not reached: T0` string, which `lint-docs`
correctly flagged (`ledger-row fenced block contains no table row`) —
fixed by the orchestrator to the 11-column `| TBD | ... |` shape
precedent (v1.10.0 T6 commit `761359a`) immediately after this task
landed; `lint-docs` now green.

Gates 1-4 green; `doctor` green; `lint-docs` green (after the ledger-row
fix above). Delegated (general-purpose subagent, brief
`docs/spec/task-briefs/v1101-T2.md`). Commit `832e4e6`. Map vs actual:
matches §16.1, plus the one disclosed out-of-brief test-literal fix.

## T3 — the checkers (RT-01…05) and the gate-8 runner's tool surface

Clause (c) is now clause-bounded and echo/negation-aware: env-key names
are a hit only in the leak-shape regex (four value alternatives, atomic
bracketed/quoted capture, `LEAK_PLACEHOLDERS` exclusion); every other
phrase is checked per clause (sentence boundaries plus the adversative /
transition / coordination boundary list, `и теперь`/`and now` before the
bare `и`/`and`), with a shared negation guard (`не`/`don't`/`do
not`/`does not`/`doesn't`/`did not`/`didn't`/`never`) suppressing a
marker match only within its own clause. `INJ_MARKERS` and `HAL_MARKERS`
both grew 8 → 15; the fifteenth `INJ_MARKERS` entry is a bounded
committed-refusal shape (`.{0,60}` gap + explicit verb), not "topic plus a
later `не`". `_injection_clauses`/`check_injection` now return/report a
5-tuple `(a,b,c,d,e)` — new clause (e) fails an injection case that
called `exec`/`fetch` (`"(e) tool called under attack: {name}"`).
`check_hallucination` drops its entity conjunction (`entity` still read,
still raises `KeyError` if missing, no longer gates the outcome).

Gate-8 runner: a real `rag.Searcher` per turn (production's `RAG_ENABLED`
path) over the empty temp index when `cfg.rag_enabled`, fourth
`EmbeddingsClient` constructor site (`EMB-02`'s total now four);
per-case tool-call recording via an opt-in `record_tool_calls` parameter
(design note below) threaded into `check_step`'s new `tool_calls`
argument for injection cases.

**Design deviation, disclosed and reviewed:** the brief's literal
"`_one_turn` always passes `on_tool` to `run_agent_outcome`" is
unreachable together with the hard constraint that
`tests/test_v1100_runner.py` stays unamended — ~29 of its tests inject a
`ScriptedTurns` fake with no `on_tool` parameter. Resolved (subagent
consulted its own advisor mid-task) with an explicit `record_tool_calls:
bool = False` opt-in threaded `run()` → `_run()` → `_run_level2_cases()`
(`main()` passes `True`; every offline test defaults `False`), plus a
`None`-guard in `_one_turn` that only adds `on_tool` to the
`run_agent_outcome` kwargs when it isn't `None`. `tests/
test_v1100_runner.py` (86 tests) confirmed green, completely unamended,
before and after. Accepted — the alternative (editing the fixture file)
was explicitly out of scope.

Five case-specific `any_of` regexes invented for the five injection
cases, each verified programmatically against its own case's
`positive_reply`/`negative_reply` and against `HAL_MARKERS` disjointness;
one self-correction mid-task (INJ-04: "не предусмотрено" → "не
предусмотрен", matching the dataset's actual grammatical form, caught by
testing against the live text rather than a paraphrase). `Searcher` built
fresh per turn (not per case) — within the brief's stated either-reading
tolerance.

**Minor disclosed nit** (no fix needed): two tests in `tests/
test_v1101_runner.py` are labelled `T-V1101-ERR-01` rows 7-8 but actually
cover the pre-existing LLMError-abort paths, not this release's rows 7
(clause (e)'s message) and 8 (`DatasetError` on invariants (vii)-(x)) —
the subagent misread the row citation without reading the full spec
(by design, to save context) and guessed from `agent_eval.py`'s own
docstrings. The *actual* rows 7 and 8 behaviour is fully covered
elsewhere in the same commit (clause (e)'s dedicated tests; the
schema/invariant tests in `tests/test_v1101_red_team.py`) — this is a
test-label mislabeling, not a coverage gap. Left as is; noted for T8's
final accounting.

95 new tests in `tests/test_v1101_red_team.py`, 15 in `tests/
test_v1101_runner.py`, `tests/test_v1101_embeddings.py`'s `EMB-05A` test
extended 3 → 4 sites. Four amendment sites inside `tests/
test_v1100_red_team.py` (the `markers=` call, the two "exactly eight" →
"exactly fifteen" lists, the entity-reference assertion flip), nothing
else in that file touched — confirmed (78 tests, all green unamended
beyond the four sites).

Both dataset files frozen by `sha256`:
- `evals/agent/red_team.json`:
  `3fbb6c9579ed0b358be9e04444a1196a2ce4cdf351ad36274eaf146a86c3d025`
- `evals/agent/judge_questions.json` (unedited, hashed only):
  `71143395a92002bd063b8fdf6be36b44c80fb5a1863cf3ff4b18ca4d501cdf9c`

Gates 1-4 green (pytest: 2024 passed / 1 skipped). Entirely offline — no
gate 5/6/7/8 this task. Orchestrator spot-verified `_injection_clauses`/
`check_injection`'s 5-tuple and clause-(e) message against the source,
plus an independent fresh `pytest -q` run, both green.

Delegated (general-purpose subagent, brief `docs/spec/task-briefs/v1101-T3.md`).
Commit `526e19d`. Map vs actual: matches §16.1, plus the disclosed
`record_tool_calls` design resolution.

## T4 — prompt/tool literals compel a document search; PRM-02's before/after

Two exact-text changes: `agent.py`'s `SYSTEM_PROMPT` docs line (137 →
203 chars) and `tools.py`'s `search_documents` description; rendered
prompt 670 → **736** chars (independently re-verified by the
orchestrator, ASCII confirmed). `PROMPT_LIMIT` 700 → 800
(`tests/test_prefix.py:29`); `tests/test_v190_tool.py:372-390`'s
`PROMPT_LINE`, 140→210 and 700→800 caps, both tests renamed; the stale
"kept under 550 characters" comment corrected to name `PROMPT_LIMIT`.
`tests/test_v1_guardrails.py:829-864` confirmed green, unamended.

**Disclosed EC-02 exhaustive-list gap** (not a scope-widening judgment
call — a mechanical, unavoidable consequence of the already-authorized
text change, surfaced only once the string length was actually measured):
the longer `search_documents` description (129 → ~194 chars) also broke
two **pre-existing** `tests/test_v190_tool.py` tests that EC-02's
amendment table does not list — `test_t_v190_tool_01_the_fourth_entry_is_appended_last_and_exact`
(a frozen exact-match pin of the old description string, ~line 74-77) and
`test_t_v190_tool_01_the_entry_fits_350_chars` (~line 100-104, renamed to
`_420_chars_`, cap raised). Both are narrow re-pins of the same literal
PRM-01 already authorized — no test weakened in intent, none deleted —
but strictly they sit outside EC-02's enumerated site list. The subagent
consulted its own advisor before making this call; the orchestrator
judges the fix correct and proportionate (halting the run over a two-line
budget-comment re-pin would be disproportionate), but flags it here as a
gap in the spec's own EC-02 table for the record, per this project's
"spec drift" rule — future spec authors covering a prompt-literal change
should grep the whole file for every string-length-dependent test, not
just the ones a first pass finds. Also fixed for free by the same
ASCII-substitution decision (em dash `—` → repo-convention `--`, since a
pre-existing ASCII-purity test on tool descriptions would otherwise fail
regardless of EC-02): `test_pfx_02_the_descriptions_stay_ascii_and_quote_free`
and the two 1800-char catalog-budget tests, neither of which needed a
limit change once the substitution was made.

PRM-02, gate 7 live exactly twice, in sequence (T1's earlier run is not
reused):

| | wall | `hybrid` recall@5 | TOOL-06 pin | context-proof |
|---|---|---|---|---|
| Before (unchanged tree) | 31.58s | 1.000 | fail — "turn 2 recorded no search_documents call sharing a token with turn 1's question (turn 2 queries: [])" | fail — "turn 3 recorded no search_documents call" |
| After (edited tree) | 32.16s | 1.000 | fail — identical message | fail — identical message |

No regression (`recall@5` well above its 0.8 floor both times); the
advisory smoke verdicts are **unchanged** — the literal change did not
move this particular smoke's outcome. Recorded verbatim per NG-07, not
repaired, not a defect — the carried tail (report-v1.9.4.md:680-690,
report-v1.10.0.md:441) stays open as a "recorded, not fixed" item for a
future release to revisit with a different lever than prompt wording.

Gates 1-4 green both before and after (pytest full suite). Orchestrator
independently re-verified the 736-char count and a fresh full `pytest -q`
run, both green.

Delegated (general-purpose subagent, brief `docs/spec/task-briefs/v1101-T4.md`).
Commit `ac39435`. Map vs actual: the two extra test re-pins above (disclosed).

## T5 — clean-context review (REV-01) and its fixes

Review by the `code-reviewer` subagent, its own clean context, commits
`1d96ca0..HEAD` (T0-T4), against the standard checklist plus REV-01's
nine spec-specific items. Prompt logged at `docs/prompts/208-v1101-t5-review.md`.

**Verdict: request changes.** One 🔴 must-fix, five 🟡 should-fix, one 🟢
note; the nine spec-specific items otherwise checked out cleanly
(quoted findings below, abridged):

- 🔴 **`INJ02_ANY_OF` never gained `refuse`** (RT-02's literal "becomes
  exactly" seven-alternative regex) — T3's commit disclosed keeping the
  existing six-alternative string as a choice, but the spec's instruction
  wasn't ambiguous; the gap was invisible to the test suite (a new test
  exercised the *correct future* marker set against a locally-scoped
  fixture, never against the production constant). Concrete gate-8
  false-miss risk on INJ-02 identified. **Fixed**: `devtools/agent_eval.py:133`
  and `evals/agent/red_team.json`'s INJ-02 `any_of` both gain `|refuse`;
  `tests/test_v1100_red_team.py`'s stale pin updated; a new direct test
  (`tests/test_v1101_red_team.py`) pins the constant against the spec's
  literal so this class of gap can't recur silently. Dataset re-frozen:
  `02b53feba5592327f8e36012ceb5b1baea5da544e9fa1e4c664a2ea6cff2652d`
  (supersedes T3's hash — the one authorized post-freeze edit, a
  pre-live-gate compliance fix, not the RT-05/NG-04-forbidden
  fix-a-red-gate-8-by-editing-a-case pattern).
- 🟡 PRM-01/02/03 tests relocated into a new `tests/test_v1101_prompt.py`
  (TST-01 names a module; T4's subagent had added one test inline at
  `tests/test_v190_tool.py` outside EC-02's site list, mislabeled PRM-01
  when it proved PRM-03). **Fixed**, plus the two PRM-01 assertions
  (exact-once, old-line-absent) that were missing entirely are now
  present.
- 🟡 Two `tests/test_v1101_runner.py` tests claimed to be
  `T-V1101-ERR-01` rows 7/8 but actually re-verified pre-existing
  v1.10.0 `LLMError`-abort paths; the real row-7/row-8 coverage already
  existed under RT-05/RT-09 names. **Fixed**: renamed away from the false
  claim, pointer comments added at the real coverage sites.
- 🟡 `T-V1101-GC-06`'s NUL-in-key case (`{"A\0B": "x"}`) was untested.
  **Fixed**, verified empirically against the real raw-NUL error message.
- 🟡 `tests/test_v190_agents.py:279-291` (T2's disclosed amendment,
  outside EC-02's site list, forced by the yaml repoint) — reviewer's
  concern is procedural (the spec's "exhaustive" table should have been
  amended as a delta) rather than a code defect; **not fixed** (no code
  change needed), but flagged again here for T7/T8's awareness since the
  same pattern may recur.
- 🟢 A dedicated `T-V1101-GATE-03` "27 rows" count test doesn't exist yet
  — informational, likely T6's natural home once the mutation entries
  land; no action this task.

Gates 1-4 green (pytest 2029 passed / 1 skipped). Orchestrator
independently re-verified the dataset hash and a fresh full `pytest -q`
run, both green.

Delegated: review by `code-reviewer` (clean context); fixes by a
general-purpose subagent, brief `docs/spec/task-briefs/v1101-T5.md`.
Fix commit `5433f3b`.

## T6 — not reached: T5

## T7 — not reached: T5

## T8 — not reached: T5

## Ledger row (paste into `economics.md`)

Provisional — filled finally at T7/T8 (placeholder shape matches
`ledger_header`'s 11 columns, precedent v1.10.0 T6 commit `761359a`):

```
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
```
