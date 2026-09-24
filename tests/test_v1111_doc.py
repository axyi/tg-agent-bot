"""spec-v1.11.1 T4 (REQ-V1111-DOC-01, REQ-V1111-DOC-02, REQ-V1111-DOC-03):
README/`docs/plan.md`/`AGENTS.md` drift corrected in T4's second commit, and
the v1.11.0 report/post correction (DOC-03) -- already landed as T4's first
commit, `9d8dc0e` -- confirmed green here. See
`docs/spec/task-briefs/v1111-T4.md` and `docs/spec/spec-v1.11.1.md:479-538`.

`T-V1111-DOC-01`/`T-V1111-DOC-02` are red before this task's README/
`docs/plan.md`/`AGENTS.md` edits; `T-V1111-DOC-03` is green on first
execution by T4's own ordering (the artefacts-only report commit lands
before this test's commit, EC-02's stated carve-out timing,
`spec-v1.11.1.md:73-74`).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import bot
from devtools import checks

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _norm(text: str) -> str:
    """Collapse whitespace runs (including newlines) so a prose sentence's
    exact hard-wrap in the file never matters to a substring check."""
    return " ".join(text.split())


def test_t_v1111_doc_01_readme_limits_error_rows_versioning():
    text = (_REPO_ROOT / "README.md").read_text(encoding="utf-8")
    norm = _norm(text)

    # (a) ## Limits: the /model catalogue-cap row lands after the "rerank
    # candidates" row, and the table gains a decimal/binary sizing note.
    limits = text.split("## Limits", 1)[1].split("## Error behaviour", 1)[0]
    rerank_idx = limits.index("rerank candidates")
    cap_idx = limits.index("`/model` catalogue cap")
    assert cap_idx > rerank_idx
    assert (
        "20 entries per provider (`MODEL_CATALOGUE_MAX`; the rest dropped "
        "at startup with a warning)"
    ) in limits
    assert (
        "Sizes shown by `/documents` are decimal (1 MB = 1,000,000 bytes); "
        "the exec and sandbox limits above are binary (MiB)."
    ) in norm

    # (b) ## Error behaviour: the /documents empty row (new), the /sessions
    # empty row (T2's own TAB-03 row, not duplicated here), and the
    # Telegram-400 row (OUT-01).
    errors = text.split("## Error behaviour", 1)[1].split("## Versioning", 1)[0]
    assert errors.count(bot.DOCUMENTS_EMPTY_REPLY) == 1
    assert "`/documents` with no documents uploaded" in errors
    assert errors.count(bot.SESSIONS_EMPTY_REPLY) == 1
    assert "Telegram 400 on a table-path send (`send_pre`/`edit_pre`)" in errors
    assert (
        "one plain resend of the same fitted body, no `parse_mode`; any "
        "other failure (429 after the retry budget, 5xx, transport) is "
        "logged and never resent"
    ) in errors
    assert "Telegram 429 on send" in errors  # unchanged, spec :493

    # (c) ## Versioning: the rewritten sentence lands, the old one is gone.
    versioning = _norm(text.split("## Versioning", 1)[1])
    assert (
        "so a release's tag — `v1.6.0` included — was created only after "
        "that release's own final commit had landed."
    ) in versioning
    assert "does not exist until this release's own final commit" not in versioning


def test_t_v1111_doc_02_plan_banner_and_agents_ruling():
    plan_lines = (
        (_REPO_ROOT / "docs" / "plan.md").read_text(encoding="utf-8").splitlines(keepends=True)
    )
    banner = [
        "> **Superseded.** Since v1.7.0 the roadmap lives in `docs/spec/spec-vN.md`\n",
        "> (the contract) and `docs/handoff-vN.md` (the `go`-session handoff written\n",
        "> by the lab for each release — what the run session reads first). This\n",
        "> file is kept as history: its last release section is `## v1.6.0 (in\n",
        "> progress)` and its status table stops at `spec-v1.7.0.md` marked in\n",
        "> progress; every release since is specified in `docs/spec/spec-vN.md` and\n",
        "> handed off in `docs/handoff-vN.md`.\n",
    ]
    assert plan_lines[:7] == banner
    assert plan_lines[7] == "\n"
    remainder = "".join(plan_lines[8:])
    tagged = subprocess.run(
        ["git", "show", "v1.11.0:docs/plan.md"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert remainder == tagged

    agents = (_REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    secrets = agents.split("## Secrets", 1)[1]
    assert "operator input, not secrets" in secrets
    assert "treats them as out of scope" in secrets


def test_t_v1111_doc_03_v1110_report_and_post_corrected():
    report_path = _REPO_ROOT / "docs" / "reports" / "report-v1.11.0.md"
    report = report_path.read_text(encoding="utf-8")

    assert "| 19 (236-254) |" in report
    assert "| 17 (236-252) |" not in report

    t2_section = report.split("## T2", 1)[1].split("## T3", 1)[0]
    for sha in ("743abc2", "ef8e453", "09f8d8a"):
        assert sha in t2_section

    phase_a_bullets = [
        line
        for line in report.splitlines()
        if line.startswith(
            "- T7 | delegated: yes | to: general-purpose subagent (claude-sonnet-5), Phase A only"
        )
    ]
    assert len(phase_a_bullets) == 1
    assert "33729eb" in phase_a_bullets[0]
    assert "bundles" in phase_a_bullets[0]

    waiver = report.split("🟡 **Finding 2", 1)[1].split("🟡 **Finding 3", 1)[0]
    assert "bot.py:2047" in waiver
    assert ":2229" in waiver
    assert "2222" not in report

    assert checks._lint_report_delegation(report_path) == []

    post_path = _REPO_ROOT / "docs" / "reports" / "tg-post-v1.11.0.md"
    post = post_path.read_text(encoding="utf-8")
    assert "236–254" in post
    assert "236–252" not in post
    assert len(post) <= 1500
