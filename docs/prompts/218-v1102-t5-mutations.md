# Prompt 218 — v1.10.2 T5: six v1102-* mutation entries, gate wiring

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** delegated implementation task (spec-v1.10.2 T5's
  mutations part: offline mutation-table authoring and gate-config wiring);
  subagent, briefed by `docs/spec/task-briefs/v1102-T5.md`.
- **Harness:** Claude Code (subagent)
- **Stage:** T5
- **Owner of:** `devtools/mutation_check.py`, `config/quality_gates.yaml`,
  `tests/test_v1100_gates.py`, `tests/test_v1101_gates.py`,
  `tests/test_v1102_gates.py`
- **REQ ids:** REQ-V1102-GATE-02

## Goal

Append the six `v1102-*` mutation entries GATE-02 names
(`v1102-secrets-line-dropped`, `v1102-first-clause-only`,
`v1102-tool-log-not-filled`, `v1102-tool-log-unredacted`,
`v1102-inj-gap-marker-dropped`, `v1102-hal-gap-marker-dropped`) to
`devtools/mutation_check.py`'s `MUTATIONS` list after the last `v1101-*`
entry, each with a rationale comment naming the mechanism, the killing
test(s), and any empirical discrepancy from the brief's predicted killer;
register `mutation-v1102` in `config/quality_gates.yaml` (same shape as
`mutation-v1101`, `--select "v1102-"`, a placeholder `timeout_seconds` for
the orchestrator's later calibration run) and add it to `mutation-subsets`;
reword `mutation-all`'s v1.10.1 T6a dated comment to drop "is now" and add
a new dated sentence recording `len(MUTATIONS)` == 139; amend
`tests/test_v1100_gates.py` and `tests/test_v1101_gates.py` per EC-02's
exhaustive-list rows 7-8, and extend `tests/test_v1102_gates.py` with
`T-V1102-GATE-01`/`T-V1102-GATE-02`.

## Constraints

Offline throughout. Never invoke `mutation_check.py`'s CLI mutate -> run ->
revert machinery over the whole `MUTATIONS` list or under `--select
"v1102-"` before this task's own commit lands (the pre-existing v1.9.3
dirty-tree guard would refuse to start against this task's own uncommitted
edit to that file) -- only a quick, direct, hand-applied per-mutation
sanity check (edit by hand, run the one targeted test, revert via `git
checkout`) is permitted, and was used to verify all six entries. Never
touch `mutation-all`'s `argv` or its existing `timeout_seconds: 1640`.
Never touch any `v1100-*`/`v1101-*`/earlier mutation entry's own
`find`/`replace`/`why` text. Test-first: all three amended/new test files
were edited and run red against the unedited tree before the six
`MUTATIONS` entries and the yaml changes landed.

## Acceptance

`T-V1102-GATE-01`, `T-V1102-GATE-02`, and the amended
`tests/test_v1100_gates.py`/`tests/test_v1101_gates.py` tests green;
`len(devtools.mutation_check.MUTATIONS) == 139`; full offline suite green
(2169 passed / 1 skipped, no test deleted); `ruff check .` clean;
`checks.py doctor` and `checks.py lint-docs` both green;
`checks.load_gate_config()` still succeeds with `mutation-v1102` present
and its `timeout_seconds` clearly marked `# PLACEHOLDER -- orchestrator
fills this from the calibration run`.

## Stop

None hit. All six empirical sanity checks (mutate -> run the one named
test -> `git checkout` revert) matched the brief's predicted killer test
by name; one fixture-literal discrepancy was disclosed in the
`v1102-tool-log-unredacted` entry's own `why` comment (the actual
registered-secret fixture in `tests/test_v1102_runner.py` is
`CANARY-V1102-RUNNER-SENTINEL-VALUE`, this repo's CANARY-named-sentinel
convention, not the brief's illustrative `VALUE-abcdefgh12` placeholder
shape) -- not a killer-test discrepancy, so not a repair-budget item.
`devtools/mutation_check.py`'s own two-entry-line INJ_MARKERS `find`
string needed one extra split to clear ruff's `E501` line-length limit
(101 > 100 chars); the split only changes how the Python source literal
is broken across lines, not the string value it produces, and uniqueness
was re-verified (`text.count(find) == 1`) after the split. The
orchestrator still owes: the `--select v1102-` calibration run (timing
it), filling in `mutation-v1102`'s real `timeout_seconds`, and the full
`mutation_check.py` run confirming all six new entries killed -- per the
brief, explicitly not this task's job.
