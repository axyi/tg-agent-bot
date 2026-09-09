"""spec-v1.8.0 T1 (REQ-V180-AGT-01, -02): `AGENTS.md` gains a `## Context
discipline` section, and `## Branch strategy` gains the ownership-zone rule.

Offline and deterministic: no network, no Docker, no `.env`, no live LLM --
this module only reads the repository's own `AGENTS.md` off disk.
"""

from __future__ import annotations

import re
from pathlib import Path

_AGENTS_MD = Path(__file__).resolve().parents[1] / "AGENTS.md"

# The four exemptions, verbatim in the words REQ-V180-AGT-01 item 3 gives.
_EXEMPTIONS = [
    "commands only",
    "artefacts only",
    "a single edit under every threshold",
    "the task is itself the clean-context review",
]

# The write trigger, verbatim from spec-v1.8.0 section 3 (REQ-V180-AGT-01
# item 1).
_WRITE_TRIGGER = "a task that writes source files — code a gate compiles, imports or runs"


def _normalize(text: str) -> str:
    """Collapse whitespace runs (AGENTS.md wraps prose at ~78 chars) and
    strip Markdown emphasis markers, so a substring check does not fail
    merely because the real text line-wraps or bolds part of the phrase."""
    text = text.replace("*", "")
    return re.sub(r"\s+", " ", text)


def _read_agents_md() -> str:
    return _AGENTS_MD.read_text(encoding="utf-8")


def test_t_v180_agt_01_context_discipline_heading_present():
    text = _read_agents_md()
    assert "## Context discipline" in text


def test_t_v180_agt_01_context_discipline_placed_after_project_layout_before_commit_format():
    text = _read_agents_md()
    layout_idx = text.index("## Project layout")
    discipline_idx = text.index("## Context discipline")
    commit_idx = text.index("## Commit format")
    assert layout_idx < discipline_idx < commit_idx


def test_t_v180_agt_01_write_trigger_present():
    text = _normalize(_read_agents_md())
    assert _normalize(_WRITE_TRIGGER) in text


def test_t_v180_agt_01_write_trigger_scoped_to_go_runs_per_task():
    section = _context_discipline_section(_read_agents_md())
    normalized = _normalize(section)
    assert _normalize("inside a `go` run, per task") in normalized


def test_t_v180_agt_01_four_exemptions_verbatim():
    section = _context_discipline_section(_read_agents_md())
    normalized = _normalize(section)
    for exemption in _EXEMPTIONS:
        assert exemption in normalized, f"missing verbatim exemption: {exemption!r}"


def test_t_v180_agt_01_main_context_holds_what_this_needs_is_not_an_exemption():
    section = _context_discipline_section(_read_agents_md())
    normalized = _normalize(section).lower()
    assert "the main context already holds what this needs" in normalized
    assert "not" in normalized


def test_t_v180_agt_01_sync_comment_names_workflow_5_1():
    section = _context_discipline_section(_read_agents_md())
    assert "<!-- SYNC:" in section
    assert "standards/workflow.md §5.1" in section


def test_t_v180_agt_01_brief_by_file_never_by_retyping():
    section = _context_discipline_section(_read_agents_md())
    normalized = _normalize(section)
    assert "task-brief file" in normalized
    assert "docs/spec/task-briefs/" in normalized
    assert "never" in normalized.lower()


def test_t_v180_agt_01_main_context_reading_rules_present():
    section = _context_discipline_section(_read_agents_md())
    normalized = _normalize(section)
    assert "offset/limit" in normalized
    assert "whole-file read" in normalized
    assert "directory walk" in normalized
    assert "Absolute paths" in normalized


def test_t_v180_agt_02_ownership_zone_rule_present():
    text = _read_agents_md()
    branch_idx = text.index("## Branch strategy")
    gates_idx = text.index("## Gates")
    branch_section = text[branch_idx:gates_idx]
    normalized = _normalize(branch_section)
    assert "edit scope" in normalized
    assert "not agent count" in normalized
    assert "ownership zone" in normalized
    assert "disjoint zones run in parallel, one worktree each" in normalized
    assert "overlapping scopes run sequentially" in normalized


def test_t_v180_agt_02_existing_branch_strategy_bullets_untouched():
    text = _read_agents_md()
    branch_idx = text.index("## Branch strategy")
    gates_idx = text.index("## Gates")
    branch_section = text[branch_idx:gates_idx]
    # The four original bullets (spec-v1.5) must still be present verbatim --
    # REQ-V180-AGT-02 appends, it never deletes or rewords.
    assert "One task → one branch" in branch_section
    assert "a single-agent run implementing a whole spec end-to-end" in branch_section
    assert "one git worktree per agent" in branch_section
    assert "the `pre-commit`/`pre-push` branch-name" in branch_section


def _context_discipline_section(text: str) -> str:
    start = text.index("## Context discipline")
    end = text.index("## Commit format")
    return text[start:end]
