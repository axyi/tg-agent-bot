"""spec-v1.10.4 T5 (REQ-V1104-VER-01): the version-bump identity tests.

`T-V1104-VER-01`: `pyproject.toml`'s live `project.version` reads `1.10.4`
(the bump this commit lands), while the frozen `v1.9.5` git-tag blob still
reads `1.9.5` forever -- the same permanent-historical-fact convention
`tests/test_v194_version.py`/`tests/test_v195_version.py` already use for
their own retired release stamps.

`T-V1104-VER-02`: the working-tree diff against the `f3ce1a5` blobs
(v1.10.3's stop-route commit, the last commit that touched `pyproject.toml`
before this bump), restricted to `pyproject.toml` and `uv.lock` only, is
project-version-only under `devtools/agent_eval.py`'s
`dependency_diff_is_version_only` helper (no whole-repository diff-shape
claim -- only these two paths are ever passed to `git diff`), and the
project-version delta from `f3ce1a5` exists (the live version differs from
the `f3ce1a5` blob's version) and resolves to `1.10.4`.

Written test-first (spec-v1.10.4.md:666-669): both tests confirmed red
against the pre-bump tree (`244b9a4`, `pyproject.toml` still `1.9.5`,
`uv.lock` unregenerated), green after `pyproject.toml:3`'s bump and the
online `uv lock` regeneration -- both runs recorded in
`docs/reports/report-v1.10.4.md`'s `## T5` section.

Offline: `git show`/`git diff` against the local repository only -- no
network, no live LLM.
"""

from __future__ import annotations

import subprocess
import tomllib

from devtools import agent_eval as ae
from devtools import checks

_PYPROJECT = checks.REPO_ROOT / "pyproject.toml"
_BASELINE_COMMIT = "f3ce1a5"


def test_t_v1104_ver_01_pyproject_version_is_1_10_4_v195_tag_frozen_at_1_9_5():
    with _PYPROJECT.open("rb") as handle:
        live_version = tomllib.load(handle)["project"]["version"]
    assert live_version == "1.10.4"

    tagged = subprocess.run(
        ["git", "show", "v1.9.5:pyproject.toml"],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tomllib.loads(tagged)["project"]["version"] == "1.9.5"


def test_t_v1104_ver_02_pyproject_and_uv_lock_diff_from_f3ce1a5_is_version_only():
    diff_text = subprocess.run(
        ["git", "diff", _BASELINE_COMMIT, "--", "pyproject.toml", "uv.lock"],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ae.dependency_diff_is_version_only(diff_text) is True

    baseline_text = subprocess.run(
        ["git", "show", f"{_BASELINE_COMMIT}:pyproject.toml"],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    baseline_version = tomllib.loads(baseline_text)["project"]["version"]

    with _PYPROJECT.open("rb") as handle:
        live_version = tomllib.load(handle)["project"]["version"]

    assert baseline_version != live_version, "no project-version delta from f3ce1a5 yet"
    assert live_version == "1.10.4"
