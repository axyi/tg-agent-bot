"""spec-v1.11.0 T8 (REQ-V1110-VER-01..04): the version-bump identity tests.

`T-V1110-VER-01`: the live tree's `pyproject.toml` `project.version` reads
`1.11.0` -- the ONE test in this release that checks the *live* tree's
version (the repointed `tests/test_v1104_version.py` checks a frozen
`v1.10.4` tag-blob read instead, never the live tree, from this task on).

`T-V1110-VER-02`: `git diff v1.10.4 -- pyproject.toml uv.lock` is
project-version-only under `devtools/agent_eval.py`'s
`dependency_diff_is_version_only` helper, and the `project.dependencies`
list (both `pyproject.toml`'s own array and the `[dependency-groups].dev`
array) is unchanged from the `v1.10.4` tag blob -- no dependency drift
beyond the version literal. Structural regression check (EC-02 carve-out):
may be green on first execution against the unbumped tree (the diff is
empty there), and the report records that honestly rather than fabricating
a red-first run.

`T-V1110-VER-03`: `AGENTS.md` carries the T8-measured test count and
`152 entries`, both dated `as of spec-v1.11.0 T8`, and no longer carries
the prior release's `2311`/`144 entries` figures; README's `## Versioning`
release table gains a `v1.11.0 | 1.11.0` row and the `v1.10.4` row no
longer ends `; this release` (that clause moves to the new row).

`T-V1110-VER-04`: README carries the T1-T6 documentation deliverables this
release's spec (`REQ-V1110-VER-02`) names, plus the `/documents` sample
this task itself completes (§13 names it as T2's deliverable; T2's own
report disclosed dropping it -- REQ-V1110-VER-02 still names it, so T8
adds it, generated from `test_t_v1110_doc_01_documents_table`'s own
fixture, not hand-drawn). Structural regression check for everything
already landed by T1-T6 (EC-02 carve-out, may be green on first
execution); genuinely red-first for the one piece T8 itself adds.

Offline: reads `README.md`/`AGENTS.md`/`pyproject.toml` off disk and
`git show`/`git diff` against the local repository only -- no network, no
live LLM (the one network call this task makes, `uv lock`, is not this
file's concern).
"""

from __future__ import annotations

import re
import subprocess
import tomllib

from devtools import agent_eval as ae
from devtools import checks

_REPO_ROOT = checks.REPO_ROOT
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_README_MD = _REPO_ROOT / "README.md"
_AGENTS_MD = _REPO_ROOT / "AGENTS.md"
_BASELINE_TAG = "v1.10.4"

# T6's own measured figure (spec-v1.11.1, mirrors REQ-V1110-EC-03's own
# convention): filled in last, after every other edit, from `uv run --locked
# pytest --collect-only -q -o addopts="" | grep -c '::'` on the fully-edited
# tree -- never guessed in advance.
_MEASURED_TEST_COUNT = 2411


def _read_readme() -> str:
    return _README_MD.read_text(encoding="utf-8")


def _read_agents_md() -> str:
    return _AGENTS_MD.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    """Collapse whitespace runs, matching `tests/test_v190_agents.py`'s own
    `_normalize` -- both docs wrap prose, so a raw substring check fails on
    a sentence that merely line-wraps differently than expected."""
    return re.sub(r"\s+", " ", text)


def test_t_v1110_ver_01_live_version_is_1_11_0():
    # Repointed at spec-v1.11.1 T6 (REQ-V1111-VER-01), exactly as
    # REQ-V1110-VER-01 repointed `tests/test_v1104_version.py`: the live-tree
    # read becomes a frozen `v1.11.0` tag-blob read, since the live tree now
    # carries T6's own bump. Function name stays (PIN-01: in place, never
    # renamed).
    tagged = subprocess.run(
        ["git", "show", "v1.11.0:pyproject.toml"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert tomllib.loads(tagged)["project"]["version"] == "1.11.0"


def test_t_v1110_ver_02_dependency_diff_version_only():
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


def test_t_v1110_ver_03_agents_md_and_release_row():
    # Repointed at spec-v1.11.1 T6: AGENTS.md's count/date lines are
    # overwritten wholesale each release, so this pin tracks forward again
    # -- the mutation-entries figure (152) is itself unchanged this
    # generation, only the test count and the dating move.
    agents_text = _read_agents_md()
    assert f"{_MEASURED_TEST_COUNT}" in agents_text
    assert "152 entries" in agents_text
    assert "as of spec-v1.11.1 T6" in agents_text
    assert "2384" not in agents_text
    assert "as of spec-v1.11.0 T8" not in agents_text

    readme_text = _read_readme()
    assert "| v1.11.0 | 1.11.0 |" in readme_text

    table_start = readme_text.index("## Versioning")
    table_end = readme_text.index("## Token economy", table_start)
    table = readme_text[table_start:table_end]
    v1104_row_start = table.index("| v1.10.4 | 1.10.4 |")
    v1104_row_end = table.index("|\n", v1104_row_start) + 1
    v1104_row = table[v1104_row_start:v1104_row_end]
    assert "; this release" not in v1104_row


def test_t_v1110_ver_04_readme_deliverables():
    readme_text = _read_readme()

    assert "## Sessions" in readme_text
    assert "## Switch provider" in readme_text
    assert "LMSTUDIO_MODELS" in readme_text
    assert "OPENROUTER_MODELS" in readme_text
    assert "embed (batched, OpenRouter by default)" in readme_text
    # REQ-V1111-TAB-05: one batch constant now, not two -- the name is
    # rewritten in place to assert absence, not presence.
    assert "documents.EMBED_BATCH_SIZE" not in readme_text
    assert "llm.embeddings.BATCH_SIZE" in readme_text
    assert "indexing runs in a worker thread" in readme_text

    # T8's own completion of REQ-V1110-VER-02's `/documents` sample
    # (named for T2, dropped there and disclosed -- see this file's
    # docstring): the real `/documents` table rendering, generated from
    # `test_t_v1110_doc_01_documents_table`'s own two-document fixture.
    stats_idx = readme_text.index("### `/stats`")
    recorded_idx = readme_text.index("### What is recorded", stats_idx)
    documents_section = readme_text[stats_idx:recorded_idx]
    assert "### `/documents`" in documents_section
    assert "Your documents (2 of 20):" in documents_section
    for col in ["#", "file", "type", "size", "chunks", "pages", "added"]:
        assert col in documents_section
    assert "1.5 MB" in documents_section
    assert "12.3 KB" in documents_section

    agents_text = _read_agents_md()
    waiver_normalized = _normalize(agents_text)
    assert ("v1.11.0 changes nothing token-bearing; the rule does not fire.") in waiver_normalized
