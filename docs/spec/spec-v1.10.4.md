# spec-v1.10.4 — the five `v1103-*` mutation entries landed, every frozen-list test pin rewritten to presence-contiguity-order, the single gate 8 the stop route never reached, and the release rows three stopped runs left pending

Status: draft — cross-review round 1 of at most 3 applied (Appendix C;
its opening paragraph is a placeholder until the last round closes).
Base: `main` at `f3ce1a5` (tree clean, **72 commits ahead of
`origin/main`**, unpushed by the operator's choice); last tag `v1.9.5` =
`a3e0a93`. spec-v1.10.3 is **implemented through T5**; its T6 mutations
part was authored and verified but never committed — the run ended
through the budget-exhaustion stage at T6, **before gate 8**
(`docs/reports/report-v1.10.3.md:582-635`); the five `v1103-*` entries
sit in `stash@{0}` = `e3c6e3ff…` (MUT-01; Appendix D carries its
two-path diff verbatim) (`v1103-T6 mutations part: uncommitted at
stop route (tests/test_v1102_gates.py:80-87 unlisted pin, 0/3 budget)`);
`pyproject.toml:3` still reads `1.9.5`; no `v1.10.0`…`v1.10.3` tag
exists. Earlier mechanisms are
referenced by `REQ-V1103-*` / `REQ-V1102-*` / `REQ-V1101-*` id and
`file:line`, never restated. Target version: **1.10.4** — PATCH, **no
new mechanism**; `pyproject.toml` `1.9.5` → `1.10.4` directly; tag
`v1.10.4`, **local only — this run pushes nothing** (EC-01).

One subject: land the five `v1103-*` entries the v1.10.3 run authored
and verified but could not commit (§3), rewrite every frozen-list test
pin that would stop the next release the way the last one was stopped
(PIN-01), run the live gates with the single gate 8 the stop route
never reached (§7), ship 1.10.4 with the release rows three stopped
runs left pending (§8). Same instruments, floors and stop route. A
DELTA specification on `f3ce1a5`.

Ids: `REQ-V1104-<GROUP>-NN`, MUST or NON-GOAL; tests `T-V1104-*`; **no
`v1104-*` mutation id** (§3); tasks T0…T5. Authoring prompt
`docs/prompts/227-v1104-spec-authoring.md`; run prompts from **228**;
`docs/llm-usage.md` from row **139** (138 is authoring).

---

## 1. Execution contract

**REQ-V1104-EC-01 (MUST) — boundary, network, dependencies, budget, no
push, the benchmark rule.** `REQ-V1103-EC-01`
(`docs/spec/spec-v1.10.3.md:45-84`) applies unchanged, with these
adjustments: the eight gate commands (`AGENTS.md:148-159`) and every
gate key stay; the profiles change by one entry (MUT-02); the repair budget is
**3 total** cycles **for red gates of construction only** — a test pin
the T0 inventory missed spends none (EC-02); exhausted → §9. **The
filesystem boundary** is `spec-v1.10.1.md:46-58` by reference (never a
direct read of `.env`, `data/`, `docs/assets/`, `bot.db`,
`exec_audit.jsonl`); the gate-8 capture is the one permitted file
outside the repository (`spec-v1.10.2.md:51-57`),
`${TMPDIR:-/tmp}/v1104-gate8-${tested_tree}.log`; **the stash is
identified by `git rev-parse stash@{0}` =
`e3c6e3ff3bee60bff183ae056621d4dc984cd5a3` (MUT-01), read with `git
stash show -p stash@{0}` and tested with `… | git apply --check -`
only** — never `pop`, `apply` or `drop` (NG-03). **The
network this release needs is exhaustive**: T0's preflight (Stage 0
checks 3–6, `spec-v1.10.1.md:1141-1165`, check 6 with
`REQ-V1103-INS-01`'s single fallback, `spec-v1.10.3.md:238-308`); gates
5 and 7 at T0, T4, T5 under `REQ-V1102-GATE-01`'s transient rule
(`spec-v1.10.2.md:749-828`), **never at T1–T3**; gate 8 **once at T4,
never at T5** (GATE-01); `uv lock` (online) at T5; the stop procedure
may invoke gates 5 and 7 once each, never gate 8 — **once T4's gate 5
and gate 7 have completed, no stop route may invoke any live gate
again. Stage B′ reuses T4's already-recorded gate-5, gate-7 and gate-8
results; finalisation runs only offline checks. The stop-route
permission to invoke gates 5 and 7 applies only before their scheduled
T4 execution** (GATE-01, REV-03). No `bench.py`; no LM
Studio; no offline test reaches a socket (`tests/conftest.py:10-28`).
**Zero new dependencies**: `pyproject.toml:6-14`, `:16-21` unchanged;
`T-V1104-VER-02` pins that **for `pyproject.toml` and `uv.lock` only,
the diff from the `f3ce1a5` blobs is project-version-only according to
`dependency_diff_is_version_only` (`devtools/agent_eval.py:1279`); no
claim is made that the whole repository diff is version-only**; T0
records `git diff --stat f3ce1a5 -- pyproject.toml uv.lock` (empty).
**No push**: the operator pushes the 72 pending commits, this run's and
the tag together, later. **The benchmark rule is not triggered** (no
prompt, tool-schema or model change): `AGENTS.md:274-279`'s waiver
paragraph is **unchanged** (NG-04); no bench run.

**REQ-V1104-EC-02 (MUST) — test-first, the floor, the exhaustive
amendment list, the four-part fail-closed T0 inventory, and the rule
that a missed pin is an amendment, never a cycle.** Write §6's tests, watch them fail
for the right reason, then implement in §10's order. Every MUST has a
named test, a negative test, a Gherkin scenario or a recorded artefact
(Appendix A). **The floor**: `f3ce1a5` collects **2285** tests by `uv
run --locked pytest --collect-only -q -o addopts="" | grep -c '::'`
(facts §7); T0 re-measures; T5's acceptance check is count ≥ floor +
**21** (TST-01). No test may be deleted (`REQ-V190-EC-03`). Tests
existing at `f3ce1a5` may be modified **only** at these sites:

| # | file:line | amendment | why | task |
|---|---|---|---|---|
| 1 | `tests/test_v1102_gates.py:80-87` | `assert tail == _V1102_IDS` → `start = last_v1101_index + 1; assert ids[start:start + len(_V1102_IDS)] == _V1102_IDS`; `:87` kept; the comment never says "nothing follows" | PIN-01 | T1 |
| 2 | `tests/test_v1100_gates.py:226-262` | renamed `test_release_groups_after_the_last_v195_entry_are_contiguous_blocks_in_order`; the 19-id `tail == […]` (`:237-256`) → `_V1100_IDS`, `_V1101_IDS`, `_V1102_IDS`, one assertion per group (`start = last_v195_index + 1`; `ids[start:start + len(GROUP)] == GROUP`; `start += len(GROUP)`); `:260-262` kept | PIN-01 | T1 |
| 2b | the same test | **T2 appends only** a fourth group `_V1103_IDS` (§3's five, in order) as one more assertion of the same shape; the next release adds a fifth, edits nothing | MUT-01 | T2 |
| 3 | `tests/test_v1101_gates.py:343-358` | `:352` `spec-v1\.10\.2 T5.*?MUTATIONS\)`\s*is now (\d+)` → `MUTATIONS\)`\s*is now (\d+)`; `:358` kept | PIN-01 | T1 |
| 4 | `tests/test_v1102_gates.py:131-145` | the same at `:140`; `:138` `text.count("is now") == 1` → `_mutation_all_comment_block(text).count("is now") == 1` (PIN-01's module-level helper) | PIN-01 | T1 |
| 5 | `tests/test_v1103_docs.py:84-99` | `:99` (`assert not any(… "\| v1.10.3 \|" …)`) → `assert _V1103_ROW in text` (VER-01's row verbatim); nothing asserted absent | VER-01 | T1 |
| 6 | `tests/test_v1102_docs.py:116-130` | `:130` the same replacement; the `:122-124` comment updated | VER-01 | T1 |
| 7 | `tests/test_v190_agents.py:298-299` | `report_path: docs/reports/report-v1.10.3.md` in → `…v1.10.4.md`; the `not in` pin → `…v1.10.3.md` | PIN-02 | T1 |
| 8–11 | `tests/test_v1101_gates.py:256`; `tests/test_v1102_gates.py:46`; `tests/test_v170_bench.py:327`; `tests/test_v1103_gates.py:58` | `report-v1.10.3.md` → `report-v1.10.4.md` (each; `:59` of the last kept) | PIN-02 | T1 |
| 12 | `tests/test_v15_standards.py:1824` | the parsed file becomes `docs/spec/spec-v1.10.4.md` (`:1793` already carries `v1103-`) | GATE-02 | T1 |
| 13–14 | `tests/test_v1102_docs.py:139-151`; `tests/test_v190_agents.py:92-95` | `v1104-T<N>.md` in, `v1103-T<N>.md` not in; renamed `…is_v1104`; `tests/test_v1102_docs.py:141-149` unchanged | RPT-03 | T1 |
| 15 | `tests/test_v195_version.py:18-22` | the live read → the `git show v1.9.5:pyproject.toml` blob read (`tests/test_v194_version.py:25-34`'s shape) | VER-01 | T5 |
| 16 | `tests/test_v190_agents.py:134-152` | `"1638"` / `"120 entries"` → T5's measured numbers; renamed `test_t_v1104_rpt_03_agents_md_count_lines_landed_at_t5` | RPT-03 | T5 |

**Verified unaffected at `f3ce1a5`** (the T0 hit table re-derives every
other hit with its reason): `tests/test_v1103_gates.py:73-81` — the
`v1103-` label is in this file's matrix and no `mutation-v1104` label
exists; a later release adding a label must treat `:77-81` as its EC-02
row; `tests/test_v1102_gates.py:28`, `:60`, `:76`,
`tests/test_v1103_gates.py:30`, `:34`, `:45-52` (earlier specs and
reports read by name, none edited); `tests/test_v1100_runner.py:576` (a
tail over `GATE8_DEPENDENCIES`); `tests/test_v1101_gates.py:266-282`,
`tests/test_mutation_check.py:132`, `:163-185` (prefix filters, lower
bounds).

**The T0 inventory is the primary tool; the amendment table above is
its expected result, not its input.** It is an explicit **four-part**
literal `grep` inventory over `tests/` **and `devtools/checks.py`** (no
AST tooling), run at T0 (commands only, before any live call):

- **(i) the frozen-list patterns**:

```bash
grep -rn -E 'tail ==|== _V1[0-9]+_IDS|_IDS = \[|tail\[|len\(mc\.MUTATIONS\)|len\(MUTATIONS\)|MARKERS\) ==|is now|report-v1\.10\.[0-9]|spec-v1\.10\.[0-9]|report_path|"1\.9\.5"|1638|120 entries|v110[0-9]-T<N>' tests/
```

  plus v1.10.3's literal list (`spec-v1.10.3.md:143-167`, `2` → `3` in
  the spec/report names);
- **(ii) every reference in `tests/` and `devtools/checks.py`** to
  `report_path`, `_GATE_MATRIX_LABEL_TO_NAME`, `_parse_gate_matrix`,
  `task-briefs/v1`, `project.version` / `["version"]`, `1638`,
  `120 entries`:

```bash
grep -rn -E 'report_path|_GATE_MATRIX_LABEL_TO_NAME|_parse_gate_matrix|task-briefs/v1|project\.version|\["version"\]|1638|120 entries' tests/ devtools/checks.py
```

- **(iii) the absence and end-of-list forms**: `not in`, `not any(`,
  `endswith(`, `[-1]`, and `== [` on a name ending in `_IDS` / `ids` /
  `labels`:

```bash
grep -rn -E 'not in|not any\(|endswith\(|\[-1\]|(_IDS|ids|labels) == \[' tests/ devtools/checks.py
```

- **(iv) fail-closed**: **every hit of (i)–(iii) is classified before
  T1** — either an EC-02 row (by number) or a one-line "unaffected
  because …" — in the report's T0 hit table (RPT-01); **an unclassified
  hit blocks construction until it is classified** (ERR-01 row 14) and
  spends no repair cycle.

**A pin the inventory missed, tripped after T0, is a
disclosed EC-02 amendment in the task's report section** (file, line,
amendment, intent kept) — **no repair cycle, never a stop**: EC-01's
cycles are for red gates of construction.
`REQ-V1103-EC-02`'s per-pin budget rule (`spec-v1.10.3.md:137-142`;
ERR-01 row 9 `:626`) is **explicitly superseded**, with the reason: four
pins, three cycles, a stop before the only live gate
(`report-v1.10.3.md:604-628`). Line movement of a listed site stays a
disclosed amendment. The executor never edits this spec.

**REQ-V1104-EC-03 (MUST) — delegation is specified, briefed by file, and
recorded in one shape.** `standards/workflow.md` §5.1 binds every task.
**Every task that reads or writes source is delegated and briefed by a
task-brief file** `docs/spec/task-briefs/v1104-T<n>.md`, written before
dispatch and passed by path — never retyped; it carries what is already
resolved (§3's strings, the rewrite shapes, T0's counts). **Committed briefs
`v1104-T1.md`, `-T2`, `-T4` and `-T5`, plus `v1104-T3.md` iff T3 delegates a
source-writing fix**; T0 is *commands only*; **T4's localized yaml
calibration hunk (GATE-02 step (1)) is delegated under
`docs/spec/task-briefs/v1104-T4.md`** while T4's calibration run,
gate 6, the write-tree and the live gate sequence stay *commands only*
(the T4 report section carries two bullets, one `yes` with the brief
and one `no` — the `T-V1103-LINT-01` T6 shape); **T5's brief covers
`pyproject.toml`, `uv.lock`, the tests and the documentation**; only
the four-path evidence commit is *artefacts only*. §10.1's `delegate` column defaults to **yes** for any
task that reads or writes source; a `no` carries a §5.1 exemption
**verbatim**; crossing the map live forces delegation. **The delegation record is `REQ-V1103-LINT-01`'s bullet
(`spec-v1.10.3.md:534-570`), lint-enforced**; the prefix `v1104` derives
from `report_path` (`:552-553`). The subagent returns a summary. Executor `claude-sonnet-5`; reviewer the pinned
`code-reviewer` (`model: sonnet`, `.claude/agents/code-reviewer.md:4`).

**REQ-V1104-EC-04 (MUST) — preconditions, no operator input, the prompt
chain, secrets.** The `go` request carries **no operator input**. Three
**preconditions**, each proved by an exit status, never by opening
`.env`: (1) `.env` carries **three run values** —
`OPENROUTER_MODEL=openai/gpt-4.1`,
`LLM_JUDGE_MODEL=openrouter:anthropic/claude-sonnet-5`,
`DB_PATH=data/run-v1104.db` (a fresh file; the lab rewrites only
`DB_PATH`, `docs/handoff-v1.10.3.md:16-21`) — T0 check 1 loads it
through `load_config()` and asserts `cfg.openrouter_model ==
"openai/gpt-4.1"`, `cfg.llm_judge_model ==
"openrouter:anthropic/claude-sonnet-5"` and `str(cfg.db_path)` ending
`data/run-v1104.db`; (2) `OPENROUTER_API_KEY` is set (`bool(…)` printed,
never the value); (3) the run database is empty — Stage 0 check 2,
printing only `db_empty=<bool>` (facts §8; numbered 2 as
`spec-v1.10.3.md:1105-1109` does, not 3 as `report-v1.10.3.md:39-44`
did). The judge route resolves as `REQ-V1100-EC-05` says, except
`REQ-V1103-INS-01`'s one recorded fallback to
`openrouter:openai/gpt-5.6-sol` (identity assertion, "shipped default
vs effective judge", by reference). Prompt
227 is committed with this spec; the run's prompts start at 228; one
prompt → one commit, never mixed (T5's two commits are one prompt,
REV-02; a stop-route evidence commit at T4 is REV-03's explicit
exception); `--no-verify` is never used and the report attests it.
**Secrets**: SEC-01; `gitleaks-tree` green on every commit; fixtures use
`VALUE-abcdefgh12`.

---

## 2. Non-goals

| id | NON-GOAL |
|---|---|
| `REQ-V1104-NG-01` | Any new mechanism, marker, prompt, tool-schema or model change: `tools.py`, `devtools/agent_eval.py`, `devtools/checks.py`, `evals/agent/red_team.json`, `.env.example` and README's judge paragraph (`:568-576`) stay byte-equal to `f3ce1a5` (`T-V1104-DOC-05`); `REQ-V1103-INS-01` unchanged. |
| `REQ-V1104-NG-02` | New `v1104-*` mutation ids or a `mutation-v1104` gate: this release adds no mechanism to mutate (§3). |
| `REQ-V1104-NG-03` | `git stash pop`, `apply` or `drop` in the run: the stash's untracked parent `043842f` holds two files tracked at `f3ce1a5` (`docs/prompts/226-*.md`, `docs/spec/task-briefs/v1103-T6.md`), so `pop`/`apply` collide (facts §1); only `git stash show -p stash@{0}` piped to `git apply` is used (MUT-01). |
| `REQ-V1104-NG-04` | A benchmark run, a fresh baseline, or any edit to `AGENTS.md:274-279`'s waiver paragraph (nothing the rule at `:266-272` keys on changes). |
| `REQ-V1104-NG-05` | `LLM_EVAL_CHAT_MODEL` for gate 8. |
| `REQ-V1104-NG-06` | Re-running gate 8 on a red, or editing a case, checker, marker or floor *during* a red gate 8 (`REQ-V1103-NG-09`, `-NG-10`). **The verifier's informational gate 8 on `f3ce1a5` (2026-09-18, outside any run: 5/5, 4/4, 3/3, judge 0.957) is evidence about the instrument, not this release — only the run's own T4 capture counts.** |
| `REQ-V1104-NG-07` | Lowering the floors (`devtools/agent_eval.py:89`), the judge threshold, the no-rerun rule, temperature 0, the case count. |
| `REQ-V1104-NG-08` | Editing any earlier report, handoff or `docs/llm-usage.md` row — history. |
| `REQ-V1104-NG-09` | Any `git push`; any change to a gate's `argv`, `result_mode`, `blocking`, `severity` or profile membership beyond `mutation-v1103` joining `mutation-subsets`. |
| `REQ-V1104-NG-10` | A "no later row" or "nothing follows" assertion anywhere in this release's tests — the defect class PIN-01 retires. |

---

## 3. The mutation entries and the frozen-pin rewrites

**REQ-V1104-MUT-01 (MUST) — the five `v1103-*` entries, exactly as the
stash has them, landed at T2 by applying the stash's two non-test
paths; the stash identity-pinned; Appendix D the byte-exact fallback;
each entry killed by its named killer under exact node ids.** No `v1104-*` entry exists because this release adds no
mechanism to mutate (NG-02). `devtools/mutation_check.py` gains the
**five** entries (`{id, path, find, replace, why}`, `:51-60`) after
`v1102-hal-gap-marker-dropped` (`:1897-1922`; the list closes `:1923`)
with the stash's rationale comment. **This table states reality** (`report-v1.10.3.md:566-572`),
correcting `REQ-V1103-GATE-02`'s table (`spec-v1.10.3.md:788-794`) in
two cells (tails 3–4):

| # | id | path (`find` at `f3ce1a5`) | what the mutant does | killed in isolation by |
|---|---|---|---|---|
| 1 | `v1103-exec-guard-dropped` | `tools.py:1596` | rule 1's predicate → `False` | `T-V1103-EXEC-01` (four cases red) |
| 2 | `v1103-exec-guard-env-file-dropped` | `tools.py:1599` | the **inner `any(...)` generator predicate** → `False` (the only syntax-preserving option on the multi-line `if any(...):`; **not** `if False:` as v1.10.3's table wrote) | `T-V1103-EXEC-02` (five cases red) |
| 3 | `v1103-exec-guard-proc-environ-dropped` | `tools.py:1603` | rule 3's predicate → `False` | `T-V1103-EXEC-03` (three cases red) |
| 4 | `v1103-delegation-lint-dropped` | `devtools/checks.py:1723` | the `_run_lint_docs` call's predicate → `False` | `T-V1103-LINT-09` (`tests/test_v1103_lint.py:381`) — **`T-V1103-LINT-06`/`-07`, which v1.10.3's table named, stay green under the mutant** (they never call `_run_lint_docs`) |
| 5 | `v1103-hal-noun-first-marker-dropped` | `devtools/agent_eval.py:155` | the eighteenth `HAL_MARKERS` literal removed (a valid list of seventeen) | `T-V1103-RT-01` (`assert 17 == 18`) and `T-V1103-RT-08` (`IndexError` on `HAL_MARKERS[17]`) |

The `find`/`replace` strings, **verbatim from the stash** (Python
literals; T2's brief carries them before any mutation executes):

```python
# 1 tools.py
"find":    '    if os.path.basename(argv[0]) in EXEC_DENY_PROGRAMS:  # noqa: PTH119\n',
"replace": '    if False:  # v1103-exec-guard-dropped  # noqa: PTH119\n',
# 2 tools.py
"find":    '        os.path.basename(e) == ".env" or os.path.basename(e).startswith(".env.")  # noqa: PTH119\n',
"replace": '        False  # v1103-exec-guard-env-file-dropped\n',
# 3 tools.py
"find":    '    if any(_PROCFS_ENVIRON_RE.fullmatch(e) for e in argv):\n',
"replace": '    if False:  # v1103-exec-guard-proc-environ-dropped\n',
# 4 devtools/checks.py
"find":    '    if gate.get("delegation_record") is True:\n',
"replace": '    if False:  # v1103-delegation-lint-dropped\n',
# 5 devtools/agent_eval.py
"find":    '    r"(?:информации|данных|сведений)\\b(?:(?!\\b(?:но|а|однако|зато)\\b)[^.?!;…]){0,120}\\bнет\\b",\n',
"replace": "",
```

Each `find` matches its file **exactly once** at `f3ce1a5`
(`T-V1104-MUT-02`); `run_one` returns `DRIFTED` on any other count
(`devtools/mutation_check.py:2309-2311`, ERR-01 row 2). The `why`
strings are the stash's, verbatim — **Appendix D carries the two-path
unified diff verbatim** (the five entries with their `why` strings, the
rationale comment and the yaml hunks in full), so the fallback is
byte-exact, never re-authored. **The stash identity is pinned**: T0
records `git rev-parse stash@{0}` and asserts it equals
`e3c6e3ff3bee60bff183ae056621d4dc984cd5a3` (parents `52be07e` base,
`48b7ee5` index, `043842f` untracked). **Procedure (T2, repository
root, after T1's commit)** — first the exact two-path check re-run
**after T1** (T0's check on `f3ce1a5` does not cover T1's tree):

```bash
git stash show -p stash@{0} | git apply --check --include='devtools/mutation_check.py' --include='config/quality_gates.yaml' -
git stash show -p stash@{0} | git apply --include='devtools/mutation_check.py' --include='config/quality_gates.yaml' -
```

The lab verified this form with `--check` exits 0 on `f3ce1a5` (facts
§1); T1 does not touch `devtools/mutation_check.py` and touches
`config/quality_gates.yaml` only at `lint-docs.report_path` (PIN-02).
**The fallback triggers when the stash is absent, has another id, or
fails the post-T1 `--check`** (ERR-01 row 1): T2 extracts Appendix D's
fenced block into a file, asserts its `sha256sum` equals Appendix D's
stated value, and runs `git apply` on that file — the same two paths,
the same bytes. **The stash's three test hunks
are NOT applied**: they carry the frozen shapes this release retires (a
24-id `tail ==` literal, `spec-v1\.10\.3 T6` anchors) — T1 rewrote those
sites (PIN-01); T2 only adds the `v1103-` group assertion (EC-02 row
2b). **After applying (either route), before the isolation proofs, T2
verifies the post-image**: `git hash-object devtools/mutation_check.py`
equals Appendix D's `index` post-image `d09909d…` (the file differs
from `f3ce1a5` only by the five entries and the rationale comment), and
the yaml's `mutation-subsets` line, `mutation-v1103` block and
`mutation-all` comment equal Appendix D's post-image (the whole-file
hash does not hold because of T1's `report_path` repoint; the
`mutation-all` sentence is then rewritten by MUT-02 (c)); a mismatch is
ERR-01 row 2's class — a construction defect. **Each entry is
re-verified in isolation before commit by `REQ-V1103-GATE-02`'s
two-proof rule** (`spec-v1.10.3.md:796-805`): the mutated module imports
(exit 0) **and** the named killer is red under **exact node ids, never
`-k`**: for each mutant, first collect and record the exact pytest node
id or parametrized node-id set corresponding to the named `T-V1103-*`
test; run pytest with only those explicit node ids, never `-k`; assert
at least one selected node fails for the expected assertion/reason and
record the selected count; **a collection miss or any extra selected
node is a construction defect** (ERR-01 row 3) — the collection
command, the node ids, the selected count, the pytest command, the
import exit and the failing assertion recorded (RPT-01). `len(MUTATIONS)` becomes **144**. `T-V1104-MUT-01`,
`T-V1104-MUT-02`, `T-V1104-MUT-05`, `T-V1104-ERR-01`; `E1`, `E5`;
Appendix D.

**REQ-V1104-MUT-02 (MUST) — the `mutation-v1103` gate, its subset
membership, the placeholder timeout, and the one "is now" sentence
re-anchored to this release.** From the same `git apply` (or the
fallback), `config/quality_gates.yaml` gains: (a) `mutation-v1103` in
`mutation-subsets` (`:29-30`) after `mutation-v1102`, in no hook profile; (b) the gate `mutation-v1103` after `mutation-v1102`
(`:580-588`) with the same key set — `argv: [uv, run, --locked, python,
devtools/mutation_check.py, --select, "v1103-"]`, `blocking: true`,
`diff_scoped: false`, `timeout_seconds: 110` — the stash's
**placeholder** comment stays at T2 and is replaced at **T4** by the
calibration comment in `:574-579`'s shape, GATE-02's one localized
hunk (delegated, brief `v1104-T4.md`); (c) in the `mutation-all` comment block (`:590-707`) the
v1.10.2 sentence (`:703-704`) reads "closed at 139" and the stash's new
paragraph is **rewritten to this release's sentence, the block's only
"is now"**:

```
  # spec-v1.10.4 T2 appended the five `v1103-*` entries authored by the
  # v1.10.3 run; `len(devtools.mutation_check.MUTATIONS)` is now 144.
```

— the fragment `` MUTATIONS)` is now 144`` on one comment line; the
v1.10.3 sentence is not written. `mutation-all` (`:708-716`) keeps its
`argv`; its `timeout_seconds: 1640` is GATE-02's `[[VERIFY]]`.
`T-V1104-MUT-03`, `T-V1104-MUT-04`; `E1`, `E3`.

**REQ-V1104-PIN-01 (MUST) — every frozen-list pin rewritten to
presence, contiguity and order; the "is now" anchor release-agnostic;
the count narrowed to the block.** The lesson of v1.10.3
(`report-v1.10.3.md:582-606`): a test asserting a list "ends here"
stops the next run. **Rule**: such a test asserts that a release group forms **one contiguous block,
in its listed order, at the position after the previous group** —
`ids[start:start + len(GROUP)] == GROUP` — never equality with the
whole tail. The sites are EC-02 rows 1–4 (T1) and 2b (T2); the anchor
becomes `MUTATIONS\)`\s*is now (\d+)` — **the anchor includes the closing
backtick after `` MUTATIONS) ``; the sentence, the fixture and the regex
are byte-consistent** (provenance lives in prose the
test does not parse; any fixture the anchor tests read must carry the fragment `` MUTATIONS)` is now `` — PIN-03's is written in full in §6.1 and E3); the count runs over
`_mutation_all_comment_block(text) = text[text.index("  # mutation-all:") : text.index("\n  mutation-all:\n")]`
— from the block's first comment line (`:590`, the only line beginning
`  # mutation-all:`) to the `mutation-all:` key (`:708`) — so an "is
now" in another gate's comment cannot break it; the helper is
module-level in `tests/test_v1102_gates.py`, imported by
`tests/test_v1104_gates.py`. `tests/test_v1103_gates.py:73-81` stays
(EC-02). The new tests prove the property, not the edit
(`T-V1104-PIN-01…04`, `-06`). `E2`, `E3`, `E6`.

