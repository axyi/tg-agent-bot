"""spec-v1.11.1 T6 (REQ-V1111-VER-01..04): the version-bump identity tests.

`T-V1111-VER-01`: the live tree's `pyproject.toml` `project.version` reads
`1.11.1`, and the frozen `v1.11.0` git-tag blob still reads `1.11.0` --
mirrors `tests/test_v1110_ver.py::test_t_v1110_ver_01_live_version_is_1_11_0`'s
own live-tree read, one release later (that function is itself repointed by
this task to a frozen `v1.11.0` tag-blob read, per the T0 pin inventory).

`T-V1111-VER-02`: `git diff v1.11.0 -- pyproject.toml uv.lock` is
project-version-only under `devtools/agent_eval.py`'s
`dependency_diff_is_version_only` helper, and the `project.dependencies`
list (both `pyproject.toml`'s own array and the `[dependency-groups].dev`
array) is unchanged from the `v1.11.0` tag blob -- no dependency drift
beyond the version literal. Structural regression check (EC-02 carve-out):
may be green on first execution against the unbumped tree (the diff is
empty there), and the report records that honestly rather than fabricating
a red-first run.

`T-V1111-VER-03`: `AGENTS.md` carries the T6-measured test count and
`152 entries`, both dated `as of spec-v1.11.1 T6`, the
`docs/spec/task-briefs/v1111-T<N>.md` brief-path token, and NG-11's one new
sentence; README's `## Versioning` release table gains a `v1.11.1 | 1.11.1`
row ending `; this release` and the `v1.11.0` row no longer does (that
clause moves to the new row).

`T-V1111-VER-04`: `config/quality_gates.yaml`'s `lint-docs.report_path`
reads `docs/reports/report-v1.11.1.md`, and `checks._lint_report_delegation`
on that report returns no findings.

Written test-first (EC-02): `-01`/`-03` confirmed red against the pre-bump
tree (`03d351c`, `pyproject.toml` still `1.11.0`, `AGENTS.md`/README not yet
repointed); `-02`/`-04` are the carve-out and may be green on first
execution -- recorded honestly in `docs/reports/report-v1.11.1.md`'s `## T6`
section.

Offline: reads `README.md`/`AGENTS.md`/`pyproject.toml`/
`config/quality_gates.yaml` off disk and `git show`/`git diff` against the
local repository only -- no network, no live LLM (the one network call this
task makes, `uv lock`, is not this file's concern).
"""

from __future__ import annotations

import subprocess
import tomllib

from devtools import agent_eval as ae
from devtools import checks

_REPO_ROOT = checks.REPO_ROOT
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_README_MD = _REPO_ROOT / "README.md"
_AGENTS_MD = _REPO_ROOT / "AGENTS.md"
_BASELINE_TAG = "v1.11.0"

# T6's own measured figure (mirrors REQ-V1110-EC-03's own convention):
# filled in last, after every other edit, from `uv run --locked pytest
# --collect-only -q -o addopts="" | grep -c '::'` on the fully-edited tree
# -- never guessed in advance.
_MEASURED_TEST_COUNT = 2411


def _read_readme() -> str:
    return _README_MD.read_text(encoding="utf-8")


def _read_agents_md() -> str:
    return _AGENTS_MD.read_text(encoding="utf-8")


def test_t_v1111_ver_01_live_version_is_1_11_1():
    with _PYPROJECT.open("rb") as handle:
        live_version = tomllib.load(handle)["project"]["version"]
    assert live_version == "1.11.1"

    tagged = subprocess.run(
        ["git", "show", f"{_BASELINE_TAG}:pyproject.toml"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tomllib.loads(tagged)["project"]["version"] == "1.11.0"


def test_t_v1111_ver_02_dependency_diff_version_only():
    diff_text = subprocess.run(
        ["git", "diff", _BASELINE_TAG, "--", "pyproject.toml", "uv.lock"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert ae.dependency_diff_is_version_only(diff_text) is True

    baseline_text = subprocess.run(
        ["git", "show", f"{_BASELINE_TAG}:pyproject.toml"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    baseline = tomllib.loads(baseline_text)
    with _PYPROJECT.open("rb") as handle:
        live = tomllib.load(handle)

    assert live["project"]["dependencies"] == baseline["project"]["dependencies"]
    assert live["dependency-groups"]["dev"] == baseline["dependency-groups"]["dev"]


def test_t_v1111_ver_03_agents_md_and_release_row():
    agents_text = _read_agents_md()
    assert f"{_MEASURED_TEST_COUNT}" in agents_text
    assert "152 entries" in agents_text
    assert "as of spec-v1.11.1 T6" in agents_text
    assert "docs/spec/task-briefs/v1111-T<N>.md" in agents_text
    assert "v1.11.1 changes nothing token-bearing either; the rule does not fire." in agents_text

    readme_text = _read_readme()
    assert "| v1.11.1 | 1.11.1 |" in readme_text

    table_start = readme_text.index("## Versioning")
    table_end = readme_text.index("## Token economy", table_start)
    table = readme_text[table_start:table_end]

    v1111_row_start = table.index("| v1.11.1 | 1.11.1 |")
    v1111_row_end = table.index("|\n", v1111_row_start) + 1
    v1111_row = table[v1111_row_start:v1111_row_end]
    assert "; this release" in v1111_row

    v1110_row_start = table.index("| v1.11.0 | 1.11.0 |")
    v1110_row_end = table.index("|\n", v1110_row_start) + 1
    v1110_row = table[v1110_row_start:v1110_row_end]
    assert "; this release" not in v1110_row


def test_t_v1111_ver_04_report_path_and_own_report_lint():
    config = checks.load_gate_config()
    lint_docs = config["gates"]["lint-docs"]
    assert lint_docs["report_path"] == "docs/reports/report-v1.11.1.md"

    report = _REPO_ROOT / "docs" / "reports" / "report-v1.11.1.md"
    assert checks._lint_report_delegation(report) == []
