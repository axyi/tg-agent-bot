# Prompt 47 — spec-v1.5 T3: install semgrep 1.176.0

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a pinned `uv tool install`; no design decision
- **Harness:** Claude Code
- **Stage:** T3
- **Owner of:** `config/quality_gates.yaml` (semgrep pin only),
  `docs/reports/report-v1.5.md` (T3 provenance row),
  `docs/prompts/47-v15-t3-semgrep.md` (new)
- **REQ ids:** REQ-V15-DEP-02, REQ-V15-DEP-03, REQ-V15-DEP-05, REQ-V15-SCAN-04

## Goal

Install semgrep 1.176.0 via `uv tool install semgrep==1.176.0`, move only
the `tools.semgrep.version` pin, and re-confirm REQ-V15-SCAN-04's argv
against `semgrep scan --help` at the new version.

## Constraints

- PyPI channel only (`uv tool install`), per REQ-V15-DEP-03.
- This commit touches only the semgrep pin — no other tool, no gate logic
  (REQ-V15-DEP-05).

## Acceptance

- `semgrep --version` prints `1.176.0`.
- `semgrep scan --help` confirms `--config`, `--severity`, `--error`,
  `--metrics`, `--disable-version-check`, `--json`, `--output` unchanged;
  any drift corrected in the same commit.
- `uv run --locked ruff check .` and `uv run --locked pytest
  tests/test_v15_standards.py` both exit 0.

## Stop

None expected — a pinned-version tool install with no ambiguity.