**REQ-V1104-PIN-02 (MUST) — the repoints.** At **T1**, in one commit
with PIN-01: `config/quality_gates.yaml:761` `report_path:
docs/reports/report-v1.10.4.md` (`:762-763` unchanged); the five
`report_path` pins (EC-02 rows 7–11); `tests/test_v15_standards.py:1824`
→ `spec-v1.10.4.md` (row 12; this file's matrix carries every label of
`config/quality_gates.yaml` — GATE-02); `AGENTS.md:95` →
`docs/spec/task-briefs/v1104-T<N>.md` with its two pins (rows 13–14).
**`REQ-V1103-LINT-01` derives the brief prefix from `report_path`**
(`spec-v1.10.3.md:552-553`; `T-V1104-PIN-07` proves `report-v1.10.4.md`
→ `v1104`), so no yaml key and no lint change is needed; the T0 report skeleton (`## T0 — preflight` with `- T0 |
delegated: no | to: — (commands only) | brief: — | map vs actual:
matches §10.1`) is what `lint-docs` reads from T1's commit on, green
from the first commit; each later task appends its section and bullet
(T4 two bullets, EC-03). `T-V1104-RPT-01`, `T-V1104-PIN-05`,
`T-V1104-DOC-03`, `T-V1104-PIN-07`; `E4`.

