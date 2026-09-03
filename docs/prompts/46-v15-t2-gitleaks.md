# Prompt 46 — spec-v1.5 T2: install gitleaks 8.30.1

- **Date:** 2026-09-03
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a pinned-version binary install with a checksum
  verification step; no design decision
- **Harness:** Claude Code
- **Stage:** T2
- **Owner of:** `config/quality_gates.yaml` (gitleaks pin only),
  `docs/reports/report-v1.5.md` (T2 provenance row),
  `docs/prompts/46-v15-t2-gitleaks.md` (new)
- **REQ ids:** REQ-V15-DEP-02, REQ-V15-DEP-03, REQ-V15-DEP-05, REQ-V15-SCAN-01,
  REQ-V15-GATE-05

## Goal

Install gitleaks 8.30.1 as a GitHub release asset with a verified SHA-256
checksum, move only the `tools.gitleaks.version` pin in
`config/quality_gates.yaml`, and re-confirm REQ-V15-SCAN-01's and
REQ-V15-GATE-05's argv against the new version's `--help` output.

## Constraints

- No `curl … | sh` — download the asset and its checksum file separately,
  verify with `sha256sum -c`, only then place the binary on `PATH`
  (REQ-V15-DEP-03, REQ-V15-SCAN-07).
- This commit touches only the gitleaks pin — no other tool's pin, no gate
  logic, no other file (REQ-V15-DEP-05: one tool, one pin, one commit).
- The network step (the GitHub release download) is one of §3's sanctioned
  steps; nothing else in this task goes online.

## Acceptance

- `gitleaks version` prints `8.30.1`.
- The downloaded asset's SHA-256 matches the published
  `gitleaks_8.30.1_checksums.txt` entry, recorded in the report.
- `gitleaks --help`, `gitleaks dir --help`, `gitleaks git --help` confirm
  every flag REQ-V15-SCAN-01/GATE-05 uses is unchanged; any drift is
  corrected in the config in this same commit.
- `uv run --locked ruff check .` and `uv run --locked pytest
  tests/test_v15_standards.py` both exit 0.

## Stop

If the checksum does not verify, delete the download and stop — do not
install an unverified binary under any circumstance.
