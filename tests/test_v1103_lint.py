"""spec-v1.10.3 T3 (docs/spec/spec-v1.10.3.md Sec.6 REQ-V1103-LINT-01,
Sec.7 rows 3-4 REQ-V1103-ERR-01): `_lint_report_delegation`, a sibling of
`_lint_report_ledger` (`devtools/checks.py:1558-1577`), checks every
non-exempt `## T<n>` report section for a valid five-cell delegation-record
bullet (`- T<n> | delegated: yes|no | to: ... | brief: ... | map vs
actual: ...`), wired behind the boolean `delegation_record` yaml key on
`lint-docs` so an absent key never re-lints an earlier release's report.

Offline: every fixture here is a synthetic report written to `tmp_path`;
nothing reads the live `docs/reports/` tree (that lives in
`tests/test_v1103_gates.py`'s `T-V1103-RPT-01`, which does).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from devtools import checks

_PREFIX = "v1103"


def _report(tmp_path: Path, body: str, *, name: str = "report-v1.10.3.md") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _good_bullet(n: int, *, prefix: str = _PREFIX) -> str:
    return (
        f"- T{n} | delegated: yes | to: general-purpose subagent | "
        f"brief: docs/spec/task-briefs/{prefix}-T{n}.md | map vs actual: matches §13.1"
    )


def _good_no_bullet(n: int) -> str:
    return (
        f"- T{n} | delegated: no | to: — (commands only) | brief: — | map vs actual: matches §13.1"
    )


# ---------------------------------------------------------------------------
# T-V1103-LINT-01: a report with a correct bullet in every non-exempt section
# is green.
# ---------------------------------------------------------------------------


def test_t_v1103_lint_01_green_report_with_valid_bullets_in_every_section(tmp_path: Path):
    body = f"""# report skeleton

## T0 — preflight

{_good_no_bullet(0)}

## T1 — the widget

{_good_bullet(1)}

## T2 — not reached: T2
"""
    report = _report(tmp_path, body)
    assert checks._lint_report_delegation(report) == []


# ---------------------------------------------------------------------------
# T-V1103-LINT-02: a section missing a bullet entirely.
# ---------------------------------------------------------------------------


def test_t_v1103_lint_02_section_missing_a_bullet_entirely(tmp_path: Path):
    body = """## T1 — the widget

- result: green

