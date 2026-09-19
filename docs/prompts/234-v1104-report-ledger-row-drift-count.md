# Prompt 234 — v1.10.4 post-release: correct the report's ledger-row drift count

- **Date:** 2026-09-19
- **Executor model:** claude-opus-5
- **Model reason:** lab session, artefacts only — a one-cell wording fix
  in a shipped report, found by `/verify-run`; no source, no gates beyond
  lint-docs; a single edit under every threshold (§5.1), not delegated.
- **Harness:** Claude Code (lab session, main context)
- **Stage:** post-release (after tag `v1.10.4`, pushed)
- **Owner of:** `docs/reports/report-v1.10.4.md` (ledger row, "Bugs"
  cell only), `docs/llm-usage.md` (row 145)
- **REQ ids:** REQ-V1104-RPT-03 (report accuracy; no requirement changes)

## Goal

The report's own `economics.md` draft (report line 959) says "four EC-02
amendment-table line-drifts disclosed across T1/T2/T4"; the report body
substantiates exactly one (T1, row 12b, a 3-line citation offset at
report :270). T2's two disclosures are a brief-text mismatch and a
ruff-format non-conformance of the stash content, T4 discloses no drift,
T5's disclosure is a lint-docs fix in its own prompt file — none is a
line-drift. Rewrite the cell to say so; the lab's `economics.md` already
carries the corrected count.

## Constraints

Docs only. No source, no test, no instrument file touched. No version
change, no re-tag. `--no-verify` never used.

## Acceptance

`uv run python devtools/checks.py lint-docs` green; `git diff --stat`
shows exactly the two owned paths; the cell's new wording matches the
report body's disclosures one-to-one.

## Stop

Any need to touch a file outside the two owned paths is a stop.
