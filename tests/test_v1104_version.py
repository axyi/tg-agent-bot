"""spec-v1.10.4 T5 (REQ-V1104-VER-01): the version-bump identity tests.

Repointed at spec-v1.11.0 T8 (REQ-V1110-VER-01): `T-V1104-VER-01`'s live-
tree read is replaced by a frozen `v1.10.4` git-tag blob read, becoming
itself a permanent-historical-fact marker -- the same convention
`tests/test_v194_version.py`/`tests/test_v195_version.py` already use for
their own retired release stamps. `T-V1104-VER-02` is kept as the
historical fact it already is (T8 does not touch its diff-shape
assertion), but its own trailing live-tree literal is a disclosed
amendment (EC-02): `"1.10.4"` -> `"1.11.0"`, since the live tree now
carries T8's own bump -- the property the test actually proves (a
project-version delta exists between `f3ce1a5` and the live tree) is
unaffected by which version number is currently live.

`T-V1104-VER-01`: `pyproject.toml`'s live `project.version` read at
spec-v1.10.4 T5 is superseded by spec-v1.11.0 T8's own
`tests/test_v1110_ver.py::test_t_v1110_ver_01_live_version_is_1_11_0`;
this function now reads the frozen `v1.10.4` git-tag blob (`== "1.10.4"`
forever) alongside the `v1.9.5` tag blob it already read (`== "1.9.5"`
forever, untouched by this repoint).

`T-V1104-VER-02`: the working-tree diff against the `f3ce1a5` blobs
(v1.10.3's stop-route commit, the last commit that touched `pyproject.toml`
before the v1.10.4 bump), restricted to `pyproject.toml` and `uv.lock` only,
is project-version-only under `devtools/agent_eval.py`'s
`dependency_diff_is_version_only` helper (no whole-repository diff-shape
claim -- only these two paths are ever passed to `git diff`), and the
project-version delta from `f3ce1a5` exists (the live version differs from
the `f3ce1a5` blob's version) and resolves to the live tree's current
version (`1.11.0` from spec-v1.11.0 T8 on).

Written test-first (spec-v1.10.4.md:666-669): both tests confirmed red
against the pre-bump tree (`244b9a4`, `pyproject.toml` still `1.9.5`,
`uv.lock` unregenerated), green after `pyproject.toml:3`'s bump and the
online `uv lock` regeneration -- both runs recorded in
`docs/reports/report-v1.10.4.md`'s `## T5` section. Repointed test-first
again at spec-v1.11.0 T8: both functions confirmed red against the
freshly-bumped tree (`live_version == "1.11.0"` breaking the un-repointed
`test_t_v1104_ver_01_...`'s `== "1.10.4"` live-tree assertion, and
`test_t_v1104_ver_02_...`'s trailing `== "1.10.4"` literal likewise), green
after this repoint -- recorded in `docs/reports/report-v1.11.0.md`'s
`## T8` section.

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
    tagged_1104 = subprocess.run(
        ["git", "show", "v1.10.4:pyproject.toml"],
        cwd=checks.REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tomllib.loads(tagged_1104)["project"]["version"] == "1.10.4"

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
    # Disclosed amendment (EC-02, spec-v1.11.0 T8): this literal tracks the
    # live version, not this function's own historical baseline -- bumped
    # from "1.10.4" to "1.11.0" alongside T8's pyproject.toml:3 bump so the
    # test keeps passing; the property it proves (a version delta from
    # f3ce1a5 exists) is unaffected by which version number is live.
    assert live_version == "1.11.0"
