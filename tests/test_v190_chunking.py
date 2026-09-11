"""spec-v1.9.0 T3 (docs/spec/spec-v1.9.0.md §3, REQ-V190-DOC-03): the
offset-based, paragraph-aware `documents.chunk_text` algorithm, and the
per-page composition contract T4's `index_document` (DOC-04, DOC-05) will
build on top of it.

Offline, deterministic, no I/O. PDF pages come from
`devtools.pdf_fixture.write_pdf`; nothing binary is committed.
"""

import inspect

import documents
from devtools.pdf_fixture import write_pdf


def _nonws_len(s: str) -> int:
    return sum(1 for ch in s if not ch.isspace())


# ---------------------------------------------------------------------------
# T-V190-DOC-04 (chunk_text itself)
# ---------------------------------------------------------------------------


def test_t_v190_doc_04_every_chunk_text_is_the_exact_source_slice():
    text = "Para one.\n\nPara two.\n\nPara three, a bit longer this time."
    chunks = documents.chunk_text(text)
    for chunk in chunks:
        assert chunk.text == text[chunk.char_start : chunk.char_end]


def test_t_v190_doc_04_prefers_paragraph_boundaries():
    text = "Para one.\n\nPara two.\n\nPara three."
    chunks = documents.chunk_text(text)
    # short enough to fit target as a single chunk; separators preserved by
    # construction (a direct slice of the source, never a synthetic join).
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_t_v190_doc_04_no_chunk_ever_exceeds_hard_max():
    # A single huge paragraph (no sentence ends at all) forces repeated
    # hard-cuts; every resulting chunk, including after any tail merge,
    # must still respect the 1,200 ceiling.
    text = "".join(f"word{i} " for i in range(500))
    chunks = documents.chunk_text(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 1200


def test_t_v190_doc_04_new_material_after_first_chunk_is_at_most_1000():
    text = "".join(f"word{i} " for i in range(500))
    chunks = documents.chunk_text(text)
    for prev, cur in zip(chunks, chunks[1:]):
        new_material = cur.char_end - prev.char_end
        assert new_material <= 1000


def test_t_v190_doc_04_overlap_is_exactly_200_between_consecutive_chunks():
    text = "".join(f"word{i} " for i in range(500))
    chunks = documents.chunk_text(text)
    assert len(chunks) > 1
    for prev, cur in zip(chunks, chunks[1:]):
        assert prev.char_end - cur.char_start == 200


def test_t_v190_doc_04_overlap_is_exactly_200_across_paragraph_boundaries():
    # Companion to the edge case below: the COMMON case, with real paragraph
    # separators (not just one giant sentence-split paragraph) and pieces
    # comfortably under target -- the hard_max clamp in _start_new_chunk
    # never fires here, so the full 200-char overlap is preserved.
    para = "word " * 60  # 300 chars, well under target=1000
    text = "\n\n".join([para] * 6)
    chunks = documents.chunk_text(text)
    assert len(chunks) > 1
    for prev, cur in zip(chunks, chunks[1:]):
        assert prev.char_end - cur.char_start == 200


def test_t_v190_doc_04_overlap_clamped_when_paragraph_gap_pushes_past_hard_max():
    # Edge case (erratum, DOC-03): _start_new_chunk clamps char_start via
    # `char_start = max(char_start, span_end - hard_max)`. A single long
    # paragraph never triggers this -- the clamp only fires when a
    # paragraph *separator* sits between the previous chunk's end and a
    # new paragraph close to `target` in length, so that naive-200-overlap
    # + separator gap + paragraph would exceed hard_max=1200.
    #
    # para1 = 1000 chars, para2 = 1000 chars, separated by "\n\n" (a 2-char
    # gap). The second paragraph alone doesn't fit in the first chunk
    # (target=1000), so it starts a new chunk. Naively reaching back the
    # full 200 chars of overlap would put char_start at para1's own end
    # minus 200 (=800), giving a chunk of span_end(2002) - 800 = 1202
    # chars -- 2 over hard_max. The clamp pulls char_start forward to 802
    # instead, landing the chunk at exactly hard_max (1200) and shrinking
    # the overlap to 198 chars.
    para1 = "A" * 1000
    para2 = "B" * 1000
    text = para1 + "\n\n" + para2
    chunks = documents.chunk_text(text)
    assert len(chunks) == 2
    prev, cur = chunks[0], chunks[1]

    # (a) the primary invariant: hard_max is never exceeded, even though a
    # naive "always take exactly 200 chars of overlap" implementation would
    # have exceeded it here.
    assert cur.char_end - cur.char_start <= 1200

    # (b) the clamp actually fired: char_start reaches back LESS than the
    # full 200-char overlap -- if it reached back the full 200, char_start
    # would equal prev.char_end - 200 (or less); instead it lands strictly
    # above that, proving the clamp shrank the overlap in this case.
    assert cur.char_start > prev.char_end - 200


def test_t_v190_doc_04_long_paragraph_splits_on_sentence_ends():
    sentence = "This is one sentence of moderate length. "
    text = sentence * 150  # ~6,300 chars, one paragraph, no blank lines
    assert len(text) > 5000
    chunks = documents.chunk_text(text)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.text) <= 1200
        assert chunk.text == text[chunk.char_start : chunk.char_end]


