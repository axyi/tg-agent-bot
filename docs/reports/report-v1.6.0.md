# Implementation report — spec-v1.6.0

**Status: STOPPED at T15, closed (operator decision, 2026-09-06).** The
preflight itself (REQ-V160-PRE-04) was resolved and passes — see "Live
preflight and STOP" below. `smoke-v160` (REQ-V160-BEN-07) then surfaced a
deterministic blocker (`S13` exceeds `tool_calls_max(4)` 5/5 across
repeats, always the correct answer — REQ-V160-TQ-06's own check working
as designed, not loosened) plus an unmet documentary precondition (the
one smoke run that executed all six scenarios was lost to this session's
own `.bench/`-wipe mistake, see "`smoke-v160` and the S13 blocker" below).
Presented to the operator as one decision: accept the stop, or authorise
a scoped correction to `S13`'s ceiling. **The operator chose to accept
the stop.** T16 (baseline), T17 (report finalisation) and T18 (final
acceptance + the `v1.6.0` tag) are **not executed this run.** T0–T14
stand as landed, gated, reviewed code on `main`; `pyproject.toml` already
reads `"1.6.0"` (from T12) but **no `v1.6.0` git tag exists** — see the
"Run closed at T15" section at the end of this report for the full
closing note.

- **Spec:** `docs/spec/spec-v1.6.0.md`
- **Spec `sha256`** (recorded at T0, MUST NOT change during the run):
  `1a2bcadaa1ce9ec703c2f8d82f8dcda93c63e925dca710d6ae12eb17fb4679ec`
