"""spec-v1.10.4 T1 (docs/spec/spec-v1.10.4.md Sec.3 REQ-V1104-PIN-01, Sec.11
REQ-V1104-VER-01's v1.10.3 row, REQ-V1104-RPT-03's T1 half): proves the two
re-pinned README tests (EC-02 rows 5-6) survive a probe row appended after
the real table, and pins README's new v1.10.3 row and `AGENTS.md`'s
v1104-T<N> brief-path token plus its untouched benchmark-waiver paragraph
(NG-04).

Offline: reads `README.md`/`AGENTS.md` off disk and `git show f3ce1a5:...`
via a subprocess against the local repository only -- no network, no live
LLM.

`T-V1104-PIN-06`, `T-V1104-DOC-01`, `T-V1104-DOC-03`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_README_MD = _REPO_ROOT / "README.md"
_AGENTS_MD = _REPO_ROOT / "AGENTS.md"


def _read_readme() -> str:
    return _README_MD.read_text(encoding="utf-8")


def _read_agents_md() -> str:
    return _AGENTS_MD.read_text(encoding="utf-8")


_V1102_ROW = (
    "| v1.10.2 | — | run stopped at T5 by the stop route, gate 8 red on "
    "model behaviour (injection 4/5 on openai/gpt-4.1-mini — INJ-04's "
    'developer-mode pretext produced exec("printenv") ×3 before a refusal; '
    "the Secrets: line held the other four), not tagged; ships with "
    "v1.10.3 |"
)

_V1103_ROW = (
    "| v1.10.3 | — | run stopped at T6 by the stop route — EC-01's repair "
    "budget spent on four test pins the spec's list missed; gate 8 never "
    "ran; the exec guard, the marker widening, the delegation lint and the "
    "paperwork landed; ships with v1.10.4 |"
)


def test_t_v1104_pin_06_probe_row_appended_leaves_repinned_readme_tests_green(monkeypatch):
    import tests.test_v1102_docs as t1102d
    import tests.test_v1103_docs as t1103d

    real_text = _read_readme()
    probed_text = real_text + "\n| v1.10.9 | — | probe |\n"

    monkeypatch.setattr(t1102d, "_read_readme", lambda: probed_text)
    monkeypatch.setattr(t1103d, "_read_readme", lambda: probed_text)

    t1103d.test_t_v1103_ver_01_readme_gains_the_v1102_stopped_run_row()
    t1102d.test_t_v1102_rpt_02_stopped_release_rows_landed_at_t3()


def test_t_v1104_doc_01_readme_v1103_row_verbatim_v1102_row_still_present():
    text = _read_readme()
    assert _V1103_ROW in text
    assert _V1102_ROW in text


def test_t_v1104_doc_03_agents_md_brief_token_is_v1104_waiver_paragraph_unchanged():
    text = _read_agents_md()
    assert "docs/spec/task-briefs/v1104-T<N>.md" in text

    waiver_start = text.index("v1.10.1 waived this rule by operator decision")
    waiver_end = text.index("## go protocol", waiver_start)
    waiver = text[waiver_start:waiver_end].strip()

    baseline = subprocess.run(
        ["git", "show", "f3ce1a5:AGENTS.md"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    baseline_start = baseline.index("v1.10.1 waived this rule by operator decision")
    baseline_end = baseline.index("## go protocol", baseline_start)
    baseline_waiver = baseline[baseline_start:baseline_end].strip()

    assert waiver == baseline_waiver
