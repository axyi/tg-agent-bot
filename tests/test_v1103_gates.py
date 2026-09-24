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
    # v1.11.0 T6 (REQ-V1110-VER-03): repointed again, disclosed amendment
    # (not in T0's pin inventory) -- function name kept stable, matching
    # every other "report_path tracks the current release" site. Repointed
    # again at spec-v1.11.1 T6 (REQ-V1111-VER-01, found by tree-wide
    # extension, not in this task's own brief's starting list): 1.11.0 ->
    # 1.11.1.
    config = checks.load_gate_config()
    lint_docs = config["gates"]["lint-docs"]
    assert lint_docs["report_path"] == "docs/reports/report-v1.11.1.md"
    assert lint_docs["delegation_record"] is True


def test_t_v1103_gate_03_gate_matrix_label_dict_matches_spec_v1103_table():
    # v1.10.4 T1 (EC-02 row 12b, REQ-V1104-PIN-01): rewritten from an
    # equality-shaped loop over every *current* label in the live
    # _GATE_MATRIX_LABEL_TO_NAME dict against the frozen spec-v1.10.3.md
    # table (an NG-10-forbidden "no later row" shape -- true only until a
    # later release added its own label, which the frozen table could
    # never contain) to presence + order of only the v1.10.3-defined
    # labels: the `v1103-` label is present, correctly named, and sits
    # immediately after the `v1102-` label -- both in the live dict and in
    # the frozen spec-v1.10.3.md matrix. Nothing here asserts anything
    # about labels a later release may add. `T-V1104-PIN-08` is the
    # negative proof (a dropped or reordered v1103- label fails; an
    # appended future label still passes). The active-spec exact-matrix
    # test stays in tests/test_v15_standards.py, repointed by v1.10.4 T1's
    # EC-02 row 12 at spec-v1.10.4.md.
    assert "`mutation_check.py --select v1103-`" in _GATE_MATRIX_LABEL_TO_NAME
    assert _GATE_MATRIX_LABEL_TO_NAME["`mutation_check.py --select v1103-`"] == "mutation-v1103"

    labels = list(_GATE_MATRIX_LABEL_TO_NAME)
    v1102_index = labels.index("`mutation_check.py --select v1102-`")
    assert labels[v1102_index + 1] == "`mutation_check.py --select v1103-`"

    spec_text = _SPEC_V1103.read_text(encoding="utf-8")
    matrix = _parse_gate_matrix(spec_text)
    assert "`mutation_check.py --select v1103-`" in matrix, (
        "spec-v1.10.3.md table row not found: '`mutation_check.py --select v1103-`'"
    )
    matrix_labels = list(matrix)
    matrix_v1102_index = matrix_labels.index("`mutation_check.py --select v1102-`")
    assert matrix_labels[matrix_v1102_index + 1] == "`mutation_check.py --select v1103-`"


def test_t_v1103_gate_03_profile_matrix_test_is_green_against_this_release():
    # Proves tests/test_v15_standards.py:1823's own repoint (this task) is
    # actually green, not merely edited -- calling the function directly
    # raises on any mismatch between the spec table and config/quality_gates.yaml.
    test_v15_gate_04_profile_matrix_agrees_with_the_spec_table()
