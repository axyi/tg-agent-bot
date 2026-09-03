# Prompt 48 — spec-v1.5 T4: install trivy 0.74.0, resolve SCAN-03's [[VERIFY]]

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a pinned binary install plus an empirical `--help`
  confirmation the spec explicitly delegates to this task; no open design
  question
- **Harness:** Claude Code
- **Stage:** T4
- **Owner of:** `config/quality_gates.yaml` (trivy pin + `[[VERIFY]]`
  resolution), `docs/reports/report-v1.5.md` (T4 provenance + DB-cache
  finding), `docs/prompts/48-v15-t4-trivy.md` (new)
- **REQ ids:** REQ-V15-DEP-02, REQ-V15-DEP-03, REQ-V15-DEP-05, REQ-V15-SCAN-03

## Goal

Install trivy 0.74.0 as a GitHub release asset with a verified SHA-256,
move only the `tools.trivy` pin, and resolve REQ-V15-SCAN-03's `[[VERIFY]]`
marker by running `trivy fs --help` at the pin and confirming every flag,
the exit-code semantics and `version_argv` before the invocation is
trusted.

## Constraints

- Release asset + checksum only, no `curl | sh` (REQ-V15-DEP-03).
- This commit touches only the trivy pin and the `[[VERIFY]]` resolution —
  no other tool, no other gate (REQ-V15-DEP-05).
- Any flag drift discovered against `--help` is corrected in this same
  commit and recorded in the report, not silently absorbed.

## Acceptance

- `trivy --version` reports `0.74.0`.
- SHA-256 of the downloaded asset matches
  `trivy_0.74.0_checksums.txt`, recorded in the report.
- `trivy fs --help` confirms `--scanners`, `--severity`, `--exit-code`,
  `--ignore-unfixed`, `--format`, `--output` all present as
  REQ-V15-SCAN-03 uses them.
- A smoke scan against a throwaway directory exits 0 with the exact argv,
  proving the invocation runs end-to-end.
- `uv run --locked ruff check .` and `uv run --locked pytest
  tests/test_v15_standards.py` both exit 0.

## Stop

If `trivy fs --help` shows any of the five flags renamed, removed or
behaving differently (exit-code semantics especially), stop and correct
the config before trusting the invocation — do not write an untested argv
into `config/quality_gates.yaml`.
