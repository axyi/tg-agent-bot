# Prompt 85 — spec-v1.6.0 T11: bench_schema 2, spans, locked instrument

- **Date:** 2026-09-05
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** spec-v1.6.0 §14.1 marks T11 "delegate: yes" -- the reading
  spans five separate regions of `devtools/bench.py` (schema/constants,
  key-set derivation, run assembly, validation, CLI/meta), past this run's
  RLM delegation threshold
- **Harness:** Claude Code
- **Stage:** T11
- **Owner of:** `devtools/bench.py` (`BENCH_SCHEMA`, `SPAN_ROW_KEYS`,
  `REQUIRED_SPAN_ROW_KEYS`, `REQUIRED_TOOL_ROW_KEYS`, `Observation.span_rows`,
  `run_bench`/`_execute_run`/`_observe`/`_read_spans`,
  `_validate`/`_validate_run`'s `mode`/`schema` parameters, `check_document`,
  the `_cmd_report` CLI split, `_tree_is_dirty`/`_generation_settings`/
  `_prompt_tools_sha256`/`_instrument_meta`, `_cmd_run`'s dirty-tree guard
  and the three new `--lmstudio-*`/`--served-model-id` flags, `_ordered`,
  the bench.py:1420-1422 report-text fix); `tests/test_bench.py:111`
  (`fake_doc`'s `bench_schema` literal only); `tests/test_v160_bench.py`
  (append-only, T11's own section); plus, applied by this same run after
  discovering it during verification against REQ-V160-BEN-02's standing
  `docs/assets/bench/baseline-v1.4.json` (see Stop), one forced amendment
  to `tests/test_dashboard.py` outside the task's own file list
- **REQ ids:** REQ-V160-BEN-03, -04, -05

## Goal

`BENCH_SCHEMA` 1 -> 2; each `runs[]` entry gains a `spans` array, serialised
exactly like `llm_calls`/`tool_calls` except `attributes_json` travels as
the parsed `attributes` object. `_validate` gains a `mode` (`"strict"` /
`"informational"`) that relaxes `bench_schema` to `(1, 2)` and turns a
`scenarios_sha256` mismatch into a note instead of a fatal error; `check`
stays strict, `report --gate` stays strict, plain `report` validates
informationally and prints the collected note to stderr. `meta` gains six
locked instrument fields (`lmstudio_version`, `served_model_id`,
`lmstudio_context_length`, `generation_settings`, `prompt_tools_sha256`,
`obs_capture_content`); `git_commit` stays unlocked. A `baseline-*` tag
refuses a dirty tree. Separately: bench.py:1420-1422's hardcoded
"2.8-3.0 pp" report text becomes a computed `100 / runs` figure.

## Constraints

- Own exactly: `devtools/bench.py` (the areas above only -- not the
  check-evaluation dispatch for existing kinds, the scenario list, or
  anything unrelated), `tests/test_bench.py:111` (the one literal),
  `tests/test_dashboard.py:136` and `:502` (already `bench.BENCH_SCHEMA` /
  `3` at HEAD -- see Stop), `tests/test_v160_bench.py` (append-only), and
  this prompt file. `REQUIRED_LLM_ROW_KEYS` must not change -- `trace_id`/
  `span_id` stay deliberately absent from it, keeping
  `tests/test_v14_patch.py`'s hand-authored 25-key row valid unamended.
- No live LLM call, no `bot.py --selftest-live`, no real bench scenario run
  against a live model -- every scenario run in this task's own tests drives
  `run_bench` with the same `ScriptedLLM`/`RecordingRunner`/`FakeFetcher`
  fakes `tests/test_bench.py` already uses.
- Do not run `devtools/mutation_check.py`. Do not commit; leave the tree
  unstaged for the orchestrator.

## Acceptance

- `tests/test_v160_bench.py` gains 28 tests (16 -> 44 total), covering:
  `SPAN_ROW_KEYS`'s derivation and exclusion of `attributes_json`/`conv_id`;
  `REQUIRED_TOOL_ROW_KEYS`'s content and that a v1.3-shaped `tool_calls` row
  (no `trace_id`/`span_id`) validates (see Stop); a missing `spans` key
  tolerated like an older `llm_calls` row missing `trace_id`;
  `REQUIRED_SPAN_ROW_KEYS` enforced only when `bench_schema == 2`; a real
  `run_bench` call producing genuine `spans` rows that round-trip through
  `check_document`; `check` refusing `bench_schema: 1`, plain `report`
  accepting it with the informational stderr banner, `report --gate`
  refusing it (`EXIT_NOT_COMPARABLE`, via the reordered "needs both" guard
  -- see Stop); a `scenarios_sha256` mismatch fatal for `check` and `report
  --gate`, a note only for plain `report`;
  `check_document(document, scenarios=None, *, mode="strict")`'s signature
  and default unchanged for every existing caller; `LOCKED_META_FIELDS`
  holding exactly the six new keys beside the ten it already had (16 total)
  and never `git_commit`; `_instrument_meta` nulling all three off
  `lmstudio` and threading the CLI values through on it;
  `_generation_settings` matching `build_payload`'s actual literal shape;
  `_prompt_tools_sha256` a 64-hex-char digest; `comparability` flagging a
  differing or one-side-omitted new locked field and staying comparable
  across a `git_commit`-only difference (both via the function directly and
  through `bench.py report --gate`); the six keys present in a real
  `bench.py run` output; `run --tag baseline-x` refusing a dirty tree
  (monkeypatching `bench._tree_is_dirty`, not the real repository) and
  proceeding on a clean one, `smoke-x` proceeding regardless; the
  bench.py:1420-1422 fix stating a computed `100 / runs` figure, never
  "2.8-3.0 pp".
- `uv run --locked ruff check .` -- clean (0 findings).
- `uv run --locked ruff format --check devtools/bench.py
  tests/test_v160_bench.py tests/test_bench.py tests/test_dashboard.py` --
  `tests/test_v160_bench.py` clean; the other three fail identically to the
  pre-T11 baseline (verified via `git stash`, see Stop) -- not run (one
  false start reformatted `tests/test_dashboard.py` whole; caught before
  finishing and reverted with `git checkout --`, then the one intended
  function re-applied by hand -- see Stop item 4).
- `uv run --locked pytest` -- **1004 passed, 0 failed** (976 at T10 + 28 new).
  `tests/test_v14_patch.py` untouched and green; `tests/test_bench.py`
  green with only its one authorised line changed.
- `git diff --stat`: `devtools/bench.py` +266/-29; `tests/test_bench.py`
  +1/-1; `tests/test_dashboard.py` +11/-6; `tests/test_v160_bench.py`
  +436/-4 (the four are the module docstring/import-block edits).
- Manually verified against the real, committed
  `docs/assets/bench/baseline-v1.4.json`: `bench.py report --baseline
  docs/assets/bench/baseline-v1.4.json` now exits 0 where it exited 1
  before the `REQUIRED_TOOL_ROW_KEYS` fix (see Stop item 4), and
  `bench.check_document(document, <the S01..S12 subset of SCENARIOS>,
  mode="informational")` returns `(0, "meta.scenarios_sha256 does not
  match devtools/bench_scenarios.py")` against that same file.

## Stop

**1. REQ-V160-TRC-11's wiring was not already in place, contrary to the
task brief's premise.** The brief states "`tracing.py`'s `start_span`
already writes [`tg_agent.scenario_id`/`tg_agent.bench_tag`] onto a fresh
root span when `tracing.set_run_context(...)` has been called, ... since
scenario/tag attribution is not new to this task." `tracing.set_run_context`
and its consumption inside `start_span` do exist (both landed with T1/T3's
tracing module), but a repo-wide grep found **zero** callers of
`set_run_context` anywhere in `devtools/bench.py` before this run --
spec-v1.6.0's own task table confirms this by mapping TRC-11 to test
`T-V160-BEN-03` and file range `bench.py:600-700`, both inside T11's own
row, not T3's. This run therefore also did the TRC-11 wiring itself:
`run_bench`/`_execute_run` gained an optional `tag: str | None = None`
parameter (defaulted so none of the ~13 existing direct `run_bench(...)`
test callers needed amendment), and `_execute_run` now calls
`tracing.set_run_context(scenario_id=scenario.id, bench_tag=tag)`
**unconditionally** -- including when `tag` is `None` -- once per run,
right before starting the worker thread, so `tracing._run_context` (a
process-global dict, not a contextvar) never leaks a stale tag forward
across runs or across tests sharing one pytest process. Verified with a
throwaway probe test before writing the real suite: a real `run_bench` call
against `ScriptedLLM`/`RecordingRunner` genuinely writes rows to the
`spans` table via the `SqliteSpanSink` wiring already in `agent.py`
(confirmed: `grep -n SqliteSpanSink agent.py` finds four call sites), and
`_read_spans` correctly recovers them.

**2. `runs[].spans` presence is tolerated, not required, regardless of
`bench_schema` -- a deliberate reading, not the literal "required" the task
brief and the spec table both use.** Both explicitly call `runs[].spans`
"required when schema is 2." Implementing that literally (raising when the
key is absent) breaks `tests/test_bench.py`'s `fake_doc()`/`fake_run()`
fixture family wholesale: `fake_doc()` now defaults `bench_schema` to
`bench.BENCH_SCHEMA` (2, per this task's own required amendment to line
111), `fake_run()` never adds a `"spans"` key (that helper is explicitly
off-limits -- only line 111 of `tests/test_bench.py` may change), and
dozens of pre-existing tests assert `bench.check_document(fake_doc()) ==
(0, "valid")`. Requiring the key's mere presence would fail all of them,
directly triggering the task's own warning: "If implementing this task
breaks any OTHER existing test not listed above, that is a strong signal
something in your implementation is wrong." Resolution: `_validate_run`'s
`REQUIRED ⊆ row ⊆ allowed` loop (the same one that already tolerates an
older `llm_calls` row missing `trace_id`/`span_id`) defaults a missing
`"spans"` key to `[]` rather than raising -- so **presence is optional at
every schema value**, while `REQUIRED_SPAN_ROW_KEYS`'s per-row enforcement
(what T-V160-BEN-03's own test-table bullet actually asks for) is what is
gated strictly on `bench_schema == 2`, exactly as specified. The writer
(`_run_record`) always emits the key regardless -- pinned by
`test_spans_round_trip_through_a_real_run`, which drives the real
`run_bench` path and asserts `run["spans"]` is non-empty. If this reading
is wrong, the forced correction is in `tests/test_bench.py`'s `fake_run`
helper (add `"spans": []`), which is out of this run's file ownership.

**3. `report --gate` reaching `EXIT_NOT_COMPARABLE` for a `bench_schema: 1`
document required reordering, not a new remapping.** The spec bullet
("`report --gate` ... stays strict, and still returns `EXIT_NOT_COMPARABLE`
(2) for a mismatch") does not, on its own, make a schema-1 baseline
document exit 2 under `--gate`: `check_document(doc, mode="strict")` raises
`_Invalid(reason, EXIT_ERROR)` (1) for a bare `bench_schema` mismatch, by
the same mechanism `bench.py check` itself uses to refuse the same
document with exit 1 -- and that mechanism must not change (`check` staying
1 is itself part of the acceptance criteria). Remapping every per-document
`check_document` failure to `EXIT_NOT_COMPARABLE` under `--gate` was
considered and rejected as unjustified scope creep (it would also catch
genuinely malformed documents that have nothing to do with comparability).
Instead, `_cmd_report`'s pre-existing `if arguments.gate and candidate is
None: return EXIT_NOT_COMPARABLE` guard -- previously placed *after* the
per-document validation loop -- was moved *before* it. This is a real
behaviour change, but a narrow and clearly-motivated one, entirely inside
the `--gate` CLI wiring this task was asked to touch: a `--gate` request
with no `--candidate` is unconditionally not comparable, so validating
documents first (only to throw the result away) was already pointless. The
one existing test exercising `--gate` (`test_cli_report_gate_exit_codes`)
always supplies both `--baseline` and `--candidate`, so it is unaffected by
the reorder; verified green. T11's own new tests use a **schema-1 baseline
with no `--candidate`** for the schema-mismatch/`EXIT_NOT_COMPARABLE` case
specifically because of this mechanism, and a **separate two-document pair**
for the `scenarios_sha256`-mismatch-is-fatal case, which is left asserting
"non-zero" rather than a specific code, since that path genuinely does
return `EXIT_ERROR` (1) from `check_document` itself, matching the spec's
own strict-mode table row ("`_Invalid`, exit 1") rather than 2.

**4. `mode="informational"` could not actually read the one document
REQ-V160-BEN-02 built it for -- `TOOL_ROW_KEYS` had the same
no-REQUIRED-fallback gap `REQUIRED_LLM_ROW_KEYS` exists to prevent, just
undiscovered until this run's own advisor review pushed on it.** First
surfaced as a narrower symptom in `tests/test_dashboard.py:168-176`
(`test_fixtures_are_arithmetically_valid_benchmark_documents`, unlisted --
both named lines, 136 and 502, were already correct at HEAD: `document()`'s
helper already used `bench.BENCH_SCHEMA`, the "invalid schema" parametrised
case already `3`, both presumably landed by T5's dashboard split, whose
`devtools/dashboard.py` carries its own independent `ACCEPTED_BENCH_SCHEMAS
= frozenset({1, 2})` unrelated to `bench.check_document` -- confirmed by
`git log -p`). That test reads `tests/fixtures/bench/{baseline,
candidate}.json` (`bench_schema: 1`) through `check_document` in strict
mode; switching it to `mode="informational"` (the fix its own docstring
now describes) initially raised a *different* error:
`runs[].tool_calls[] is missing required column(s): span_id, trace_id`.
Root cause, and the reason it matters far beyond one test: `TOOL_ROW_KEYS`
doubled as its own REQUIRED bound (`("tool_calls", TOOL_ROW_KEYS,
TOOL_ROW_KEYS)`), on a comment's premise -- "that schema is unchanged by
this spec, so REQUIRED == current" -- that was true when written and has
been **stale since T2/T3** added `trace_id`/`span_id` to
`storage.TOOL_CALL_COLUMNS` with no REQUIRED fallback of their own.
Concretely: `uv run --locked python devtools/bench.py report --baseline
docs/assets/bench/baseline-v1.4.json` (the real, committed artefact
REQ-V160-BEN-02 keeps specifically to render an informational comparison
at T16) **exited 1** with that exact message before this fix, on every
commit since T2/T3 landed -- `mode="informational"`'s own relaxations
(schema, `scenarios_sha256`) never even got a chance to apply, because the
`tool_calls` shape check comes after them in `_validate` and rejected the
document regardless of mode. Fixed the way `REQUIRED_LLM_ROW_KEYS` already
models the identical situation: a new literal `REQUIRED_TOOL_ROW_KEYS`
(the twelve pre-trace columns), used in place of `TOOL_ROW_KEYS` as the
REQUIRED bound in `_validate_run`'s row-family loop; `TOOL_ROW_KEYS`
stays the ALLOWED bound unchanged. No existing test asserted the opposite
(a `trace_id`/`span_id`-missing `tool_calls` row must be rejected) -- grepped
for one before making the change. `docs/assets/bench/baseline-v1.4.json`
now reads clean end to end (`report --baseline` exits 0 with the expected
`scenarios_sha256` note; verified with the S01..S12 subset via the Python
API too -- see Acceptance). `tests/test_dashboard.py`'s fix reverted to
the clean `mode="informational"` form once this was fixed (a wider
string-tolerance hack was tried and abandoned first, precisely because it
was masking this exact bug rather than fixing it). Diff confined to that
one function's docstring and assertion line; the fixture JSON files
themselves were not touched.

**4a. Remaining, unresolved gap for T16: `bench.py report`'s CLI has no
way to narrow the scenario set, so REQ-V160-BEN-02's actual comparison
still cannot be produced by a plain CLI command today.** After the fix
above, `report --baseline baseline-v1.4.json` (no narrowing) still fails,
now on `_validate_run_set`: `missing run(s): S13-1, S14-1, ...` -- because
that document's `meta.only` is `null` ("every scenario of the catalog"),
and the *current* catalog now has 18 scenarios where the v1.4 catalog had
12. This is not new (it would have surfaced identically at any point since
T10 added S13..S18, for any tool that got this far), and it is orthogonal
to everything T11 was asked to change (BEN-03/-04/-05; not BEN-02/-06,
which are T16's). `check_document`'s own `scenarios` parameter already
supports exactly this narrowing (confirmed empirically: passing the
S01..S12 subset makes the same document validate cleanly -- see
Acceptance), but `bench.py report`'s CLI subcommand has no `--only`-style
flag to reach it -- unlike `run`, which does. T16's own task-table row
lists no files of its own ("none -- the tree is frozen; only commands
run"), which reads as: **T16 cannot add that flag itself.** This run did
not add one either, since it was not asked for and is a real design
question (does `--only` on `report` mean "validate against this subset,"
"render only these rows," or both?) that deserves an explicit decision,
not a unilateral one buried in an unrelated task. Flagged here explicitly
so it is resolved -- either by a small, scoped follow-up adding the flag,
or by T16 invoking `bench.check_document`/`bench.render_report` directly
through a short Python snippet instead of the `report` CLI subcommand for
this one comparison -- before T16 is blocked by it.

**5. The three PRE-04 instrument fields (`lmstudio_version`,
`served_model_id`, `lmstudio_context_length`) have no live-probe wiring in
`bench.py`'s call graph, by design, and this run did not invent one.**
Per REQ-V160-PRE-04, `lmstudio_version` and the loaded
`lmstudio_context_length` are **operator-typed** values (the `go` request's
own text, captured at T0/T15, never a network read), and `served_model_id`
is `bot.py`'s `_live_lmstudio` (`GET /models`), a live call this offline
task is explicitly forbidden from making or wiring a new invocation of.
Cross-checked against the task's own §11 command blocks (the T16 baseline
`bench.py run --tag baseline-v1.6.0 ...` and the T15/BEN-07 smoke
`--tag smoke-v160 ...` invocations) -- neither shows an instrument flag,
but neither shows `--provider` either despite the run clearly needing one,
so the omission there reads as the spec eliding operational detail rather
than proof no flag exists. Resolution: three new optional CLI flags on
`bench.py run` (`--lmstudio-version`, `--served-model-id`,
`--lmstudio-context-length`), consumed by a new `_instrument_meta(cfg,
arguments)` that nulls all three off `lmstudio` and threads them straight
into `meta` when present and on `lmstudio`. This is a genuine design
decision, not a discovered fact -- flagged explicitly for the orchestrator
to confirm (or substitute an env-var mechanism) before T15/T16 actually
run a live baseline. `generation_settings`, `prompt_tools_sha256` and
`obs_capture_content` all have concrete, already-wired sources
(`cfg.llm_max_tokens`/`cfg.llm_summary_max_tokens`/`agent.SUMMARY_MAX_TOKENS`;
`agent.build_system_prompt` + `tools.tool_specs()`, the same pair
`_prefix_tokens` already assembles; `cfg.obs_capture_content`) and needed
no such flag.

**6. `meta.scenarios_sha256`/the fresh baseline.** Unrelated to this task's
own edits -- noted only so it is not rediscovered as a surprise: nothing in
this run recorded a new baseline (forbidden -- T16's job, after T15's live
preflight), so `docs/assets/bench/baseline-v1.6.0.json` still does not
exist at the end of this run.
