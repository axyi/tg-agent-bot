# Prompt 51 — spec-v1.5 T7: scanners wiring

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** the gate-execution engine's shape (diff-scope
  partition, fail-closed, severity membership) is fully specified by
  REQ-V15-GATE-06/07/08/12; the empirical parts (allowlist form, semgrep
  offline proof, tool JSON shapes) require running the actual tools, not a
  design choice
- **Harness:** Claude Code
- **Stage:** T7
- **Owner of:** `devtools/checks.py` (gate execution engine + four
  adapters), `.gitleaks.toml` (new), `.semgrep/` (new, vendored),
  `tests/test_v15_standards.py` (T-V15-SCAN-*, N4, N5),
  `docs/reports/report-v1.5.md` (T7 section),
  `docs/prompts/51-v15-t7-scanners.md` (new)
- **REQ ids:** REQ-V15-SCAN-01..08, REQ-V15-GATE-06, REQ-V15-GATE-07,
  REQ-V15-GATE-08, REQ-V15-GATE-12

## Goal

Wire the four scanners into the runner: `.gitleaks.toml` with the
allowlist form settled by the N4 control/suppression/escape experiment,
the vendored `.semgrep/` ruleset resolved from the registry (the run's
last sanctioned online step), and the generic gate-execution engine
(diff-scope partition, fail-closed operational-failure handling, severity
membership, shadow mode) that all four scanner gates — and every later
`kind: command` gate — run through.

## Constraints

- `.semgrep/` is vendored (committed YAML), never fetched at gate time;
  `N5` proves this with the network denied and semgrep's cache emptied.
- `.gitleaks.toml`'s allowlist form is settled by experiment against the
  installed 8.30.1, not assumed from the sibling lab project's 8.24.3
  finding — record which form is honoured either way.
- No policy value (severity threshold, argv fragment, tool name) is a
  Python literal in `checks.py`; only the four adapter names and structural
  schema keys are permitted (REQ-V15-GATE-02, carried over from T1).
- A shadow gate's operational failure (missing binary, timeout, crash,
  unparseable output) still fails the profile closed — `blocking: false`
  withholds findings only, never run failures (REQ-V15-GATE-06).
- No project or lab file outside the repository is read (REQ-V15-EC-01).

## Acceptance

- `T-V15-SCAN-01` through `T-V15-SCAN-12`, `N4`, `N5` all green.
- `N4` records which allowlist table form 8.30.1 honours and all three
  exit codes.
- `N5` passes with the network denied and an empty semgrep cache.
- `uv run --locked ruff check .` and the full `uv run --locked pytest`
  suite (806 tests) both exit 0.

## Stop

If no combination of `.gitleaks.toml` allowlist form suppresses the
control canary while still catching the escape sentinel, stop and record
that as a finding — widening the allowlist to force assertion 3 to pass is
a defect (REQ-V15-SCAN-08), not an acceptable fix.
