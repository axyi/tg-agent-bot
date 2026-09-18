"""spec-v1.10.3 T3 (docs/spec/spec-v1.10.3.md Sec.6 REQ-V1103-LINT-01,
Sec.10 REQ-V1103-RPT-01): `T-V1103-RPT-01` -- the shipped
`docs/reports/report-v1.10.3.md` is green under `_lint_report_delegation`
once T3 lands, and `docs/reports/report-v1.10.2.md` (whose task sections
carry prose, not the five-cell bullet grammar, and whose gate config is
never repointed at it) is red under the function when called directly.

T4 (docs/spec/task-briefs/v1103-T4.md, REQ-V1103-GATE-03) adds
`T-V1103-GATE-03`: the new `mutation-v1103` gate-matrix label is
registered, and `tests/test_v15_standards.py`'s own
`test_v15_gate_04_profile_matrix_agrees_with_the_spec_table` (already
repointed at `spec-v1.10.3.md` there) is green -- mirroring
`tests/test_v1102_gates.py`'s own `T-V1102-GATE-03` shape.

Offline: both reads are of the committed tree, no network, no live LLM.
"""

from __future__ import annotations

from pathlib import Path

from devtools import checks
from tests.test_v15_standards import (
    _GATE_MATRIX_LABEL_TO_NAME,
    _parse_gate_matrix,
    test_v15_gate_04_profile_matrix_agrees_with_the_spec_table,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SPEC_V1103 = _REPO_ROOT / "docs" / "spec" / "spec-v1.10.3.md"


def test_t_v1103_rpt_01_current_report_is_green_under_the_new_lint():
    report = _REPO_ROOT / "docs" / "reports" / "report-v1.10.3.md"
    assert checks._lint_report_delegation(report) == []


def test_t_v1103_rpt_01_v1102_report_is_red_under_the_function_directly():
    # Not via the gate -- report-v1.10.2.md's gate config is never repointed
    # at this checker; this proves the function itself would reject that
    # report's prose-style delegation records if it ever were: every one of
    # its non-exempt task sections (T1-T5) has zero `^- T\d+ | ` candidates,
    # so the grammar rejects it with "has no delegation-record bullet" for
    # each one, not merely some incidental, unrelated problem.
    report = _REPO_ROOT / "docs" / "reports" / "report-v1.10.2.md"
    problems = checks._lint_report_delegation(report)
    assert problems != []
    assert "report-v1.10.2.md: T1 has no delegation-record bullet" in problems
    assert "report-v1.10.2.md: T2 has no delegation-record bullet" in problems
    assert "report-v1.10.2.md: T3 has no delegation-record bullet" in problems
    assert "report-v1.10.2.md: T4 has no delegation-record bullet" in problems
    assert "report-v1.10.2.md: T5 has no delegation-record bullet" in problems


def test_t_v1103_rpt_01_quality_gates_yaml_repoints_and_enables_the_key():
    config = checks.load_gate_config()
    lint_docs = config["gates"]["lint-docs"]
    assert lint_docs["report_path"] == "docs/reports/report-v1.10.3.md"
    assert lint_docs["delegation_record"] is True


def test_t_v1103_gate_03_gate_matrix_label_dict_matches_spec_v1103_table():
    # Light duplicate of test_v15_standards.py's own
    # test_v15_gate_04_profile_matrix_agrees_with_the_spec_table (already
    # repointed at spec-v1.10.3.md there) -- this asserts the same
    # precondition directly against the new label, per the task brief.
    assert "`mutation_check.py --select v1103-`" in _GATE_MATRIX_LABEL_TO_NAME
    assert _GATE_MATRIX_LABEL_TO_NAME["`mutation_check.py --select v1103-`"] == "mutation-v1103"

    # The new label sits immediately after the v1102- entry and before the
    # "(all)" entry, per the task brief's exact insertion point.
    labels = list(_GATE_MATRIX_LABEL_TO_NAME)
    v1102_index = labels.index("`mutation_check.py --select v1102-`")
    all_index = labels.index("`mutation_check.py` (all)")
    assert labels[v1102_index + 1] == "`mutation_check.py --select v1103-`"
    assert labels.index("`mutation_check.py --select v1103-`") == all_index - 1

    spec_text = _SPEC_V1103.read_text(encoding="utf-8")
    matrix = _parse_gate_matrix(spec_text)
    for label in _GATE_MATRIX_LABEL_TO_NAME:
        assert label in matrix, f"spec-v1.10.3.md table row not found: {label!r}"


def test_t_v1103_gate_03_profile_matrix_test_is_green_against_this_release():
    # Proves tests/test_v15_standards.py:1823's own repoint (this task) is
    # actually green, not merely edited -- calling the function directly
    # raises on any mismatch between the spec table and config/quality_gates.yaml.
    test_v15_gate_04_profile_matrix_agrees_with_the_spec_table()
