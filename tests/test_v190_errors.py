"""spec-v1.9.0 T4 (docs/spec/spec-v1.9.0.md Sec.3/Sec.8, REQ-V190-DOC-04,
-05): the storage-facing rows of the ERR-01 error matrix owned by
`documents.index_document` -- rows 4, 5b, 6, 7, 10c and row 13's
*transactional* recheck only (the pre-check before the status message is
T7's own, in `bot.py` and T7's own tests -- not here). Also
`T-V190-CMD-07`'s budget half: `IndexBudgetExceeded` raised at every stage
boundary and between PDF pages, always as its own type.

Every test proves the one indexing transaction's "nothing stored on
failure" property (DOC-04) for the stage it exercises. Offline,
deterministic, `tmp_path` databases only.
"""

from __future__ import annotations

import sqlite3

import pytest
import sqlite_vec

import documents
import storage
from devtools.pdf_fixture import write_pdf
from llm.embeddings import EmbeddingError
from tests.fakes import FakeEmbedder

NOW = "2026-09-10T00:00:00Z"


def _add_document(conn, user_id, filename, **overrides):
    fields = {
        "user_id": user_id, "filename": filename, "file_type": "txt",
        "created_at": NOW, "size_bytes": 5, "text_chars": 5,
        "page_count": None, "chunk_count": 1, "sha256": "x" * 8,
    }
    fields.update(overrides)
    return storage.add_document(conn, **fields)


def _new_conn(tmp_path, name="a.db", *, dim=16):
    conn = storage.connect(tmp_path / name)
    storage.init_schema(conn, embedding_dim=dim, embedding_model="m")
    return conn


def _assert_nothing_stored(conn, *, user_id=1, expected_documents=0):
    assert storage.document_count(conn, user_id=user_id) == expected_documents
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0


def _connection_that_fails_on(path, trigger_prefix, exception=sqlite3.OperationalError):
    """A connection whose `execute` raises `exception` the moment a statement
    starting with `trigger_prefix` runs -- otherwise behaves exactly like
    `storage.connect`. Injects a mid-transaction failure to prove the
    rollback (ERR-01 row 7)."""

    class _BoomConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if isinstance(sql, str) and sql.startswith(trigger_prefix):
                raise exception("boom")
            return super().execute(sql, *args, **kwargs)

    conn = sqlite3.connect(
        str(path), isolation_level=None, timeout=5.0, factory=_BoomConnection
    )
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _seq_clock(*values):
    """Returns `values[0]`, then `values[1]`, ... clamped to the last value
    once exhausted -- so a test can make an early budget check pass and a
    later one fail without guessing exactly how many `monotonic()` calls the
    implementation makes after the interesting one."""
    values = list(values)
    state = {"i": 0}

    def _mono():
        i = min(state["i"], len(values) - 1)
        state["i"] += 1
        return values[i]

    return _mono


# ----------------------------------------------------------------------------
# ERR-01 row 4 -- fewer than 20 non-whitespace characters extracted.
# ----------------------------------------------------------------------------


def test_t_v190_err_01_row_4_empty_document_raises_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    embedder = FakeEmbedder(dim=16)

    with pytest.raises(documents.EmptyDocumentError):
        documents.index_document(
            conn, user_id=1, filename="empty.txt", data=b"hi",
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=lambda: 0.0,
        )

    _assert_nothing_stored(conn)
    assert embedder.calls == []  # extraction stage: embed never reached
    conn.close()


# ----------------------------------------------------------------------------
# ERR-01 row 5b -- extracted text over 500,000 chars, and (T3's own guards,
# just propagating) the DOCX archive / PDF page-count bounds.
# ----------------------------------------------------------------------------


def test_t_v190_err_01_row_5b_text_too_large_raises_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    data = b"a" * (documents.MAX_EXTRACTED_TEXT_CHARS + 1)

    with pytest.raises(documents.ExtractedTextTooLargeError) as exc_info:
        documents.index_document(
            conn, user_id=1, filename="big.txt", data=data,
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=lambda: 0.0,
        )

    assert isinstance(exc_info.value, documents.DocumentTooLargeError)
    _assert_nothing_stored(conn)
    assert embedder.calls == []
    conn.close()


def test_t_v190_err_01_row_5b_pdf_too_many_pages_propagates_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    data = write_pdf(["x"] * (documents.PDF_MAX_PAGES + 1))

    with pytest.raises(documents.PdfTooManyPagesError) as exc_info:
        documents.index_document(
            conn, user_id=1, filename="big.pdf", data=data,
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=lambda: 0.0,
        )

    assert isinstance(exc_info.value, documents.DocumentTooLargeError)
    _assert_nothing_stored(conn)
    assert embedder.calls == []
    conn.close()


# ----------------------------------------------------------------------------
# ERR-01 row 6 -- EmbeddingError from the embed stage propagates un-caught.
# ----------------------------------------------------------------------------


def test_t_v190_err_01_row_6_embedding_error_propagates_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    embedder = FakeEmbedder(dim=16, script=[EmbeddingError("boom")])

    with pytest.raises(EmbeddingError):
        documents.index_document(
            conn, user_id=1, filename="a.txt", data=b"hello world, plenty of text here.",
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=lambda: 0.0,
        )

    _assert_nothing_stored(conn)
    conn.close()


# ----------------------------------------------------------------------------
# ERR-01 row 7 -- sqlite3.Error from the store stage rolls back; nothing
# survives the failed transaction.
# ----------------------------------------------------------------------------


