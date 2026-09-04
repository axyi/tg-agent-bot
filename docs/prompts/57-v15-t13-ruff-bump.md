# Prompt 57 — spec-v1.5 T13: ruff 0.16.5 → 0.16.6

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** a single, fully-specified version bump with an
  explicit exclusion list (REQ-V15-DEP-05: `requires-python`,
  `.python-version`, `target-version` must not move here) — mechanical,
  no design judgment beyond verifying the target version is real
  before pinning it
- **Harness:** Claude Code
- **Stage:** T13
- **Owner of:** `pyproject.toml` (dev-dependency pin), `config/
  quality_gates.yaml` (`tools.ruff.version`), `uv.lock` (regenerated),
  `docs/reports/report-v1.5.md` (T13 section, RLM row),
  `docs/prompts/57-v15-t13-ruff-bump.md` (new)
- **REQ ids:** REQ-V15-DEP-04, REQ-V15-DEP-05, REQ-V15-GATE-03

## Goal

Bump ruff 0.16.5 → 0.16.6 and nothing else: move both pins
(`pyproject.toml`'s dev group, `quality_gates.yaml`'s
`tools.ruff.version`) in the same commit and regenerate `uv.lock`.

## Constraints

- `requires-python`, `.python-version` and `[tool.ruff]
  target-version` are T14's, not this task's — must not move here
  (REQ-V15-DEP-05).
- Both ruff pins move together, in the same commit, or not at all
  (REQ-V15-GATE-03).
- Verify 0.16.6 is a real, installable published version before
  pinning it, not assumed from memory.

## Acceptance

- `T-V15-GATE-03` (the drift test) green.
- `checks.py doctor` green at 0.16.6.
- `uv run --locked ruff check .` green; the full `uv run --locked
  pytest` suite exits 0; `bot.py --selftest` → `OK`.

## Stop

If 0.16.6 cannot be verified as a real published version, or if
upgrading surfaces new lint findings that would require touching files
beyond the two pins and the lock file, stop and report rather than
silently expanding scope.
