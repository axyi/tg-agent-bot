# Prompt 66 — v1.5.1 patch: D1, fixture git-env isolation

- **Date:** 2026-09-04
- **Executor model:** claude-sonnet-5 (Claude Code)
- **Model reason:** root-causing a real incident (a live git-hook process
  environment leaking into a test suite's own subprocess calls) needs
  correct reasoning about git's `GIT_DIR`/`GIT_WORK_TREE` resolution
  rules and a faithful, evidence-based reproduction, not a plausible
  guess — the model's forensic trace was verified empirically before
  any fix code was written
- **Harness:** Claude Code
- **Stage:** v1.5.1 patch, D1 (CRITICAL)
- **Owner of:** `tests/test_v15_standards.py` (fixture helpers `_init_repo`,
  `_commit_all`, `git_worktree`, and every ad hoc `git` subprocess call
  they or the tests around them make; one new regression test)
- **REQ ids:** REQ-V12-OFF-01 (offline/isolated test discipline; §15 of
  spec-v1.5 restates it for this suite: "use a temporary git repo in a
  `tmp_path` fixture, never the real one")

## Goal

Fix a CRITICAL defect found by post-run `/verify-run`: running this test
suite from inside a real git hook in a linked worktree let `refs/heads/main`
of the enclosing repository get force-renamed onto a throwaway fixture
commit (repaired manually with `git update-ref`; no content lost). Root
cause: no fixture `git` subprocess call in `tests/test_v15_standards.py`
passes its own `env=`, so a real git hook's `GIT_DIR`/`GIT_WORK_TREE`
(set for its own child-process chain: `.githooks/pre-push` -> `checks.py`
-> `uv run pytest`) leaks straight through into `_init_repo`/`_commit_all`
and ad hoc calls such as `test_v15_hook_05`'s `git branch -M main`. Fix:
every fixture `git` call goes through a shared `_git()` helper that builds
its own scrubbed environment (every `GIT_*` variable stripped, an explicit
`GIT_CEILING_DIRECTORIES`) regardless of the ambient process environment,
plus a fail-loud assertion that a freshly created fixture repo's resolved
git-dir is actually confined to its own directory (or, for `git_worktree`,
genuinely shares the real repository's common dir rather than some
env-redirected other one) before any write.

## Constraints

- Test-file-only change (`tests/test_v15_standards.py`); no production
  code outside `tests/` touched, no bot behaviour altered.
- No git history rewrite of the incident itself; this is a forward fix.
- The regression test must reproduce the exact incident shape (a fixture
  used while `GIT_DIR`/`GIT_WORK_TREE` point at another repo) against a
  disposable stand-in "enclosing" repo it creates itself in `tmp_path` --
  never the real repository.
- Every existing test in the file must still pass unmodified in behaviour
  (only the git-invocation plumbing changes).

## Acceptance

- The new test (`test_d1_fixture_repo_never_touches_enclosing_repo_via_leaked_git_env`)
  fails against the pre-fix fixture code (red, empirically verified via a
  temporary unscrubbed `_git`/`_assert_git_dir_confined` substitution) and
  passes against the fixed code (green).
- `uv run --locked pytest tests/test_v15_standards.py` exits 0 (116 tests).
- `uv run --locked ruff check tests/test_v15_standards.py` and
  `uv run --locked ruff format --check tests/test_v15_standards.py` both
  exit 0.

## Stop

If the fix required changing production code outside `tests/` in a way
that alters the bot's behaviour, stop and report instead of proceeding.
Not triggered: the whole fix stayed inside `tests/test_v15_standards.py`.
