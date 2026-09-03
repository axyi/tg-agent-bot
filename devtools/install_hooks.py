"""REQ-V15-HOOK-05: activates the versioned `.githooks/` chain.

No argument: sets `core.hooksPath` to `.githooks`, makes each hook file
executable, prints what changed -- a second run changes nothing and says so
(idempotence, REQ-V15-HOOK-05/E9). `--check`: verifies without changing,
exits non-zero on the first of four problems: `core.hooksPath` unset, it
points elsewhere, a hook is missing, or a hook is not executable.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_PATH_VALUE = ".githooks"
HOOK_NAMES = ["commit-msg", "pre-commit", "pre-push"]
_EXEC_BITS = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH


def _run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo_root, capture_output=True, text=True, check=False
    )


def _in_git_work_tree(repo_root: Path) -> bool:
    result = _run_git(["rev-parse", "--is-inside-work-tree"], repo_root)
    return result.returncode == 0 and result.stdout.strip() == "true"


def _configured_hooks_path(repo_root: Path) -> str | None:
    """This repo's own `core.hooksPath`, `--local` scope only -- a global or
    system-level value (from the operator's own git config) must never read
    as "installed" or shadow a genuine "not set" verdict for this repo."""
    result = _run_git(["config", "--local", "--get", "core.hooksPath"], repo_root)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _is_executable(path: Path) -> bool:
    return path.exists() and bool(path.stat().st_mode & stat.S_IXUSR)


def check(repo_root: Path = REPO_ROOT) -> list[str]:
    problems = []
    configured = _configured_hooks_path(repo_root)
    if configured is None:
        problems.append("core.hooksPath is not set")
    elif configured != HOOKS_PATH_VALUE:
        problems.append(f"core.hooksPath is {configured!r}, expected {HOOKS_PATH_VALUE!r}")
    hooks_dir = repo_root / HOOKS_PATH_VALUE
    for name in HOOK_NAMES:
        hook = hooks_dir / name
        if not hook.exists():
            problems.append(f"hook missing: {HOOKS_PATH_VALUE}/{name}")
        elif not _is_executable(hook):
            problems.append(f"hook not executable: {HOOKS_PATH_VALUE}/{name}")
    return problems


def install(repo_root: Path = REPO_ROOT) -> list[str]:
    changed = []
    if _configured_hooks_path(repo_root) != HOOKS_PATH_VALUE:
        _run_git(["config", "core.hooksPath", HOOKS_PATH_VALUE], repo_root)
        changed.append(f"set core.hooksPath to {HOOKS_PATH_VALUE!r}")
    hooks_dir = repo_root / HOOKS_PATH_VALUE
    for name in HOOK_NAMES:
        hook = hooks_dir / name
        if not _is_executable(hook):
            hook.chmod(hook.stat().st_mode | _EXEC_BITS)
            changed.append(f"made {HOOKS_PATH_VALUE}/{name} executable")
    return changed


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not _in_git_work_tree(REPO_ROOT):
        print("install_hooks.py: not inside a git work tree", file=sys.stderr)
        return 2

    if "--check" in args:
        problems = check(REPO_ROOT)
        if problems:
            for problem in problems:
                print(f"install_hooks.py --check: {problem}", file=sys.stderr)
            return 1
        print("install_hooks.py --check: hooks installed correctly")
        return 0

    changed = install(REPO_ROOT)
    if changed:
        for item in changed:
            print(f"install_hooks.py: {item}")
    else:
        print("install_hooks.py: nothing to change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