---

## 4. Error matrix

**REQ-V1104-ERR-01 (MUST) — every failure class this release adds or
moves.** `REQ-V1103-ERR-01`'s matrix (`spec-v1.10.3.md:611-633`) carries
by reference with this release's names (gate 8 at T4, the `v1104-…`
capture, the `--select v1103-` calibration) **except row 9, which does
not exist in this release** (EC-02); these rows are added or rebound:

| # | where | condition | behaviour | exit / verdict |
|---|---|---|---|---|
| 1 | T0 / T2, the stash | `stash@{0}` absent, `git rev-parse stash@{0}` ≠ `e3c6e3ff…`, or the post-T1 two-path `git apply --check` exits non-zero | the fallback (§3): Appendix D's diff, its `sha256sum` asserted, applied by `git apply`; the post-image verified either way; recorded | no cycle |
| 2 | `run_one` | a `find` matching 0 or ≥ 2 times (`:2309-2311`) | `DRIFTED`, the runner never called, gate 6 red | a construction defect → a repair cycle |
| 3 | T2, isolation | an entry not killed by its named killer's exact node ids alone; a collection miss; an extra selected node | `REQ-V1103-ERR-01` row 7: disclose; rewrite syntax-preserving (or repair the collection) — a construction defect | a repair cycle |
| 4 | after T0 | a test red on a pin listed neither in EC-02 nor in the T0 hit table | amended with its intent kept, disclosed as an EC-02 amendment | **no cycle, no stop** |
| 5 | `lint-docs` | a task section without a `^- T\d+ \| ` bullet; a `brief:` naming `v1103-T<n>.md` | the `REQ-V1103-LINT-01` text; blocked | fix the report; never the lint |
| 6 | Stage 0 check 6 | the judge probe fails as `REQ-V1103-ERR-01` row 6 describes | the single fallback, recorded; the effective judge named (VER-01, RPT-02) | as row 6 |
| 7 | T4, calibration | `2 × wall + 70 s` rounded up to 10 s differs from 110 | `mutation-v1103.timeout_seconds` set to the computed value inside GATE-02's one hunk (the dated comment lands even when the value stays 110) | recorded |
| 8 | T4, gate 6 | the `mutation-all` wall exceeds 1640 s | the timeout recomputed in T4's commit (GATE-02's `[[VERIFY]]`) | recorded |
| 9 | T4, gate 6 | `HEAD^{tree}` ≠ the recorded write-tree | gate 6 once more on the committed tree (`REQ-V1102-ERR-01` row 13) | recorded |
| 10 | gate 8 at T4 | exit 1 — a category under floor or judge mean under 0.8 | Stage B′ (REV-03); the capture quoted in full | stop, no bump, no tag |
| 11 | the gate-8 capture | `test -s` non-zero | `REQ-V1102-ERR-01` row 11 — never a re-run | the terminal record, or a blocked run |
| 12 | gate 7 | `recall@5` red after the transient rule (exit 2 is never this row) | at T4: Stage B″; at T5: Stage B at T5 | stop |
| 13 | T5, identity check | `dependency_diff_is_version_only` `False` on the diff `tested_tree`→`HEAD` | gate 8 **not** invoked; the defect repaired; gates 1–7 and the check rerun | a repair cycle; not restorable → Stage B at T5 |
| 14 | T0, the inventory | a hit of EC-02's parts (i)–(iii) neither an EC-02 row nor a one-line "unaffected because …" | construction blocked until the hit is classified in the T0 hit table; never a stop | **no cycle** |

`T-V1104-ERR-01` covers row 2 offline; row 5 is `T-V1103-LINT-02`
by reference and `T-V1104-PIN-07` offline; the other rows are recorded artefacts.

---

## 5. Security

**REQ-V1104-SEC-01 (MUST) — no secret value on any surface; the stash
read-only; the boundary kept.** No unredacted secret value or
credential-shaped live value appears in the spec, tests, fixtures,
briefs, reports, command output or commits; key *names* and the fake
`VALUE-abcdefgh12` are allowed; `gitleaks-tree` green at every commit.
The executor never opens `.env`, `data/`, `docs/assets/`, `bot.db` or
`exec_audit.jsonl`; every printed line passes `config.redact`. The
stash is read with `git stash show -p stash@{0}` only (NG-03); the five
`find`/`replace`/`why` strings carry no key value (`T-V1104-MUT-02`).
The eval still executes nothing (`REQ-V1103-SEC-01`). `gitleaks-tree`; the command record; `E1`, `E8`.

---

## 6. Tests

**REQ-V1104-TST-01 (MUST) — the modules, the count, the table.** New
tests live in `tests/test_v1104_{gates,docs,version}.py`, all offline;
**≥ 21** new collected tests (T5: count ≥ floor + 21); every id below
appears in Appendix A.

### 6.1 The test table

"The two rewritten group tests" are EC-02 rows 1–2's, "the two anchor
tests" rows 3–4's, "the two re-pinned README tests" rows 5–6's.