def test_t_v190_err_01_row_7_sqlite_error_rolls_back_and_stores_nothing(tmp_path):
    path = tmp_path / "a.db"
    conn = _new_conn(tmp_path, "a.db")
    conn.close()

    boom = _connection_that_fails_on(path, "INSERT INTO documents")
    embedder = FakeEmbedder(dim=16)

    with pytest.raises(sqlite3.Error):
        documents.index_document(
            boom, user_id=1, filename="a.txt", data=b"hello world, plenty of text here.",
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=lambda: 0.0,
        )
    boom.close()

    check = storage.connect(path)
    _assert_nothing_stored(check)
    check.close()


# ----------------------------------------------------------------------------
# ERR-01 row 10c / T-V190-CMD-07 (budget half) -- documents.IndexBudgetExceeded
# at every stage boundary and between PDF pages; always its own type, never
# caught anywhere in documents.py, always leaving zero rows.
# ----------------------------------------------------------------------------


def test_t_v190_cmd_07_budget_after_extraction_raises_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    embedder = FakeEmbedder(dim=16)

    with pytest.raises(documents.IndexBudgetExceeded):
        documents.index_document(
            conn, user_id=1, filename="a.txt", data=b"hello world, plenty of text here.",
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=lambda: 400.0, budget_s=300.0,
        )

    _assert_nothing_stored(conn)
    assert embedder.calls == []  # never reached the embed stage
    conn.close()


def test_t_v190_cmd_07_budget_after_chunking_raises_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    # 1st check (after extraction) passes at 50s; 2nd (after chunking) fails at 400s.
    clock = _seq_clock(50.0, 400.0)

    with pytest.raises(documents.IndexBudgetExceeded):
        documents.index_document(
            conn, user_id=1, filename="a.txt", data=b"hello world, plenty of text here.",
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=clock, budget_s=300.0,
        )

    _assert_nothing_stored(conn)
    assert embedder.calls == []  # never reached the embed stage
    conn.close()


def test_t_v190_cmd_07_budget_after_embedding_batch_raises_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    # extraction and chunking checks pass; the check after the (one) embed
    # batch fails.
    clock = _seq_clock(50.0, 60.0, 400.0)

    with pytest.raises(documents.IndexBudgetExceeded):
        documents.index_document(
            conn, user_id=1, filename="a.txt", data=b"hello world, plenty of text here.",
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=clock, budget_s=300.0,
        )

    assert len(embedder.calls) == 1  # the batch itself did run
    _assert_nothing_stored(conn)
    conn.close()


def test_t_v190_cmd_07_budget_between_pdf_pages_raises_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    embedder = FakeEmbedder(dim=16)
    data = write_pdf(["Page one has readable text.", "Page two also has text."])
    # the check before page 1 passes; the check before page 2 fails -- so
    # this fires from inside `_extract_pdf`'s loop, never even reaching the
    # after-extraction stage-boundary check.
    clock = _seq_clock(10.0, 400.0)

    with pytest.raises(documents.IndexBudgetExceeded):
        documents.index_document(
            conn, user_id=1, filename="a.pdf", data=data,
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=clock, budget_s=300.0,
        )

    _assert_nothing_stored(conn)
    assert embedder.calls == []
    conn.close()


def test_t_v190_index_budget_exceeded_is_not_a_document_too_large_error():
    # DOC-02/DOC-04's exact exception-boundary rule: a corruption handler's
    # `except documents.DocumentTooLargeError` (row 5b) must never also
    # swallow a budget failure (row 10c), and vice versa.
    assert not issubclass(documents.IndexBudgetExceeded, documents.DocumentTooLargeError)
    assert not issubclass(documents.DocumentTooLargeError, documents.IndexBudgetExceeded)


# ----------------------------------------------------------------------------
# ERR-01 row 13 (transactional recheck only) -- the user already has 20
# documents and this filename would not be a replace.
# ----------------------------------------------------------------------------


def test_t_v190_err_01_row_13_transactional_recheck_raises_and_stores_nothing(tmp_path):
    conn = _new_conn(tmp_path)
    for i in range(20):
        _add_document(conn, 1, f"d{i}.txt")
    embedder = FakeEmbedder(dim=16)

    with pytest.raises(documents.DocumentLimitExceededError):
        documents.index_document(
            conn, user_id=1, filename="new.txt", data=b"hello world, plenty of text here.",
            embedder=embedder, progress=lambda s: None, now=NOW,
            started_at=0.0, monotonic=lambda: 0.0,
        )

    assert storage.document_count(conn, user_id=1) == 20  # unchanged, not 21
    assert storage.document_id_for(conn, user_id=1, filename="new.txt") is None
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
    # the limit is re-checked in-transaction, only right before the insert --
    # after embedding has already run (DOC-04) -- yet nothing lands.
    assert len(embedder.calls) == 1
    conn.close()


def test_t_v190_err_01_row_13_replace_at_20_is_not_the_limit(tmp_path):
    # "this filename is not one of them" -- a re-upload of an existing
    # filename never counts against the limit, even sitting at exactly 20.
    conn = _new_conn(tmp_path)
    for i in range(19):
        _add_document(conn, 1, f"d{i}.txt")
    _add_document(conn, 1, "existing.txt")
    embedder = FakeEmbedder(dim=16)

    result = documents.index_document(
        conn, user_id=1, filename="existing.txt", data=b"hello world, plenty of text here.",
        embedder=embedder, progress=lambda s: None, now=NOW,
        started_at=0.0, monotonic=lambda: 0.0,
    )

    assert result.replaced is True
    assert storage.document_count(conn, user_id=1) == 20
    conn.close()
