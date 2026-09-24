"""spec-v1.9.0 T10 (REQ-V190-RPT-01, RPT-05, EC-13; test id T-V190-EC-01):
`AGENTS.md` names the five RAG dependencies, the seven-gate block and the
`v190-T<N>.md` brief path; `README.md` gains `## Documents (RAG)` with its
seven mandatory subsections in order.

Offline and deterministic: no network, no Docker, no `.env`, no live LLM --
this module only reads the repository's own `AGENTS.md`/`README.md` off
disk, the same pattern `tests/test_v180_agents.py` uses. It asserts no test
count or mutation count anywhere -- those are `AGENTS.md:146`/`:155`,
explicitly T12's job (RPT-05), never T10's or this file's.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENTS_MD = _REPO_ROOT / "AGENTS.md"
_README_MD = _REPO_ROOT / "README.md"

# The five RAG-over-documents distributions (docs/reports/report-v1.9.0.md's
# T0 preflight record; pyproject.toml pins the exact versions).
_RAG_DEPENDENCIES = [
    "sqlite-vec",
    "pypdf",
    "python-docx",
    "rank-bm25",
    "snowballstemmer",
]

# README's mandatory subsection order for ## Documents (RAG) (REQ-V190-RPT-05).
_DOCUMENTS_RAG_SUBSECTIONS = [
    "### Architecture",
    "### Chunking",
    "### Embeddings",
    "### Retrieval",
    "### Storage",
    "### Security",
    "### Limitations",
]


def _read_agents_md() -> str:
    return _AGENTS_MD.read_text(encoding="utf-8")


def _read_readme() -> str:
    return _README_MD.read_text(encoding="utf-8")


def _normalize(text: str) -> str:
    """Collapse whitespace runs (both docs wrap prose at ~78 chars) so a
    substring check does not fail merely because the real text line-wraps."""
    return re.sub(r"\s+", " ", text)


def test_t_v190_ec_01_agents_md_names_the_five_rag_dependencies():
    text = _read_agents_md()
    for dep in _RAG_DEPENDENCIES:
        assert f"`{dep}`" in text, f"missing RAG dependency: {dep!r}"


def test_t_v190_ec_01_agents_md_sqlite_vec_named_as_the_vector_store():
    text = _normalize(_read_agents_md())
    assert "`sqlite-vec` (the vector store)" in text


# v1.10.2 T3 amendment (an EC-02-shaped gap found beyond the task brief's
# own named one, docs/spec/task-briefs/v1102-T3.md sec.3): this test's
# literal and its own name went stale the moment AGENTS.md's count sentence
# became "All eight MUST exit 0" (gate 8, `agent_eval.py`, was already in
# the command list) -- bumped here only so this assertion stays live and
# pytest stays green, the same precedent as test_t_v1100_ec_01_quality_
# gates_yaml_repoints_report_path's own disclosed bump below.
def test_t_v1102_ec_01_agents_md_eight_gate_block_present():
    text = _read_agents_md()
    assert "All eight MUST exit 0" in text
    for gate_cmd in [
        "uv sync --locked",
        "uv run --locked ruff check .",
        "uv run --locked pytest",
        "uv run --locked python bot.py --selftest",
        "uv run --locked python bot.py --selftest-live",
        "uv run --locked python devtools/mutation_check.py",
        "uv run --locked python devtools/rag_eval.py",
        "uv run --locked python devtools/agent_eval.py",
    ]:
        assert gate_cmd in text, f"missing gate command: {gate_cmd!r}"


def test_t_v1104_rpt_03_agents_md_brief_path_token_is_v1104():
    # Disclosed amendment (EC-02, spec-v1.11.0 T8, a site not in the T8
    # brief's starting list): repointed from v1104 to v1110, mirroring
    # AGENTS.md:95's own T8 repoint (REQ-V1110-VER-01). Function name stays
    # as-is (PIN-01: rewritten in place, never renamed).
    text = _read_agents_md()
    assert "docs/spec/task-briefs/v1110-T<N>.md" in text
    assert "docs/spec/task-briefs/v1104-T<N>.md" not in text


def test_t_v190_ec_01_agents_md_brief_path_sentence_unchanged_besides_token():
    # tests/test_v180_agents.py:84-89 pins these exact substrings; T10 must
    # not disturb them while repointing the token on the same line.
    section = _context_discipline_section(_read_agents_md())
    normalized = _normalize(section)
    assert "task-brief file" in normalized
    assert "docs/spec/task-briefs/" in normalized
    assert "never" in normalized.lower()


def test_t_v190_ec_01_agents_md_six_env_vars_named():
    text = _read_agents_md()
    for var in [
        "EMBEDDING_BASE_URL",
        "EMBEDDING_MODEL",
        "EMBEDDING_DIM",
        "EMBEDDING_TIMEOUT_S",
        "RAG_TOP_K",
        "RAG_RERANK",
    ]:
        assert f"`{var}`" in text, f"missing env var: {var!r}"


def test_t_v190_ec_01_agents_md_layout_bullets_present():
    text = _read_agents_md()
    for entry in [
        "`rag.py`",
        "`documents.py`",
        "`llm/embeddings.py`",
        "`devtools/rag_eval.py`",
        "`pdf_fixture.py`",
        "`evals/rag/`",
    ]:
        assert entry in text, f"missing layout bullet: {entry!r}"


def test_t_v1104_rpt_03_agents_md_count_lines_landed_at_t5():
    # RPT-03 (T-V1104-DOC-04): AGENTS.md's gate-3 test count and gate-6
    # mutation count lines were written for v1.9.0 at T12 (1560 tests, 105
    # entries), then for v1.9.1 at T2 (1593 tests, 108 entries), then for
    # v1.9.2 at T3 (1601 tests, 110 entries), then for v1.9.3 at T4 (1610
    # tests, 114 entries), then for v1.9.4 at T5 (1634 tests, 119 entries),
    # then for v1.9.5 at T2 (1638 tests, 120 entries) -- this test's own
    # v1.9.5-era predecessor (test_t_v195_rpt_05_agents_md_count_lines_
    # landed_at_t2) pinned those figures and named T2 as their landing
    # point. v1.10.0-v1.10.3 were stopped runs that never bumped
    # pyproject.toml or landed this paperwork (Stage B'/Stage B, no T5
    # equivalent reached). spec-v1.10.4 T5 landed 2311 tests and 144
    # mutation entries, dated "as of spec-v1.10.4 T5". spec-v1.11.0 T8
    # (this task, REQ-V1110-VER-01) lands the real, final post-run
    # figures: 2384 tests (measured via `pytest --collect-only -q
    # -o addopts="" | grep -c '::'` on the tree after every other T8 edit,
    # including this task's own new tests/test_v1110_ver.py and
    # tests/test_v1110_inventory.py) and 152 mutation entries, dated "as of
    # spec-v1.11.0 T8".
    text = _read_agents_md()
    assert "2384" in text
    assert "152 entries" in text
    assert "as of spec-v1.11.0 T8" in text
    assert "2311 tests as of spec-v1.10.4 T5" not in text
    assert "144 entries as of spec-v1.10.4 T5" not in text


def test_t_v190_ec_01_readme_documents_rag_heading_present():
    text = _read_readme()
    assert "## Documents (RAG)" in text


def test_t_v190_ec_01_readme_documents_rag_placed_between_fetch_tool_and_add_a_skill():
    text = _read_readme()
    fetch_idx = text.index("## The fetch tool")
    rag_idx = text.index("## Documents (RAG)")
    skill_idx = text.index("## Add a skill")
    assert fetch_idx < rag_idx < skill_idx


def test_t_v190_ec_01_readme_documents_rag_subsections_in_order():
    section = _documents_rag_section(_read_readme())
    positions = [section.index(heading) for heading in _DOCUMENTS_RAG_SUBSECTIONS]
    assert positions == sorted(positions), (
        "Documents (RAG) subsections out of order: "
        f"{list(zip(_DOCUMENTS_RAG_SUBSECTIONS, positions, strict=True))}"
    )


def test_t_v190_ec_01_readme_documents_rag_chunking_numbers():
    section = _documents_rag_section(_read_readme())
    for number in ["1000", "1200", "200", "50"]:
        assert number in section


def test_t_v190_ec_01_readme_documents_rag_embedding_pair_and_batch():
    section = _documents_rag_section(_read_readme())
    assert "text-embedding-nomic-embed-text-v1.5" in section
    assert "768" in section
    assert "32" in section
    assert "rag.embedding" in section


def test_t_v190_ec_01_readme_documents_rag_retrieval_funnel():
    section = _documents_rag_section(_read_readme())
    assert "k=60" in section
    for count in ["20", "10", "5"]:
        assert count in section


def test_t_v191_readme_gate_7_recorded_green():
    # v1.9.1 T1 fixed the rerank contract (response_format + LLM_RERANK_MODEL)
    # that made gate 7 structurally unable to finish under v1.9.0; this
    # supersedes test_t_v190_ec_01_readme_gate_7_recorded_red's "currently
    # red" claim, which is now false and must not survive in either spot --
    # the eval-numbers subsection and the ## Tests gate block itself.
    rag_section = _normalize(_documents_rag_section(_read_readme())).lower()
    assert "gate 7 (`devtools/rag_eval.py`) passes" in rag_section
    assert "currently red" not in rag_section

    text = _read_readme()
    tests_section = _normalize(text[text.index("## Tests") :]).lower()
    assert "gate 7 passes as of v1.9.1" in tests_section
    assert "currently red" not in tests_section


def test_t_v190_ec_01_readme_eval_numbers_table_present():
    section = _documents_rag_section(_read_readme())
    assert "devtools/rag_eval.py" in section
    assert "recall@5" in section
    assert "1.000" in section
    assert "0.950" in section


def test_t_v190_ec_01_readme_commands_table_gains_documents_and_delete():
    text = _read_readme()
    commands_idx = text.index("## Commands")
    observability_idx = text.index("## Observability")
    section = text[commands_idx:observability_idx]
    assert "/documents" in section
    assert "/delete" in section
    assert "/reload_skills" in section
    # /reload_skills must still precede the two new rows (appended after it).
    assert section.index("/reload_skills") < section.index("/documents")
    # v1.11.0 T6 (REQ-V1110-EXT-01/-03): every `COMMANDS` name has a README
    # row -- import here, not at module level, so this file never needs
    # `bot` as a hard dependency for its other, bot.py-agnostic tests.
    import bot as bot_module

    for name, _desc in bot_module.COMMANDS:
        assert f"/{name}" in section, f"README Commands table missing a row for /{name}"


def test_t_v190_ec_01_readme_limits_table_gains_rag_rows():
    """v1.11.0 T5 (REQ-V1110-ING-01/DOC-03) rewrote the four needles the
    caps rise touches: 20,000,000 bytes / 2,000,000 chars / 1800 s / 2,000
    pages, replacing the prior (v1.10.4 and earlier) byte/character/budget/
    page-count ceilings -- spelled out as prose here, not as the retired
    literal values themselves, so this docstring doesn't trip v1.11.0 T6's
    own `tests/test_v1110_pin.py::test_t_v1110_pin_01_no_retired_literal_in_tests`."""
    text = _read_readme()
    limits_idx = text.index("## Limits")
    error_idx = text.index("## Error behaviour")
    section = text[limits_idx:error_idx]
    for needle in [
        "20,000,000",
        "2,000,000",
        "20 (`DOCUMENT_LIMIT`)",
        "1800 s",
        "2,000 members",
        "2,000 pages",
        "1000 chars, hard max 1200, overlap 200, minimum 50",
        "5 (`RAG_TOP_K`",
        "10 (RRF cut",
        "12,000 chars",
    ]:
        assert needle in section, f"missing Limits row content: {needle!r}"


def test_t_v190_ec_01_readme_error_behaviour_table_gains_document_rows():
    """v1.11.0 T5 (REQ-V1110-ING-01/DOC-03/ERR-01) rewrote the size/budget
    strings for the raised caps and added rows 10 and 17 (`T-V1110-ERR-01`,
    `T-V1110-PIN-01`)."""
    text = _read_readme()
    error_idx = text.index("## Error behaviour")
    versioning_idx = text.index("## Versioning")
    section = text[error_idx:versioning_idx]
    for exact_string in [
        "Unsupported file type. Supported: .txt .md .docx .pdf",
        "Could not read this PDF file.",
        "Could not read this DOCX file.",
        "The document contains no readable text.",
        "File too large (over 20 MB).",
        "Document too large (over 2,000,000 characters).",
        "Document too large (DOCX archive bounds).",
        "Document too large (over 2,000 pages).",
        "Embedding service error. Please try again later.",
        "Storage error. The document was not saved.",
        "Download timed out. Please try again.",
        "Embedding service timed out. Please try again later.",
        "Indexing timed out (over 1800 s). Nothing was saved.",
        "Telegram error while receiving the file. Please try again.",
        "Limit of 20 documents reached. Use /delete <filename> or /delete #<id>.",
        "Document search is not configured on this bot.",
        "Something went wrong while processing the document.",
        "❌ Interrupted by restart.",
        "Indexing is already finishing.",
    ]:
        assert exact_string in section, f"missing exact ERR-01 string: {exact_string!r}"


def test_t_v190_ec_01_readme_ec_13_partial_lift_sentence():
    section = _documents_rag_section(_read_readme())
    normalized = _normalize(section).lower()
    assert "partially" in normalized
    assert "ng-05" in normalized or "non-goal" in normalized


def test_t_v1100_ec_01_quality_gates_yaml_repoints_report_path():
    # REQ-V190-RPT-01 / REQ-V1100-RPT-01 / REQ-V1101-RPT-01: lint-docs'
    # report_path tracks the current release and is repointed again at
    # each one (T10 did 1.8.0 -> 1.9.0; v1.9.1 T2 did 1.9.0 -> 1.9.1;
    # v1.9.2 T3 did 1.9.1 -> 1.9.2; v1.9.3 T4 did 1.9.2 -> 1.9.3; v1.9.4 T5
    # did 1.9.3 -> 1.9.4; v1.9.5 T2 did 1.9.4 -> 1.9.5; v1.10.0 T6 did
    # 1.9.5 -> 1.10.0; v1.10.1 T2 did 1.10.0 -> 1.10.1; v1.11.0 T6's own
    # repoint does 1.10.4 -> 1.11.0 -- not in this task's own file list
    # either (T0's pin inventory names it as a disclosed amendment, not
    # in the brief's starting list), bumped here only because T6's yaml
    # edit would otherwise leave this assertion stale and pytest red; the
    # function name is deliberately left stable across releases (its own
    # docstring/comment says so) for whichever task owns this repoint
    # next).
    text = (_REPO_ROOT / "config" / "quality_gates.yaml").read_text(encoding="utf-8")
    assert "report_path: docs/reports/report-v1.11.0.md" in text
    assert "report_path: docs/reports/report-v1.10.4.md" not in text


def _context_discipline_section(text: str) -> str:
    start = text.index("## Context discipline")
    end = text.index("## Commit format")
    return text[start:end]


def _documents_rag_section(text: str) -> str:
    start = text.index("## Documents (RAG)")
    end = text.index("## Add a skill")
    return text[start:end]
