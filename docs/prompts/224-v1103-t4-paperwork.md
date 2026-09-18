# Prompt 224 — v1103 T4: paperwork (`.env.example`, README, `AGENTS.md`, GATE-03)

- **Date:** 2026-09-18
- **Executor model:** claude-sonnet-5
- **Model reason:** source-writing task (docs + one test-file repoint),
  delegated per EC-03 default.
- **Harness:** Claude Code (general-purpose subagent)
- **Stage:** T4
- **Owner of:** `.env.example`, `README.md`, `AGENTS.md`,
  `tests/test_v15_standards.py`, `tests/test_v1103_docs.py`,
  `tests/test_v1103_gates.py`
- **REQ ids:** REQ-V1103-RPT-03 (T4 part), REQ-V1103-GATE-03,
  REQ-V1103-VER-01 (the v1.10.2 row only)

## Goal

Update the shipped-default model literals and vendor names in
`.env.example`/README/`AGENTS.md`, add the v1.10.2 stopped-run release
row, and repoint the gate-matrix test at `spec-v1.10.3.md`. Full detail
in `docs/spec/task-briefs/v1103-T4.md` — every value in it is
pre-verified against the current file content.

## Constraints

Do NOT add the `v1.10.3` release-table row (T7's job — gate 8 hasn't
run yet). Do NOT touch `AGENTS.md`'s count lines (T7's job). Do NOT
touch `config/quality_gates.yaml` (T3 already repointed `lint-docs`).
Do NOT touch `spec-v1.10.2.md` (frozen, NG-11). If the matrix test fails
for any reason beyond the missing `v1103-` label, stop and report —
repair budget is at 2 of 3 cycles spent.

## Acceptance

See the brief's Acceptance section — the gate-matrix test green against
`spec-v1.10.3.md`, no `v1.10.3` row yet, the v1.10.2 waiver sentence in
`AGENTS.md` intact verbatim, gates 1-4 green.

## Stop

If any of the four paperwork edits would require touching a file or
line outside this brief's exact list, stop and report rather than
expanding scope.