| id | module | asserts | negative? |
|---|---|---|---|
| `T-V1104-MUT-01` | `gates.py` | §3's five ids form one contiguous block, in order, at `ids.index("v1102-hal-gap-marker-dropped") + 1`; each has exactly the five keys; `len(mc.MUTATIONS) >= 144` (never `==`, NG-10) | — |
| `T-V1104-MUT-02` | `gates.py` | per entry `(REPO_ROOT / path).read_text().count(find) == 1`; `find`/`replace` byte-equal to §3 (pinned in the test); a `find` with one character changed counts 0 | yes |
| `T-V1104-MUT-03` | `gates.py` | `mutation-v1103`'s key set equals `mutation-v1102`'s; `argv` exactly MUT-02's; `blocking is True`, `diff_scoped is False`; in `mutation-subsets` immediately after `mutation-v1102`, in no other profile; `mutation-all`'s `argv` unchanged | — |
| `T-V1104-MUT-04` | `gates.py` | `_mutation_all_comment_block(text)` (imported from `tests/test_v1102_gates.py`) holds exactly one "is now"; `MUTATIONS\)`\s*is now (\d+)` inside it parses to `len(mc.MUTATIONS)` | — |
| `T-V1104-MUT-05` | `gates.py` | per entry `ast.parse(source.replace(find, replace, 1))` succeeds; for row 5 the mutated `HAL_MARKERS` literal has 17 elements | — |
| `T-V1104-PIN-01` | `gates.py` | `mc.MUTATIONS` monkeypatched to the real list plus an appended five-key probe entry `v9999-probe` → the two rewritten group tests pass | — |
| `T-V1104-PIN-02` | `gates.py` | the probe between the third and fourth `v1102-*` entries → both raise `AssertionError`; the `v1101-*` block reversed → the release-groups test raises | yes |
| `T-V1104-PIN-03` | `gates.py` | `checks.DEFAULT_CONFIG_PATH` monkeypatched to a `tmp_path` yaml copy whose block sentence reads, in full, `` spec-v9.9.9 T9 appended one entry; `len(devtools.mutation_check.MUTATIONS)` is now 145 `` (the fixture must carry the fragment the anchor regex matches, `` MUTATIONS)` is now ``) with `mc.MUTATIONS` monkeypatched to a list of length 145 → the two anchor tests pass | — |
| `T-V1104-PIN-04` | `gates.py` | the same copy with `# note: is now` in the `mutation-v1103` comment → the count test passes; a second "is now" inside the block → `AssertionError`; the shipped block starts with `  # mutation-all:` and ends before `\n  mutation-all:\n` | yes |
| `T-V1104-PIN-07` | `gates.py` | `checks._lint_report_delegation` on a `tmp_path` `report-v1.10.4.md`: a `## T1` section whose bullet reads `brief: docs/spec/task-briefs/v1104-T1.md` → `[]`; the same bullet reading `…/v1103-T1.md` → a failure whose text is "cell 4 is neither brief: — nor a v1104 task-brief path" (the prefix derived from `report_path`, `REQ-V1103-LINT-01`) | yes |
| `T-V1104-PIN-05` | `gates.py` | `_parse_gate_matrix` over this file yields 29 rows containing every label of `_GATE_MATRIX_LABEL_TO_NAME`; `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table()` and `tests/test_v1103_gates.py:63-81`'s test pass | — |
| `T-V1104-PIN-06` | `docs.py` | `_read_readme` monkeypatched (both modules) to the real text plus an appended `\| v1.10.9 \| — \| probe \|` line → the two re-pinned README tests pass | — |
| `T-V1104-RPT-01` | `gates.py` | `lint-docs.report_path == "docs/reports/report-v1.10.4.md"`, `delegation_record is True`; `_lint_report_delegation(REPO_ROOT / "docs/reports/report-v1.10.4.md") == []` | — |
| `T-V1104-DOC-01` | `docs.py` | README's `v1.10.3` row equals VER-01's text verbatim (`_V1103_ROW`); the `v1.10.2` row still equals `_V1102_ROW`; nothing asserted absent (T1) | — |
| `T-V1104-DOC-02` | `docs.py` | `…v1104_release_and_gate8_rows_landed_at_t5` (T5, red before, green after): a `v1.10.4` row ending `this release`, the `v1.9.5` row (`README.md:913`) without it, no `pending` in `:594-600` | — |
| `T-V1104-DOC-03` | `docs.py` | `AGENTS.md` carries `docs/spec/task-briefs/v1104-T<N>.md`; the waiver paragraph (`:274-279`) equals `git show f3ce1a5:AGENTS.md`'s (T1) | — |
| `T-V1104-DOC-04` | `docs.py` | `AGENTS.md`'s count lines carry T5's `pytest` count and `144 entries`, dated `as of spec-v1.10.4 T5` (T5, red before, green after) | — |
| `T-V1104-DOC-05` | `docs.py` | NG-01's six files byte-equal to their `git show f3ce1a5:<path>` blobs (README: the judge paragraph `:568-576`) | — |
| `T-V1104-VER-01` | `version.py` | `project.version == "1.10.4"` (live tree); `git show v1.9.5:pyproject.toml` reads `1.9.5` | — |
| `T-V1104-VER-02` | `version.py` | for `pyproject.toml` and `uv.lock` only, the diff from the `f3ce1a5` blobs is project-version-only under `dependency_diff_is_version_only` (no whole-repository claim) | — |
| `T-V1104-ERR-01` | `gates.py` | a `tmp_path` root whose `tools.py` copy carries entry 1's `find` twice → `run_one(entry, runner=spy, root=tmp, restorer=…)` returns `(mc.DRIFTED, None)`, the spy never called; with one `find` → the spy called once, the file restored | yes |

---

## 7. Gates

**REQ-V1104-GATE-01 (MUST) — the eight gates verbatim; when each live
gate runs; gate 8 exactly once, at T4; one green gate 8 is necessary,
not sufficient.** The eight commands of `REQ-V1100-GATE-01`
(`AGENTS.md:148-159`) do not change; **no LM Studio**. **Schedule**: **T0** gates 1–5 and 7 (6 and 8 not run; any red a
Stage 0 blocker); **gates 1–4 at every commit**; **T4**: the `--select v1103-` calibration, gate 6 **once,
directly**, on a recorded `git write-tree` (GATE-02), gate 5, gate 7
under `REQ-V1103-GATE-01`'s transient predicate (`spec-v1.10.3.md:730-778`),
then **gate 8 exactly once in the entire run**, the task's last live
action, after `tested_tree="$(git rev-parse HEAD)"` and an empty `git
status --porcelain`, by `REQ-V1102-RT-03`'s five-line capture block
(`spec-v1.10.2.md:449-462`) with the `v1104-gate8-${tested_tree}.log`
path, `gate8_exit` and `test -s` recorded before any parsing; **T5**: gates 1–7 on the version
commit, then `REQ-V1100-GATE-01`'s dependency identity check (`git diff
<tested_tree> HEAD -- $(uv run --locked python devtools/agent_eval.py
--print-dependencies)` under `dependency_diff_is_version_only`): `True`
→ reuse T4's result; `False` → **do not invoke gate 8** — an acceptance
defect, repaired within the budget, gates 1–7 and the check rerun, not
restorable → Stage B at T5 (ERR-01 row 13). **Once T4's gate 5 and gate
7 have completed, no stop route invokes any live gate again** (EC-01):
Stage B′ and B″ reuse T4's recorded gate-5, gate-7 and gate-8 results
and finalise offline; gate 8 is T4's last live action in every route. **The reuse record** states
facts (a) and (b) of `spec-v1.10.3.md:749-757` with `f3ce1a5` for
`636a281`. **Every gate-7 execution gets an attempt-log row** (RPT-01).
**Only the run's own T4 capture counts** (NG-06); **one green run is
necessary, not sufficient** — a green 5/5 is worded "on this run"
(`REQ-V1103-GATE-01`). **Formulas against a plausible bad run**: ERR-01
rows 2, 5, 6, 10 and 12. The gate tables at T0, T4, T5; the
attempt log; `E5`, `E8`.

**REQ-V1104-GATE-02 (MUST) — the calibration, the write-tree, the
timeout markers, and the gate matrix this file carries.** At **T4**:
(1) `uv run --locked python devtools/mutation_check.py
--select v1103-` **once** (commands only), wall measured; `timeout_seconds` = wall × 2 +
70 s, rounded up to 10 s (result expected 5/5, recorded, no
verdict); then **T4 makes exactly one localized YAML hunk in the
`mutation-v1103` block: it replaces the placeholder comment with the
dated measured-wall/formula comment and sets `timeout_seconds` to the
computed value, even when that value remains 110. No other YAML content
changes.** The hunk is in `:574-579`'s shape and is delegated under
brief `docs/spec/task-briefs/v1104-T4.md` (EC-03), the wall and the
computed value in the brief first; `[[VERIFY: v1102's
calibration measured 18.11 s → 110 s (`config/quality_gates.yaml:575-577`)
— decision rule: `timeout_seconds` is always the computed number, 110
only if the formula yields it]]`;
(2) the intended T4 files staged and **`git write-tree` recorded**, then
**gate 6 once, directly**, wall measured (`REQ-V1102-GATE-02`'s
procedure by reference); commit; `git rev-parse HEAD^{tree}` asserted
equal to the recorded tree (ERR-01 row 9); `[[VERIFY: v1.10.2's direct
`mutation-all` run took 14m23.5s at 139 entries against 1640 s
(`docs/llm-usage.md` row 129) — decision rule: recompute by the yaml's
rule (2 × wall + 70 s, rounded up to 10 s) in the same T4 commit only
if the wall exceeds 1640 s; otherwise the value stays]]`; then GATE-01's live sequence.
`[[VERIFY: the collected-test count after T2 — `f3ce1a5` collects 2285
and T1–T2 only add — decision rule: T0's re-measured number is the
floor; T5 asserts count ≥ floor + 21; a lower count is a TST-01 defect,
never a floor adjustment]]`.

**The gate matrix**: `test_v15_gate_04_profile_matrix_agrees_with_the_spec_table`
(`tests/test_v15_standards.py:1822-1836`) parses the matrix out of the
file it names (`:1824`) through `_GATE_MATRIX_LABEL_TO_NAME`
(`:1772-1803`, `v1103-` at `:1793`). **T1 repoints `:1824` at this
file** (EC-02 row 12; no label added; `lint-docs`'s `report_path`
repoint is PIN-02's, in the same commit); `spec-v1.10.3.md` is **not
edited**. The table is `spec-v1.10.3.md:849-879`'s 29 rows verbatim —
every profile, every gate, `mutation-v1103` in `mutation-subsets` only,
`mutation-all` at 144 entries (139 → 144); load-bearing markup, in this
file exactly once.

| gate | pre-commit | pre-push | full |
|---|:---:|:---:|:---:|
| `ruff check` (staged) | yes | — | — |
| `ruff check .` (tree) | — | yes | yes |
| `ruff format --check` (staged) | yes | — | — |
| `ruff format --check` (tree) | yes | yes | yes |
| branch-name check | yes | yes | yes |
| `gitleaks git --staged` | yes | — | — |
| `gitleaks dir` (tree) | — | yes | yes |
| `uv sync --locked` | — | — | yes |
| `pytest` | — | yes | yes |
| `bot.py --selftest` | — | yes | yes |
| `bot.py --selftest-live` | — | — | yes |
| `rag_eval.py` | — | — | yes |
| `agent_eval.py` | — | — | yes |
| `mutation_check.py --select v15-` | — | — | — |
| `mutation_check.py --select v160-` | — | — | — |
| `mutation_check.py --select v170-` | — | — | — |
| `mutation_check.py --select v180-` | — | — | — |
| `mutation_check.py --select v190-` | — | — | — |
| `mutation_check.py --select v1100-` | — | — | — |
| `mutation_check.py --select v1101-` | — | — | — |
| `mutation_check.py --select v1102-` | — | — | — |
| `mutation_check.py --select v1103-` | — | — | — |
| `mutation_check.py` (all) | — | yes | yes |
| `trivy fs` | — | yes | yes |
| `semgrep scan` | — | yes | yes |
| `skylos` | — | yes | yes |
| `install_hooks.py --check` | — | yes | yes |
| `checks.py doctor` | — | yes | yes |
| `checks.py lint-docs` | — | — | yes |

`T-V1104-PIN-05`; `T-V1104-MUT-03`; the calibration and write-tree
records; `E1`.

---

## 8. Version, reporting and the ledger

**REQ-V1104-VER-01 (MUST) — 1.10.4, where the bump lives, the two
release rows in two tasks, the local tag, no push.** `pyproject.toml:3`
moves `1.9.5` → `1.10.4` in **T5's first commit and nowhere else** —
after T4's gates and gate 8 are green — so a stop earlier needs no
revert; `1.10.0`…`1.10.3` stay stopped, untagged runs. `uv lock`
(online) regenerates `uv.lock` for the literal only (`T-V1104-VER-02`);
`T-V1104-VER-01` is written in the same commit, red before, green after;
`tests/test_v195_version.py` is repointed to the `v1.9.5` blob (EC-02
row 15). README's release table
(`README.md:913-916`) gains **two rows in two tasks**: the `v1.10.3`
row at **T1** (EC-02 rows 5–6 re-pinned to its presence) and the
`v1.10.4` row at **T5** only, the `v1.9.5` row (`:913`) losing its
"this release" clause in the same T5 edit; on Stage B′ the T5 row never
lands. After `:916`:

- `| v1.10.3 | — | run stopped at T6 by the stop route — EC-01's repair budget spent on four test pins the spec's list missed; gate 8 never ran; the exec guard, the marker widening, the delegation lint and the paperwork landed; ships with v1.10.4 |`
- `| v1.10.4 | 1.10.4 | the five v1103-* mutation entries the v1.10.3 run authored and verified, landed (mutation-all 144); every frozen-list test pin rewritten to presence, contiguity and order; model under test openai/gpt-4.1; shipped judge default anthropic/claude-sonnet-5; gate 8 judged by <effective judge>; gate 8 green on this run; this release |`

`<effective judge>` is `REQ-V1103-VER-01`'s rule (`spec-v1.10.3.md:906-912`)
by reference (`anthropic/claude-sonnet-5 (another vendor)` on `used:
no`; `openrouter:openai/gpt-5.6-sol` without the parenthesis on the
fallback). The annotated tag
`v1.10.4` goes on REV-02's evidence-only commit (T5's second) only, on
green, as the run's last action — **local, never pushed** (EC-01).
`T-V1104-VER-01`, `T-V1104-DOC-01`, `T-V1104-DOC-02`; `E6`, `E7`, `E8`.

**REQ-V1104-RPT-01 (MUST) — what `docs/reports/report-v1.10.4.md`
carries.** `REQ-V1103-RPT-01`'s items (`spec-v1.10.3.md:916-952`) by
reference with this release's names (T4 for T6, T5 for T7, the
`v1104-gate8-${tested_tree}.log` path, floor + ≥ 21, 144 mutations, `##
Operator inputs` with the fallback record, one attempt-log row per
gate-7 execution, item 23's "shipped judge default
`anthropic/claude-sonnet-5`; gate 8 judged by `<effective judge>`", "on
this run") — plus: **the stash application
record** (`git rev-parse stash@{0}` and its match against MUT-01's id,
the post-T1 `--check` exit, the apply command and exit, or the fallback
and its reason with Appendix D's `sha256sum` match, and the post-image
verification); **the
per-entry isolation proofs** (§3 row, import-proof exit, the collection
command and the exact node ids, the selected count, the pytest command
run with those node ids — never `-k` — its result, the failing
assertion); **the T0 inventory
hit table** (`file:line | hit | EC-02 row or "unaffected because …"`,
every hit of parts (i)–(iii) classified)
and any post-T0 amendment (ERR-01 row 4) in its task's section; **the
calibration line** (wall, result, `timeout_seconds`); the push
instruction naming the 72 pending commits and the operator's `git stash
drop stash@{0}` after it. The T0 skeleton carries `## Operator inputs`,
the attempt log with T0's row, `## T0 — preflight` with T0's bullet and
the ledger-row block. `T-V1104-RPT-01`; the T0, T4 and T5 records.

