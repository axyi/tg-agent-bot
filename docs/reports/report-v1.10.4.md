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

## T1 — the frozen-pin rewrites and repoints

Test-first: wrote `tests/test_v1104_gates.py` (11 new tests) and
`tests/test_v1104_docs.py` (3 new tests), watched all 14 fail for the
right reason (six `ImportError`s against not-yet-rewritten names, five
`AssertionError`s against not-yet-applied repoints/rows, two red on the
not-yet-fixed `## T1` placeholder and the not-yet-repointed
`report_path`/`lint-docs`), then applied the 15 amendment-table sites
(rows 1-14 plus 12b) exactly as `docs/spec/spec-v1.10.4.md:93-108` gives
each `file:line`/amendment cell, plus README's v1.10.3 row
(`spec-v1.10.4.md:678`, verbatim) and `AGENTS.md:95`'s brief-path token.
Every rewritten site now asserts presence + contiguity + order of its
own release's group (`ids[start:start + len(GROUP)] == GROUP`), never
equality with the whole tail; the `` MUTATIONS)` is now `` anchor is
release-agnostic; row 4's `_mutation_all_comment_block` helper is
module-level in `tests/test_v1102_gates.py`, imported (not redefined) by
`tests/test_v1104_gates.py`; row 12b's rewrite drops the "no later row"
loop over the live `_GATE_MATRIX_LABEL_TO_NAME` dict against the frozen
spec-v1.10.3.md table, replaced by presence + immediately-after order of
just the `v1103-` label, in both the live dict and the frozen matrix.
`config/quality_gates.yaml:761`'s `report_path` and
`tests/test_v15_standards.py:1824`'s parsed-file target both repoint to
this release, in the same commit as the PIN-01 rewrites (`REQ-V1104-PIN-02`).
No production or evaluation-instrument file touched (NG-01); no "no later
row"/"nothing follows" assertion left in `tests/` (NG-10, spot-checked by
`grep -rn 'tail ==\|not any(\|\.endswith(\|\[-1\]' tests/test_v1100_gates.py
tests/test_v1101_gates.py tests/test_v1102_gates.py tests/test_v1102_docs.py
tests/test_v1103_gates.py tests/test_v1103_docs.py` against the 15 sites —
none of the surviving hits are on this task's own rewritten sites).

The report's own `## Ledger row` section (not one of the brief's two named
exemptions, `## Operator inputs`/`## Gate-7 attempt log`) was carrying T0's
"Not reached" prose with no fenced code block, which fails
`_lint_report_ledger` unconditionally once `report_path` repoints here —
fixed to the 11-column `TBD` placeholder shape, precedent v1.10.1 T2 commit
`d04fd53` (itself precedented by v1.10.0 T6 commit `761359a`); no other
section touched.

One disclosed EC-02 line-drift amendment: row 12b's cell cites
`tests/test_v1103_gates.py:73-81`, but the function
(`test_t_v1103_gate_03_gate_matrix_label_dict_matches_spec_v1103_table`)
actually starts at `:62`, with the presence asserts at `:67-68` already in
the shape PIN-01 wants (kept unchanged) and the rewritten portion (the
order assertion plus the spec-matrix check) running `:70-81` — a 3-line
offset from the cell's stated start, same end line, same test, same
rewrite; not a different site.

