"""spec-v1.9.0 T6 (docs/spec/spec-v1.9.0.md Sec.6, REQ-V190-TOOL-05): the
structural `Sources:` guarantee -- `rag.attach_sources`/`rag._render_sources`.
Attribution is never validated by parsing a filename back out of a reply
line; it is validated by generating the closed set of canonical renderings
the returned passages license and checking a candidate line for whole-string
equality against it.

Offline and deterministic throughout: `rag.Passage`/`rag.SearchResult` are
built by hand, no I/O.
"""

import logging

import rag

WARNING = "stripped an invented source line"


def passage(**overrides):
    fields = {
        "chunk_id": 1,
        "filename": "policy.pdf",
        "page": 3,
        "chunk_index": 0,
        "text": "passage text",
    }
    fields.update(overrides)
    return rag.Passage(**fields)


def result(passages=(), *, documents_present=True):
    return rag.SearchResult(
        passages=list(passages),
        documents_present=documents_present,
        rerank_attempted=False,
        rerank_succeeded=False,
        rerank_failure=None,
    )


# --------------------------------------------------------------------------
# rag._render_sources -- the pure rendering grouping/order rules
# --------------------------------------------------------------------------


def test_render_sources_single_page():
    assert rag._render_sources([("a.pdf", 3)]) == "a.pdf (page 3)"


def test_render_sources_no_page_omits_the_parenthetical():
    assert rag._render_sources([("a.txt", None)]) == "a.txt"


def test_render_sources_several_pages_of_one_file_in_first_seen_order():
    assert rag._render_sources([("a.pdf", 5), ("a.pdf", 2)]) == "a.pdf (pages 5, 2)"


def test_render_sources_several_files_joined_and_in_first_seen_filename_order():
    pairs = [("b.pdf", 1), ("a.pdf", 9), ("b.pdf", 4)]
    assert rag._render_sources(pairs) == "b.pdf (pages 1, 4), a.pdf (page 9)"


def test_render_sources_duplicate_pages_of_one_file_are_not_repeated():
    assert rag._render_sources([("a.pdf", 2), ("a.pdf", 2)]) == "a.pdf (page 2)"


# --------------------------------------------------------------------------
# T-V190-TOOL-06 -- passages were returned
# --------------------------------------------------------------------------


def test_t_v190_tool_06_a_canonical_line_survives_untouched():
    calls = [result([passage(filename="hr.pdf", page=4)])]
    reply = "You have 30 days.\n\nSources: hr.pdf (page 4)"
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == reply
    assert changed is False


def test_t_v190_tool_06_the_singular_source_prefix_is_also_accepted():
    calls = [result([passage(filename="hr.pdf", page=4)])]
    reply = "You have 30 days.\nSource: hr.pdf (page 4)"
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == reply
    assert changed is False


def test_t_v190_tool_06_no_source_line_gets_the_canonical_block_appended():
    calls = [result([passage(filename="hr.pdf", page=4)])]
    new_reply, changed = rag.attach_sources("You have 30 days.", calls)
    assert new_reply == "You have 30 days.\n\nSources: hr.pdf (page 4)"
    assert changed is True


def test_t_v190_tool_06_an_invented_line_is_stripped_and_replaced(caplog):
    calls = [result([passage(filename="hr.pdf", page=4)])]
    reply = "You have 30 days.\nSources: made-up.pdf (page 1)"
    with caplog.at_level(logging.WARNING):
        new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == "You have 30 days.\n\nSources: hr.pdf (page 4)"
    assert changed is True
    assert [r for r in caplog.records if WARNING in r.getMessage()]


def test_t_v190_tool_06_multiple_invented_lines_log_exactly_one_warning(caplog):
    calls = [result([passage(filename="hr.pdf", page=4)])]
    reply = "Line one.\nSource: a.pdf\nLine two.\nSources: b.pdf (page 9)\nLine three."
    with caplog.at_level(logging.WARNING):
        new_reply, changed = rag.attach_sources(reply, calls)
    assert changed is True
    assert new_reply.endswith("\n\nSources: hr.pdf (page 4)")
    assert len([r for r in caplog.records if WARNING in r.getMessage()]) == 1