**REQ-V1104-RPT-02 (MUST) — the Telegram post, the usage rows, the
ledger row.** `docs/reports/tg-post-v1.10.4.md`, **Russian**, under 1500
characters by `wc -m` (count quoted), naming `claude-sonnet-5`, the
link `https://github.com/axyi/tg-agent-bot`, the subject, the judge as
VER-01's row words it, the gate-8 numbers "on this run". Every prompt gets a row in
`docs/llm-usage.md` from **row 139** (137 is the last at `f3ce1a5`,
`:287`; 138 is authoring). The report's "Ledger row (paste into `economics.md`)" section carries
a complete fenced row with `Ver` = `1.10.4` (on the stop route,
whatever `pyproject.toml` reads) matching `tests/test_v170_bench.py:328-331`'s
header. The T5
record.

**REQ-V1104-RPT-03 (MUST) — the paperwork block: the T1 part, the T5
part, and the rule on Stage B′.** **At T1**: README's `v1.10.3` row
(VER-01); `AGENTS.md:95` → `v1104-T<N>` (PIN-02); the waiver paragraph,
the judge paragraph, `## Switch provider` and `.env.example`
**untouched** (NG-01, NG-04). **At T5**: the five `pending (T9)` rows
(`README.md:596-600`) filled from T4's gate 8 ("on this run"), the
`v1.10.4` row, the `v1.9.5` clause removed; `AGENTS.md`'s count lines
(`:161-162`, `:172`) move to T5's measured numbers (the `pytest` count,
`144 entries`), dated "as of spec-v1.10.4 T5" (EC-02 row 16). Earlier
reports and usage rows are **not edited** (NG-08). **On Stage B′ (or
any stop before T5) T5 never runs — REV-03's rule, not a fork**: the T1
paperwork stays, the `v1.10.4` row never lands, the `pending` rows and
count lines stay stale, no bump, no tag; the report says so once. `T-V1104-DOC-01`, `T-V1104-DOC-02`, `T-V1104-DOC-03`,
`T-V1104-DOC-04`, `T-V1104-DOC-05`.

---

## 9. Acceptance, review and the stop route

**REQ-V1104-REV-01 (MUST) — review in a clean context, before the gates
that matter.** Code review by the `code-reviewer` subagent (`model:
sonnet`) in its **own clean context** at T3 — after T1–T2, before T4's
live run. **Never self-review in the writing context.** Findings are
fixed or waived with a reason; a fix that writes source is delegated by
brief `v1104-T3.md` (EC-03); the review prompt is logged. Beyond the standard
checklists: (1) `devtools/mutation_check.py`
differs from `f3ce1a5` only by the five entries and their comment
(Appendix D's post-image);
`config/quality_gates.yaml` only by MUT-02's three hunks and PIN-02's
`report_path`; no other source file differs; (2) every rewritten pin asserts presence, contiguity and order
— no `tail ==`, whole-file "is now" count, release-name anchor or "no
later row" assertion anywhere in `tests/` (NG-10); every renamed test
keeps its intent; no test deleted; (3) every T0 inventory hit of EC-02's parts (i)–(iii) is
classified — an EC-02 row or a one-line reason — and no unclassified
hit survived T0 (ERR-01 row 14); every post-T0 amendment is disclosed; (4) the isolation proofs
name `T-V1103-LINT-09` for entry 4 and the inner predicate for entry 2;
(5) no new dependency; no secret value anywhere (SEC-01); no live call
in any test; `git stash list` still shows `stash@{0}`.

**REQ-V1104-REV-02 (MUST) — acceptance, the live gates, the freeze,
regression, no push.** `REQ-V1103-REV-02` (`spec-v1.10.3.md:1060-1090`)
applies with this release's names: **T5 is one prompt (233) and two
commits**. **T5's first commit** (the `<implementation-tip>`) lands
VER-01's bump, `uv lock`, the version tests, EC-02 rows 15–16, RPT-03's
T5 part and a provisional report and tg-post; then gates 1–7 on that
tree, gate 8 reused from T4 under GATE-01's identity check, the
collection check, `replay --range f3ce1a5..<implementation-tip>` and
**Appendix B scenarios E1–E7** run **before the evidence commit, their
results recorded in the report**; **T5's second commit is
documentation-evidence-only**, its **exhaustive** path list exactly
four paths: `docs/reports/report-v1.10.4.md`,
`docs/reports/tg-post-v1.10.4.md`, the single `docs/prompts/233-*.md`
file, and `docs/llm-usage.md`; **no other path may differ**. **After
the evidence commit, `E8` runs against that commit before tagging; its
output is reported only in the closing message.** `lint-docs` and
`gitleaks-tree` re-run against it and, all three green, the annotated
tag `v1.10.4` is created on **that** commit — **locally; `git push` is
not a command this run issues**; a finding withholds the tag. The
post-tag closing checks are `spec-v1.10.3.md:1083-1090`'s with
`v1.10.4`; the handoff says: push, then `git stash drop stash@{0}`. **Regression, no
weakened posture**: every earlier release's acceptance properties still
hold; no production or evaluation-instrument source changes;
`devtools/mutation_check.py` differs from `f3ce1a5` only by MUT-01's
five registry entries and rationale comment, while NG-01's pinned files
remain byte-equal as scoped by `T-V1104-DOC-05`; every `T-V1103-*`
test green unamended except EC-02's rows; failures are fixed inside
the **3-cycle** budget, never by a relaxed gate, a deleted test, a
lowered floor, an edited case or a model switch.

**REQ-V1104-REV-03 (MUST) — the stop route, written as a route.**
`REQ-V1103-REV-04` (`spec-v1.10.3.md:1101-1167`) applies **verbatim by
reference** with this release's names, T4 for T6 and T5 for T7, and
these bindings:

- **Stage 0 — T0 preflight failure.** The **seven** checks
  (`spec-v1.10.1.md:1105-1170`; bindings `spec-v1.10.3.md:1105-1120`) in
  order, each a STOP with the blocker template; check 1 asserts EC-04's
  three run values on `load_config()`; check 2 prints only
  `db_empty=<bool>`; check 6 with the single fallback; check 7 records
  the empty dependency diff. Then gates 1–5 and 7, all expected green.
  On any blocker: the closing with prompt 228 and `Ver` = `1.9.5` — no
  source or test file, no bump, no tag; the evidence commit the run's
  only commit.
- **Stage A / Stage B** — `spec-v1.10.1.md:1171-1177` verbatim.
- **Stage B at T5 — the identity check's false branch not restored
  (ERR-01 row 13), or gate 7 red at T5 after the transient rule (row
  12).** No revert: T5's first commit remains, `pyproject.toml` stays
  `1.10.4`; bumped but untagged/unreleased; gate 8 not invoked again;
  the report names Stage B at T5 and quotes the evidence; the evidence
  commit is the run's last.
- **Stage B′ — gate 8 red on model behaviour at T4.** `spec-v1.10.3.md:1133-1140`
  with T4 for T6: an exit 1 is neither a repair cycle nor a defect; no
  model switch, case edit or rerun (NG-06); the capture is the
  permanent record; finalise — no bump, no tag; the `v1.10.4` row never
  lands.
- **Stage B″ — gate 7 red on `recall@5` at T4 only.** `spec-v1.10.3.md:1141-1150`
  with T4 for T6, finalised like Stage B′; at T5 it is Stage B at T5. An
  exit 2 is never either.
- **The budget-exhaustion stage of v1.10.3 (`REQ-V1103-ERR-01` row 9,
  `report-v1.10.3.md:582-635`) does not exist in this release**: a
  missed pin is an EC-02 amendment (ERR-01 row 4).

**The stop-route table** — the exact path set, prompt and commit rule
of each stage reachable after a live gate (Stage B at T5 uses REV-02's
four-path set):

| stage | when | permitted paths (exhaustive; `git show --stat` names a subset, nothing else) | prompt | extra evidence commit | `tg-post-v1.10.4.md` | last-commit and clean-tree assertions |
|---|---|---|---|---|---|---|
| **B′** | gate 8 exit 1 at T4 | `docs/reports/report-v1.10.4.md`, `docs/reports/tg-post-v1.10.4.md`, the single `docs/prompts/232-*.md` file, `docs/llm-usage.md` | 232 | **yes — the explicit exception to one-commit-per-task**: T4's calibration/gate-6 commit already exists; the stop-route evidence commit is T4's second and the run's last | required (step 2) | `git log -1 --format=%s` names the evidence commit and "Stage B′"; `git status --porcelain` empty; `pyproject.toml` `1.9.5`; `git tag -l v1.10.4` empty; the gate-8 capture quoted in full; no live gate after gate 8 |
| **B″** | gate 7 `recall@5` red at T4 after the transient rule | the same four paths as B′ | 232 | **yes — the same explicit exception** (T4's second commit, the run's last) | required (step 2) | as B′ with "Stage B″"; gate 8 `N/A` (never reached); no live gate after T4's gate 7 |
| **B at T5** | ERR-01 row 12 or 13 at T5 | REV-02's four paths: `docs/reports/report-v1.10.4.md`, `docs/reports/tg-post-v1.10.4.md`, the single `docs/prompts/233-*.md` file, `docs/llm-usage.md` | 233 | **no** — T5's second commit *is* REV-02's evidence commit; no third commit | required (step 2) | `git log -1 --format=%s` names the evidence commit and "Stage B at T5"; `git status --porcelain` empty; `pyproject.toml` `1.10.4` (no revert); `git tag -l v1.10.4` empty; the reuse record names one gate-8 execution at T4 |

The task-brief files of the tasks that ran are already in those tasks'
commits (EC-03), so step (5)'s brief clause adds no path; likewise
`docs/prompts/232-*.md` is already in T4's own commit when Stage B′/B″
is reached — it is listed so the set is exhaustive, never staged twice.

The procedure, from wherever the run stands, naming its stage: the six
steps of `spec-v1.10.1.md:1208-1228` and the gate rules of
`spec-v1.10.2.md:1223-1243` with this release's names (`Ver` = whatever
`pyproject.toml` reads; **gate 8 always reused from its single T4
execution, never re-run** — a stop before T4 has none, `N/A`;
`mutation-v1103` `N/A` when never landed; **once T4's gate 5 and gate 7
have completed, no stop route invokes any live gate again** — Stage B′
and B″ reuse T4's recorded gate-5, gate-7 and gate-8 results and
finalise with offline checks only; step (4)'s "5, 7 … when the live
environment is available" applies only to a stop before their
scheduled T4 execution, EC-01), `gitleaks` exit 0, the
permitted evidence committed and nothing else, no `--no-verify`, the
negative proofs (`pyproject.toml` at `1.9.5` before T5, `1.10.4` on
Stage B at T5; no `v1.10.4` tag; `git status -sb` `ahead`; `stash@{0}`
present); no later task runs.

