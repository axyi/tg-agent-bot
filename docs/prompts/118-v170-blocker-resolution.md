# Prompt 118 — spec-v1.7.0 T12: two discovered test/checker blockers, resolved

- **Date:** 2026-09-08
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T12 (blocker resolution, landing before the selection commit)
- **Owner of:** `tests/test_v170_bench.py`, `tests/test_bench.py`,
  `tests/test_v14_patch.py`, `docs/prompts/118-v170-blocker-resolution.md`
  (new)
- **REQ ids:** REQ-V170-REV-01 item 8, REQ-V170-ACC-03, REQ-V170-POL-07,
  REQ-V170-EC-03

## Goal

Resolve two discovered blockers standing between T11's tip and the actual
T12 selection commit, both empirically proven (not merely reasoned about)
against the real validator/test functions, both authorized by the operator.

**Blocker 1 — REQ-V170-REV-01 item 8's checker cannot be satisfied by any
wording of the required `config.py` edit.**
`_acc03_validate_selection_commit_hunks` (and the spec's own item-8 prose,
`spec-v1.7.0.md:2264`) checks **every changed line** (added and removed) of
the selection commit's `config.py` diff for one of the two lowercase
identifiers. `config.py`'s pre-existing `_parse_choice` call site
(`source, "LLM_REASONING_POLICY", "model-default", REASONING_POLICIES`,
wrapped across lines by `ruff format`'s own 100-column rule) never paired
the identifier with the default value on one line. Changing the default to
`"by-purpose"` necessarily removes that line — and a removed line's
pre-existing text cannot retroactively satisfy a naming requirement it
predates, no matter how the replacement is worded. Proven exhaustively: 7+
wording attempts tested directly against `_acc03_validate_selection_commit_hunks`,
all failing on the same removed line. The identical structural problem
independently blocked correcting `AGENTS.md`'s stale default mention and
`.env.example`'s inverted `LLM_REASONING_ON_PURPOSES` wording (T11's own
finding).

**Resolution, operator-authorized**: `_acc03_selection_commit_diff` now
returns **added lines only** (drops `-` lines entirely) — the check's own
purpose is to prove what T12 *adds* is on-topic; a removed line was never
under any obligation to anticipate a naming rule written after it existed.
`_acc03_validate_selection_commit_hunks`'s docstring updated to match. No
other test's assertions changed; the two hunk-validator unit tests
(`..._rejects_a_sixth_path`, `..._rejects_an_off_topic_line`) construct
`per_file` directly and are unaffected. Re-verified: the real synthetic
locator test still passes; the actual `config.py` edit (now: a named
`llm_reasoning_policy_default` local, both its own line and the call's
args line each carrying the lowercase identifier) empirically passes the
real validator.

**Blocker 2 — flipping the shipped default breaks two more unlisted
pre-existing tests.**
`tests/test_bench.py::test_env_flags_are_exactly_the_nine_keys_with_null_for_absent_fields`
and
`tests/test_v14_patch.py::test_t_v14_ben_02_env_flags_holds_nine_keys_null_for_a_stage_a_config`
both hardcode `flags["LLM_REASONING_POLICY"] == "model-default"`, read via
`bench.env_flags(make_config(tmp_path))` — `make_config` constructs `Config`
directly (bypassing `load_config()`), so this is `Config`'s dataclass field
default, verbatim. Neither test is in spec-v1.7.0 §14.1's exhaustive
amendment list; both already carry a "T4 erratum, authorised by the
operator, prompt 107" comment from an earlier instance of this exact
conflict shape (REQ-V170-POL-01 vs. REQ-V170-EC-03).

**Resolution, operator-authorized (second erratum, this prompt)**: both
assertions now read the expected value from
`dataclasses.fields(config.Config)`'s own default for `llm_reasoning_policy`
instead of a literal, so neither goes stale on a future default change.
`tests/test_v14_patch.py` gained the `dataclasses` import and `Config` in
its `config` import line (previously only `ConfigError`, `load_config`).

## Constraints

- Both fixes verified against the real functions/fixtures before landing,
  not by re-reading the code.
- No other test's behaviour changes; full suite re-run green after both
  fixes (`pytest`: same collected count, 0 new failures).
- This file is deliberately **not** named `docs/prompts/\d+-v170-t12-[\w.-]*\.md`
  (renamed from an initial draft that was): `_acc03_find_selection_commit`
  locates the selection commit by that exact regex against a commit body,
  and citing a second matching path in this commit's own trailer would make
  the locator ambiguous (two matches, `None` returned, REQ-V170-REV-01 item
  8's check silently skipped rather than exercised) once the real selection
  commit lands citing `docs/prompts/117-v170-t12-selection-commit.md`.

## Acceptance

- `_acc03_validate_selection_commit_hunks({})`-style unit tests: unaffected,
  still green.
- `test_t_v170_acc_03_selection_commit_locator_and_hunks_synthetic`: green.
- `test_env_flags_are_exactly_the_nine_keys_with_null_for_absent_fields` and
  `test_t_v14_ben_02_env_flags_holds_nine_keys_null_for_a_stage_a_config`:
  green against the current (and any future) `Config` default.
- Full `pytest`: 0 failures.

## Stop

None. Both blockers escalated to the operator via `AskUserQuestion` before
any fix landed; both resolutions match the operator's selected option.
