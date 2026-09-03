# Prompt 53 — spec-v1.5 T9: `checks.py doctor`

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** REQ-V15-GATE-03 and REQ-V15-RTK-03 fully specify the
  comparison semantics (equality, not ordering; rtk's single warn-only
  exception); the only judgment call is confirming the `last_token`
  parser's exact semantics against each pinned tool's real, measured
  `--version` output before writing it, rather than assuming a shape
- **Harness:** Claude Code
- **Stage:** T9
- **Owner of:** `devtools/checks.py` (`_run_doctor`, two version
  parsers, `cmd_doctor` wired for real), `tests/test_v15_standards.py`
  (`N7` plus supporting doctor tests, one incidental fixture-branch-name
  fix), `docs/reports/report-v1.5.md` (T9 section, RLM row),
  `docs/prompts/53-v15-t9-doctor.md` (new)
- **REQ ids:** REQ-V15-GATE-03, REQ-V15-RTK-03

## Goal

Implement `checks.py doctor`: for every `tools:` entry, run its
`version_argv` verbatim, parse the resolved version with its named
`version_parser`, and compare against the pinned `version` — equality,
not an ordering check, so an unannounced upgrade is as visible as a
missing tool. Also verify the hook chain is installed
(`install_hooks.py --check`). `rtk` is the sole `warn_only_tools`
exception (REQ-V15-RTK-03): a mismatch there warns, never blocks.

## Constraints

- No tool name, command or flag is a Python literal — every
  `version_argv` runs verbatim from `quality_gates.yaml`
  (REQ-V15-GATE-02, carried over).
- The comparison is strict equality against the pin; "newer than
  pinned" fails exactly like "older than pinned" or "missing."
- `doctor`'s own hook-chain check and the standalone `hooks-installed`
  gate are allowed to overlap — both check `install_hooks.py --check`
  independently, per the CLI table's own description of `doctor`.

## Acceptance

- `N7` (both an older and a newer stub version reported by `doctor`,
  both fail closed, naming the tool, expected and found) green.
- `checks.py doctor` run against the live repository: `[PASS] doctor:
  all tools at pin, hooks installed`.
- `uv run --locked ruff check .` and the full `uv run --locked pytest`
  suite both exit 0.

## Stop

If the `last_token` parser cannot be made to agree with every pinned
tool's real, measured `--version` output (not an assumed shape), stop
and record which tool's output doesn't fit rather than special-casing
it silently in Python.
