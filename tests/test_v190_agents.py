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


def test_t_v190_ec_01_agents_md_seven_gate_block_present():
    text = _read_agents_md()
    assert "All seven MUST exit 0" in text
    for gate_cmd in [
        "uv sync --locked",
        "uv run --locked ruff check .",
        "uv run --locked pytest",
        "uv run --locked python bot.py --selftest",
        "uv run --locked python bot.py --selftest-live",
        "uv run --locked python devtools/mutation_check.py",
        "uv run --locked python devtools/rag_eval.py",
    ]:
        assert gate_cmd in text, f"missing gate command: {gate_cmd!r}"


def test_t_v190_ec_01_agents_md_brief_path_token_is_v190():
    text = _read_agents_md()
    assert "docs/spec/task-briefs/v190-T<N>.md" in text
    assert "docs/spec/task-briefs/v180-T<N>.md" not in text


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


def test_t_v190_ec_01_agents_md_count_bearing_lines_untouched():
    # RPT-05: AGENTS.md:146's test count and :155's mutation count are
    # written once, in T12 -- T10 must not touch them. Both still carry
    # their pre-T10 figures (1220 tests, 98 mutation entries).
    text = _read_agents_md()
    assert "1220" in text
    assert "98 entries" in text


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
        f"{list(zip(_DOCUMENTS_RAG_SUBSECTIONS, positions))}"
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


def test_t_v190_ec_01_readme_gate_7_recorded_red():
    # Honesty in two places: the eval-numbers subsection and the ## Tests
    # gate block itself -- neither may claim gate 7 passes.
    rag_section = _documents_rag_section(_read_readme())
    assert "currently red" in rag_section.lower()

    text = _read_readme()
    tests_section = text[text.index("## Tests") :]
    assert "currently red" in tests_section.lower()


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


def test_t_v190_ec_01_readme_limits_table_gains_rag_rows():
    text = _read_readme()
    limits_idx = text.index("## Limits")
    error_idx = text.index("## Error behaviour")
    section = text[limits_idx:error_idx]
    for needle in [
        "10,485,760",
        "500,000",
        "20 (`DOCUMENT_LIMIT`)",
        "300 s",
        "2,000 members",
        "500 pages",
        "1000 chars, hard max 1200, overlap 200, minimum 50",
        "5 (`RAG_TOP_K`",
        "10 (RRF cut",
        "12,000 chars",
    ]:
        assert needle in section, f"missing Limits row content: {needle!r}"


def test_t_v190_ec_01_readme_error_behaviour_table_gains_document_rows():
    text = _read_readme()
    error_idx = text.index("## Error behaviour")
    versioning_idx = text.index("## Versioning")
    section = text[error_idx:versioning_idx]
    for exact_string in [
        "Unsupported file type. Supported: .txt .md .docx .pdf",
        "Could not read this PDF file.",
        "Could not read this DOCX file.",
        "The document contains no readable text.",
        "File too large (over 10 MiB).",
        "Document too large (over 500,000 characters).",
        "Embedding service error. Please try again later.",
        "Storage error. The document was not saved.",
        "Download timed out. Please try again.",
        "Embedding service timed out. Please try again later.",
        "Indexing timed out (over 300 s). Nothing was saved.",
        "Telegram error while receiving the file. Please try again.",
        "Limit of 20 documents reached. Use /delete <filename>.",
        "Document search is not configured on this bot.",
        "Something went wrong while processing the document.",
    ]:
        assert exact_string in section, f"missing exact ERR-01 string: {exact_string!r}"


def test_t_v190_ec_01_readme_ec_13_partial_lift_sentence():
    section = _documents_rag_section(_read_readme())
    normalized = _normalize(section).lower()
    assert "partially" in normalized
    assert "ng-05" in normalized or "non-goal" in normalized


def test_t_v190_ec_01_quality_gates_yaml_repoints_report_path():
    text = (_REPO_ROOT / "config" / "quality_gates.yaml").read_text(encoding="utf-8")
    assert "report_path: docs/reports/report-v1.9.0.md" in text
    assert "report_path: docs/reports/report-v1.8.0.md" not in text


def _context_discipline_section(text: str) -> str:
    start = text.index("## Context discipline")
    end = text.index("## Commit format")
    return text[start:end]


def _documents_rag_section(text: str) -> str:
    start = text.index("## Documents (RAG)")
    end = text.index("## Add a skill")
    return text[start:end]
