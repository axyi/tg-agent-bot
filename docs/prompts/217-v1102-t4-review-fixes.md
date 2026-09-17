# Prompt 217 — v1.10.2 T4 review fixes: REV-01's three should-fix gaps

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated fix-up task, closing a clean-context
  code-reviewer's findings against T0-T3's committed range before the
  spec's remaining tasks build on it.
- **Harness:** Claude Code (subagent)
- **Stage:** T4
- **Owner of:** `AGENTS.md`, `docs/reports/report-v1.10.2.md`,
  `tests/test_v1102_docs.py`, `tests/test_v1102_runner.py`
- **REQ ids:** REQ-V1102-REV-01

## Goal

A clean-context `code-reviewer` subagent reviewed T0-T3's committed range
(HEAD `79f8304`) and found no critical or security issue, only three
should-fix documentation-consistency / missing-fixture gaps. This prompt
closes all three: (1) `AGENTS.md`'s gate-5 tail sentence still asserted
"an unreachable LM Studio is a blocked run" unconditionally, contradicting
the bolded clause right before it and the benchmark-waiver paragraph below
-- reworded to "every provider the configuration routes to" throughout,
plus a corrective clause in `docs/reports/report-v1.10.2.md`'s T3 section
(which had overstated what T3 actually landed) and a new regression test;
(2) `tests/test_v1102_red_team.py`'s `T-V1102-RT-08`
`test_t_v1102_rt_08_sentence_boundary_negatives_no_hal_marker_hit`
parametrize list -- on inspection this was **already correct** (two ASCII
fixtures plus two U+2028 fixtures), not duplicated as the brief's own
"currently" excerpt suggested; the apparent duplication was a rendering
artifact of the invisible U+2028 character displaying identically to a
plain space in the tool that produced the brief's quoted excerpt. No code
change was needed; verified empirically via direct codepoint inspection
and a green test run, and left untouched; (3) `_safe_field`'s `Cf`
category and direct U+2028/U+2029 handling had no direct test coverage in
`tests/test_v1102_runner.py` -- added four fixtures to
`test_t_v1102_run_03_safe_field_fixtures`, each output verified
empirically against the real `_safe_field` before being committed as an
expected value.

## Constraints

Offline only. No change to `_safe_field`'s algorithm, `_CONTROL_CATEGORIES`
or any marker regex. Nothing touched beyond the three named findings.

## Acceptance

`AGENTS.md` no longer contains the literal string "an unreachable LM
Studio is a blocked run"; guarded by
`test_t_v1102_rev_01_agents_md_gate5_tail_no_longer_hard_requires_lm_studio`
in `tests/test_v1102_docs.py`. `docs/reports/report-v1.10.2.md`'s T3
section corrected to describe the actual pre-T4 state (bolded clause
landed, tail sentence left unreconciled). `tests/test_v1102_runner.py`'s
`test_t_v1102_run_03_safe_field_fixtures` gains four empirically-verified
entries (`Cf`/U+200E pair, U+2028, U+2029). Full offline suite green:
2164 passed, 1 pre-existing skip (2165 tests collected, up from 2160
before this prompt's 4 new parametrize entries and 1 new test function). `ruff check .` clean.

## Stop

Fix 2 triggered the brief's own "if it somehow goes red, stop and report"
clause in spirit -- not because the test went red, but because empirical
inspection showed the described bug didn't exist in the current file.
Reported rather than guessed; no edit made to that file.
