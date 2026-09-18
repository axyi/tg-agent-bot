"""spec-v1.10.3 T3 (docs/spec/spec-v1.10.3.md Sec.6 REQ-V1103-LINT-01,
Sec.10 REQ-V1103-RPT-01): `T-V1103-RPT-01` -- the shipped
`docs/reports/report-v1.10.3.md` is green under `_lint_report_delegation`
once T3 lands, and `docs/reports/report-v1.10.2.md` (whose task sections
carry prose, not the five-cell bullet grammar, and whose gate config is
never repointed at it) is red under the function when called directly.

Offline: both reads are of the committed tree, no network, no live LLM.
"""

from __future__ import annotations

from pathlib import Path

from devtools import checks

_REPO_ROOT = Path(__file__).resolve().parents[1]


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
