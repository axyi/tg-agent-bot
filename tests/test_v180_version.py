"""T-V180-VER-01 (REQ-V180-VER-01): pyproject.toml's project.version reads
1.8.0 -- the release stamp, landed only in T9, after every gate is green."""

import tomllib

from devtools import checks


def test_t_v180_ver_01_pyproject_version_is_1_8_0():
    path = checks.REPO_ROOT / "pyproject.toml"
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    assert data["project"]["version"] == "1.8.0"