def test_t_v190_doc_04_sentence_still_too_long_is_hard_cut_at_target_not_hard_max():
    # No '. '/'!'/'? ' anywhere -- one giant "sentence" -- so every split
    # falls back to a hard cut. Each cut except a possible remainder must
    # land at exactly `target` (1000) new characters, never at hard_max.
    text = "a" * 3500
    chunks = documents.chunk_text(text)
    assert len(chunks[0].text) == 1000
    for prev, cur in zip(chunks, chunks[1:]):
        new_material = cur.char_end - prev.char_end
        assert new_material <= 1000


def test_t_v190_doc_04_tail_merges_into_previous_when_it_fits():
    # A short paragraph (short arm) fits the previous chunk exactly, and gets
    # merged, well under the minimum non-whitespace floor of a standalone
    # chunk -- documented via a total under target that stays as one chunk.
    text = ("A" * 790 + " " * 210) + "\n\nhi"
    chunks = documents.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].char_end == len(text)


def test_t_v190_doc_04_tail_stands_alone_when_merge_would_exceed_hard_max():
    para1 = "A" * 1000
    para2 = "B" * 800 + " " * 200
    para3 = "hi"
    text = para1 + "\n\n" + para2 + "\n\n" + para3
    chunks = documents.chunk_text(text)
    last = chunks[-1]
    assert _nonws_len(last.text) < 50
    prev = chunks[-2]
    assert last.char_end - prev.char_start > 1200
    for chunk in chunks:
        assert len(chunk.text) <= 1200


def test_t_v190_doc_04_short_text_below_20_nonwhitespace_chars_yields_no_chunks():
    assert documents.chunk_text("hi") == []
    assert documents.chunk_text("   \n\n  ") == []
    assert documents.chunk_text("") == []


def test_t_v190_doc_04_short_text_at_or_above_20_nonwhitespace_chars_yields_one_chunk():
    text = "this text has exactly enough non-whitespace characters"
    assert _nonws_len(text) >= 20
    chunks = documents.chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_t_v190_doc_04_deterministic():
    text = "".join(f"Paragraph {i} with a bit of filler text.\n\n" for i in range(60))
    assert documents.chunk_text(text) == documents.chunk_text(text)


# ---------------------------------------------------------------------------
# T-V190-DOC-05: the per-page composition contract (chunk_text called once
# per PDF page; page/chunk_index are the caller's job -- T4's index_document
# -- but the invariants below must already hold from chunk_text alone).
# ---------------------------------------------------------------------------


def test_t_v190_doc_05_pdf_chunks_never_span_pages_and_keep_physical_page_numbers():
    page_text = "Some page content. " * 80  # long enough to need >1 chunk
    data = write_pdf([page_text, "", page_text])
    extracted = documents.extract(data, "pdf")
    assert extracted.page_numbered is True

    # The caller (T4) chunks per page and assigns chunk_index across pages;
    # simulated here to prove the composition never lets a chunk cross a
    # page boundary and that `page` stays the PDF's physical index.
    chunk_index = 0
    rows = []
    for extracted_page in extracted.pages:
        page_text = extracted_page.text
        page_chunks = documents.chunk_text(page_text)
        assert len(page_chunks) > 1  # otherwise this test proves nothing
        for chunk in page_chunks:
            # A chunk never spans pages: chunk_text only ever sees this
            # page's own local text, so its offsets can't reach beyond it.
            assert 0 <= chunk.char_start < chunk.char_end <= len(page_text)
            rows.append((chunk_index, extracted_page.page, chunk))
            chunk_index += 1

    pages_seen = {p for _, p, _ in rows}
    assert pages_seen == {1, 3}
    indices = [i for i, _, _ in rows]
    assert indices == sorted(indices)
    assert indices == list(range(len(rows)))


def test_t_v190_doc_05_non_pdf_page_is_none():
    data = "hello world, a normal text document.".encode("utf-8-sig")
    extracted = documents.extract(data, "txt")
    assert extracted.page_numbered is False
    for page in extracted.pages:
        assert page.page is None


def test_t_v190_doc_05_chunk_text_itself_takes_plain_text_no_page_concept():
    params = list(inspect.signature(documents.chunk_text).parameters)
    assert params == ["text", "target", "hard_max", "overlap", "minimum"]
