"""spec-v1.10.2 T3 (docs/spec/spec-v1.10.2.md Sec.9 REQ-V1102-GATE-03,
Sec.10 REQ-V1102-RPT-01 first sentence): `lint-docs.report_path` repointed
to this release's report, and the gate-matrix test in
`tests/test_v15_standards.py` repointed at `docs/spec/spec-v1.10.2.md`'s
own §9 table (which already carries the `mutation_check.py --select
v1102-` row verbatim, per the task brief).

Offline: `devtools.checks.load_gate_config()` reads the committed yaml off
disk, no network, no live LLM.
"""

from __future__ import annotations

from pathlib import Path

from devtools import checks
from tests.test_v15_standards import _GATE_MATRIX_LABEL_TO_NAME, _parse_gate_matrix

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC_V1102 = _REPO_ROOT / "docs" / "spec" / "spec-v1.10.2.md"


def test_t_v1102_rpt_01_lint_docs_repointed_to_this_release():
    config = checks.load_gate_config()
    assert config["gates"]["lint-docs"]["report_path"] == "docs/reports/report-v1.10.2.md"


def test_t_v1102_gate_03_gate_matrix_label_dict_matches_spec_v1102_table():
    # Light duplicate of test_v15_standards.py's own
    # test_v15_gate_04_profile_matrix_agrees_with_the_spec_table (already
    # repointed at spec-v1.10.2.md there) -- this asserts the same
    # precondition directly against the new label, per the task brief.
    assert "`mutation_check.py --select v1102-`" in _GATE_MATRIX_LABEL_TO_NAME
    assert _GATE_MATRIX_LABEL_TO_NAME["`mutation_check.py --select v1102-`"] == "mutation-v1102"

    spec_text = _SPEC_V1102.read_text(encoding="utf-8")
    matrix = _parse_gate_matrix(spec_text)
    for label in _GATE_MATRIX_LABEL_TO_NAME:
        assert label in matrix, f"spec-v1.10.2.md table row not found: {label!r}"