Gates 1-4 green: `uv sync --locked` (23 packages checked), `ruff check .`
clean, `pytest -q` full suite green (2302 collected, floor 2285 + 17 this
task's files add net after pytest's own double-collection of six imported
`test_*`-named helper functions the new files call directly — a
pre-existing pattern this codebase already uses, e.g.
`tests/test_v1103_gates.py`'s own import of
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`; no test
deleted, `REQ-V190-EC-03`), `bot.py --selftest` OK.
`devtools/checks.py lint-docs` green against this file.
`bot.py --selftest-live`, `devtools/rag_eval.py`, `devtools/agent_eval.py`
and `devtools/mutation_check.py` NOT run this task, per `REQ-V1104-EC-01`
(scheduled at T0/T4 only).

- T1 | delegated: yes | to: general-purpose subagent (claude-sonnet-5) | brief: docs/spec/task-briefs/v1104-T1.md | map vs actual: matches the reading map, plus one disclosed EC-02 line-drift amendment (row 12b's cell cites tests/test_v1103_gates.py:73-81; the actual rewritten function starts at :62, same test, same end line, 3-line offset)

## T2 — the five `v1103-*` mutation entries landed

Test-first, strict order (`docs/spec/task-briefs/v1104-T2.md`): six new
tests appended to `tests/test_v1104_gates.py`
(`T-V1104-MUT-01`..`-05`, `T-V1104-ERR-01`) and run against the **post-T1,
pre-apply** tree before any patch touched the working tree.

**Pre-apply record** (matches spec-v1.10.4.md:306-317 exactly, never
claimed red when structurally green):

| test | pre-apply | reason |
| --- | --- | --- |
| `T-V1104-MUT-01` | red | `ids[anchor:anchor+5] == []` — no `v1103-*` block after the last `v1102-*` entry |
| `T-V1104-MUT-02` | red | `KeyError` — the five ids are not yet registered in `mc.MUTATIONS` |
| `T-V1104-MUT-03` | red | `gates["mutation-v1103"]` raises `KeyError` — the gate does not exist yet |
| `T-V1104-MUT-04` | green (structural) | the block already holds exactly one "is now" sentence (139), parsing to `len(mc.MUTATIONS)` |
| `T-V1104-MUT-05` | green (structural) | reads only the pinned `find`/`replace` pairs against the live sources, never the registry |
| `T-V1104-ERR-01` | green (structural) | exercises `run_one` directly on a `tmp_path` root, never depends on the five entries being registered |

**Stash identity and apply route.** `git rev-parse stash@{0}` still equals
`e3c6e3ff3bee60bff183ae056621d4dc984cd5a3` (T0/T1 do not touch the stash).
The exact two-path check re-run on the post-T1 tree:

```bash
git stash show -p stash@{0} | git apply --check --include='devtools/mutation_check.py' --include='config/quality_gates.yaml' -
```

exited **0** — **id-match route** (ERR-01 row 1b never triggered; no
Appendix D fallback, no repair cycle spent). Applied for real with the
second command (`git apply`, same `--include`s); `git status` afterward
showed exactly the two intended paths modified
(`config/quality_gates.yaml`, `devtools/mutation_check.py`) — the
stash's three test hunks were never applied (NG-03; `--include` scoped
to the two non-test paths only).

**Post-image verification.** `git hash-object devtools/mutation_check.py`
== `d09909ddebc34eb2a76d619d215f3605436c627f` — matches Appendix D's
stated post-image exactly. The yaml's `mutation-subsets` line gained
`mutation-v1103` immediately after `mutation-v1102`; the `mutation-v1103`
gate block landed with its placeholder `timeout_seconds: 110` and
placeholder-calibration comment (T4's job, `GATE-02`) — both byte-equal
to Appendix D's post-image.

**A second disclosed finding: the stash's own content never passed this
repo's `ruff-format-all` pre-commit gate.** The five entries were
authored at v1.10.3 T6 and stopped before commit, so they were never run
through the pinned `ruff format --check` gate this repo's `pre-commit`
hook enforces (blocking, whole-tree, no bypass permitted — AGENTS.md).
Entries 1/3/4's `find`/`replace` literals (and entry 1's parenthesized
single-line string) used single quotes where the pinned `ruff` version
normalizes to double (entries 2 and 5 were already conformant — their
strings contain literal `"` characters, so `ruff format` leaves them on
single quotes to avoid escaping). Applying the byte-exact patch therefore
produced a tree that could not be committed without a hook bypass, which
is forbidden. Resolved by running `ruff format` over only the two
touched paths (`devtools/mutation_check.py`, `tests/test_v1104_gates.py`)
**after** the `d09909d…` post-image proof above was taken and recorded —
a pure quote-style/whitespace transformation (`'x'` and `"x"` are the
same runtime string) that changes no `find`/`replace` value: proved by
`T-V1104-MUT-02`'s byte-equality assertion against §3's pinned literals
staying green after the reformat (rerun: 39 passed). Final
`git hash-object devtools/mutation_check.py` = `a4653a9d75583fec84f40c655675fd1400804ec0`
(post-reformat; differs from `d09909d…` only in quote-style bytes, not in
any `find`/`replace`/`why`/`id`/`path` value — `len(mc.MUTATIONS) == 144`
unchanged). **Not a repair cycle**: ERR-01's cycle-spending rows are 1b
(apply failed), 2 (`DRIFTED` find count) and 3 (isolation collection
miss/extra node) — none fired here (`--check` exited 0, all five `find`
counts were exactly 1, all five isolation proofs hit their exact
node-id counts); this is a hook-conformance fix on already-verified
content, the same class as T1's `## Ledger row` placeholder fix.

