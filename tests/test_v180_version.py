"""T-V180-VER-01 (REQ-V180-VER-01): pyproject.toml's project.version read
1.8.0 at the point this test proved it, T9, before that commit landed.

Superseded at spec-v1.9.0 T12's own required VER-01 bump (1.8.0 -> 1.9.0):
this test's live-tree read broke the moment the bump landed, the same
structural class every other EC-03-list gap in this run's history
disclosed. REQ-V190-EC-03 forbids deleting a test, so rather than delete
it (its coverage would simply vanish) or leave it permanently red, it is
repointed -- the exact convention `tests/test_v170_bench.py`'s
`test_t_v170_acc_03_version_half` already established for the identical
problem at v1.8.0's own T9 -- to assert the permanent historical fact
instead of the live tree: the `v1.8.0` tag's own `pyproject.toml` blob
reads `1.8.0` forever, regardless of what any later release bumps the
live tree to. This is now a repo convention: `tests/test_v190_version.py`
(`T-V190-VER-01`) will need the identical treatment -- repoint to `git show
v1.9.0:pyproject.toml`, never delete -- at whatever release retires 1.9.0;
expected, not a defect to fix now."""

import subprocess
import tomllib

from devtools import checks


def test_t_v180_ver_01_v180_was_tagged():
    result = subprocess.run(
        ["git", "show", "v1.8.0:pyproject.toml"],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    version = tomllib.loads(result.stdout)["project"]["version"]
    assert version == "1.8.0"
