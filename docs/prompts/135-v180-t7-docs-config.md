# Prompt 135 — v1.8.0 T7 docs + config

- **Date:** 2026-09-10
- **Executor model:** claude-sonnet-5
- **Model reason:** small, fully-specified docs/config correction with the
  exact facts and target wording given in the brief — mechanical editing
  against a verified tree, not open design search.
- **Harness:** Claude Code
- **Stage:** T7
- **Owner of:** `AGENTS.md`, `README.md`, `config/quality_gates.yaml`,
  `docs/prompts/135-v180-t7-docs-config.md`
- **REQ ids:** REQ-V180-AGT-03 (T7's half), REQ-V180-RPT-01

## Goal

Implement `docs/spec/task-briefs/v180-T7.md` end to end, in one commit:
correct the two count-bearing sentences in `AGENTS.md`'s `## Gates` section
(1133→1217 tests citing spec-v1.8.0 T8, 92→98 mutation entries citing T6 and
`report-v1.8.0.md`, `--select v170-`→`--select v180-`); fix `README.md`'s
`## Dashboard` section, which falsely claims no route ever serves message
content now that `/conversations`/`/conversations/<id>` serve redacted
transcript content by design; review `docs/plan.md` for anything v1.8.0
falsifies; and repoint `config/quality_gates.yaml`'s `lint-docs.report_path`
from `report-v1.7.0.md` to `report-v1.8.0.md`.

## Constraints

- No version bump anywhere (`pyproject.toml` stays `1.7.0`).
- No source or test code changes — only `AGENTS.md`, `README.md`, possibly
  `docs/plan.md`, and `config/quality_gates.yaml`'s one `report_path` line.
- `AGENTS.md`: touch nothing but the two count-bearing sentences — no
  reflow, no other paragraph.
- No file outside this repository read or written (EC-01).

## Acceptance

`uv run --locked python devtools/checks.py lint-docs` exits 0 against the
repointed `report_path`. `uv run --locked ruff check .` exits 0 (no-op on
these files). `AGENTS.md` reads 1217 tests / spec-v1.8.0 T8, 98 entries /
T6 / `report-v1.8.0.md`, `--select v180-`. `README.md`'s Dashboard section
lists all five live routes and states the real invariant (trace/span
content gated by `OBS_CAPTURE_CONTENT`; the conversation transcript is a
separate, always-available, redacted source).

## Stop

A concrete claim in `docs/plan.md` that v1.8.0 falsifies would require an
edit and a note in the report instead of leaving it unchanged; none was
found — the file's content is token-economy history and candidates, none
of which v1.8.0 touches.