No delegation-record bullet here.
"""
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1 has no delegation-record bullet" in p for p in problems)


# ---------------------------------------------------------------------------
# T-V1103-LINT-03: cell-count mismatches (4 and 6 cells).
# ---------------------------------------------------------------------------


def test_t_v1103_lint_03_bullet_with_four_cells(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: yes | to: someone | brief: docs/spec/task-briefs/v1103-T1.md\n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: bullet has 4 cells, expected 5" in p for p in problems)


def test_t_v1103_lint_03_bullet_with_six_cells(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: yes | to: someone | brief: docs/spec/task-briefs/v1103-T1.md | "
        "map vs actual: matches §13.1 | extra cell\n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: bullet has 6 cells, expected 5" in p for p in problems)


# ---------------------------------------------------------------------------
# T-V1103-LINT-04: `delegated: no` without / with a §5.1 exemption phrase.
# ---------------------------------------------------------------------------


def test_t_v1103_lint_04_delegated_no_without_exemption_phrase(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: no | to: nobody in particular | brief: — | map vs actual: fine\n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: delegated: no without a §5.1 exemption phrase" in p for p in problems)


@pytest.mark.parametrize(
    "phrase",
    [
        "commands only",
        "artefacts only",
        "a single edit under every threshold",
        "the task is itself the clean-context review",
    ],
)
def test_t_v1103_lint_04_delegated_no_with_exemption_phrase_is_green(tmp_path: Path, phrase: str):
    body = (
        "## T1 — the widget\n\n"
        f"- T1 | delegated: no | to: — ({phrase}) | brief: — | map vs actual: fine\n"
    )
    report = _report(tmp_path, body)
    assert checks._lint_report_delegation(report) == []


# ---------------------------------------------------------------------------
# T-V1103-LINT-05: a bullet naming the wrong task number in cell 1.
# ---------------------------------------------------------------------------


def test_t_v1103_lint_05_bullet_names_the_wrong_task(tmp_path: Path):
    body = f"## T1 — the widget\n\n{_good_bullet(2)}\n"
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: bullet names T2" in p for p in problems)


# ---------------------------------------------------------------------------
# T-V1103-LINT-06: EXTRA_KEYS_BY_GATE["lint-docs"] gains delegation_record,
# exact set membership (not merely doctor's rejection).
# ---------------------------------------------------------------------------


def test_t_v1103_lint_06_extra_keys_by_gate_exact_set():
    assert checks.EXTRA_KEYS_BY_GATE["lint-docs"] == {
        "prompt_glob",
        "exempt_files",
        "report_path",
        "ledger_header",
        "delegation_record",
    }


def test_t_v1103_lint_06_delegation_record_must_be_a_bool(tmp_path: Path):
    gate = {
        "kind": "builtin",
        "handler": "lint_docs",
        "prompt_glob": "docs/prompts/*.md",
        "exempt_files": [],
        "report_path": "docs/reports/report-v1.10.3.md",
        "ledger_header": "| a |",
        "delegation_record": "yes",
        "blocking": True,
        "diff_scoped": False,
        "timeout_seconds": 15,
    }
    with pytest.raises(
        checks.GateConfigError,
        match=r"gates\.lint-docs\.delegation_record must be a boolean",
    ):
        checks._validate_one_gate("lint-docs", gate)


def test_t_v1103_lint_06_delegation_record_true_is_accepted():
    gate = {
        "kind": "builtin",
        "handler": "lint_docs",
        "prompt_glob": "docs/prompts/*.md",
        "exempt_files": [],
        "report_path": "docs/reports/report-v1.10.3.md",
        "ledger_header": "| a |",
        "delegation_record": True,
        "blocking": True,
        "diff_scoped": False,
        "timeout_seconds": 15,
    }
    checks._validate_one_gate("lint-docs", gate)  # must not raise


# ---------------------------------------------------------------------------
# T-V1103-LINT-07: `delegated: yes` cell-4 shapes -- em dash (invalid), a
# correct brief path (valid), a brief naming the wrong task (invalid).
# ---------------------------------------------------------------------------


def test_t_v1103_lint_07_delegated_yes_with_em_dash_brief_is_invalid(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: yes | to: someone | brief: — | map vs actual: fine\n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: delegated: yes without a brief path" in p for p in problems)


def test_t_v1103_lint_07_delegated_yes_with_correct_brief_path_is_green(tmp_path: Path):
    body = f"## T1 — the widget\n\n{_good_bullet(1)}\n"
    report = _report(tmp_path, body)
    assert checks._lint_report_delegation(report) == []


def test_t_v1103_lint_07_delegated_yes_brief_names_the_wrong_task(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: yes | to: someone | brief: docs/spec/task-briefs/v1103-T2.md | "
        "map vs actual: fine\n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: brief names T2" in p for p in problems)


def test_t_v1103_lint_07_delegated_no_with_a_brief_path_is_invalid(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: no | to: — (commands only) | "
        "brief: docs/spec/task-briefs/v1103-T1.md | map vs actual: fine\n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: delegated: no with a brief path" in p for p in problems)


def test_t_v1103_lint_07_cell_4_neither_em_dash_nor_brief_path(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: yes | to: someone | brief: garbage | map vs actual: fine\n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: cell 4 is neither brief: — nor a v1103 task-brief path" in p for p in problems)


# ---------------------------------------------------------------------------
# T-V1103-LINT-08: empty cell 3 / cell 5; zero task sections; an unparseable
# report_path basename; an exempt section needing no bullet; a section with
# two candidates, both valid; candidates ignored outside any task section.
# ---------------------------------------------------------------------------


def test_t_v1103_lint_08_empty_cell_3(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: yes | to:  | brief: docs/spec/task-briefs/v1103-T1.md | "
        "map vs actual: fine\n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: cell 3 is empty" in p for p in problems)


def test_t_v1103_lint_08_empty_cell_5(tmp_path: Path):
    body = (
        "## T1 — the widget\n\n"
        "- T1 | delegated: yes | to: someone | brief: docs/spec/task-briefs/v1103-T1.md | "
        "map vs actual: \n"
    )
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert any("T1: cell 5 is empty" in p for p in problems)


def test_t_v1103_lint_08_zero_task_sections(tmp_path: Path):
    body = "# just a report\n\nNo ## T sections at all.\n"
    report = _report(tmp_path, body)
    problems = checks._lint_report_delegation(report)
    assert problems == ["report-v1.10.3.md: no ## T<n> section found"]


def test_t_v1103_lint_08_unparseable_report_path_basename(tmp_path: Path):
    body = f"## T1 — the widget\n\n{_good_bullet(1, prefix='vfinal')}\n"
    report = _report(tmp_path, body, name="report-final.md")
    problems = checks._lint_report_delegation(report)
    assert problems == ["report-final.md: cannot derive a brief prefix from report-final.md"]


def test_t_v1103_lint_08_exempt_section_needs_no_bullet(tmp_path: Path):
    body = "## T4 — not reached: T4\n\nNothing here, and that's fine.\n"
    report = _report(tmp_path, body)
    assert checks._lint_report_delegation(report) == []


def test_t_v1103_lint_08_two_candidates_both_valid(tmp_path: Path):
    body = (
        "## T6 — two parts\n\n"
        f"{_good_bullet(6)}\n"
        "- T6 | delegated: yes | to: another subagent | brief: docs/spec/task-briefs/v1103-T6.md | "
        "map vs actual: the second part\n"
    )
    report = _report(tmp_path, body)
    assert checks._lint_report_delegation(report) == []


def test_t_v1103_lint_08_candidate_before_first_heading_is_ignored(tmp_path: Path):
    body = f"{_good_bullet(9)}\n\n## T1 — the widget\n\n{_good_bullet(1)}\n"
    report = _report(tmp_path, body)
    assert checks._lint_report_delegation(report) == []


def test_t_v1103_lint_08_candidate_under_non_task_section_is_ignored(tmp_path: Path):
    body = f"## T1 — the widget\n\n{_good_bullet(1)}\n\n## Operator inputs\n\n{_good_bullet(9)}\n"
    report = _report(tmp_path, body)
    assert checks._lint_report_delegation(report) == []


def test_t_v1103_lint_08_missing_report_file(tmp_path: Path):
    report = tmp_path / "report-v1.10.3.md"
    problems = checks._lint_report_delegation(report)
    assert problems == ["report-v1.10.3.md: report file does not exist"]


# ---------------------------------------------------------------------------
# The `_run_lint_docs` call site: `is True`, not truthy -- absent/False keys
# never run the delegation check.
# ---------------------------------------------------------------------------


_LEDGER_OK_BODY = (
    "# no task sections, would be red if the delegation check ran\n\n"
    "## Ledger row (paste into `economics.md`)\n\n```\n| a |\n```\n"
)


def test_t_v1103_lint_09_absent_key_never_runs_the_check(tmp_path: Path):
    report = _report(tmp_path, _LEDGER_OK_BODY)
    gate = {
        "handler": "lint_docs",
        "prompt_glob": "no/such/*.md",
        "exempt_files": [],
        "report_path": report.name,
        "ledger_header": "| a |",
        "blocking": True,
    }
    result = checks._run_lint_docs("lint-docs", gate, tmp_path)
    assert not result.blocked
    assert result.message == "all prompts and the report ledger row pass"


def test_t_v1103_lint_09_false_key_never_runs_the_check(tmp_path: Path):
    report = _report(tmp_path, _LEDGER_OK_BODY)
    gate = {
        "handler": "lint_docs",
        "prompt_glob": "no/such/*.md",
        "exempt_files": [],
        "report_path": report.name,
        "ledger_header": "| a |",
        "delegation_record": False,
        "blocking": True,
    }
    result = checks._run_lint_docs("lint-docs", gate, tmp_path)
    assert not result.blocked


def test_t_v1103_lint_09_true_key_runs_the_check_and_blocks(tmp_path: Path):
    report = _report(tmp_path, _LEDGER_OK_BODY)
    gate = {
        "handler": "lint_docs",
        "prompt_glob": "no/such/*.md",
        "exempt_files": [],
        "report_path": report.name,
        "ledger_header": "| a |",
        "delegation_record": True,
        "blocking": True,
    }
    result = checks._run_lint_docs("lint-docs", gate, tmp_path)
    assert result.blocked
    assert "no ## T<n> section found" in result.message
