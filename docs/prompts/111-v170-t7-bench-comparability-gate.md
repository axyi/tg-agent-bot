# Prompt 111 — spec-v1.7.0 T7: bench.py comparability, meta.reasoning, the 3/3 gate, --tag

- **Date:** 2026-09-07
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** same as prior prompts
- **Harness:** Claude Code
- **Stage:** T7
- **Owner of:** `devtools/bench.py`, `devtools/mutation_check.py` (no new
  entries yet -- T9's job; find-string sync only), `tests/test_bench.py`
  (fixtures updated), `tests/test_v170_reasoning.py` (extended),
  `docs/prompts/111-v170-t7-bench-comparability-gate.md` (new)
- **REQ ids:** REQ-V170-BEN-01, -02, -03, -04, -05, -06, -07, -08,
  REQ-V170-CAR-01, REQ-V170-AMEND-01

## Goal

Replace the v1.3 worktree-contract's "baseline must be null" comparability
rule with a plain equality rule over `STAGE_C_KEYS`; add an always-present
`meta.reasoning` block; add the executable REQ-V170-BEN-06 3/3 gate over
`GATE_REQUIRED_FULL_SCENARIOS` (S13..S18) plus the `meta.aborted` refusal
inside `verdict()` itself; add the `--tag` path-safety sanitiser
(REQ-V170-CAR-01); correct `ENV_FLAG_FIELDS`'s stale comment
(REQ-V170-AMEND-01).

## Constraints

- No hand-built baseline stand-in anywhere in this task's tests --
  REQ-V170-BEN-01 requires exercising the real, committed
  `docs/assets/bench/baseline-v1.6.0.json` directly.
- `LLM_REASONING_POLICY`/`LLM_REASONING_ON_PURPOSES` stay out of
  `CONFIG_HASH_EXCLUDED`'s complement -- i.e. join `CONFIG_HASH_EXCLUDED` --
  so a policy-only pair keeps the locked `config_sha256` stable.
- `_TAG_RE` checked before `arguments.tag` reaches any path-building code,
  `.`/`..` rejected explicitly even though the charset already excludes them.
- Test-fixture breakage caused directly by REQ-V170-BEN-02's contract change
  is the pre-authorized §14.1 class (disclosed, not re-confirmed); anything
  outside that class stops and asks.
- One prompt -> one commit, referencing this file.

## Acceptance

- `tests/test_v170_reasoning.py` + `tests/test_bench.py` green: 25 new tests
  (BEN-01, BEN-02 x5, BEN-03 x2, BEN-04 x5, BEN-05 x2, N6, CAR-01 x12, N7).
- Full suite green: `uv run --locked pytest` (1122 collected).
- `uv run --locked ruff check .` exits 0.
- `uv run --locked python bot.py --selftest` and `--selftest-live` both
  exit 0.
- `uv run --locked python devtools/bench.py check docs/assets/bench/baseline-v1.6.0.json`
  exits 0.
- `uv run --locked python devtools/mutation_check.py` exits 0 (83/83
  killed, 0 survived/errored/drifted).

## Stop

None triggered on the spec's own terms. One self-caught defect, fixed
in-scope rather than stopped on: the first full mutation-gate run after this
task's fixture changes landed showed `v13-bench-quality-minus-one` SURVIVED
(82/83 killed) -- root-caused to this task's own `_pair()` patch (forcing
`GATE_REQUIRED_FULL_SCENARIOS` to a fake 3/3 on the returned candidate) not
surviving `test_the_quality_gate_allows_no_lost_run`'s own internal
`bench.summarize()` recompute, which let the new REQ-V170-BEN-06 gate mask
the `QUALITY_GATE_SLACK` boundary the test was designed to probe. Fixed by
extracting the patch into a named, reusable helper
(`_force_full_gate_scenarios`) and re-applying it after the test's own
recompute; re-verified by hand-applying the mutation and confirming the test
now fails, then reverting and re-running the full 83-mutation gate.
