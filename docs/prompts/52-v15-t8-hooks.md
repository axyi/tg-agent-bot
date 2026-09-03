# Prompt 52 — spec-v1.5 T8: hook chain

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** the hook shims, installer semantics and `replay`
  substitute set are fully specified by REQ-V15-HOOK-01..06 and
  REQ-V15-GATE-05; the only judgment calls are testing strategy (a
  disposable git worktree for `uv run`-dependent gates, a mocked
  `run_argv` for the path-resolution invariant) and two pre-existing-bug
  fixes an advisor review surfaced before activation
- **Harness:** Claude Code
- **Stage:** T8
- **Owner of:** `.githooks/{commit-msg,pre-commit,pre-push}` (new),
  `devtools/install_hooks.py` (new), `devtools/checks.py` (replay
  implementation, the `ruff-check` diff-scoping fix, stdin support in
  `run_argv`), `tests/test_v15_standards.py` (T-V15-HOOK-01..05, N1, N2,
  N3, N6, T-V15-GATE-06, plus a pre-existing-fixture fix), `docs/reports/
  report-v1.5.md` (T8 section, T7's missing RLM row),
  `docs/prompts/52-v15-t8-hooks.md` (new)
- **REQ ids:** REQ-V15-HOOK-01..06, REQ-V15-GATE-05

## Goal

Wire and activate the versioned hook chain: three shim files under
`.githooks/`, an idempotent `devtools/install_hooks.py` (install +
`--check`), and `checks.py replay --range <rev>..<rev>` re-running a named
substitute set (not literally `pre-commit`) against git history without
ever touching the working tree. Activate `core.hooksPath` for this repo
once the whole chain is proven on throwaway fixtures — every commit from
here on passes through it.

## Constraints

- Each hook file is at most ten lines: shebang, `set -eu`, one call into
  `checks.py` (REQ-V15-HOOK-06) — no regex, threshold or tool invocation
  lives in a hook.
- `install_hooks.py --check` distinguishes four problems with four
  distinct messages and never mutates state; a second `install` run is a
  byte-identical no-op (REQ-V15-HOOK-05, E9).
- `replay` never checks out, resets or otherwise mutates the working
  tree — blobs are read via `git show`/`git cat-file` only. Ruff runs
  from the repository root with `--stdin-filename <repo-relative path>`,
  never a `$TMPDIR` path (REQ-V15-GATE-05).
- Activation is gated on proof, not assumed: the whole chain must pass on
  disposable fixture repos/worktrees before `core.hooksPath` is set on
  the real repository, per an advisor review's explicit warning.

## Acceptance

- `T-V15-HOOK-01` through `-05`, `N1`, `N2`, `N3`, `N6`, `T-V15-GATE-06`
  all green.
- `uv run --locked ruff check .` and the full `uv run --locked pytest`
  suite both exit 0.
- `devtools/install_hooks.py --check` exits 0 against the real repository
  after activation.
- This commit itself is produced through the now-active `commit-msg` and
  `pre-commit` hooks — first live evidence the chain works end to end.

## Stop

If any of the four `install_hooks.py --check` problem cases cannot be
made to produce a distinct message, or if `replay`'s per-commit ruff
invocation cannot be proven to run with the repository root as `cwd` and
a repository-relative `--stdin-filename`, stop before activating
`core.hooksPath` and record the gap — a chain that cannot be proven safe
must not go live.
