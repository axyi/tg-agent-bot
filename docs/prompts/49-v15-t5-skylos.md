# Prompt 49 — spec-v1.5 T5: install skylos 4.35.0, resolve SCAN-05's [[VERIFY]]

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a pinned tool install plus an empirical CLI-surface
  confirmation the spec explicitly delegates to this task
- **Harness:** Claude Code
- **Stage:** T5
- **Owner of:** `config/quality_gates.yaml` (skylos pin + `[[VERIFY]]`
  resolution), `docs/reports/report-v1.5.md` (T5 findings),
  `docs/prompts/49-v15-t5-skylos.md` (new)
- **REQ ids:** REQ-V15-DEP-02, REQ-V15-DEP-03, REQ-V15-DEP-05, REQ-V15-SCAN-05

## Goal

Install skylos 4.35.0 via `uv tool install`, move only the `tools.skylos`
pin, and resolve REQ-V15-SCAN-05's `[[VERIFY]]` marker — subcommand, path
passing, JSON-output flag, exit codes — by running `skylos --help` and
measuring exit-code behaviour empirically against this repository, since
no local docs exist for this tool.

## Constraints

- PyPI channel only (`uv tool install`), per REQ-V15-DEP-03.
- This commit touches only the skylos pin and the `[[VERIFY]]` resolution
  (REQ-V15-DEP-05).
- skylos stays a **shadow** gate (`blocking: false`) — this task does not
  promote it.
- Only the flags needed for a working, correctly-exit-coded invocation are
  added; `--secrets`/`--danger`/`--quality`/`-a` are not enabled, since
  they are off by default and outside the spec's own illustrative argv.

## Acceptance

- `skylos --version` reports `4.35.0`.
- Exit-code semantics measured and recorded: which flag combination gives
  "0 when clean, non-zero when findings exist" — not assumed from `--help`
  text alone.
- `config/quality_gates.yaml`'s skylos gate's `argv`, `success_exit_codes`
  and `findings_exit_codes` reflect the measured behaviour.
- `uv run --locked ruff check .` and `uv run --locked pytest
  tests/test_v15_standards.py` both exit 0.

## Stop

If no flag combination gives a reliable clean/findings exit-code split,
stop and record that as a finding rather than guessing at one — a shadow
gate with an unreliable "did it find anything" signal is worse than no
gate, since REQ-V15-GATE-06 still requires distinguishing "ran, found
nothing" from "crashed" even in shadow mode.