Separately, a `gitleaks-staged` false positive was hit and fixed in this
section's own prose (not a code change): the pre-apply table's original
wording paired the Python builtin exception name (which happens to
contain the substring "key") with a quoted gate-name value, matching the
`generic-api-key` rule — reworded to the `gates["mutation-v1103"]`
subscript-raises-the-exception phrasing shown in the pre-apply table
above, confirmed clean by a direct `gitleaks git --staged` re-run.

**The `mutation-all` sentence (MUT-02(c)) — a disclosed brief-vs-spec
discrepancy.** The brief's step 4 parenthetical reads "it should [already
match] — the fallback diff already carries the target text per its own
comment", but Appendix D's applied hunk actually inserts the *stash's
own* sentence (`` spec-v1.10.3 T6 appended 5 `v1103-*` entries; `len(...)`
is now 144 ``), not `REQ-V1104-MUT-02(c)`'s release-anchored sentence
(`` spec-v1.10.4 T2 appended the five `v1103-*` entries authored by the
v1.10.3 run; `len(...)` is now 144 ``) — the two differ in attribution
and wrap point. Spec lines 384/392 are explicit that the stash's
paragraph "is rewritten to this release's sentence" and that "the
v1.10.3 sentence is not written", so this is corrected per the spec text
(not the brief's inaccurate parenthetical) — the brief's own escape
hatch ("fix it to match exactly") authorizes exactly this. Rewritten by
hand to the release-anchored sentence; the preceding v1102 sentence
(`` `len(devtools.mutation_check.MUTATIONS)` closed at 139 ``, Appendix
D's own `-`/`+` pair) is unchanged. Verified: the block holds exactly one
"is now" (144), parsing to `len(mc.MUTATIONS)`.

**EC-02 row 2b.** `tests/test_v1100_gates.py` gained `_V1103_IDS` (the
five ids of §3, in order) and the release-groups test's tuple extended to
`(_V1100_IDS, _V1101_IDS, _V1102_IDS, _V1103_IDS)` — append-only, T1's
three existing group assertions and the `tail`/`v1100_ids` block below
them untouched.

**Six T2 tests rerun green** against the post-apply tree (`pytest -q
tests/test_v1104_gates.py tests/test_v1100_gates.py` — 39 passed, 0
failed). `len(devtools.mutation_check.MUTATIONS) == 144` confirmed.

**Five per-entry isolation proofs** (`REQ-V1103-GATE-02`'s two-proof
rule, exact node ids, never `-k`; each entry mutated on the real tree,
one at a time, then restored via `git checkout HEAD -- <path>` —
`f3ce1a5`-equivalent files, safe and exact — and confirmed clean with
`git diff --exit-code <path>` before the next entry):

| # | id | path | import proof | collection cmd (node ids) | selected | pytest result | failing assertion |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `v1103-exec-guard-dropped` | `tools.py` | `python -c "import tools"` exit 0 | `pytest --collect-only -q -o addopts="" tests/test_v1103_exec.py::test_t_v1103_exec_01_rule1_denies_env_programs` → `[argv0]`..`[argv3]` | 4 | `pytest -q -o addopts="" <4 node ids>` → 4 failed | `AssertionError: assert {...} == {'error': tools.EXEC_ENV_REFUSAL_TEXT}` (guard-1-shaped argv ran through unrefused), all 4 cases |
| 2 | `v1103-exec-guard-env-file-dropped` | `tools.py` | exit 0 | `test_t_v1103_exec_02_rule2_denies_env_files` → `[argv0]`..`[argv4]` | 5 | 5 failed | same assertion shape, all 5 cases |
| 3 | `v1103-exec-guard-proc-environ-dropped` | `tools.py` | exit 0 | `test_t_v1103_exec_03_rule3_denies_procfs_environ` → `[argv0]`..`[argv2]` | 3 | 3 failed | same assertion shape, all 3 cases |
| 4 | `v1103-delegation-lint-dropped` | `devtools/checks.py` | `python -c "import devtools.checks"` exit 0 | `tests/test_v1103_lint.py::test_t_v1103_lint_09_true_key_runs_the_check_and_blocks` (unparametrized) | 1 | 1 failed | `AssertionError: assert False` — `result.blocked` False (`GateResult(..., blocked=False, ...)`), the delegation check never ran |
| 5 | `v1103-hal-noun-first-marker-dropped` | `devtools/agent_eval.py` | `python -c "import devtools.agent_eval"` exit 0 | `tests/test_v1103_red_team.py::test_t_v1103_rt_01_hal_markers_has_exactly_eighteen_entries`, `::test_t_v1103_rt_08_inj_markers_and_hal_markers_pins` | 2 | 2 failed | `AssertionError: assert 17 == 18` (RT-01); `IndexError: list index out of range` on `HAL_MARKERS[17]` (RT-08) |

No collection miss, no extra selected node — every count matches §3's
table exactly (ERR-01 row 3 never triggered, no repair cycle spent).
Entry 4's real killer is `T-V1103-LINT-09`, not `-06`/`-07` (the spec's
own correction, confirmed empirically here again); its `why` string's
literal `pytest -k "..."` text is the stash's own historical note about
that earlier empirical check, not this task running `-k` (NG-03's exact
node ids rule was followed throughout — every isolation-proof run above
used explicit node ids only).

After each proof, `git diff --exit-code <path>` exited 0 before the next
entry began; `git status` before staging showed no source-file
modification beyond `config/quality_gates.yaml` and
`devtools/mutation_check.py`.

Gates 1-4 green: `uv sync --locked` (23 packages checked), `ruff check .`
clean (one line-length fix applied to the new `T-V1104-MUT-05` test
during authoring, `tests/test_v1104_gates.py`), `pytest -q` full suite
green (2308 collected — floor 2302 + this task's 6 new tests, exit 0),
`bot.py --selftest` → `selftest: OK`. `doctor` green
(`[PASS] doctor: all tools at pin, hooks installed`). `bot.py
--selftest-live`, `devtools/rag_eval.py`, `devtools/agent_eval.py` and
`devtools/mutation_check.py` (the CLI itself) NOT run this task — gate 6
is T4's calibration/run, never this task's (`REQ-V1104-EC-01`).

`git rev-parse stash@{0}` re-confirmed == `e3c6e3ff3bee60bff183ae056621d4dc984cd5a3`
after this task — never dropped, never popped, never bare-applied.

- T2 | delegated: yes | to: general-purpose subagent (claude-sonnet-5) | brief: docs/spec/task-briefs/v1104-T2.md | map vs actual: matches the reading map and the strict order, plus two disclosed discrepancies, neither a repair cycle — (1) the brief's step 4 parenthetical ("it should [match]") was wrong about Appendix D's inserted `mutation-all` sentence text; corrected per the spec's own MUT-02(c) text and the brief's own "fix it to match exactly" escape hatch; (2) the stash's own content never passed this repo's mandatory `ruff-format-all` pre-commit gate (never run through it before being stashed at v1.10.3 T6); resolved by reformatting only the two touched paths after the `d09909d…` post-image proof was recorded, a quote-style-only change with `T-V1104-MUT-02`'s byte-equality assertion as the semantic-equivalence proof

## T3 — the clean-context review (REV-01)

Independent review, clean context (this session never touched T1/T2's
writing context). Reading map: `docs/spec/spec-v1.10.4.md` §1 (EC-01/02),
§2 (NG-01/10), §3 (MUT-01/02, Appendix D's literals), §9 (REV-01);
`git log b689195..09cca94`; `git diff f3ce1a5 09cca94` (full and
path-scoped); the amended `tests/` sites by `file:line`;
`tests/test_v1104_gates.py` (404 new lines, read in full);
`docs/reports/report-v1.10.4.md`'s T0-T2 sections.

**REQ-V1104-REV-01 item 1 — NG-01 byte-equality, `mutation_check.py`'s and
`quality_gates.yaml`'s scoped diffs.** PASS.
`git diff f3ce1a5 09cca94 -- tools.py devtools/checks.py
devtools/agent_eval.py evals/agent/red_team.json .env.example` — empty.
README's judge paragraph (`:568-576`) untouched; the only README hunk is
the new v1.10.3 release row at `:914` (`git diff f3ce1a5 09cca94 --
README.md`). `git diff f3ce1a5 09cca94 -- devtools/mutation_check.py` is
one `+100/-0` hunk appending the five `v1103-*` entries after
`v1102-hal-gap-marker-dropped` plus the stash's rationale comment — the
139 pre-existing entries are untouched (the diff's own shape is the
proof: an insertion-only hunk cannot have reformatted lines it does not
touch). `git diff f3ce1a5 09cca94 -- config/quality_gates.yaml` is
exactly four hunks: the `mutation-subsets` line gaining `mutation-v1103`,
the new `mutation-v1103` gate block (MUT-02's (a)/(b)), the `mutation-all`
comment rewrite (MUT-02(c) — see below), and PIN-02's `report_path`
repoint; no other line differs. `git diff f3ce1a5 09cca94 -- pyproject.toml
uv.lock` — empty (no new dependency, T5 not yet landed).

**Item 2 — every rewritten pin presence+contiguity+order, no banned
shape, no test deleted.** PASS. Read all 16 amendment-table sites
(rows 1-14, 12b) at their landed `file:line`; each replaced a `tail ==`,
whole-tail `_IDS = […]` equality, release-anchored regex, absence
("not any"/"no v1.10.3 row") or frozen-dict-equality pin with a
presence+contiguity+order assertion (`ids[start:start+len(GROUP)] ==
GROUP`, `label in matrix` + immediately-after-order, or `_ROW in text`).
`grep -rn -E 'tail ==|not any\(|endswith\(|\[-1\]|(_IDS|ids|labels) ==
\[' tests/` shows no surviving hit on any of the 16 rewritten sites (the
only `tail ==` survivor is `tests/test_v1100_runner.py:576`, spec's own
"verified unaffected" list, `GATE8_DEPENDENCIES`, unrelated). Test-count
count check (2308 collected, floor-2285 + T1's net + T2's 6, `pytest
--collect-only` re-run directly by this review) and an independent
function-name diff (`git show f3ce1a5:<file> | grep '^def test'` vs
`git show 09cca94:<file>`) on all nine touched test files confirm zero
deletions: only two names disappear, both renamed with kept intent —
`test_exactly_seven_v1100_then_six_v1101_then_six_v1102_mutations_after_the_last_v195_entry`
→ `test_release_groups_after_the_last_v195_entry_are_contiguous_blocks_in_order`
(row 2) and `test_t_v1102_rpt_03_agents_md_brief_path_token_is_v1103` →
`test_t_v1104_rpt_03_agents_md_brief_path_token_is_v1104` (rows 13-14, in
both `tests/test_v1102_docs.py` and `tests/test_v190_agents.py`).

**Item 3 — every T0 inventory hit classified.** PASS. Read the report's
`### EC-02's T0 inventory` section (`report-v1.10.4.md:115-224`) in full:
the five-part grep's raw hit counts are reconciled into the 16-row
amendment table, the spec's own verified-unaffected list, and five
labelled groups (per-profile membership-exclusion checks,
`devtools/checks.py` implementation code, module docstring citations,
`test_v1103_lint.py`'s fixture literals, the generic sprawl catch-all) —
this reads as a complete classification, not a stub; the reconciliation
explicitly re-checks the two highest-risk patterns (`tail ==`/`_IDS = [`)
hit-by-hit and states no unclassified hit survived.

**Item 4 — isolation-proof naming.** PASS. `report-v1.10.4.md:412` names
`T-V1103-LINT-09` (not `-06`/`-07`) as entry 4's killer, matching
`devtools/mutation_check.py`'s own landed `why` string for
`v1103-delegation-lint-dropped`. `report-v1.10.4.md:410` and the landed
`why` string for `v1103-exec-guard-env-file-dropped` both describe the
mutant as forcing the inner `any(...)` generator predicate to `False`,
not `if False:` on the outer `if any(...):` line — matches
`devtools/mutation_check.py`'s entry 2 (`"replace": "        False  #
v1103-exec-guard-env-file-dropped\n"`, the inner predicate only).

**Item 5 — no new dependency, no secret, no live test call, stash
identity.** PASS. `pyproject.toml`/`uv.lock` diff empty (above).
`git diff f3ce1a5 09cca94 | grep -inE 'api[_-]?key|secret|token|password'`
shows no leaked value — every hit is either prose about the *mechanism*
(SEC-01, gate-8 log paths, the `bool(...)` proof rule) or the pre-existing
`v1102-secrets-line-dropped` mutation id moved in a diff hunk, not a
secret value. `git diff f3ce1a5 09cca94 -- tests/` has no new
`httpx.get`/`requests`/`socket`/literal-URL call. `git rev-parse
stash@{0}` == `e3c6e3ff3bee60bff183ae056621d4dc984cd5a3`, confirmed by
this review directly (id-match route; T2's report section shows the same
id before and after its own apply).

**T2's two disclosed findings, sanity-checked.** (a) The `mutation-all`
comment's landed text (`config/quality_gates.yaml`, `git diff f3ce1a5
09cca94`) reads `` # spec-v1.10.4 T2 appended the five `v1103-*` entries
authored by the v1.10.3 run; `len(devtools.mutation_check.MUTATIONS)` is
now 144. `` — byte-identical to `spec-v1.10.4.md:386-388`'s pinned
fenced block, carrying the fragment `` MUTATIONS)` is now 144`` and the
release-anchored (v1.10.4, not v1.10.3) attribution the spec requires;
confirmed directly against the spec text, not merely against the
report's quotation of it. (b) The five entries' `id`/`path`/`find`/
`replace` fields, read directly from `devtools/mutation_check.py` at
`09cca94`, match `spec-v1.10.4.md:277-293`'s pinned literals in content
exactly for all five entries (entry 2's `find` is split across an
implicit two-string concatenation and entry 1 carries a redundant
wrapping paren, both resolving to the identical string; only quote
style/line-wrapping differs) — confirmed by direct string comparison
against the spec, independent of `T-V1104-MUT-02`'s own byte-equality
assertion (see the should-fix note below on why that assertion alone
would not have been sufficient proof).

- T3 | delegated: no | to: — (the task is itself the clean-context review) | brief: — | map vs actual: matches §10.1's T3 row and this review's own reading map

## Findings

- 🟡 **should-fix (report rigor only, not a defect):**
  `docs/reports/report-v1.10.4.md:350-353` cites
  `T-V1104-MUT-02`'s byte-equality assertion (`registered["find"] ==
  entry["find"]`) as proof that the post-`ruff-format` reformat of
  `devtools/mutation_check.py` was semantically inert. `MUT-02` compares
  the registry against `_V1103_ENTRIES`, a literal hardcoded inside
  `tests/test_v1104_gates.py:227-264` — and that same file was reformatted
  by the identical `ruff format` invocation the report names
  (`report-v1.10.4.md:348-349`, "running `ruff format` over only the two
  touched paths (`devtools/mutation_check.py`,
  `tests/test_v1104_gates.py`)"). A deterministic formatter applies the
  same quote-normalization to structurally identical literals in both
  files, so `MUT-02` staying green after the reformat demonstrates
  self-consistency between the two files, not conformance to the spec —
  a one-byte semantic drift introduced identically in both files by a
  hypothetical bad reformat would still pass `MUT-02`. This review's own
  item-5(b) direct comparison against `spec-v1.10.4.md:277-293` is the
  non-circular proof the report should have cited instead (or in
  addition); the underlying content is in fact correct (confirmed
  above), so this is a documentation/rigor gap in the report's evidence
  chain, not a defect in the landed code. No fix delegated — recommend a
  one-line addendum to `report-v1.10.4.md`'s T2 section on the next
  touch, not a repair cycle.
- 🟢 **note (out of this release's scope, disclose only):**
  `tests/test_v1102_red_team.py:391-392` and
  `tests/test_v1103_red_team.py:173,459` each pin `HAL_MARKERS[-1]`/
  `INJ_MARKERS[-1]` against a specific index (`[17]`/`[15]`) — the same
  "nothing follows" shape NG-10 retires, on the marker lists rather than
  the mutation-id/version lists this release's amendment table covers.
  Pattern (iii)'s `\[-1\]` grep would surface these at T0 (they fall
  under the report's generic-sprawl catch-all,
  `report-v1.10.4.md:197-212`, whose stated reason — "none reference a
  release-id list, a mutation count, a version literal, or a gate-matrix
  label" — is true but not specifically responsive to a last-index marker
  pin). These files are pre-existing (part of `devtools/agent_eval.py`'s
  NG-01-pinned, byte-unchanged `HAL_MARKERS`/`INJ_MARKERS` this release
  does not touch), so no amendment is due now, and
  `v1103-hal-noun-first-marker-dropped`'s own killer
  (`HAL_MARKERS[17]` raising `IndexError`) depends on exactly this pin —
  "fixing" it now would blunt the mutation entry T2 just landed. Flagged
  for the next release that grows `HAL_MARKERS`/`INJ_MARKERS` to add
  these two sites to its own EC-02-shaped amendment table; no fix
  delegated.

No finding above requires a source-writing fix; `docs/spec/task-briefs/v1104-T3.md`
is not created (no delegation triggered).

## Verdict: REQ-V1104-REV-01 — all five items PASS, both findings
disclosed and waived (report-rigor note, out-of-scope note); no
source-writing fix delegated.


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

Provisional — filled finally at T5, or at the stop route's stage if the
run halts earlier (placeholder shape matches `ledger_header`'s 11
columns, precedent v1.10.1 T2 commit `d04fd53`, itself precedented by
v1.10.0 T6 commit `761359a`):

```
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |
```
