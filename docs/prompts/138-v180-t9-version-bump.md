# Prompt 138 — v180 T9: the version bump

- **Date:** 2026-09-10
- **Executor model:** claude-sonnet-5
- **Model reason:** small, mechanical, single-edit-class change across
  `pyproject.toml`/`uv.lock`; orchestrator context, no delegation needed.
- **Harness:** Claude Code
- **Stage:** T9
- **Owner of:** `pyproject.toml`, `uv.lock`, `tests/test_v180_version.py`
- **REQ ids:** REQ-V180-VER-01

## Goal

Land the release stamp, the last task before tagging, strictly after T8's
gates are green: `pyproject.toml`'s `project.version` moves `1.7.0` →
`1.8.0`, `uv.lock` regenerated to match (`uv sync --locked` fails
otherwise — the lockfile embeds the same version for this virtual
package), and `tests/test_v180_version.py` proves it (`T-V180-VER-01`,
red before the bump, green after — verified both ways).

`README.md`'s `## Versioning` section (`:614-629`) and `AGENTS.md` were
both checked for a hardcoded current-version literal to echo: neither
carries one. `README.md`'s Versioning section is policy prose (the
MAJOR/MINOR/PATCH table) with no current-version number in it;
`bot.py --version` and `/api/health` both read `pyproject.toml` fresh
(`dashboard_server.py`'s `_project_version()`), so nothing else needs a
matching literal. `AGENTS.md`'s two "1.7.0" occurrences are historical
prose (`"...up from 92 at spec-v1.7.0's close"`, `"Two environment
variables (spec-v1.7.0): ..."`) correctly describing *when* a past
feature landed, not the current version — left untouched.

## Constraints

`pyproject.toml`, `uv.lock`, `tests/test_v180_version.py` only. No other
file. No tag, no annotated tag — that's T10, only after full re-acceptance.

## Acceptance

`T-V180-VER-01` red before, green after (confirmed via `git stash`).
`uv sync --locked` exits 0 against the regenerated lockfile.

## Stop

N/A — completed in one step.