def test_t_v190_tool_06_a_prose_mention_does_not_satisfy_attribution():
    calls = [result([passage(filename="hr.pdf", page=4)])]
    reply = "I read hr.pdf and it says 30 days."
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == reply + "\n\nSources: hr.pdf (page 4)"
    assert changed is True


def test_t_v190_tool_06_collection_is_capped_at_five_pairs_first_seen():
    passages = [passage(filename=f"f{i}.pdf", page=i, chunk_id=i, chunk_index=i) for i in range(7)]
    calls = [result(passages)]
    new_reply, _ = rag.attach_sources("answer", calls)
    rendered = new_reply.split("Sources: ", 1)[1]
    assert rendered.count(".pdf") == 5
    assert "f0.pdf" in rendered and "f4.pdf" in rendered
    assert "f5.pdf" not in rendered and "f6.pdf" not in rendered


def test_t_v190_tool_06_pairs_span_multiple_calls_in_call_order():
    calls = [
        result([passage(filename="a.pdf", page=1)]),
        result([passage(filename="b.pdf", page=2)]),
    ]
    new_reply, _ = rag.attach_sources("answer", calls)
    assert new_reply == "answer\n\nSources: a.pdf (page 1), b.pdf (page 2)"


# --------------------------------------------------------------------------
# T-V190-TOOL-07 -- no passage was returned by any call
# --------------------------------------------------------------------------


def test_t_v190_tool_07_no_passages_strips_any_source_line(caplog):
    calls = [result([], documents_present=True)]
    reply = "The documents do not cover it.\nSources: hr.pdf (page 4)"
    with caplog.at_level(logging.WARNING):
        new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == "The documents do not cover it."
    assert changed is True
    assert [r for r in caplog.records if WARNING in r.getMessage()]


def test_t_v190_tool_07_no_documents_present_strips_any_source_line():
    calls = [result([], documents_present=False)]
    reply = "No documents.\nSource: hr.pdf (page 4)"
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == "No documents."
    assert changed is True


def test_t_v190_tool_07_no_passages_and_no_source_line_is_untouched():
    calls = [result([], documents_present=True)]
    reply = "The documents do not cover it."
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == reply
    assert changed is False


def test_t_v190_tool_07_zero_calls_is_untouched():
    new_reply, changed = rag.attach_sources("hello", [])
    assert new_reply == "hello"
    assert changed is False


# --------------------------------------------------------------------------
# T-V190-TOOL-08 (negative) -- a delimiter-hostile filename; validation is
# never by parsing, only by canonical-rendering equality.
# --------------------------------------------------------------------------


def test_t_v190_tool_08_the_exact_canonical_line_survives():
    calls = [result([passage(filename="a, b (page 9).pdf", page=9)])]
    reply = "Answer.\nSources: a, b (page 9).pdf (page 9)"
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == reply
    assert changed is False


def test_t_v190_tool_08_an_added_file_is_stripped_and_replaced():
    calls = [result([passage(filename="a, b (page 9).pdf", page=9)])]
    reply = "Answer.\nSources: a, b (page 9).pdf (page 9), extra.pdf"
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == "Answer.\n\nSources: a, b (page 9).pdf (page 9)"
    assert changed is True


def test_t_v190_tool_08_a_dropped_page_is_stripped_and_replaced():
    calls = [result([passage(filename="a, b (page 9).pdf", page=9)])]
    reply = "Answer.\nSources: a, b (page 9).pdf"
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == "Answer.\n\nSources: a, b (page 9).pdf (page 9)"
    assert changed is True


def test_t_v190_tool_08_reordered_entries_are_stripped_and_replaced():
    calls = [
        result([passage(filename="a, b (page 9).pdf", page=9)]),
        result([passage(filename="z.pdf", page=1)]),
    ]
    reply = "Answer.\nSources: z.pdf (page 1), a, b (page 9).pdf (page 9)"
    new_reply, changed = rag.attach_sources(reply, calls)
    assert new_reply == ("Answer.\n\nSources: a, b (page 9).pdf (page 9), z.pdf (page 1)")
    assert changed is True