- **Executor:** claude-sonnet-5 (Claude Code)
- **`<base>`** (HEAD before this run's first commit):
  `d7e1d395bdb37d575e95ce3dbef1893172d9329e`
- **`<implementation-tip>`**: recorded at T17/T18 — a commit cannot contain
  its own SHA.

## Operator inputs

Supplied by the operator in the turn following the initial `go` request
(which itself carried neither value, correctly stopping the executor at T0
per REQ-V160-PRE-04):

- **LM Studio version:** `Bionic v1.1.1`
- **LM Studio address:** `http://192.168.0.145:1234/v1` (probed and
  confirmed reachable at T0; the `.env` rewrite of REQ-V160-PRE-03 itself
  still runs at T15, not here)
- **Loaded context length:** `42496` (positive integer; this is the
  *operationally loaded* value the operator read off the running instance,
  not `LMSTUDIO_CONTEXT_LENGTH` from `.env`/`Config`, which REQ-V160-PRE-04
  explicitly distinguishes)
- **Served model id** (for reference only — the formal value is populated at
  T15 from a live `GET <base>/models` read, per REQ-V160-PRE-04's table):
  operator-reported as `qwen/qwen3.8-27b`
- **Dashboard port override:** none requested ("take a free one"); `8765`
  confirmed free at T0, so the default stands.

## Preconditions (T0 — REQ-V160-PRE-01, PRE-02, PRE-04)

Gates 1–4 and 6 of §14, run verbatim, offline, before any change in this
run. Gate 5 (`bot.py --selftest-live`) and the `full` profile's live member
are **not** run here — REQ-V160-PRE-04 reserves them for T15.

| # | gate | command | exit |
|---|---|---|---|
| 1 | uv sync | `uv sync --locked` | 0 — 15 packages resolved, 13 checked, no new dependency |
| 2 | ruff check | `uv run --locked ruff check .` | 0 |
| 3 | pytest | `uv run --locked pytest` | 0 — 843 collected, all pass |
| 4 | selftest | `uv run --locked python bot.py --selftest` | 0 |
| 5 | selftest-live | *(deferred to T15 per REQ-V160-PRE-04)* | — |
| 6 | mutation | `uv run --locked python devtools/mutation_check.py` | 0 — 72 mutations, 72 killed, 0 survived, 0 errored, 0 drifted |

`full` profile's remaining non-live members, run in their own right (the
CLI has no per-gate exclusion flag, so these were run individually rather
than through `checks.py run --profile full`, which would have attempted the
live member; each is noted with how it was actually invoked):

- `ruff format --check` — 44 pre-existing files would reformat; per the
  profile matrix (REQ-V160-GATE-03) this is "blocking on new files only,
  shadow elsewhere," and no new file exists yet at T0, so this is
  informational, not a failure (REQ-V15-NG-04: no whole-tree reformat).
- branch-name — on `main`, warn-only per `warn_refs`, passes.
- `gitleaks dir` — run against the actual git-tracked tree, materialised via
  `checks.py`'s own `materialize_tracked_tree`/`list_tree_entries("HEAD", …)`
  (not the raw working directory, which also holds git-ignored `.env`,
  `.idea/` and `__pycache__/` content and produced four false positives on
  a first, incorrect attempt): **0 leaks**.
- trivy / semgrep — both `diff_scoped: true`; at T0, `<base> == HEAD`, so the
  diff is empty and these have nothing to scan yet. Exercised for real from
  T1 on as source changes land.
- skylos — shadow (`blocking: false` always); same empty-diff note as
  trivy/semgrep at T0.
- `install_hooks.py --check` — 0, hooks installed correctly.
- `checks.py doctor` — 0, all six pinned tools at pin.
- `checks.py lint-docs` — 0 (checks `docs/reports/report-v1.5.md`'s ledger
  row today; `config/quality_gates.yaml`'s `report_path` pointer moves to
  this file at T13, alongside the new mutation gate it already touches).

Test count re-measured at HEAD: **843** (`uv run --locked pytest
--collect-only -q`), matching REQ-V160-EC-03's floor exactly — no drift
since the 2026-09-04 measurement the spec cites.

Docker: `docker version` exits 0, no `sudo` needed. The digest-pinned
`python:3.14-slim@sha256:cad9a2c871761c413caa6fdd6441c783451e740a48aaeba60ae62a8b53525ef6`
(`config.py:28`) is present locally.

`.env`: present, git-ignored, keys checked by name only —
`TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`, `LMSTUDIO_BASE_URL`,
`LMSTUDIO_MODEL` present. Values never read or printed.

Port `127.0.0.1:8765`: free at T0.

`docs/prompts/71-v160-spec-authoring.md` and `docs/spec/spec-v1.6.0.md` are
present and already committed at HEAD (`d7e1d39`); `71` is the highest
pre-existing prompt number, confirming this run's `go` prompt is `72`
(REQ-V160-TREE-03's prompt-numbering rule). `docs/spec/spec-v1.5.md`,
`docs/reports/report-v1.5.md` and `docs/reports/report-v1.5.1.md` are all
present at HEAD.

## Benchmark-affecting changes (REQ-V160-EC-06)

Declared up front, per the spec: (1) REQ-V160-TQ-01, the truncated-summary
retry; (2) REQ-V160-TQ-04, the repeat-call refusal. Both change tool/summary
output the benchmark observes. §11 records a **fresh, post-change** baseline
(`baseline-v1.6.0.json`); this is explicitly not a before/after comparison,
and the `AGENTS.md` before/after rule is superseded for these two changes by
REQ-V160-EC-06.

## RLM delegation record, per task (REQ-V160-EC-07)

| T | delegated? | to what |
|---|---|---|
| T0 | no | — |
| T1 | no | — (reading stayed within `config.py:118-135`, `:455-540` plus the new files) |
| T2 | yes | general-purpose subagent, full task (schema migration + storage helpers) |
| T3 | no (deviation, justified in `docs/prompts/76-v160-t3-agent-span-wiring.md`) | reading stayed within the map's ranges; done directly rather than by a subagent because TRC-08's turn_id repair over the existing retry control flow is exactly the kind of high-risk mechanism this release requires mutation proof for, and the reading cost was already paid |
| T4 | no | — (matches §14.1: whole-file reads of `metrics.py` and `bot.py:776-830` only) |
| T5 | yes | general-purpose subagent, full task (dashboard_render.py + devtools/dashboard.py refactor) |
| T6 | no | — (matches §14.1: one new self-contained module, same shape as T1) |
| T7 | no | — (matches §14.1: CLI grammar and server lifecycle interleave with `main()`'s existing startup/shutdown sequence closely enough that a fresh subagent would need to re-derive the T3/T6 control-flow understanding already in hand) |
| T8 | no | — (matches §14.1: the truncation retry interleaves with `_ask_for_summary`'s existing malformed-JSON repair path and the shared `_record_llm_call` transaction sequence closely enough that a fresh subagent would need to re-derive the T3 control-flow understanding already in hand) |
| T9 | no | — (matches §14.1: the refusal decision sits directly inside `_execute_tool_calls`'s existing budget/excess branching, small and self-contained enough that direct implementation is cheaper than a delegation round-trip) |
| T10 | yes | general-purpose subagent, full task (six literal scenarios + `tool_calls_max` kind + `_validate_catalog` rule + `tests/test_v160_bench.py`); orchestrator applied a bounded follow-up fix to `tests/test_bench.py` (see Deviations) |
| T11 | yes | general-purpose subagent, full task (`BENCH_SCHEMA` 2, `runs[].spans`, `_validate`'s `mode`, six locked `meta` fields, dirty-tree guard, the bench.py:1420-1422 report-text fix, plus REQ-V160-TRC-11's own bench-side wiring, undiscovered until this task); orchestrator confirmed one genuine design decision and tracked one open gap for T16 (see Deviations) |
| T12 | yes | general-purpose subagent, full task (`pyproject.toml` version bump, `README.md`/`AGENTS.md`/`docs/plan.md` documentation catch-up); orchestrator independently re-verified all gates (see Deviations) |
| T13 | yes | general-purpose subagent, full task (ten `v160-*` mutation entries, `mutation-v160` gate, both re-measured timeouts — subagent ran `mutation_check.py` itself, the one authorised exception to the no-self-run rule); orchestrator independently reproduced the most consequential finding by hand-mutation before trusting it (see Deviations) |
| T14 | n/a | REQ-V160-EC-07's threshold does not apply — T14 *is* the clean-context review itself (REQ-V160-REV-01), run directly by the reviewing session over the full diff and the full 2726-line spec |
| T15 | no | — (matches §14.1: "only commands run," no file scope; the live preflight's own diagnostic step is a second read-only completion call, not a delegable implementation task) |

*(filled in per task as the run proceeds)*

## Deviations (running log — compiled into the final §13 Deviations at T17)

**T2 — two existing tests amended outside §15.1's list, both forced,
mechanical consequences of `SCHEMA_VERSION` 3 → 4 that the list does not
enumerate.** §15.1 names exactly one amendment to
`tests/test_observability.py:431` (`SCHEMA_VERSION == 3` → `== 4`, `"spans"`
added to the checked-table loop) and marks the list "exhaustive" —
REQ-V160-EC-03: "a change making an unlisted test fail means the change is
wrong — stop and reconsider, do not edit the test." Implementing T2 (the
version bump REQ-V160-AMEND-01 itself mandates) also broke two further
tests that were not anticipated:

- `tests/test_observability.py::test_obs03_a_future_version_is_still_refused`
  hardcoded `UPDATE schema_version SET version = 4` / `assert "4" in
  str(raised.value)` to mean "one past the current max." With 4 now
  supported, this stopped testing a future version at all.
- `tests/test_summary.py::test_t_v1_sum_01_migration_from_version_one` had
  the identical pattern (`version = 4` / `assert "4" in …`).

Both were bumped to `5` — the only value that keeps either test asserting
what its name says it asserts ("a future version is still refused"); there
is no alternative reading under which the change is "wrong" and should be
reconsidered, since REQ-V160-AMEND-01 mandates the version bump outright.
Swept the full test tree afterward (`grep` for `SCHEMA_VERSION`/hardcoded
`version = `) to confirm no third instance survived — none did; the other
existing references (`tests/test_storage.py:44`, `tests/test_summary.py`
:139/147/165) already compare against `storage.SCHEMA_VERSION` dynamically,
matching §15.1's "Explicitly NOT amended" list.

Recorded per REQ-V12-REP-02 process honesty. Worth feeding back: §15.1's
exhaustiveness claim should be verified against the repository (as PRE-01
items are) rather than asserted, at least for any requirement that changes
a version constant multiple tests hardcode independently.

**T5 — REQ-V160-TST-02's test-first rule was not followed.** `dashboard_render.py`
and the refactored `devtools/dashboard.py` were written before
`tests/test_v160_dashboard.py`; the new suite was not observed to fail
against an absent implementation first. 21 of the 23 new tests passed on
their first run against already-written code — the other two
(`test_t_v160_dsh_01_dashboard_render_never_imports_devtools`, which
initially flagged the module's own docstring mentioning `devtools/dashboard.py`
in prose, and `test_t_v160_dsh_07_histogram_zero_count_bucket_still_shows_its_label`,
whose overflow-bucket assertion did not account for `esc()`'s own escaping
of `>`) failed on the first run and were corrected in the test, not the
implementation, which is the opposite of what test-first would have shown.
Rationale, not excuse: T5's own byte-identity constraint (REQ-V160-DSH-05 —
`render()`'s output must match the pre-refactor page exactly) meant the
relocation had to be verified against the *existing* `tests/test_dashboard.py`
suite as the primary correctness signal before any new test made sense to
write; the new DTO/chart/section functions were then implemented as one
unit against the spec text directly. Recorded per REQ-V12-REP-02; no
retroactive "write it red first" was attempted, as that would be theater
over code already known to work.

**T5 — REQ-V160-PRE-04's T15-only reservation on gate 5 was violated.**
`docs/prompts/78-v160-t5-dashboard-render.md`'s own Acceptance section
(part of the committed `b3cb9a0` diff) states: "`uv run --locked python
bot.py --selftest` and `--selftest-live` both exit 0 (the live gate's
`docker` check required pulling `python:3.14-slim@<pinned digest>` into
this environment first — an environment provisioning step, not a code
change)." REQ-V160-PRE-04 reserves gate 5 exclusively for T15, after
REQ-V160-PRE-03 resolves the LM Studio address; R1-4's cross-review
decision (Appendix C) is explicit that "T0 is offline-only," and T5 falls
inside that window. This was not requested by T5's delegation brief (which
asked only for `ruff check`, `ruff format --check` on new files, `pytest`
and `mutation_check.py`) and was not recorded in this Deviations log by the
delegated subagent — discovered afterward by the orchestrator, cross-
checked with a fresh, independent verification agent (2026-09-05) with no
memory of T5's execution, working from the committed artefacts alone.

That agent could not confirm from repo-local evidence (`~/.bash_history`,
`~/.local/share/rtk/tee/`) whether a real network call actually reached
LM Studio/OpenRouter, nor resolve why a `docker pull` would have been
needed when T0's own record (this file, §"Preconditions") already found
the pinned digest present locally on 2026-09-04 — a discrepancy left
unresolved. What is established by reading `bot.py`'s `run_selftest_live`
directly: by design it never spends an inference token — the LM Studio
check is `GET {base}/models` and the OpenRouter check is `GET
https://openrouter.ai/api/v1/models`, both listing endpoints, no
`chat/completions` call. So even on the worst-case reading (the live
calls really fired), no paid inference occurred and no secret was
exposed beyond the OpenRouter key reaching its own legitimate endpoint
exactly as `run_selftest_live` always sends it. The violation is of
REQ-V160-PRE-04's *ordering* rule, not of secrets discipline or of cost
control. No corrective rerun of T5 was performed: its actual deliverable
(`dashboard_render.py`, the `devtools/dashboard.py` refactor) is
independently verified correct (927 tests, 72/72 mutations, both
re-checked by the orchestrator after the fact) and unaffected by this
process deviation. T15 will still perform its own from-scratch PRE-03/
PRE-04 resolution and preflight regardless, per §17's ordering, so this
does not shortcut or invalidate anything T15 itself must do.

**T8 — two existing tests amended outside §15.1's list, both forced,
mechanical consequences of `summarize_conversation` gaining a keyword-only
`retry_max_tokens` parameter that the list does not enumerate.** Two
pre-existing test doubles fully replace `agent.summarize_conversation` and
mirror its whole caller-visible signature: `tests/test_pricing.py`'s
`fake_summarize` inside
`test_prc02_the_resolver_reaches_the_summarizer`, and a `lambda` in
`tests/test_v11_patch.py::test_t_v11_red_04_summary_reply_redacted_only_by_send`
(whose own comment already documents the "mirrors the *whole*
caller-visible signature" intent). `bot.py` now always passes
`retry_max_tokens=cfg.llm_summary_max_tokens` at both call sites
(REQ-V160-TQ-02), so both stubs raised `TypeError` on the unexpected
keyword before either test's own assertions ran. Both gained
`retry_max_tokens=None` in their signature and nothing else — no
behavioural change, the same shape as T2's precedent. Swept
`tests/*.py` for any other `summarize_conversation` stub/lambda
afterward; none found.

**T10 — five existing tests amended outside §15.1's list, all forced by
`SCENARIOS` growing from 12 to 18 (REQ-V160-TQ-05), plus one deliberately
NOT touched.** `tests/test_bench.py:249` (`len(SCENARIOS) == 12` and the
`S01..S12` id range — the test itself renamed
`test_catalog_is_the_twelve_frozen_scenarios` →
`..._eighteen_frozen_scenarios` for honesty, nothing else about it
touched); `:401-403` and `:408-409` (`skipped_scenarios == ["S08"]` →
`["S08", "S17"]`, S17 being the second `network=True` scenario S13-S18
add, plus the run/skip counts that follow from it); `:1334` (the literal
`"failed_calls rose 0 → 24"` → `"→ 36"`, `_pair()`'s 2-failed-rows-per-
scenario fixture scaling with the catalogue). All four are pure literal-
value updates — no alternative reading makes the change "wrong" per
REQ-V160-EC-03, since REQ-V160-TQ-05 mandates the scenario count outright.

The fifth, `:1350` (`test_the_quality_gate_allows_no_lost_run`), is **not**
a literal bump: `bench.QUALITY_GATE_SLACK = 0.02` is a fixed 2-percentage-
point tolerance, and at the old 12-scenario x 3-repeat = 36-run
denominator, one lost run (2.78 pp) deliberately exceeded it, tripping the
quality gate. At 18 x 3 = 54 runs the same single lost run is only 1.85 pp
— now *inside* the slack, so the gate would silently start passing a
regression it used to catch. Consulted `advisor()` before acting, since
recalibrating a quality-gate formula is a design decision, not a
mechanical one. Resolution: **`QUALITY_GATE_SLACK` itself is untouched**
— REQ-V160-NG-02 explicitly defers *any* cost or quality gate against the
new baseline to v1.7.0 ("gating on an instrument recorded in the same run
is circular"), which reads as covering recalibrating this constant too.
Instead the test's own `_pair(repeats=3, ...)` became `_pair(repeats=2,
...)` (18 x 2 = 36, the same denominator as before), restoring the exact
property the test's name asserts without touching anything out of T10's
scope. A related, separate finding — `bench.py:1420-1422` emits an
f-string into the rendered **report** (not just a comment) claiming "one
flipped run is already 2.8–3.0 pp", which is now false at 18 scenarios and
would land in a T16-committed artifact — is tracked as a new task for T11
(which owns that code) rather than fixed here, since T10 does not own
`bench.py`'s report-rendering section.

Delegated to a general-purpose subagent (RLM: whole-file
`devtools/bench_scenarios.py`, ~160-line check-evaluation region of
`devtools/bench.py`); the subagent's own delegation brief explicitly
forbade it from touching `tests/test_bench.py` even if a test broke, so
these five amendments were applied by the orchestrator after review, not
by the subagent. Swept for a sixth affected assertion (grepped
`devtools/` for bare `12`/`36` literals outside test files); none found.

**T11 — REQ-V160-TRC-11 wiring was missing, not merely unread; one bug
found and fixed; one design decision confirmed; one gap tracked for T16.**
Four findings, all documented in the subagent's own
`docs/prompts/85-v160-t11-bench-schema2.md` and independently verified by
the orchestrator before commit:

1. **`tracing.set_run_context` had zero callers in `devtools/bench.py`
   before this task**, contrary to the delegation brief's premise that
   scenario/tag attribution already existed. The spec's own task table
   confirms this by mapping TRC-11 to `T-V160-BEN-03` inside T11's row, not
   T3's. The subagent did the wiring itself: `run_bench`/`_execute_run`
   gained an optional `tag: str | None = None` (defaulted, so none of the
   ~13 existing direct `run_bench(...)` test callers needed amendment),
   calling `tracing.set_run_context(...)` unconditionally once per run so
   the process-global `tracing._run_context` never leaks a stale tag
   forward. Verified independently: a real `run_bench` call now produces
   genuine `spans` rows that round-trip through `check_document`.
2. **A real, pre-existing bug**: `TOOL_ROW_KEYS` doubled as its own
   REQUIRED bound on a comment's premise ("that schema is unchanged by this
   spec") that had been stale since T2/T3 added `trace_id`/`span_id` to
   `storage.TOOL_CALL_COLUMNS` with no REQUIRED fallback — silently making
   `docs/assets/bench/baseline-v1.4.json` (the real, committed artefact
   REQ-V160-BEN-02 keeps specifically for T16's informational comparison)
   unreadable on every commit since T2/T3, masked only because a bare
   `bench_schema` mismatch always raised first. Fixed with a new
   `REQUIRED_TOOL_ROW_KEYS`, mirroring how `REQUIRED_LLM_ROW_KEYS` already
   handles the identical situation. Orchestrator re-verified independently
   (not just trusting the subagent's own claim):
   `bench.check_document(json.loads(baseline-v1.4.json), <S01..S12 subset>,
   mode="informational")` returns `(0, "meta.scenarios_sha256 does not
   match devtools/bench_scenarios.py")` — exactly the one expected note,
   nothing else.
3. **One forced amendment outside the task's own file list**:
   `tests/test_dashboard.py::test_fixtures_are_arithmetically_valid_benchmark_documents`
   (not one of the two lines, `:136`/`:502`, §15.1 names for BEN-03) had to
   move from tolerating only a stale `scenarios_sha256` to
   `mode="informational"` outright, once `BENCH_SCHEMA` became 2 and its
   frozen, never-bumped dashboard fixtures (pinned at `bench_schema: 1`)
   started failing strict validation on schema too, not just on the digest.
   A forced, mechanical consequence of BEN-03's mandated schema bump, the
   same pattern as T2/T8/T10's amendments.
4. **One design decision, confirmed by the orchestrator**: `meta.lmstudio_version`/
   `served_model_id`/`lmstudio_context_length` have no live-probe source
   anywhere in `bench.py`'s call graph, by design — the first two are
   operator-typed text (the `go` request's own answers), the third a T15-
   exclusive live `/models` read this offline harness must never call
   itself. The subagent added three new optional CLI flags on `bench.py
   run` (`--lmstudio-version`, `--served-model-id`,
   `--lmstudio-context-length`) as the threading mechanism and flagged the
   choice explicitly rather than deciding it unilaterally. Confirmed: this
   is the only clean way to get operator/T15-preflight data into an offline
   CLI tool with no other channel, and it changes nothing for any caller
   that omits the flags. **Consequence for T15/T16**: their own `bench.py
   run` invocations must pass these three flags when running against
   `lmstudio`, or the six-key `meta` lock will carry three `null`s instead
   of the real instrument fingerprint.

A fifth item — `bench.py report`'s CLI has no scenario-narrowing flag, so
REQ-V160-BEN-02's actual S01–S12 comparison cannot be produced by a bare
CLI command yet, even though `check_document`'s Python `scenarios=`
parameter already supports it — was left unresolved on purpose (T11 does
not own BEN-02/-06, and T16's own task-table row adds no files of its
own). Tracked as a task-tracker item for T16 preparation, with both
resolution options recorded (a small scoped flag addition before T16, or
T16 calling the Python API directly instead of the CLI for this one
comparison).

Delegated to a general-purpose subagent (RLM: five separate regions of
`devtools/bench.py` — schema/constants, key-set derivation, run assembly,
validation, CLI/meta). Orchestrator independently re-ran all gates plus
the `baseline-v1.4.json` verification above before trusting the subagent's
own claims.

**T12 — one forced amendment outside the task's own file list
(`uv.lock`), both fully mechanical.** `uv sync --locked` (gate 1) failed
immediately after the `pyproject.toml` version bump: `uv.lock` records the
local `tg-agent-bot` package's own version independently
(`source = { virtual = "." }`), left out of sync by the edit. `uv lock`
regenerated exactly one line (`0.1.0` → `1.6.0` inside that package's own
block); orchestrator independently confirmed `git diff --stat uv.lock`
shows `1 file changed, 1 insertion(+), 1 deletion(-)`, no dependency
touched, and re-ran `uv sync --locked` to confirm it now succeeds. A
direct, unavoidable consequence of REQ-V160-VER-01 itself — no alternative
reading makes the version bump "wrong" per REQ-V160-EC-03.

Two scope decisions the subagent made and the orchestrator reviewed and
accepted: (1) `AGENTS.md` does not enumerate individual environment
variables anywhere (verified by the subagent's own reading, spot-checked
by the orchestrator against the committed diff), so the four new env vars
went into `README.md`'s `## Configure` table only, which was renamed
("Output windows, history and pricing" → "…, pricing and observability")
to stay accurate; (2) `AGENTS.md`'s gate section gained the measured
`pytest` count ("1004 tests as of spec-v1.6.0 T12") but deliberately left
the pre-existing "72 entries as of spec-v1.5" mutation-registry sentence
untouched, correctly deferring that number's update to T13's own commit
(the one that actually adds the ten new `v160-*` entries) — matching
REQ-V160-VER-06's "same commit as the change it describes" clause exactly,
and avoiding describing the not-yet-existing `mutation-v160` gate anywhere
in `AGENTS.md`.

Delegated to a general-purpose subagent (RLM: four large documentation
files — README.md 706 lines, AGENTS.md 192 lines, docs/plan.md 260 lines —
past this run's threshold). Orchestrator independently re-ran
`lint-docs`, `ruff check`, the full `pytest` suite (1004 passed, unchanged
— a docs-only task adds no tests), `bot.py --version` and `bot.py
--selftest` before trusting the subagent's own claims.

**T13 — one substituted mutation id, two related coverage gaps found and
independently reproduced, one recovered incident.** Full ten-row ledger
and both raw wall-clock measurements are in
`docs/prompts/87-v160-t13-mutation-entries.md`; the highlights:

1. **`v160-content-redact-bypassed` (spec §15.4's own id) could not be
   landed as prescribed.** Its named target — `tracing.py:343`,
   `set_content_attribute`'s `text = config.redact(value)` — is masked by
   a redundant upstream protection: every content-capture test path
   reaches this call with content already redacted by
   `storage.add_user_message`/`add_assistant_message` before `agent.py`
   ever re-reads it from storage, so removing this specific `redact()`
   call changes nothing any current test observes. **Orchestrator
   independently reproduced this by hand**: mutated the line directly,
   ran the full 1007-test suite, 0 failures, confirming the gap is real
   and not an artifact of the subagent's own testing. The subagent
   substituted `v160-status-message-redact-bypassed`, proving the same
   redact-before-storage mechanism one call site over
   (`MutableSpan.set_error`'s `tracing.py:224`, REQ-V160-TRC-11, which has
   no such upstream double-protection) rather than landing an entry that
   would look like it proves REQ-V160-TRC-10 while actually proving
   nothing — the right call: REQ-V160-REV-01 item 5 checking "a mutation
   entry whose `find` matches once" would have passed on a false premise
   otherwise. Ten `v160-*` entries landed either way (net count unchanged).
2. **A second, related gap**: `config.py:334`'s `load_config()`-path
   parsing of `OBS_CAPTURE_CONTENT` is equally untested (no test calls
   `load_config()` and inspects the resulting field for this variable
   specifically) — `v160-capture-content-default-on` was retargeted to the
   `Config` dataclass field default itself (`config.py:123`), which every
   content-capture test actually exercises.
3. **`T-V160-DSH-05`'s "canary sweep"** doesn't appear to exercise the
   specific error-body-echo failure mode `v160-error-echoes-request-input`
   proves — the real killer is N5
   (`test_n5_bad_params_400_names_only_the_parameter`). Not a defect in
   the landed entry (it is still honestly killed by a real test), just a
   mismatch between the spec table's claimed killer and what's actually
   true today.

All three flagged in a new task-tracker item for T14 (the clean-context
code review — the correct place per its own "findings are fixed, not
suppressed" rule and "every fix of this run lands here or earlier — never
after T16"), not fixed inside T13 itself, since T13's own file ownership
does not include the production/test files a real fix for finding 1 would
need to touch.

**Incident, disclosed for transparency**: mid-task, an earlier
(uncorrected) full-suite mutation measurement attempt was interrupted with
`pkill -9` while `bot.py` was mid-mutation, bypassing
`mutation_check.py`'s `finally`-based restore and briefly leaving the
working tree dirty outside the task's owned files. Caught via `git status
--porcelain`, restored with `git checkout -- bot.py`, and the restore was
verified — not assumed — by rerunning `tests/test_mutation_check.py`
before relaunching the (successful) corrected run via `nohup ... &
disown`. Orchestrator's own final `git status --porcelain` before staging
confirmed only the task's owned files were dirty.

Delegated to a general-purpose subagent (RLM: ten precise, unique-match
mutation targets across five production files, plus running and timing
the mutation suite twice — the one task in this run where an agent was
explicitly authorised to run `devtools/mutation_check.py` itself, since
measuring the two timeouts requires a real run). Given the mutation-all
run's own cost (~32 minutes, just completed successfully), the
orchestrator's gate-6 verification for this task consisted of: reading the
subagent's own just-completed 82/82 full-run output directly (not merely
trusting a secondhand claim), independently re-running `ruff check`,
`pytest` (1007 passed), `lint-docs` and `bot.py --selftest`, and — for the
one claim carrying real security weight — independently reproducing the
`tracing.py:343` finding by hand-mutation rather than accepting the
narrative. A third full 32-minute mutation run was judged disproportionate
given that level of direct verification already performed.

## Code review (T14, REQ-V160-REV-01)

Performed in a clean context (no memory of T0–T13's own reasoning), reading
`docs/spec/spec-v1.6.0.md` in full (2726 lines) and every commit from
`<base>` (`d7e1d395bdb37d575e95ce3dbef1893172d9329e`) to the T13 tip (16
commits). Review prompt: `docs/prompts/88-v160-t14-code-review.md`.

### REQ-V160-REV-01 checklist, item by item

| # | item | result | evidence |
|---|---|---|---|
| 1 | No production module imports `devtools/`; `dashboard_render.py` is the only HTML-emitting module | **FAIL → fixed, PASS** | `dashboard_server.py:466-468` and its `/` page footer line each held one HTML literal of their own. Grepped every top-level production module (`bot.py agent.py config.py storage.py metrics.py tools.py tracing.py dashboard_render.py dashboard_server.py llm/*.py`) for `devtools` — only docstring/comment mentions remain, no import |
| 2 | Every route, error routes included, sets all four security headers; no handler writes a request-derived string into a response body | **PASS** | `_write()` is the sole header-setting call site, reached by every `_respond`/`_send_fixed` path, the pre-routing `Host`-rejection `_FixedResponse` included. The one request-derived value reaching a body — `_parse_query`'s rejected/duplicate query *key name* in the 400 JSON `"parameter"` field — matches REQ-V160-API-03's own text ("the name of the offending parameter") and `N5`'s own assertions, which permit the key name and forbid only the value; not a finding |
| 3 | `connect_readonly` is the only path by which the server reaches the database; no server code path writes | **PASS** | Every connection in `dashboard_server.py` comes from `self._connect()` → `storage.connect_readonly`; every executed statement is a `SELECT`. `storage.connect_readonly` (storage.py:255-266) independently re-read: both `mode=ro` in the URI and `PRAGMA query_only = ON` are present together (T13's claim, reproduced here by direct reading, not merely trusted) |
| 4 | Every content attribute passes through `config.redact()` before storage; no content attribute ever reaches a dashboard response | **unproven → fixed, PASS** | `tracing.py`'s content-attribute redact call had no test reaching it with fresh, never-persisted content (T13's finding, independently reproduced again here — see Finding 3 below); no test proved the dashboard never serves one (the canary sweep did not exist — Finding 5). Both closed this task; `served_span()`'s structural key-drop is now proven end to end |
| 5 | Each mechanism of §15.4 has a mutation entry whose `find` matches exactly once | **PASS, 11/10** | All eleven `v160-*` entries in `devtools/mutation_check.py` cross-tabulated by reading each `find`/`replace`/`why` directly against §15.4's ten table rows (not trusted from the spec table or the T13 report). Ten now match their spec-named mechanism at its spec-named line (two retargeted this task — Findings 3–4); the eleventh, `v160-status-message-redact-bypassed`, proves an adjacent mechanism the ten-row table doesn't separately name and was kept, not removed, per this task's own brief. One pre-existing documentation mismatch, not a coverage gap: §15.4 names `T-V160-DSH-05` as `v160-error-echoes-request-input`'s killer; the real killer is `N5` — confirmed by reading both tests, `T-V160-DSH-05` (this task's own new canary sweep, Finding 5) exercises a different code path and does not touch this mutation either, since both seed only valid query parameters |

### Findings — all fixed, none waived

**1. 🔴 `dashboard_server.py:466-468` held an HTML literal of its own**
(`'<section id="errors"><h2>Errors</h2>...'`, plus a second literal building
the `/` page's `<p class="meta">` footer), violating REQ-V160-DSH-01
("`dashboard_render.py` is the only module in the repository that emits
HTML" / "`dashboard_server.py`... holds no HTML literal of its own").
*Failure scenario*: a future edit to the error-breakdown markup only touches
`dashboard_server.py`, drifting from `dashboard_render.py`'s escaping/styling
conventions with no single place enforcing consistency, and the module
boundary the spec's whole security model (`DSH-06`'s "escape once,
everywhere") depends on quietly erodes. *Fix*: added
`dashboard_render.error_breakdown_section(breakdown)` and
`dashboard_render.meta_line(text)`, two pure functions matching the module's
existing `<p class="meta">` idiom; `dashboard_server.py` now calls them
instead of building markup itself. Output is byte-identical (full suite
green, including the pre-existing byte-identity test `T-V160-DSH-02`).

**2. 🟡 `T-V160-DSH-01` as landed did not implement its own spec clause.**
§15.2's table states it as: "no string literal in `dashboard_server.py`
contains `<` followed by a letter or `/`." The landed test
(`test_t_v160_dsh_01_bench_report_imports_dashboard_render_and_emits_no_html`)
only swept `devtools/dashboard.py` against a five-needle list — which is
exactly why Finding 1 survived through T13 unnoticed. *Fix*: added
`test_t_v160_dsh_01_dashboard_server_holds_no_html_literal`, scanning
`dashboard_server.py`'s AST for `Constant` string nodes matching `<[A-Za-z/]`
(not a source regex, so a `<` inside a comparison operator, a type hint or a
docstring can never false-positive, and an f-string's literal segments —
visited by `ast.walk` as `Constant` nodes inside `JoinedStr` — can't
false-negative). Verified discriminating: pasting Finding 1's literal back
into `dashboard_server.py` makes this test fail at the correct line; with the
fix in place it passes.

**3. 🔴 `tracing.py`'s content-attribute redaction had no test reaching it
with genuinely fresh content** — the gap T13 found and independently
reproduced (hand-mutated `text = config.redact(value)` → `text = value`,
full suite, zero failures) but could not close inside its own file-ownership
scope. *Failure scenario, concretely*: an LLM response containing a secret
(a leaked credential the model echoes back, for instance) reaches
`gen_ai.output.messages` via `_record_llm_call`, which runs *before* the
reply is ever persisted (and redacted) by `finish()` — so this call is the
only thing standing between a fresh secret and a stored, dashboard-visible
span attribute, and nothing proved it worked. *Fix*: added
`test_t_v160_trc_10_content_capture_on_redacts_a_fresh_never_stored_secret`
(`tests/test_v160_observability.py`) — a `FakeLLM` response whose `.content`
carries a freshly `config.register_secret`-ed canary, asserted redacted in
the resulting `chat` span's `gen_ai.output.messages`. Verified the
discriminating property twice: by hand-mutation (exactly one failure — this
test — across all 1008 tests then present, confirmed via `junit.xml`
`tests="1008" failures="1"`), and through the real mutation harness
(`--only v160-content-redact-bypassed` → `killed`). Restored the spec's own
entry, `v160-content-redact-bypassed`, at its originally-named target
(`tracing.py:343`), landed *alongside* (not replacing) T13's
`v160-status-message-redact-bypassed` substitute — now 11 `v160-*` entries,
83 total. Updated `tests/test_mutation_check.py`'s `_V160_MUTATION_IDS` list
and both ordering/count-dependent test names (`_all_ten_entries_are_present`
→ `_all_eleven_entries_are_present`, similarly for the `--select` test),
`AGENTS.md`'s "82 entries" → "83 entries" sentence, and re-estimated (not
re-measured — see the note below) `mutation-v160`'s timeout in
`config/quality_gates.yaml`.

**4. 🟡 `config.py`'s `load_config()`-path parsing of `OBS_CAPTURE_CONTENT`
had no test calling `load_config()` and inspecting the result** (T13's
second reported gap) — every existing test built `Config` directly via
`make_cfg()`, bypassing `load_config()`'s own
`_parse_bool(source, "OBS_CAPTURE_CONTENT", False)` call entirely.
*Fix*: added `test_obs_capture_content_defaults_to_false_via_load_config`
and `test_obs_capture_content_rejects_anything_else` to
`tests/test_config.py`, matching `test_history_tool_stub_defaults_to_on`'s
existing shape for a sibling boolean env var. Verified via hand-mutation
(`False` → `True`; exactly two failures, both new tests, nothing else —
`junit.xml` `tests="1012" failures="2"`) and via the real harness
(`--only v160-capture-content-default-on` → `killed`). Retargeted that
mutation entry from T13's stand-in (the `Config` dataclass field default,
`config.py:123`) to the spec's own named line (`config.py:334`), now that a
real test proves it there.

**5. 🔴 `T-V160-DSH-05`/`-06` (the canary sweep, REQ-V160-DSH-07's own proof)
did not exist anywhere in the test suite.** REQ-V160-DSH-07 is a MUST; its
designated verification and Appendix B's scenario `E6` had no implementation
at all before this task — the closest existing test
(`test_a_trace_page_and_api_serve_real_spans`) checks `status_message`
absence on exactly one route, not a seeded secret swept across every served
route, response header and log line. *Failure scenario*: a future change to
a dashboard handler starts reading `messages`/`summaries` (e.g. to add a
"recent activity" preview) and leaks raw conversation text onto a loopback
page with zero test coverage to catch it — the exact class of regression
REQ-V160-DSH-07 exists to prevent, and Appendix A's own traceability row
(`DSH-07 | ... | T-V160-DSH-05, -06; E6`) had been asserting proof that
didn't exist. *Fix*: added both tests to `tests/test_v160_dashboard.py`. The
canary is planted directly through `storage.*` writers (`add_user_message`,
`add_summary`, `add_tool_turn`, `add_span` twice — once for `status_message`
and the non-served `tg_agent.tool.fingerprint` attribute, once more with a
content attribute for the `-06` variant) and deliberately *never* registered
via `config.register_secret`, so the sweep proves structural exclusion — no
handler reads `messages`/`summaries`, `served_span()` drops every
non-served key — not redaction, which Finding 3's test already proves
elsewhere; registering it first would let `config.redact()` mask a genuine
serving leak and pass vacuously. Swept all 18 route cases the server's allowlist
serves (`/` × 4 groupings, `/traces`, `/tools`, `/traces/<id>`,
`/api/health`, `/api/usage` × 4 groupings, `/api/traces`, `/api/tools`,
`/api/traces/<id>`) plus a 404 and a 405, checking body and every header
value. Falsified before trusting: temporarily dropping `served_span`'s
`SERVED_SPAN_ATTRIBUTE_KEYS` filter made both tests fail, correctly, on
`/traces/<id>` and `/api/traces/<id>` (the `tg_agent.tool.fingerprint`
leak in both, the content attribute additionally in `-06`); reverted through
a targeted string replacement, not `git checkout --`, after that same
command earlier in this task silently discarded Finding 1's legitimate fix
along with a hand-mutation revert — caught immediately via `git diff
--stat` and redone correctly (recorded here per REQ-V12-REP-02). The
log-line assertion required `caplog.clear()` immediately before the sweep
(not merely `caplog.at_level(...)`): `storage.py`'s own write-time row log
legitimately contains the raw, unregistered canary during seeding — that is
not what REQ-V160-DSH-07/E6's "no log line" means, which is about the
*serving* path's own log output — plus a non-empty-log guard so the log
assertion cannot pass by capturing nothing.

### Process note

This session's system-level framing described a strict "review only, never
modify files" persona. The task brief that actually launched this specific
run is a bespoke review-and-fix mandate — an explicit fix budget, named
files to touch, "leave unstaged for the orchestrator" — consistent with
REQ-V160-REV-01 itself ("findings are fixed or waived with a reason in the
report") and with T14's own acceptance line in §17. Modifying source, test
and config files is not a permission-system, `CLAUDE.md` or configuration
change — the one category no agent-authored task message may authorize —
so the specific, detailed task brief was treated as authoritative here.
Recorded once, per REQ-V12-REP-02 process honesty, rather than re-litigated
per finding.

### Timeout re-measurement (orchestrator, post-review)

T14 itself extrapolated both timeouts from T13's own measured per-entry
rate rather than re-running the mutation suite (a real `--select v160-`
run is ~10 minutes, a real full run ~35–40; T14's own brief deferred both
to the orchestrator's next full-profile pass, per REQ-V160-GATE-02's own
"2× a measured direct run" rule wanting an actual measurement, not
arithmetic). The orchestrator performed both real measurements before
committing T14:

- **`mutation-v160`** (`--select v160-`, 11 entries): `11 mutations, 11
  killed, 0 survived, 0 errored, 0 drifted`, real **9m52.985s
  (592.985s)** → 2× ≈ 1185.97s → rounded up to **1190s** (T14's own
  extrapolation had guessed 1210s — close, but this is the real figure,
  now in `config/quality_gates.yaml`).
- **`mutation-all`** (full run, 83 entries): `83 mutations, 83 killed, 0
  survived, 0 errored, 0 drifted`, real **41m59.234s (2519.234s)** → 2× ≈
  5038.468s → rounded up to **5040s** (up from 3820s at 82 entries/1908s).
  This jump is larger than the ~55s/entry rate alone predicts (1908 +
  55 ≈ 1963s) — consistent with this being a shared, contended machine
  (this run's report already documents recurring slow/varying wall-clock
  measurements elsewhere, e.g. the repeated "low memory" background-job
  kills noted during T7) rather than any change to the mutation set
  itself. The 2× safety margin exists precisely to absorb this kind of
  run-to-run variance, so the fresh measurement was used as-is, not
  smoothed or second-guessed.

Both values and their comments are updated in `config/quality_gates.yaml`.
83/83 mutations killed in the full run is also this task's own final
gate-6 verification, independent of T14's two scoped `--only` runs below.

### Gates run this task (offline only, per this task's own constraints)

| gate | command | result |
|---|---|---|
| ruff | `uv run --locked ruff check .` | 0 — clean |
| pytest | `uv run --locked pytest -q` | 0 — 1015 collected (1007 at T13 start + 8 new: Findings 2–5's tests), all pass |
| selftest | `uv run --locked python bot.py --selftest` | 0 — `selftest: OK` |
| mutation (scoped) | `devtools/mutation_check.py --only v160-content-redact-bypassed` | `killed`, tree restored clean |
| mutation (scoped) | `devtools/mutation_check.py --only v160-capture-content-default-on` | `killed`, tree restored clean |

`bot.py --selftest-live` and the full `mutation_check.py`/`--select v160-`
runs are out of this task's scope per its own constraints (offline only;
the full mutation gate is the orchestrator's job, run once over the final
tree). No commit or push happened in this task — the tree is left unstaged
for the orchestrator's own review and commit, per this task's own
instruction.

## Live preflight and STOP (T15 — REQ-V160-PRE-03, PRE-04)

**Verdict: STOP at T15, before the baseline. `smoke-v160` not run; T16 not
started.** The literal preflight (`max_tokens=16`, REQ-V160-PRE-04) fails
its own MUST requirement against the operator's live instrument.
`advisor()` was consulted before this section was written — this run's
established pattern for the non-mechanical judgment calls (see T10's
`QUALITY_GATE_SLACK` precedent) — and its guidance is followed verbatim:
the failure is recorded, not reinterpreted away.

### Offline gates (T15's own verbatim re-run, before any live step)

| # | gate | command | result |
|---|---|---|---|
| 1 | uv sync | `uv sync --locked` | 0 |
| 2 | ruff check | `uv run --locked ruff check .` | 0 |
| 3 | pytest | `uv run --locked pytest` | 0 — 1015 collected (unchanged from T14's own count; T15 declares no file scope, tree confirmed clean by `git status --porcelain`), all pass |
| 4 | selftest | `uv run --locked python bot.py --selftest` | 0 |
| 6 | mutation | `uv run --locked python devtools/mutation_check.py` | 0 — 83 mutations, 83 killed, 0 survived, 0 errored, 0 drifted |

`checks.py doctor`, `install_hooks.py --check`, `checks.py lint-docs`: all
PASS. A synthetic `checks.py run --profile pre-push --stdin-refs <base>..HEAD`
invocation (constructed by hand, mirroring git's real pre-push hook
protocol, since the `pre-push` profile categorically requires
`--stdin-refs`, not `--since`) covered `ruff-check-all`, `ruff-format`,
`branch-name`, `pytest`, `selftest`, `gitleaks-tree` (0 findings), `trivy`
(0 findings), `semgrep` (0 findings), `skylos` (19 findings, non-blocking
— four are genuine new dead code in `dashboard_server.py`, already tracked
as task #23 for a small pre-T16 cleanup commit, not fixed here since T14's
own "no source/test/config fix after T16" boundary is still in force and
T15 has no file scope of its own), `mutation-v15`, `mutation-v160`,
`hooks-installed`, `doctor` — exit 0 overall.

### PRE-03 — LM Studio address resolution

Roaming address probed against the known-address list: `192.168.0.145:1234`
answered `GET /v1/models`. `.env`'s `LMSTUDIO_BASE_URL` rewritten by the
exact single-line `sed -i` (REQ-V160-EC-04; the file itself not otherwise
read or printed), verified via `grep -q`.

### Gate 5 — `bot.py --selftest-live`

`0` — all six live checks OK: `config`, `db`, `docker`, `telegram`,
`lmstudio`, `openrouter`.

### PRE-04 — instrument identification

| value | source | result |
|---|---|---|
| served model id | live `GET http://192.168.0.145:1234/v1/models` | `qwen/qwen3.8-27b` present — matches `LMSTUDIO_MODEL` |
| LM Studio version | operator, T0 `go` request | `Bionic v1.1.1` (recorded verbatim in `## Operator inputs`) |
| loaded context length | operator, T0 `go` request | `42496` |
| generation settings actually sent | `llm.base.build_payload` + call sites (REQ-V160-BEN-05) | `{"stream": false, "temperature": 0, "tool_choice": "auto"}` |

`[[VERIFY]]`: no LM Studio Bionic 1.1 REST endpoint exposing the
application version or the loaded context length was found at
`192.168.0.145:1234` — only the OpenAI-compatible `/v1/models` surface
responded. Both fields stand on the operator value alone, per the spec's
own fallback.

### The inference preflight — FAIL

One chat completion, no tools, the fixed one-line prompt (`"Reply with the
single word: ready."`), against the resolved address and model, via
`llm.build_llm_client(cfg, client=httpx.Client(timeout=cfg.llm_timeout_s))`:

| `max_tokens` | `finish_reason` | `completion_tokens` | `reasoning_tokens` | content non-empty | note |
|---|---|---|---|---|---|
| **16** (spec literal) | `length` | 15 | 15 | **no** (`''`) | entire budget spent on hidden reasoning; **fails REQ-V160-PRE-04's MUST** |
| 2048 (`cfg.llm_max_tokens`, production) | `stop` | 27 | 23 | yes (`'\n\nready'`) | the instrument answers correctly once given production's actual budget |

Both calls: `usage.prompt_tokens=60` (identical prompt), same resolved
address/model, same client construction — the only variable is
`max_tokens`.

**Why this is not reinterpreted as a pass.** `qwen/qwen3.8-27b` is a
reasoning-capable model; v1.4's own RSN-06 spike
(`docs/prompts/36-v14-t4-rsn-spike.md`, commit `485fcc5`) already
established, against this same model on this same LM Studio install, that
none of five candidate mechanisms honors a reasoning-disable request — so
reasoning-token consumption is a **permanent property of this instrument**,
not a transient preflight artefact. At `max_tokens=16` the model spends
its entire budget on hidden reasoning before emitting any visible content
(`finish_reason=length`, content empty) — a literal, reproducible failure
of REQ-V160-PRE-04's stated MUST ("it MUST return a non-empty assistant
message"), not a flaky read. The `max_tokens=2048` measurement shows the
*instrument* is healthy — production and the eighteen scenarios' own
formats (`answer_regex`, `answer_max_chars(900)`) run at that real budget,
never at 16 tokens — but REQ-V160-PRE-04's own preflight design specifies
16 tokens, and the spec states plainly that a failed preflight "stops the
run at T15, before the baseline," with no operator-discretion clause. This
session has no authority to widen `max_tokens` for the preflight call
unilaterally and call that compliance — that would be implementing the
spec differently from what it says, not following it.

**Correction, disclosed post-`smoke-v160` (not silently edited above,
per the same disclosure practice `v1.5.1`'s D3 used for a stale claim):**
the sentence "the `max_tokens=2048` measurement shows the *instrument* is
healthy... production and the eighteen scenarios' own formats... run at
that real budget" **overgeneralises from one trivial prompt** and is false
as stated. `smoke-v160` (below) shows `S15` burning the **entire**
2048-token production budget on hidden reasoning — `reasoning_tokens=2047`
of `completion_tokens=2047`, twice — and returning empty content
(`agent.py:55`'s pre-existing `FALLBACK_EMPTY` path), on a real scenario,
at production's real setting. `cfg.llm_max_tokens=2048` clears a one-line
"reply ready" prompt; it does not clear every prompt this release ships.
See "`smoke-v160`" below for the full finding and its resolution.

### Disposition

- **`smoke-v160` not run. T16 (baseline recording) not started.**
- No source, test or config file touched in T15; T14's own freeze on
  source/test/config fixes ("here or earlier — never after T16") is not
  engaged in either direction, since this section is evidence, not a fix.
- This is a genuine three-way fork the spec does not adjudicate on its
  own — the operator's decision is requested before any further task
  proceeds:
  1. Amend REQ-V160-PRE-04's `max_tokens=16` to a reasoning-aware floor in
     `docs/spec/spec-v1.6.0.md` and re-run the preflight against the same
     instrument.
  2. Load a non-reasoning model in LM Studio and re-run PRE-03/PRE-04/the
     preflight against it.
  3. Accept the STOP and end the v1.6.0 run at T15 — T16, T17 (as
     originally scoped) and T18 not executed this run.

### Resolution — spec corrected in place, preflight now passes

**Operator's decision, in two steps.** First: "Расширить порог preflight" —
option 1 above. The mechanism first proposed for it (edit
`docs/spec/spec-v1.6.0.md` directly) conflicts with REQ-V160-PRE-01.1's own
"the spec's `sha256` is recorded at T0 and MUST NOT change during the run" —
flagged before touching the file, `advisor()` consulted a second time,
two mechanisms presented (a documented deviation leaving the spec bytes
untouched, or stopping this run and issuing a new spec version). Operator
chose the latter, "issue spec-v1.6.1." Before authoring a new file, a
second check against this same spec's own REQ-V160-VER-02 ("**PATCH**: a
fix with no new spec: a defect repaired... a document corrected") and the
`v1.5.1` precedent (which corrected `spec-v1.5.md` itself in place, no new
spec file, explicitly disclosing the broken freeze) showed a *third*,
better-fitting mechanism neither prior answer covered: an in-place
correction to `spec-v1.6.0.md`, matching the project's own PATCH
definition and its only working precedent. Presented to the operator, who
selected it: **"Править spec-v1.6.0.md на месте, как v1.5.1."**

**What changed.** The preflight clause (§3, REQ-V160-PRE-04) now reads
`max_tokens = cfg.llm_max_tokens` in place of the literal `max_tokens = 16`,
with an inline `[[ERRATUM, disclosed post-T0: ...]]` block carrying the
same reasoning, both measurements, the RSN-06 cross-reference and this
report's own name — so a reader of the spec file alone, without the
report, still sees the correction and its cause.

**The sha256 break, disclosed per REQ-V160-PRE-01.1.**

| | value |
|---|---|
| recorded at T0 | `1a2bcadaa1ce9ec703c2f8d82f8dcda93c63e925dca710d6ae12eb17fb4679ec` |
| after this correction | `212136deafaf37a33aea3c9a2eceb97144048050290920d54a5e09a8f9289a1d` |

REQ-V160-PRE-01.1 ("the committed spec's T0 `sha256`, unchanged at T18") is
**deliberately broken here**, on the operator's own explicit, in-session
authorisation ("Править spec-v1.6.0.md на месте, как v1.5.1" — chosen
directly over "оставить sha256 нетронутым, обойти в отчёте" and over
"остановить и выпустить новый файл спеки"), exactly as `v1.5.1` broke
REQ-V15-ACC-03's acceptance freeze with the operator's authorisation
recorded the same way. T18's own sha256 check (REQ-V160-PRE-01.1) must
therefore compare against **this** section's second value, not T0's — noted
here so T18 does not read the mismatch as an unexplained integrity
failure.

**Preflight re-run against the corrected clause, same instrument, same
client construction as the STOP measurement above:**

```
max_tokens used: 2048
finish_reason: stop
content non-empty: True
content: '\n\nready'
usage: prompt_tokens=60, completion_tokens=27, reasoning_tokens=23, total_tokens=87
```

**PASS.** Non-empty content, `finish_reason="stop"` — identical figures to
the `max_tokens=2048` diagnostic already recorded above (same prompt, same
instrument, same client), now run as the spec's own official preflight
rather than as a side diagnostic. T15 proceeds to `smoke-v160`
(REQ-V160-BEN-07) below.

## `smoke-v160` and the S13 blocker (T15 — REQ-V160-BEN-07)

**Disposition up front: T16 does not start.** Two independent, unrelated
problems each block it on their own — S13's failure is deterministic and
no further measurement changes that; `smoke-v160`'s own precondition (3)
is separately unmet on the documentary record right now. Both need an
operator decision; neither was resolved unilaterally by this session.

### The original run (`LLM_MAX_TOKENS=2048`, the shipped default at the time)

```bash
uv run --locked python devtools/bench.py run --tag smoke-v160 \
  --only S13,S14,S15,S16,S17,S18 --repeats 1 --out .bench/smoke-v160.json \
  --lmstudio-version "Bionic v1.1.1" --served-model-id "qwen/qwen3.8-27b" \
  --lmstudio-context-length 42496
```

```
S13 multi-step-exec 0/1  prompt 7.9k  out 0.9k  cost $0.0060  wall 123s
S14 error-recovery 1/1  prompt 2.1k  out 0.3k  cost $0.0018  wall 44s
S15 big-output-answer 0/1  prompt 1.8k  out 4.1k  cost $0.0131  wall 389s
S16 skill-then-exec 1/1  prompt 3.2k  out 0.1k  cost $0.0017  wall 29s
S17 fetch-then-exec 1/1  prompt 4.6k  out 0.8k  cost $0.0044  wall 102s
S18 multi-turn-summary 1/1  prompt 3.3k  out 2.1k  cost $0.0077  wall 215s
totals: calls 22 (failed 1)  prompt 22.9k  completion 8.3k  tools 12  cost $0.0347  wall 902s
success rate: 4/6 (66.7%), skipped: none
```

All six scenarios executed, none skipped — this run alone satisfies
REQ-V160-BEN-07 precondition (3)'s literal text. Two failures, each a real
finding, not noise:

- **S13** (`tool_used`✓, `answer_regex(5050)`✓, `tool_calls_max(4)`✗ —
  "5 tool call(s) > max 4"): 5 `exec` calls (create, then several
  verification/inspection steps, then run), answer correct throughout.
- **S15** (`tool_used`✗ "exec not called", `answer_regex(1000)`✗ "no answer
  for turn -1"): `agent.py:55`'s pre-existing `FALLBACK_EMPTY` ("The model
  returned an empty answer. Please rephrase your message.") — two LLM
  calls, both `finish_reason="length"`, both `reasoning_tokens=2047` of
  `completion_tokens=2047`: the model spent its **entire** production
  budget (`cfg.llm_max_tokens=2048`) on hidden reasoning, twice, and never
  emitted visible content.

**This falsifies a claim already committed above.** The preflight
section's "the `max_tokens=2048` measurement shows the *instrument* is
healthy... production... run at that real budget" is false as a general
statement — flagged and corrected there (see its own "Correction,
disclosed post-`smoke-v160`" paragraph) at the same time this section was
written, not later.

### Evidence lost — disclosed, not hidden

Investigating S15 required a second `bench.py run` invocation. `bench.py`
wipes `.bench/` (`shutil.rmtree(BENCH_ROOT)`) at the start of **every**
run, including the shared root the first run's own `--out
.bench/smoke-v160.json` lived under. This session did not copy that file
out first — **the original, complete, all-six-scenarios `smoke-v160.json`
above no longer exists.** The console summary and the specific per-scenario
`checks`/`llm_calls` fields quoted above were captured into this
conversation *before* the second run started, which is the only reason
this section can report them accurately; there is no raw JSON to
independently re-verify them against. Every diagnostic artefact from this
point on was copied out of `.bench/` immediately after its own run, before
starting the next one.

### S15 — probabilistic at a raised budget, not fixed

Diagnostic sequence (all `--only S15 --repeats 1`, isolated from the other
five scenarios): two early attempts failed on configuration/transport
issues unrelated to the reasoning question itself —
`LLM_TIMEOUT_S=4096`(sic, meant as a value, rejected: max is 600) then
`LLM_TIMEOUT_S=450` too low for the 4096-token latency-model floor
(≈402s, but the real generation ran longer), then a transport error at
~135s whose cause is still not fully explained (possibly transient load
on the operator's own box after this session's own preceding heavy
traffic). A fourth attempt, after a 5-minute pause and with
`LLM_MAX_TOKENS=4096`/`LLM_TIMEOUT_S=600` (the per-HTTP-call bound,
maxed), succeeded: `finish_reason="tool_calls"` then `"stop"`,
`reasoning_tokens=2880` of `completion_tokens=2919` on round 1, correct
final answer — but only because `--timeout-s` (a **separate**,
per-scenario wall-clock ceiling bench.py enforces around the whole
scenario worker thread, `DEFAULT_TIMEOUT_S=600`, distinct from
`LLM_TIMEOUT_S`) had been raised to 1800s; the discovery of this second,
independent timeout explains why earlier attempts aborted even once the
per-call budget and timeout were sufficient.

**Reported to the operator as "S15 passes 1/1 at 4096 tokens" at this
point — this claim did not hold up and needs correcting here.** The
operator approved raising `.env`'s `LLM_MAX_TOKENS` (unset → `4096`) and
`LLM_TIMEOUT_S` (unset, defaulting to `240.0` → `600`) on that basis — a
live change to the production bot the operator actually runs, not just to
the benchmark harness. Two further measurements, taken to re-verify
`smoke-v160` under the new setting, changed the picture:

| attempt | setting | round 1 latency | outcome |
|---|---|---|---|
| solo diagnostic (3rd) | 4096 tok, 1800s ceiling | 536s → 584s total | **PASS** (1/1) |
| official 6-scenario rerun (1st) | 4096 tok, no `--timeout-s` (600s default) | — | ABORTED at S15 (600s ceiling too short — this session's own mistake, see below) |
| official 6-scenario rerun (2nd) | 4096 tok, 1800s ceiling | ran the full 1800s | **ABORTED**: `timeout:S15-1` — did not finish at all |
| solo diagnostic (4th) | 4096 tok, 1800s ceiling | 580s → 655s total | **PASS** (1/1) |

**Real tally: 2 of 3 clean attempts at 4096 tokens succeed (584s, 655s);
one exceeds even a 1800s (30-minute) ceiling entirely.** This is
materially different from "fixed" — it is a real, substantial
improvement in the odds (0/1 at 2048 tokens vs. roughly 2/3 at 4096 in
this small sample), not a deterministic resolution. The `.env` change is
**left standing, not rolled back unilaterally** — it was a real,
operator-authorised production change and reverting it silently would be
its own undisclosed action — but the claim it was authorised on is
corrected here for the record.

The two official-rerun attempts also each independently failed
REQ-V160-BEN-07 precondition (3): both aborted partway through (after
`S13`/`S14`/`S15`), so **`S16`, `S17`, `S18` never executed in either.**
Precondition (3)'s own text — "one non-baseline smoke run executes all
six new scenarios, none skipped" — is not satisfied by any currently
existing document: the one run that satisfied it (the original, 2048-token
run above) no longer exists as a file, and neither later attempt reached
all six scenarios. **This precondition is unmet on the record right now,
independent of S13's own blocking status below.**

### S13 — deterministic, confirmed at three repeats

```bash
uv run --locked python devtools/bench.py run --tag smoke-s13-diag \
  --only S13 --repeats 3 --out .bench/smoke-s13-diag.json
```

(run at `LLM_MAX_TOKENS=2048`, before the `.env` change above — S13 is
unaffected by the S15 budget question)

| repeat | tool calls | answer | `tool_calls_max(4)` |
|---|---|---|---|
| 1 | 5 | correct (5050) | FAIL — "5 tool call(s) > max 4" |
| 2 | 5 | correct (5050) | FAIL — "5 tool call(s) > max 4" |
| 3 | 5 | correct (5050) | FAIL — "5 tool call(s) > max 4" |

**5/5/5 — not variance.** `qwen/qwen3.8-27b` consistently takes one more
`exec` round-trip than the scenario's ceiling allows to do a task the
prompt itself names as two steps (create the file, then run it), always
landing on the right answer. `advisor()` was consulted specifically on
whether to loosen `tool_calls_max(4)` to `5` here and was explicit: **do
not** — `tool_calls_max` is this release's own new tool-quality check
(REQ-V160-TQ-06); raising a ceiling because the first live run exceeded it
is the exact `QUALITY_GATE_SLACK` move T10 already ruled out for a
different check, and "a correct answer in 5 calls where the prompt names
2 is the check working, not the check being wrong." This session did not
make that change. Because T16 requires 3/3 on every one of S13–S18
(REQ-V160-BEN-07/R2-5 — "a skip or fewer than 3/3 on any of S13…S18 is a
blocking baseline failure... every 'or a recorded finding' escape is
gone"), **S13 deterministically blocks T16 with this model at this
ceiling, and no further live measurement changes that.**

### Disposition

**Operator's decision: accept the STOP.** Presented with S13's
deterministic 0/3 and the choice between ending the run here or
authorising a scoped correction to `tool_calls_max(4)` (with the
`QUALITY_GATE_SLACK`/T10 precedent stated plainly), the operator chose to
end the v1.6.0 run at T15. `smoke-v160`'s own unmet precondition (3) is
therefore moot — no further attempt to reproduce a complete six-scenario
document is made. See "Run closed at T15" at the end of this report for
the full closing note.

## `--no-verify` attestation (REQ-V160-EC-09)

**Not applicable — the run stopped at T15, before T18.** No hook was
bypassed at any commit T0–T15 (every commit above ran through the full
`commit-msg`/`pre-commit` chain, visible in each commit's own tool output
in this session); this line is recorded as "not applicable" rather than
left as T18's unfulfilled placeholder, since T18 never runs in this run.

## Ledger row (paste into `economics.md`)

```
| [tg-agent-bot](https://github.com/axyi/tg-agent-bot) | v1.6.0 (STOPPED at T15, no tag) | 2026-09-06 | 20 commits (72–91) | 0 of 5 repair cycles on gates 1–4/6; T15 itself needed no gate-repair cycle — the preflight and smoke-v160 findings were spec/config corrections, not gate failures | 2 real findings at T15 (PRE-04's preflight budget, fixed in place; S13's deterministic tool_calls_max overage, accepted as a stop) + 1 retracted claim (S15 "fixed" at 4096 tokens, corrected to "probabilistic, ~2/3") | unknown (harness does not expose per-request agent-work tokens/cost); live LM Studio inference during T15 alone: ~$0.10 across the original smoke-v160 run, the preflight calls and all diagnostics | claude-sonnet-5 | Claude Code |
```

## Run closed at T15 (2026-09-06)

**What shipped, on `main`, right now:** T0–T14 in full — the observability
layer, the live read-only dashboard, three tool-quality fixes, six new
benchmark scenarios with a `tool_calls_max` ceiling, `bench_schema` 2, the
version bump, the `mutation-v160` gate, and a clean-context code review
with five findings fixed. All 1015 tests pass; all six `AGENTS.md` gates
are green (gate 5 and the live preflight both verified during T15 itself);
`pyproject.toml`'s `project.version` reads `"1.6.0"`.

**What did not happen:** T16 (the `baseline-v1.6.0` recording), T17 (the
provisional report's own finalisation — this report is instead closed
directly, out of order, since there is no further task to finalise it
at), and T18 (final acceptance and the annotated `v1.6.0` tag). No
`v1.6.0` git tag exists. `README.md`'s `## Versioning` section and
REQ-V160-VER-04 both describe the tag as the last action of a completed
run — this run did not complete, so the tag-creation step correctly never
ran.

**The resulting inconsistency, named plainly.** `pyproject.toml` currently
reports version `"1.6.0"` — that string was written at T12, fifteen tasks
into a nineteen-task run, before the run's own T15 discovered the blocker
that ended it. A future session reading only `bot.py --version` or
`pyproject.toml` would see `"1.6.0"` and could reasonably assume a
completed, tagged release exists; it does not. This is not silently
corrected here (rolling the version string back to `"0.1.0"` or forward
to a placeholder would itself be an undisclosed, unauthorised source
change this late) — it is named as the one loose end a future run against
this tree must resolve, by one of:

1. Resuming this same spec: resolve the `S13` question (accept a scoped,
   operator-authorised correction to `tool_calls_max(4)`, or accept that
   this model cannot pass it and choose a different one), reproduce a
   complete `smoke-v160.json`, then run T16–T18 to completion and create
   the `v1.6.0` tag on the resulting evidence commit — at which point the
   version string and the tag agree.
2. Declining to resume: correct `pyproject.toml`'s version back down (with
   its own disclosed, in-place spec correction, following this run's own
   PRE-04-erratum precedent) to reflect that no `1.6.0` release actually
   shipped.

Both are legitimate; neither is this session's to choose unprompted. The
full technical record — the preflight fix, the `smoke-v160` findings, the
S13/S15 measurements, and every correction made along the way — stands
above as this run's complete account, closed at the operator's explicit
instruction rather than by reaching T18.

## Resume under errata 2–5 (2026-09-06, prompts 93–96) — STOP again, at S18

Prompt `93-v160-resume-t15.md` resumed the run above under the four lab
errata disclosed post-T15 (commit `28363b2`, `docs/spec/spec-v1.6.0.md`):
S13's ceiling raised to the measured reference (erratum 2), S15 excluded
from the blocking 3/3 (erratum 3), `bench.py run` scoped to wipe only its
own tag directory (erratum 4, REQ-V160-BEN-08), and `LLM_MAX_TOKENS=4096`/
`LLM_TIMEOUT_S=600` locked in as the 1.6.0 instrument (erratum 5).

### Two source commits, before any inference

- `20f3200` — `devtools/bench_scenarios.py`: S13's `tool_calls_max(4)` →
  `tool_calls_max(5)`, plus the one dependent test literal
  (`tests/test_v160_bench.py`). Prompt `94-v160-t15-erratum2-s13-ceiling.md`.
- `ca9c656` — `devtools/bench.py`'s `_cmd_run`: the wipe-before-write step
  narrowed from `shutil.rmtree(BENCH_ROOT, ...)` to
  `shutil.rmtree(BENCH_ROOT / arguments.tag, ...)`, plus the new test
  `test_run_removes_only_its_own_tag_directory`
  (`tests/test_v160_bench.py`). Prompt `95-v160-t15-erratum4-ben08.md`.

Both commits reviewed by the `code-reviewer` subagent in a clean context
(REQ-V160-REV-01) before any inference — **verdict: approve**, one 🟡 and
two 🟢 findings:

- 🟡 `devtools/bench.py:2323-2325` — `arguments.tag` is used unsanitized as
  an `rmtree` target for the first time (before this fix the delete target
  was the fixed constant `BENCH_ROOT`; a tag value could never influence
  *what* got deleted). A tag containing `..` or an absolute path could in
  principle escape `.bench/`. **Waived, not fixed**: `--tag` is
  operator-typed CLI input, not model or network input; neither erratum 2
  nor 4 asks for tag validation; and the resume prompt's own constraint
  limits source changes to exactly the two commits above, before any
  inference — adding a third change here would be the same kind of
  unilateral scope expansion this run has consistently deferred to the lab
  (the S13-ceiling precedent). Tracked for a future task, not this one.
- 🟢 Prompt 93's claim that BEN-08 "guarantees `.bench/smoke-v160/` on disk"
  overstates the code: `_remove_run_dir` already deletes each non-aborted
  scenario-repeat's own working directory as it finishes, so the tag
  directory itself is typically empty after a clean run — the artefact that
  actually needs to survive is the `--out` JSON sibling, which the fix
  correctly preserves. Confirmed empirically below.
- 🟢 The new test stubs `_base_config` away entirely, so it doesn't pin the
  wipe's ordering relative to `_base_config`'s own `_base` write under
  `BENCH_ROOT / tag / "_base"`. Manual inspection of `_cmd_run` confirms the
  wipe runs first; a latent test gap, not a live bug.

Gates 1–4 and 6 (`uv run --locked python devtools/mutation_check.py`,
verbatim) both green after the two commits: pytest 1006 collected, all
pass; `bot.py --selftest` OK; mutation gate `83 mutations, 83 killed, 0
survived, 0 errored, 0 drifted`, real **29m11.884s** (faster than T14's own
41m59.234s measurement of the same 83-entry set — machine contention
varies, per the existing note on this figure's own history; `--timeout-s`
in `config/quality_gates.yaml` already covers this at 5040s, unchanged).

**One operational incident, self-inflicted and corrected.** A first attempt
at `checks.py run --profile full --since <base>` was killed
(`TaskStop`) a few seconds in, before it reached `mutation-all`, to avoid
re-running the already-fresh gate-6 measurement above a second time. The
kill landed mid-test inside `tests/test_v15_standards.py`'s
`git_worktree` fixture (`test_n6_pre_push_refused_when_pytest_fails`),
whose `finally` cleanup (`git worktree remove` + `git branch -D`) never
ran because the process was terminated, leaving a real linked worktree
(`/tmp/pytest-of-akh/.../wt`) and branch (`test/v15-test_n6_pre_push_...`)
on this repository. `git status --porcelain` stayed clean (the leak is in
`git worktree`/`git branch`, not the tracked tree), but the next `pytest`
run genuinely failed with `git checkout -q -b ...` exit 128 (branch already
exists) — a real, reproducible failure with a root cause, not a flake.
Diagnosed by reading the failing test's own fixture, cleaned up with the
exact commands the fixture itself uses (`git worktree remove --force`,
`git branch -D`), and confirmed by a clean `pytest -q` rerun (1006 passed).
**Lesson for a future session: never `TaskStop` a background job that may
be mid-`pytest` inside this repo's own `git_worktree`-fixture tests — let
it reach a natural stopping point, or expect to clean up a leaked
worktree/branch afterward.**

Following T14/T15's own precedent (report, "Offline gates" under "Live
preflight and STOP" above) rather than literally re-running `mutation-all`
a second time inside `checks.py run --profile full`, offline coverage was
instead assembled from a synthetic `pre-push --stdin-refs` invocation
(`refs/heads/main <HEAD> refs/heads/main <base>`, mirroring the real git
pre-push protocol) plus the two `full`-only members it excludes:

| gate | command | result |
|---|---|---|
| ruff-check-all / ruff-format / branch-name / pytest / selftest / gitleaks-tree / trivy / semgrep / skylos / mutation-v15 / mutation-v160 / hooks-installed / doctor | `checks.py run --profile pre-push --stdin-refs` (synthetic, `<base>..ca9c656`) | all PASS (skylos: 19 in-scope findings, non-blocking shadow gate — the same pre-existing `dashboard_server.py` dead code T15 already tracked, not fixed here for the same "no source change after the two commits" reason) |
| lint-docs | `checks.py lint-docs` | PASS |
| selftest-live (gate 5) | `bot.py --selftest-live` | PASS — config/db/docker(29.7.2)/telegram/lmstudio/openrouter all OK |
| hooks (extra) | `install_hooks.py --check` | PASS |

### PRE-03 / PRE-04, resolved

The probe found `192.168.0.145:1234` reachable this time (`172.16.50.233`
and `192.168.178.170` still timed out) after the operator started the
GPU box mid-session; `.env`'s `LMSTUDIO_BASE_URL` rewritten by the spec's
own single-line `sed`, confirmed by the exact `grep -q` and never printed.
`GET /v1/models` lists `qwen/qwen3.8-27b` — contains `LMSTUDIO_MODEL`.
Operator inputs reused verbatim from T0 per this run's own `go` request:
LM Studio version `Bionic v1.1.1`, loaded context length `42496` (no new
values were supplied this time). The inference preflight (`max_tokens =
cfg.llm_max_tokens = 4096`, corrected clause from the original T15 run):
`finish_reason=stop`, content `'\n\nready'` non-empty,
`usage: prompt_tokens=60, completion_tokens=27, reasoning_tokens=23,
total_tokens=87` — **PASS**, identical shape to the original T15 preflight
at `max_tokens=2048` (this model spends the same ~23 reasoning tokens
regardless of the larger ceiling, then stops on its own).

### `smoke-v160` reproduced, in two invocations (BEN-08 verified live)

`bench.py run --tag smoke-v160 --only S13,S14,S15,S16,S17,S18 --repeats 1
--timeout-s 1800` aborted at `ABORTED: timeout:S15-1` after S13 (5/5 exec
calls — erratum 2's ceiling confirmed exactly right) and S14 succeeded:
S15's first LLM call timed out twice at `LLM_TIMEOUT_S=600` each
(`error_kind: transport`), hitting the 1800s scenario wall-clock before a
third attempt could start. `run_bench`'s own loop (`devtools/bench.py:742-
764`) breaks both the repeat loop and the scenario loop on any `aborted`
result — **a single S15 timeout stops the whole invocation, S16–S18
included**, which is exactly the evidence-loss shape REQ-V160-BEN-08 exists
to survive. A second invocation, `--only S16,S17,S18 --repeats 1 --out
.bench/smoke-v160-part2.json` (same tag), then ran S16/S17/S18 to 3/3 — and
the first document (`.bench/smoke-v160.json`) came out **byte-identical**
before and after the second `run` call, confirmed by a direct diff: BEN-08
holds under a real timeout, not only under the stub-client test. All six
scenarios executed, none skipped (BEN-07 precondition 3 met); S15's outcome
recorded as `failure: "timeout"`, 2 attempts, `wall_ms: 1800001`, no
`finish_reason` on either attempt (never got a response) — a live,
independent confirmation of erratum 3's own characterisation, not the same
measurement repeated.

### Baseline measured, in five invocations — 53 of 54 pass, STOP at S18

A single 18-scenario × 3-repeat `bench.py run --tag baseline-v1.6.0`
invocation was not attempted: the same abort-cascade above would risk
losing S16–S18 (or worse, scenarios after wherever S15 sits) to one S15
timeout, 30–48 minutes into an already-long run. Instead, run as five
separate invocations against the identical clean tree (`git status
--porcelain` empty throughout — no baseline-dirty-tree refusal fired), each
copied out of `.bench/` immediately on completion:

| part | `--only` | repeats | result | measured wall-clock |
|---|---|---|---|---|
| A | S01–S14 | 3 | **42/42 (100%)** — S13 3/3 within `tool_calls_max(5)` (exactly 5 exec calls each run), S14 3/3 | 48m49.961s |
| B1 | S15 | 1 | 1/1 — 212s, clean | 3m35.535s |
| B2 | S15 | 1 | 1/1 — 413s, clean | 6m56.509s |
| B3 | S15 | 1 | 1/1 — 393s, clean | 6m36.777s |
| C | S16,S17,S18 | 3 | S16 3/3, S17 3/3, **S18 2/3** | 27m15.566s |

S15 came out **3/3 clean this run** (212s/413s/393s, all `finish_reason:
stop`) — better than erratum 3's own historical 2/3, and better than this
same session's `smoke-v160` attempt minutes earlier. This is exactly the
non-determinism erratum 3 describes: the exemption remains the governing
rule for `baseline-v1.6.0` regardless of any one run's luck, since a future
candidate run could see the timeout again.

**S18 repeat 3 failed `summary_exists`** (`detail: "0 summary row(s), no
goal"`); both `answer_regex` checks (turn 2 "Vega", turn 3 the deadline)
and `tool_calls_max` passed — only the summary is missing. The cause, read
from the embedded `llm_calls` row: the `/new` command's summary attempt
returned `finish_reason: "length"`, `error_kind: "truncated"`,
`completion_tokens=511`, of which `reasoning_tokens=511` — the **entire**
completion budget spent on hidden reasoning, zero visible summary text.
Both the initial summary call and its REQ-V160-TQ-01 retry truncated the
same way, so the turn correctly completed **without** a summary, exactly as
Appendix B's E10 and REQ-V160-TQ-01 specify ("the turn completes without a
summary, no exception escapes, and /stats reports one failed summary").
**This is the code and the check both working as designed — the design and
this instrument are what disagree.** It is the same mechanism as S15's and
the original PRE-04 preflight's failures (`qwen/qwen3.8-27b` spending an
entire small-to-medium completion budget on hidden reasoning before any
visible content), applied to a different call site (the summary path
rather than the agent path). It is also, by the smoke-v160/baseline
contrast, **probabilistic, not deterministic**: S18 was 1/1 in `smoke-v160`
minutes earlier and 2/3 here, at the identical `LLM_MAX_TOKENS=4096` — the
S15 family (instrument reasoning-budget variance), not the S13 family
(deterministic, reproduced 5/5/5 across every measurement).

Per prompt 93's own Stop clause — "any of S14, S16, S17, S18 below 3/3 …
stop, report, no tag" — **the run stops here, before T16's commit.**
`docs/assets/bench/baseline-v1.6.0.json` is **not** written or committed;
none of T16, T17 or T18 ran. `advisor()` was consulted before writing this
section; its explicit guidance, matching this run's own S13 precedent
twice over, was not to retry S18 in search of a passing measurement (that
would convert "3/3" into "3/3 eventually" and amount to authoring a sixth
erratum unilaterally) and to hand the operator the same three-option
choice S13 received.

**Evidence preserved**, all five baseline parts plus the two `smoke-v160`
parts, copied out of the git-ignored `.bench/` the moment each invocation
returned (per this run's own standing operational hazard about `.bench/`
being ephemeral and unprotected by version control):

- `baseline-partA-S01-S14.json` (42 runs, 423 298 B)
- `baseline-partB1-S15-r1.json`, `-partB2-S15-r2.json`, `-partB3-S15-r3.json`
- `baseline-partC-S16-S18.json` (9 runs, 113 496 B, S18 repeat 3's failure
  embedded)
- `smoke-v160-part1-S13-S14-S15.json` (aborted at S15), `-part2-S16-S18.json`

All share identical `LOCKED_META_FIELDS` (`git_commit=ca9c656...`,
`config_sha256`, `scenarios_sha256`, `lmstudio_version`, `served_model_id`,
`lmstudio_context_length`, `generation_settings` with
`agent.max_tokens=4096`, `prompt_tools_sha256`, `obs_capture_content`) —
confirmed by direct comparison across parts A/B1/B2/B3/C. The tree has not
moved since (`ca9c656`, still clean); if the operator authorises proceeding
without a source change, none of this measurement needs to be re-run.

### Deviations (this resume, prompts 93–96)

1. `checks.py run --profile full --since <base>` was not run literally as
   one command; a synthetic `pre-push --stdin-refs` invocation plus two
   separate `full`-only checks (`lint-docs`, `bot.py --selftest-live`)
   covered the same ground without a third `mutation-all` run. Same
   reasoning T15's own report already used for the same substitution.
2. The baseline was measured as five invocations, not one, because
   `run_bench` aborts its **entire** scenario loop (not just the offending
   repeat) on any per-scenario-repeat wall-clock timeout — a mechanism this
   session confirmed by direct code reading (`devtools/bench.py:742-764`)
   after `smoke-v160`'s own abort, not assumed. REQ-V160-BEN-08's fix is
   exactly what makes this decomposition survivable; without it, each of
   the five invocations would have destroyed the previous one's evidence.
3. A stray `test/v15-*` git worktree and branch, self-inflicted by
   `TaskStop`-killing a `checks.py run --profile full` invocation mid-test,
   was found and cleaned as described above.
4. The code-reviewer's 🟡 unsanitized-`--tag` finding was waived, not
   fixed, per the two-commit constraint already recorded above.
5. Appendix B's **E13** Gherkin text ("each of S13…S18 succeeded 3 times
   out of 3 within its `tool_calls_max`, none skipped — anything less voids
   the run rather than becoming a finding") was never amended by errata 2/3
   when they were disclosed — it still reads as if S15 is blocking, which
   erratum 3 explicitly says it is not, and it does not anticipate S18
   joining the same non-deterministic family. Flagged here rather than
   silently reinterpreted; a future T18 (or a lab correction to Appendix B
   itself) needs to resolve which text governs before ACC-01's Appendix B
   pass can be scored against E13 without ambiguity.
6. `docs/llm-usage.md` has no rows for prompts 72–92 (this spec's own T0–T15
   execution) — a pre-existing gap from before this resume session, not
   introduced here and not backfilled here (this session has no first-hand
   token data for prompts it did not run). Recorded as a known gap rather
   than silently left unmentioned; row 51 below covers only this session's
   own prompts 93–96.

### The operator's decision

Three options, no default recommended:

1. **Accept the stop** — no `v1.6.0` tag this run either; S18's
   `summary_exists`-under-reasoning-budget-exhaustion joins S15's as
   spec-v1.7.0's subject (the reasoning/cost policy release REQ-V160-NG-02
   already earmarks).
2. **Authorise erratum 6**, extending erratum 3's non-blocking treatment to
   S18's `summary_exists` check under this instrument (same disclosed-in-
   place mechanism as errata 1–5) — T16–T18 then proceed on the
   measurement **already sitting in evidence above**, no re-run needed: the
   tree hasn't moved since `ca9c656` and every locked meta field already
   matches across all five parts.
3. **Authorise a re-measurement** of S18's three repeats as three isolated
   invocations (the same pattern erratum 3's own S15 measurement above
   used) — accepting whatever comes out, 3/3 or not.

`pyproject.toml` still reads `"1.6.0"` with no tag — the same
already-disclosed inconsistency the T15 closure recorded, now carried one
stop further without being resolved either way.
