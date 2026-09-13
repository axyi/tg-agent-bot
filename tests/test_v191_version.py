"""T-V191-VER-01 (REQ-V190-VER-01): pyproject.toml's project.version read
1.9.1 -- the release stamp, landed only in T2, before this commit.

Superseded at spec-v1.9.2 T3's own required VER-01 bump (1.9.1 -> 1.9.2):
this test's live-tree read broke the moment the bump landed, the same
structural class tests/test_v180_version.py and tests/test_v190_version.py
already disclosed at their own release's retirement. REQ-V190-EC-03 forbids
deleting a test, so rather than delete it (its coverage would simply vanish)
or leave it permanently red, it is repointed -- the exact convention
tests/test_v190_version.py established -- to assert the permanent historical
fact instead of the live tree: the `v1.9.1` tag's own `pyproject.toml` blob
reads `1.9.1` forever, regardless of what any later release bumps the live
tree to. `tests/test_v192_version.py` (`T-V192-VER-01`) will need the
identical treatment -- repoint to `git show v1.9.2:pyproject.toml`, never
delete -- at whatever release retires 1.9.2; expected, not a defect to fix
now."""

import subprocess
import tomllib

from devtools import checks


def test_t_v191_ver_01_v191_was_tagged():
    result = subprocess.run(
        ["git", "show", "v1.9.1:pyproject.toml"],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    version = tomllib.loads(result.stdout)["project"]["version"]
    assert version == "1.9.1"