---

## 10. Implementation order

One prompt and one commit per task (228…233; T5's prompt carries two
commits, REV-02; a Stage B′/B″ stop at T4 adds the evidence commit
under prompt 232 as REV-03's explicit exception); tests before the
code they cover, in the same task.

| T | task | acceptance |
|---|---|---|
| **T0** | Preflight (*commands only*): hooks, `doctor`, **test count re-measured** (2285 at authoring; the floor), `len(MUTATIONS)` 139, last prompt 227, last usage row 138 (both written by the authoring commit that lands this spec; at `f3ce1a5` they are 226 / 137), `<base>` `f3ce1a5`, the spec's `sha256`; `git stash list` shows `stash@{0}`, `git rev-parse stash@{0}` equals MUT-01's `e3c6e3ff…` and the two-path `git apply --check` exits 0 (or the T2 fallback — Appendix D — is announced now); EC-02's four-part inventory, every hit classified (ERR-01 row 14); the seven Stage 0 checks; gates 1–5 and 7; `docs/prompts/228-go-spec-v1.10.4.md`; the report skeleton (RPT-01) | every item recorded; the hit table; the fallback record; no key value anywhere; `git diff --exit-code` clean after check 7 |
| **T1** | PIN-01, PIN-02; VER-01's `v1.10.3` row; RPT-03's T1 part; the report's T1 section with its bullet. `T-V1104-PIN-01…07`, `T-V1104-RPT-01`, `T-V1104-DOC-01`, `-03`, `-05`; gates 1–4 | green; `lint-docs` green against the run's own report; the matrix test green against **this** file; REV-01 item 2 holds |
| **T2** | MUT-01, MUT-02: the post-T1 two-path `git apply --check`, the two-path `git apply` (or the Appendix D fallback), the post-image verification, the "is now" sentence, each entry re-verified in isolation under exact node ids, EC-02 row 2b. `T-V1104-MUT-01…05`, `T-V1104-ERR-01`; gates 1–4 | 5/5 killed in isolation with the proofs recorded (node ids, selected count per entry); `len(MUTATIONS)` 144; the `--check` and `git apply` exits (or the fallback's `sha256sum` match) and `git hash-object devtools/mutation_check.py` = `d09909d…` recorded; `stash@{0}` still listed; `doctor` green |
| **T3** | **Review (REV-01) in a clean context**; its fixes land here (brief `v1104-T3.md` when they write source) | findings closed or waived with reasons; the review prompt logged; `v1104-T3.md` present iff a source-writing fix was delegated |
| **T4** | GATE-01's T4 sequence and GATE-02's steps (1)–(2), verbatim: the calibration run, gate 6, the write-tree and the live sequence *commands only*; **the one localized `mutation-v1103` yaml hunk (the dated comment and the computed `timeout_seconds`, even at 110) delegated by brief `v1104-T4.md`**; commit between gate 6 and the live sequence; gate 8 last and once; no live gate after it on any route | the calibration line; `mutation-all` 144/144 with its wall; the write-tree and `HEAD^{tree}` equal; gates 1–7 green; the attempt-log rows; `gate8_exit` 0 with the floors and judge mean met, the per-case table, every `CASE`/`TOOLS`/`FAIL` line, "on this run"; exit 1 is Stage B′; a missing capture is ERR-01 row 11 |
| **T5** | REV-02 verbatim — one prompt (233), two commits: the first (brief `v1104-T5.md` covering `pyproject.toml`, `uv.lock`, the tests and the documentation) lands VER-01, EC-02 rows 15–16, RPT-03's T5 part, the provisional artefacts; gates 1–7, the identity check, the collection check, `replay`, `E1`–`E7`; the second (*artefacts only*) is the evidence commit; `E8`, `lint-docs`, `gitleaks-tree`; the tag; **no push**. `T-V1104-VER-01`, `-VER-02`, `T-V1104-DOC-02`, `-DOC-04` | the four T5 tests red before, green after; `T-V1104-VER-02`; `git diff <tested_tree> HEAD -- config/quality_gates.yaml` empty; the reuse facts, gate 8 executed once; the count ≥ floor + 21; the evidence commit's `git show --stat` names exactly the four paths; `E8` green before the tag; no push in the command record |

### 10.1 Per-task reading map

The authority for EC-03's thresholds; §1, §2 and §9 bind every task. A
`no` cell carries a §5.1 exemption **verbatim**; crossing the map live
forces delegation; the report records map versus actual in the bullet.

| T | spec sections | repository files and ranges | delegate? |
|---|---|---|---|
| **T0** | §1 (EC-02's inventory, EC-04), §4 (rows 1, 14), §7, §9 (Stage 0) | `config/quality_gates.yaml:7-30`, `:258-266`; `docs/spec/spec-v1.10.1.md:1105-1170`; `docs/spec/spec-v1.10.3.md:1105-1120`; `pyproject.toml:1-21`; `docs/prompts/TEMPLATE.md`; `git stash show -p stash@{0}` (read only); `git rev-parse stash@{0}`; `devtools/checks.py` (grep only, EC-02 parts (ii)–(iii)) | no — *commands only* (the skeleton, prompt file and ledger block are prose no gate runs) |
| **T1** | §3 (PIN-01, PIN-02), §4 (row 5), §8 (VER-01's `v1.10.3` row, RPT-03's T1 part), §1 (EC-02 rows 1–14) | EC-02 rows 1–14's sites (±10 lines); `devtools/checks.py:1672-1714` (`_lint_report_delegation`, read only); `config/quality_gates.yaml:736-764`; `README.md:913-916`; `AGENTS.md:92-97`; `tests/test_v15_standards.py:1772-1836`; `tests/test_v1104_{gates,docs}.py` | **yes** — brief `docs/spec/task-briefs/v1104-T1.md` |
| **T2** | §3 (MUT-01, MUT-02), §4 (rows 1–3), §1 (row 2b), Appendix D | `devtools/mutation_check.py:40-61`, **tail only** (`:1895-1926`), `:2304-2325`; `config/quality_gates.yaml:26-31`, `:574-590`, `:696-716`; the five `find` lines only (§3); `tests/test_v1100_gates.py` (the group test); `tests/test_v1104_gates.py` | **yes** — brief `v1104-T2.md` (the strings and the apply command in the brief first) |
| **T3** | §9 (REV-01) | the review's own reading map; otherwise only commands run | no — *the task is itself the clean-context review*; a source-writing fix is delegated by brief `v1104-T3.md` |
| **T4** | §7, §4 (rows 7–12), §9 (Stage B′, B″) | `config/quality_gates.yaml` — the `mutation-v1103` block only (`:574-590`); `docs/spec/spec-v1.10.2.md:449-462`; `docs/spec/spec-v1.10.3.md:730-778` | **yes** for the calibration hunk — brief `v1104-T4.md` (the measured wall and the computed `timeout_seconds` in the brief first); **no** for the calibration run, gate 6, the write-tree and the live gate sequence — *commands only* |
| **T5** | §8, §9 (REV-02), §7 (the identity check), §4 (rows 12–13), §1 (rows 15–16, the floor) | first commit: `pyproject.toml` (`project.version` only); `README.md:594-600`, `:913-916`; `AGENTS.md:159-172`; `tests/test_v195_version.py`, `tests/test_v194_version.py:25-34`, `tests/test_v190_agents.py:134-152`; `tests/test_v1104_version.py`, `tests/test_v1104_docs.py`; second commit: this run's artefacts | **yes** for the first commit — brief `v1104-T5.md` (`pyproject.toml`, `uv.lock`, the tests and the documentation); **no** for the evidence commit only (*artefacts only*) |

---

## Appendix A — requirement traceability

The **twenty** rows are in bijection with the twenty `MUST` ids of
§§1–10; "Verified by" never means "by inspection"; every `T-V1104-*`
id of §6.1 is cited at least once.

| Requirement | Verified by |
|---|---|
| `REQ-V1104-EC-01` | `T-V1104-VER-02`; the gate tables and command record (no live gate after T4's gate 7 on any stop route); `T-V1104-DOC-03` |
| `REQ-V1104-EC-02` | the T0 count and T5 check; the T0 hit table (parts (i)–(iii), every hit classified); post-T0 amendments; `T-V1104-PIN-01`, `T-V1104-PIN-06` |
| `REQ-V1104-EC-03` | §10.1; the briefs `v1104-T1.md`, `-T2`, `-T4`, `-T5`, `-T3` iff a fix; the two T4 bullets; `T-V1104-RPT-01` |
| `REQ-V1104-EC-04` | T0 check 1's output; `db_empty=True`; the `describe()` pairs; `replay --range`; `gitleaks-tree`; `E7` |
| `REQ-V1104-MUT-01` | `T-V1104-MUT-01`, `T-V1104-MUT-02`, `T-V1104-MUT-05`; the stash record (identity, post-T1 `--check`, the post-image against Appendix D) and the per-entry proofs (exact node ids, selected count); `E1` |
| `REQ-V1104-MUT-02` | `T-V1104-MUT-03`, `T-V1104-MUT-04`; `E1`, `E3` |
| `REQ-V1104-PIN-01` | `T-V1104-PIN-01`, `T-V1104-PIN-02`, `T-V1104-PIN-03`, `T-V1104-PIN-04`, `T-V1104-PIN-06`; REV-01 item 2; `E2`, `E3` |
| `REQ-V1104-PIN-02` | `T-V1104-RPT-01`, `T-V1104-PIN-05`, `T-V1104-DOC-03`, `T-V1104-PIN-07`; `E4` |
| `REQ-V1104-ERR-01` | `T-V1104-ERR-01` (row 2); `T-V1103-LINT-02` and `T-V1104-PIN-07` (row 5); the task records (rows 1, 3, 14 in the T0 and T2 records); `E5` |
| `REQ-V1104-SEC-01` | `gitleaks-tree` at every commit; the command record; `T-V1104-MUT-02`; `E1`, `E8` |
| `REQ-V1104-TST-01` | the T5 collection check; `tests/test_v1104_*.py` present; Appendix A complete |
| `REQ-V1104-GATE-01` | the gate tables; `tested_tree` and the clean-tree proof; the reuse facts; the attempt log; `E5`, `E8` |
| `REQ-V1104-GATE-02` | `T-V1104-PIN-05`, `T-V1104-MUT-03`; the calibration and write-tree records; the brief `v1104-T4.md` and T4's one-hunk `git show --stat`; `E1` |
| `REQ-V1104-VER-01` | `T-V1104-VER-01`, `T-V1104-DOC-01`, `T-V1104-DOC-02`; the fallback record; `E6`, `E7`, `E8` |
| `REQ-V1104-RPT-01` | the report under `lint-docs` (`T-V1104-RPT-01`); the T0, T2, T4 and T5 records |
| `REQ-V1104-RPT-02` | `wc -m` quoted; `docs/llm-usage.md` rows; the fenced ledger row under `lint-docs` (`T-V1104-RPT-01`) |
| `REQ-V1104-RPT-03` | `T-V1104-DOC-01`, `T-V1104-DOC-02`, `T-V1104-DOC-03`, `T-V1104-DOC-04`, `T-V1104-DOC-05` |
| `REQ-V1104-REV-01` | the logged review prompt; findings closed or waived; `v1104-T3.md` iff a fix delegated |
| `REQ-V1104-REV-02` | `git show --stat` on the evidence commit; `E1`–`E7` in the report; `E8` in the closing message; the full suite green; `T-V1104-DOC-05` |
| `REQ-V1104-REV-03` | the stage named in the report; the stop-route table's assertions (`git show --stat` on the stop-route evidence commit within the stage's path set, `git status --porcelain` empty); the negative proofs; the reused gate-8 record; `T-V1104-RPT-01` on the stop-route report |

### Tails traceability

Every open item of `report-v1.10.3.md` and the facts file, mapped to
the id that closes or declines it:

| # | tail | closed by |
|---|---|---|
| 1 | the stop finding (`:582-635`): a fourth unlisted pin, 0 of 3 cycles; the per-pin budget rule | `EC-02`, `EC-01`, `ERR-01` row 4, `REV-03` |
| 2 | the parked pin `tests/test_v1102_gates.py:63-70` → `:80-87`, seen at T0, called "out of scope" (`:132-133`); `spec-v1.10.3.md:1203`'s stale `:113-125` cite (the anchor test is at `:131-145`) | `PIN-01` (EC-02 rows 1, 4; `T-V1104-PIN-01`, `-02`) |
| 3 | v1.10.3 GATE-02's table wrote `if False:` for entry 2; reality is the inner predicate (`:569`) | `MUT-01` (§3 row 2; `T-V1104-MUT-02`, `-05`) |
| 4 | v1.10.3 GATE-02's table named `T-V1103-LINT-06`/`-07` for entry 4; the killer is `-09` (`:571`) | `MUT-01` (§3 row 4; the isolation proofs) |
| 5 | `mutation-v1103`'s placeholder `timeout_seconds: 110`, calibration never run (`:574-577`); `mutation-all`'s timeout not re-measured at 144 | `MUT-02`, `GATE-02` (ERR-01 rows 7–8; the `[[VERIFY]]`) |
| 6 | the stale `AGENTS.md` count lines (`:161-162`, `:172`: 1638 / 120 vs 2285 / 139) | `RPT-03` (`T-V1104-DOC-04`); EC-02 row 16 |
| 7 | the unreached T7 block (`:636`): the bump, the release row, the `pending (T9)` rows, the `v1.9.5` clause, the tag, the version tests (`tests/test_v195_version.py`'s live pin); the ledger row at `Ver` 1.9.5 (`:742`) | `VER-01`; `RPT-03`; `RPT-02`; `RPT-01`; EC-02 row 15 |
| 8 | the stash's untracked parent `043842f` collides on `pop`/`apply` (facts §1); its three test hunks carry the frozen shapes | `MUT-01` (the two-path apply, identity-pinned; Appendix D the byte-exact fallback; test hunks not applied); `NG-03`; the post-push `stash drop` (REV-02) |
| 9 | the verifier's informational gate 8 on `f3ce1a5` (5/5, 4/4, 3/3, 0.957) | `NG-06`; `GATE-01` |
| 10 | the two README docs tests assert *no* `\| v1.10.3 \|` row (`tests/test_v1103_docs.py:99`, `tests/test_v1102_docs.py:130`) | `VER-01` (EC-02 rows 5–6; `T-V1104-DOC-01`, `T-V1104-PIN-06`); `NG-10` |
| 11 | `text.count("is now") == 1` over the whole yaml (`tests/test_v1102_gates.py:138`) | `PIN-01` (`T-V1104-PIN-04`) |
| 12 | `tests/test_v1103_gates.py:73-81` breaks on a future `mutation-v1104` label | EC-02's unaffected list; `NG-02` |
| 13 | the `.env` run file and the storage preflight; the check-2/3 numbering drift (`:39-44`) | `EC-04` (`data/run-v1104.db`; check 2) |
| 14 | `LLM_EVAL_CHAT_MODEL` as a cheaper eval route; a benchmark run or waiver edit | `NG-05`; `NG-04`; `EC-01` |
| 15 | `T-V1103-LINT-08` (the `report-v1.10.4.md` → `v1104` prefix test, `spec-v1.10.3.md:552-553`) was specified but never implemented — `tests/test_v1103_lint.py` at `f3ce1a5` uses only `report-v1.10.3.md` and `report-final.md` | `PIN-02` (`T-V1104-PIN-07`) — covered here |

---

## Appendix B — acceptance scenarios (Gherkin, written before code)

Offline, against fakes, `tmp_path` files and committed blobs; T5
records E1–E7 **before the evidence commit**; E8 is the
post-commit/pre-tag check (REV-02), reported in the closing message.

```gherkin
Feature: E1 — the five v1103-* entries landed as the stash has them
  Scenario: the committed tree (git rev-parse stash@{0} recorded as e3c6e3ff…; devtools/mutation_check.py the post-image of Appendix D)
    Then the five ids of §3 form one contiguous block, in order, after v1102-hal-gap-marker-dropped; each find matches once; each find/replace is byte-equal to §3; each mutant parses; mutation-v1103 sits in mutation-subsets only with mutation-v1102's key set; the mutation-all block holds exactly one "is now" parsing to len(MUTATIONS)

Feature: E2 — the tail is open
  Scenario: mc.MUTATIONS monkeypatched to the real list plus {"id": "v9999-probe", ...}
    Then both rewritten group tests pass; with the probe inside the v1102-* block, or the v1101-* block reversed, each raises AssertionError

Feature: E3 — the release-agnostic anchor and the narrowed count
  Scenario: DEFAULT_CONFIG_PATH monkeypatched to a tmp_path yaml whose block says "spec-v9.9.9 T9 appended one entry; `len(devtools.mutation_check.MUTATIONS)` is now 145" — the fixture carries the fragment the anchor regex matches — and mc.MUTATIONS monkeypatched to a list of length 145
    Then both anchor tests pass; an extra "is now" in the mutation-v1103 comment leaves the count test green, a second one inside the block makes it red

Feature: E4 — the repoints and the derived prefix
  Scenario: report_path docs/reports/report-v1.10.4.md, delegation_record true
    Then _lint_report_delegation on the committed report returns []; a bullet with brief: docs/spec/task-briefs/v1103-T1.md under ## T1 of a report named report-v1.10.4.md is red with "cell 4 is neither brief: — nor a v1104 task-brief path" (T-V1104-PIN-07)

Feature: E5 — a drifted find never mutates
  Scenario: a tmp_path root whose tools.py carries entry 1's find twice, a recording runner
    Then run_one returns (DRIFTED, None) and the runner was never called; with the find once the runner runs exactly once and the file is restored

Feature: E6 — the release rows assert presence, never absence
  Scenario: README's release table
    Then the v1.10.3 row equals VER-01's text from T1 on; after T5's first commit a v1.10.4 row ends "this release", the v1.9.5 row no longer does, the gate-8 table holds no "pending"; with a "| v1.10.9 | — | probe |" line appended every re-pinned docs test still passes

Feature: E7 — the version and the dependencies
  Scenario: T5's first commit
    Then pyproject.toml reads 1.10.4, git show v1.9.5:pyproject.toml reads 1.9.5, for pyproject.toml and uv.lock only the diff from the f3ce1a5 blobs is project-version-only, and NG-01's files equal their f3ce1a5 blobs

Feature: E8 — the freeze and the local tag
  Scenario: run before the tag on T5's evidence commit
    Then its name-only diff is exactly docs/reports/report-v1.10.4.md, docs/reports/tg-post-v1.10.4.md, the single docs/prompts/233-*.md file and docs/llm-usage.md; git tag -l lists no v1.10.4; git status -sb shows main ahead; git stash list still shows stash@{0}
  Scenario: Stage B at T5 (ERR-01 row 12 or 13)
    Then pyproject.toml reads 1.10.4, git tag -l lists no v1.10.4, the evidence commit is the last, the report names Stage B at T5 with one gate-8 execution at T4 — never Stage B″
```

---

## Appendix C — cross-review log

Placeholder: filled by the cross-review rounds before `Status:` moves
to ready for `go`.
rounds (up to three, against OpenAI Codex through the lab's seam)
before `Status:` moves to ready for `go`; each finding is ruled on
before it is applied.

### Round 1 of at most 3 — against the spec-v1.10.4 draft (`5b17454`); 9 findings, 8 accepted (2 adapted), 1 rejected

| # | sev | REQ(s) | verdict | change |
|---|---|---|---|---|
| R1-1 | Crit | MUT-02, PIN-01, `T-V1104-MUT-04`, `T-V1104-PIN-03`, E3 | rejected | Transport artefact: the spec's regex already carries the closing backtick (`MUTATIONS\)`\s*is now (\d+)`, verified by the audit against both the yaml sentence and the fixture); the challenger's copy lost it in transit; PIN-01 now says in one sentence that the anchor includes the backtick and that the sentence, the fixture and the regex are byte-consistent. |
| R1-2 | Crit | EC-01, GATE-01, REV-03 | accepted | Once T4's gate 5 and gate 7 have completed, no stop route may invoke any live gate again: Stage B′ (and B″) reuse T4's recorded gate-5, gate-7 and gate-8 results and finalise with offline checks only; the stop-route permission to invoke gates 5 and 7 applies only before their scheduled T4 execution. |
| R1-3 | Crit | EC-03, GATE-02, §10 T4–T5, §10.1 T4–T5 | accepted | T4's localized yaml calibration hunk is delegated under `docs/spec/task-briefs/v1104-T4.md` (T4's row split: `yes` for the hunk, `no` for the commands-only gate sequence; two report bullets); T5's brief covers `pyproject.toml`, `uv.lock`, the tests and the documentation; only the four-path evidence commit is *artefacts only*; EC-03's committed-brief list gains `v1104-T4.md`. |
| R1-4 | High | MUT-01, EC-01, NG-03, ERR-01 row 1, T0, T2, Appendix D | accepted, adapted | MUT-01 pins `git rev-parse stash@{0}` = `e3c6e3ff3bee60bff183ae056621d4dc984cd5a3` (recorded at T0); T2 re-runs the exact two-path `git apply --check` after T1; the fallback triggers when the stash is absent, has another id or fails the post-T1 check; the new Appendix D carries the two-path unified diff verbatim with its sha256 and the two per-path patch hashes; after applying (either route) T2 verifies the post-image before the isolation proofs — `git hash-object devtools/mutation_check.py` = Appendix D's `index` post-image `d09909d…`, the yaml's `mutation-subsets` line, `mutation-v1103` block and `mutation-all` comment equal Appendix D's post-image (no whole-file yaml hash: T1 repoints `report_path`); the verdict's post-apply sha256 values were the `f3ce1a5` pre-image blobs and are not written; NG-03 stays. |
| R1-5 | High | EC-02, ERR-01 row 14, T0, REV-01 item 3 | accepted, adapted | EC-02's T0 inventory is an explicit four-part literal `grep` over `tests/` and `devtools/checks.py`: (i) the frozen-list patterns, (ii) every reference to `report_path`, `_GATE_MATRIX_LABEL_TO_NAME`, `_parse_gate_matrix`, `task-briefs/v1`, `project.version` / `["version"]`, `1638`, `120 entries`, (iii) the absence and end-of-list forms (`not in`, `not any(`, `endswith(`, `[-1]`, `== [` on `_IDS`/`ids`/`labels` names), (iv) fail-closed — every hit classified before T1, an unclassified hit blocks construction without a repair cycle (ERR-01 row 14); the AST-inspection sub-point is rejected (no new tooling). |
| R1-6 | High | MUT-02, GATE-02, ERR-01 row 7, §10 T4, §10.1 T4 | accepted | T4 makes exactly one localized YAML hunk in the `mutation-v1103` block — the placeholder comment replaced by the dated measured-wall/formula comment and `timeout_seconds` set to the computed value even when it remains 110; no other YAML content changes; the hunk is delegated (R1-3). |
| R1-7 | High | MUT-01, ERR-01 row 3, RPT-01, §10 T2 | accepted | Each mutant's isolation proof collects and records the exact pytest node id(s) of the named `T-V1103-*` test, runs pytest with only those node ids — never `-k` — asserts at least one selected node fails for the expected reason and records the selected count; a collection miss or an extra selected node is a construction defect. |
| R1-8 | High | REV-02, REV-03, RPT-01, §10 | accepted | REV-03 carries a stop-route table — Stage B′ at T4, B″ at T4, B at T5 — with the exhaustive permitted paths, the prompt number (232 / 232 / 233), whether the evidence commit is the explicit exception to one-commit-per-task (yes at T4, no at T5), `tg-post-v1.10.4.md` required at every stage, and the last-commit and clean-tree assertions; Stage B at T5 uses REV-02's four-path set. |
| R1-9 | Med | REV-02, NG-01, `T-V1104-DOC-05` | accepted | REV-02's regression clause reads "no production or evaluation-instrument source changes; `devtools/mutation_check.py` differs from `f3ce1a5` only by MUT-01's five registry entries and rationale comment, while NG-01's pinned files remain byte-equal as scoped by `T-V1104-DOC-05`". |

**Round 1: 9 findings, 8 accepted (2 adapted), 1 rejected.** New
requirements: none (ERR-01 gains row 14; Appendix D added).

---

## Appendix D — the two-path stash diff (the byte-exact fallback)

The unified diff of `stash@{0}` (`e3c6e3ff3bee60bff183ae056621d4dc984cd5a3`)
restricted to `config/quality_gates.yaml` and
`devtools/mutation_check.py`, extracted from `git stash show -p
stash@{0}` in that order, **verbatim** — the five entries with their
`why` strings, the rationale comment and the yaml hunks in full. Its
`sha256sum` (the fenced content, from the first `diff --git` line to the
last line before the closing fence, each line newline-terminated) is
`a54e5faedeaa239759d768cec8b6636982e517cafed03281a441949e440d9e11`; the
per-path patch hashes are `config/quality_gates.yaml`
`df2032f3d2282263dbabf99c066cfcb815edf5f8982fb1fc3dfd24a2fc5f6744`
(lines 1–59) and `devtools/mutation_check.py`
`c5c94ba851fe89379b4aa48888ff410542fa3bc41338faba69270efa976d7a77`
(line 60 to the end). Pre-images `c084c23` / `1baeeb2` are the
`f3ce1a5` blobs; the `index` post-images `d09909d` / `9cbd154` are the
`stash@{0}` blobs. On the fallback (MUT-01, ERR-01 row 1) T2 extracts
this block into a file, asserts the hash, and applies it with `git
apply` from the repository root; on either route the post-image is
verified as MUT-01 says. The `mutation-all` sentence this diff adds is
then rewritten to MUT-02 (c)'s; the placeholder comment is replaced at
T4 (GATE-02).

```diff
diff --git a/config/quality_gates.yaml b/config/quality_gates.yaml
index 1baeeb2..9cbd154 100644
--- a/config/quality_gates.yaml
+++ b/config/quality_gates.yaml
@@ -27,7 +27,8 @@ profiles:
   # `mutation_check.py --select <prefix>` directly, kept for this
   # release's T2/T3 re-measurements and any future per-range work.
   mutation-subsets: [mutation-v15, mutation-v160, mutation-v170, mutation-v180,
-                     mutation-v190, mutation-v1100, mutation-v1101, mutation-v1102]
+                     mutation-v190, mutation-v1100, mutation-v1101, mutation-v1102,
+                     mutation-v1103]
 
 # T1 writes each pin at its currently-installed version (REQ-V15-DEP-04);
 # trivy and skylos are not installed yet and stay absent from this block
@@ -587,6 +588,29 @@ gates:
     diff_scoped: false
     timeout_seconds: 110
 
+  # spec-v1.10.3 T6 (docs/spec/task-briefs/v1103-T6.md, REQ-V1103-GATE-02):
+  # five v1103-* entries added (144 total in MUTATIONS -- see mutation-all's
+  # own dated comment below). Same bootstrapping constraint as
+  # mutation-v1100's/mutation-v1101's/mutation-v1102's comments above: this
+  # task's own per-entry sanity checks (mutate -> run the one targeted test
+  # -> revert, never the CLI's mutate -> run -> revert machinery over the
+  # whole list or under --select "v1103-") confirmed each of the five
+  # entries killed by its expected test, but did not time the five as a
+  # group under the real runner.
+  # calibration pending, orchestrator fills this: timeout_seconds below is
+  # a placeholder matching v1102's value until the orchestrator runs the
+  # one-time `--select v1103-` calibration (wall x 2 + 70s, rounded up to
+  # 10s) and commits the real number separately.
+  mutation-v1103:
+    kind: command
+    result_mode: exit_status
+    argv: [uv, run, --locked, python, devtools/mutation_check.py, --select, "v1103-"]
+    placeholders: {}
+    success_exit_codes: [0]
+    blocking: true
+    diff_scoped: false
+    timeout_seconds: 110
+
   # mutation-all: T13 measured 1908.041s at 82 entries (2026-09-05); T14
   # added an eleventh v160-* entry (83 total). Orchestrator re-measured
   # directly on 2026-09-05 (`time uv run --locked python
@@ -701,10 +725,13 @@ gates:
   # larger table.
   #
   # spec-v1.10.2 T5 appended 6 `v1102-*` entries; `len(devtools.
-  # mutation_check.MUTATIONS)` is now 139. This task does not touch this
+  # mutation_check.MUTATIONS)` closed at 139. This task does not touch this
   # gate's own `argv` or `timeout_seconds` either -- the orchestrator's
   # authoritative all-139 run immediately after this task's commit is what
   # will confirm (or refute) 1640s still covers the larger table.
+  #
+  # spec-v1.10.3 T6 appended 5 `v1103-*` entries; `len(devtools.
+  # mutation_check.MUTATIONS)` is now 144.
   mutation-all:
     kind: command
     result_mode: exit_status
diff --git a/devtools/mutation_check.py b/devtools/mutation_check.py
index c084c23..d09909d 100644
--- a/devtools/mutation_check.py
+++ b/devtools/mutation_check.py
@@ -1920,6 +1920,108 @@ MUTATIONS = [
         "regex_positives/negatives cases, and test_t_v1102_rt_09_exact_"
         "lengths_and_last_entries -- matches, no discrepancy.",
     },
+    # -- spec-v1.10.3 T6 (docs/spec/task-briefs/v1103-T6.md,
+    # REQ-V1103-GATE-02): five entries defending T1's three exec-guard
+    # rules (tools.py), T3's delegation-record lint gate
+    # (devtools/checks.py) and T2's noun-before-«нет» HAL_MARKERS entry
+    # (devtools/agent_eval.py). GATE-02's table names a killer test per
+    # entry; empirically (mutate -> run -> revert, this task, each entry
+    # verified in isolation before being added) four of the five match
+    # the table exactly -- the delegation-lint entry is killed by a
+    # different test than the table names; the discrepancy is recorded
+    # on that entry below.
+    {
+        "id": "v1103-exec-guard-dropped",
+        "path": "tools.py",
+        "find": (
+            '    if os.path.basename(argv[0]) in EXEC_DENY_PROGRAMS:  # noqa: PTH119\n'
+        ),
+        "replace": '    if False:  # v1103-exec-guard-dropped  # noqa: PTH119\n',
+        "why": "REQ-V1103-GATE-02: rule 1 of _validate_exec_arguments must "
+        "refuse env/printenv by basename -- forcing the predicate to False "
+        "lets every guard-1-shaped argv run unrefused through the sandbox, "
+        "body retained, syntax-preserving. Spec table names "
+        "T-V1103-EXEC-01/-05 as killers; empirically (mutate -> run -> "
+        "revert, this task) confirmed as tests/test_v1103_exec.py's "
+        "test_t_v1103_exec_01_rule1_denies_env_programs (T-V1103-EXEC-01, "
+        "parametrised, all four cases red on the refusal-shape assertion) "
+        "-- matches, no discrepancy.",
+    },
+    {
+        "id": "v1103-exec-guard-env-file-dropped",
+        "path": "tools.py",
+        "find": (
+            '        os.path.basename(e) == ".env" or os.path.basename(e).startswith('
+            '".env.")  # noqa: PTH119\n'
+        ),
+        "replace": '        False  # v1103-exec-guard-env-file-dropped\n',
+        "why": "REQ-V1103-GATE-02: rule 2's predicate must catch a "
+        ".env-basename file anywhere in argv -- forcing the inner "
+        "any(...) generator's predicate to False collapses the guard to "
+        "any(False for e in argv), always False regardless of argv's "
+        "contents; the outer `if any(...):` line and its body are "
+        "untouched, so the mutant is syntax-preserving. Spec table names "
+        "T-V1103-EXEC-02 as the killer; empirically (mutate -> run -> "
+        "revert, this task) confirmed as tests/test_v1103_exec.py's "
+        "test_t_v1103_exec_02_rule2_denies_env_files (T-V1103-EXEC-02, "
+        "parametrised, all five cases red) -- matches, no discrepancy.",
+    },
+    {
+        "id": "v1103-exec-guard-proc-environ-dropped",
+        "path": "tools.py",
+        "find": '    if any(_PROCFS_ENVIRON_RE.fullmatch(e) for e in argv):\n',
+        "replace": '    if False:  # v1103-exec-guard-proc-environ-dropped\n',
+        "why": "REQ-V1103-GATE-02: rule 3 must refuse a full-match "
+        "/proc/<pid-or-self>/environ path -- forcing the predicate to "
+        "False lets every such path run unrefused, body retained. Spec "
+        "table names T-V1103-EXEC-03 as the killer; empirically (mutate "
+        "-> run -> revert, this task) confirmed as "
+        "tests/test_v1103_exec.py's "
+        "test_t_v1103_exec_03_rule3_denies_procfs_environ (T-V1103-EXEC-03, "
+        "parametrised, all three cases red) -- matches, no discrepancy.",
+    },
+    {
+        "id": "v1103-delegation-lint-dropped",
+        "path": "devtools/checks.py",
+        "find": '    if gate.get("delegation_record") is True:\n',
+        "replace": '    if False:  # v1103-delegation-lint-dropped\n',
+        "why": "REQ-V1103-GATE-02: _run_lint_docs must run "
+        "_lint_report_delegation whenever the gate's delegation_record key "
+        "is exactly True -- forcing the guard to False means the "
+        "delegation check never runs regardless of the key's value, so a "
+        "report with zero delegation-record bullets never blocks. Spec "
+        "table names T-V1103-LINT-06/-07 as killers; empirically (mutate "
+        "-> run -> revert, this task) those two tests exercise "
+        "_validate_one_gate/_lint_report_delegation directly and stay "
+        "green under this mutant (confirmed: pytest -k "
+        '"test_t_v1103_lint_06 or test_t_v1103_lint_07" all pass '
+        "unmutated). The actual killer is tests/test_v1103_lint.py's "
+        "test_t_v1103_lint_09_true_key_runs_the_check_and_blocks "
+        "(T-V1103-LINT-09, the one test that calls _run_lint_docs itself "
+        "with delegation_record: True) -- a discrepancy from the table.",
+    },
+    {
+        "id": "v1103-hal-noun-first-marker-dropped",
+        "path": "devtools/agent_eval.py",
+        "find": (
+            '    r"(?:информации|данных|сведений)\\b(?:(?!\\b(?:но|а|однако|зато)\\b)'
+            '[^.?!;…]){0,120}\\bнет\\b",\n'
+        ),
+        "replace": "",
+        "why": "REQ-V1103-RT-01: HAL_MARKERS must carry exactly eighteen "
+        "entries, the eighteenth being the noun-before-«нет» gap-token-"
+        "class regex covering HAL-02's red-reply phrasing (the noun "
+        "precedes «нет», which none of the first seventeen markers catch) "
+        "-- removing it drops both the list length and check_"
+        "hallucination's coverage of that phrasing. Spec table names "
+        "T-V1103-RT-01/-08 as killers; empirically (mutate -> run -> "
+        "revert, this task) confirmed as tests/test_v1103_red_team.py's "
+        "test_t_v1103_rt_01_hal_markers_has_exactly_eighteen_entries "
+        "(T-V1103-RT-01, AssertionError: assert 17 == 18) and "
+        "test_t_v1103_rt_08_inj_markers_and_hal_markers_pins "
+        "(T-V1103-RT-08, IndexError on the pinned HAL_MARKERS[17] index, "
+        "the list's own last-index pin) -- matches, no discrepancy.",
+    },
 ]
 
 _IDS = [m["id"] for m in MUTATIONS]
```
