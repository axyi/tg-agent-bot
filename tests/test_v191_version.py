"""T-V191-VER-01 (REQ-V190-VER-01, patch-release convention): pyproject.toml's
project.version reads 1.9.1 -- the v1.9.1 release stamp, landed only in T2,
after every gate is green.

Superseded at whatever release retires 1.9.1: per REQ-V190-EC-03 (no test may
be deleted), this file's own test gets the same treatment
tests/test_v180_version.py and tests/test_v190_version.py already received --
repointed to the frozen `v1.9.1` git-tag blob (`git show v1.9.1:pyproject.toml`),
never deleted."""

import tomllib

from devtools import checks


def test_t_v191_ver_01_pyproject_version_is_1_9_1():
    path = checks.REPO_ROOT / "pyproject.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["project"]["version"] == "1.9.1"
