"""T-V195-VER-01 (REQ-V190-VER-01): pyproject.toml's project.version read
1.9.5 -- the release stamp, landed only in T2, before this commit.

Superseded at spec-v1.10.4 T5's own required VER-01 bump (1.9.5 -> 1.10.4):
this test's live-tree read broke the moment the bump landed, the same
structural class tests/test_v180_version.py, tests/test_v190_version.py,
tests/test_v191_version.py, tests/test_v192_version.py,
tests/test_v193_version.py and tests/test_v194_version.py already disclosed
at their own release's retirement. REQ-V190-EC-03 forbids deleting a test, so
rather than delete it (its coverage would simply vanish) or leave it
permanently red, it is repointed -- the exact convention
tests/test_v194_version.py established -- to assert the permanent historical
fact instead of the live tree: the `v1.9.5` tag's own `pyproject.toml` blob
reads `1.9.5` forever, regardless of what any later release bumps the live
tree to."""

import subprocess
import tomllib

from devtools import checks


def test_t_v195_ver_01_v195_was_tagged():
    result = subprocess.run(
        ["git", "show", "v1.9.5:pyproject.toml"],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    version = tomllib.loads(result.stdout)["project"]["version"]
    assert version == "1.9.5"
