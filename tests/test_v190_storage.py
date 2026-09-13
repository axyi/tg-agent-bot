"""spec-v1.9.0 T1 (docs/spec/spec-v1.9.0.md §4, REQ-V190-STO-01…05): the
sqlite-vec extension load, schema 6 (`documents`/`chunks`/`vec_chunks`), the
5 -> 6 migration's `llm_calls` rebuild and its normative rollback control
flow, the `rag.embedding` pair's binding/rebind rules, and the storage API
the rest of the release builds on.

`T-V190-STO-05` here is the storage-layer half only (`add_chunks`'s
`lastrowid` ordering and its ownership check) -- the `index_document`
replace-on-reupload half of that same test id belongs to T4.

Offline, deterministic, `tmp_path` databases only.
"""

from __future__ import annotations

import hashlib
import sqlite3

import pytest
import sqlite_vec

import config
import documents
import storage
from devtools.pdf_fixture import write_pdf
from tests.fakes import FakeEmbedder

NOW = "2026-09-10T00:00:00Z"

CALL_DEFAULTS = {
    "turn_id": 1,
    "purpose": "agent",
    "round_no": 1,
    "attempt": 1,
    "ts": NOW,
    "provider": "lmstudio",
    "model": "small",
    "prompt_chars": 10,
    "prompt_chars_by_role": {},
    "messages_n": 2,
    "tools_exposed": 3,
    "latency_ms": 5,
}

TOOL_DEFAULTS = {
    "turn_id": 1,
    "tool_call_id": "call_1_0",
    "tool": "exec",
    "ts": NOW,
    "input_chars": 20,
    "raw_output_chars": 100,
    "output_chars": 100,
    "output_tokens_est": 33,
    "duration_ms": 7,
    "outcome": "ok",
}


def _add_call(conn, conv_id, **overrides):
    fields = dict(CALL_DEFAULTS, conv_id=conv_id)
    fields.update(overrides)
    return storage.add_llm_call(conn, **fields)


def _add_tool(conn, conv_id, **overrides):
    fields = dict(TOOL_DEFAULTS, conv_id=conv_id)
    fields.update(overrides)
    return storage.add_tool_call(conn, **fields)


def _add_document(conn, user_id, filename, **overrides):
    fields = {
        "user_id": user_id,
        "filename": filename,
        "file_type": "txt",
        "created_at": NOW,
        "size_bytes": 5,
        "text_chars": 5,
        "page_count": None,
        "chunk_count": 1,
        "sha256": "x" * 8,
    }
    fields.update(overrides)
    return storage.add_document(conn, **fields)


def _document_with_vector(conn, user_id=1, filename="a.txt", dim=16):
    doc_id = _add_document(conn, user_id, filename)
    [chunk_id] = storage.add_chunks(
        conn, user_id=user_id, document_id=doc_id, chunks=[(0, "hello", None, 0, 5)]
    )
    vector = sqlite_vec.serialize_float32([0.1] * dim)
    storage.add_vectors(conn, user_id=user_id, rows=[(chunk_id, vector)])
    return doc_id, chunk_id


def _seed_v5_database(path) -> sqlite3.Connection:
    """A genuine v5 database, built exactly as `T-V190-STO-02` specifies: v5's
    own `_SCHEMA` + `_MIGRATION_4_TO_5`, never `init_schema` (which, on this
    tree, chains straight through to 6). `storage._SCHEMA` never gained
    `documents`/`chunks` (deliberately -- see the comment above
    `storage._DOCUMENTS_DDL`), so it is exactly v5's own schema, unmodified."""
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(storage._SCHEMA)
    conn.executescript(storage._MIGRATION_4_TO_5)
    assert storage.schema_version(conn) == 5
    assert (
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'documents'"
        ).fetchone()
        is None
    )
    return conn


def _reopen_with_failure(path, trigger_prefix, exception=RuntimeError):
    """A connection whose `execute` raises `exception` the moment a statement
    starting with `trigger_prefix` is issued -- otherwise behaves exactly like
    `storage.connect`. Used to inject a failure mid-transaction and prove the
    rollback (T-V190-STO-09, the T-V190-STO-03 failing-vector-delete half)."""

    class _BoomConnection(sqlite3.Connection):
        def execute(self, sql, *args, **kwargs):
            if isinstance(sql, str) and sql.startswith(trigger_prefix):
                raise exception("boom")
            return super().execute(sql, *args, **kwargs)

    conn = sqlite3.connect(str(path), isolation_level=None, timeout=5.0, factory=_BoomConnection)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ----------------------------------------------------------------------------
# T-V190-STO-01 -- sqlite-vec loaded on every connection; embedding_dim=None
# skips vec_chunks; a dim creates it idempotently.
# ----------------------------------------------------------------------------


def test_t_v190_sto_01_vec_version_through_connect(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    assert conn.execute("select vec_version()").fetchone()[0] == "v0.1.9"
    conn.close()


def test_t_v190_sto_01_vec_version_through_connect_readonly(tmp_path):
    path = tmp_path / "b.db"
    conn = storage.connect(path)
    storage.init_schema(conn)
    conn.close()
    ro = storage.connect_readonly(path)
    assert ro.execute("select vec_version()").fetchone()[0] == "v0.1.9"
    ro.close()


def test_t_v190_sto_01_no_dim_creates_no_vec_chunks(tmp_path):
    conn = storage.connect(tmp_path / "c.db")
    storage.init_schema(conn)
    assert not storage._vec_chunks_exists(conn)
    conn.close()


def test_t_v190_sto_01_a_dim_creates_vec_chunks_idempotently(tmp_path):
    conn = storage.connect(tmp_path / "d.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    assert storage._vec_chunks_exists(conn)
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    assert storage._vec_chunks_exists(conn)
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-STO-02 -- the 5 -> 6 migration: all four observability/message
# tables preserved by count and content, foreign keys restored, the index
# recreated, rerank now insertable, documents/chunks present; fresh is 6;
# a future version (7) is refused.
# ----------------------------------------------------------------------------


def test_t_v190_sto_02_migration_preserves_all_four_tables(tmp_path):
    path = tmp_path / "v5.db"
    conn = _seed_v5_database(path)

    conv_id = storage.get_or_create_active_conversation(conn, 7)
    storage.add_user_message(conn, conv_id, "hi")
    _add_call(conn, conv_id)
    _add_tool(conn, conv_id)
    storage.add_span(
        conn,
        trace_id="t1",
        span_id="s1",
        parent_span_id=None,
        conv_id=conv_id,
        turn_id=1,
        name="n",
        kind="INTERNAL",
        ts=NOW,
        start_ns=1,
        duration_ms=1,
        status="ok",
        status_message=None,
        attributes_json="{}",
    )

    before = {
        table: [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
        for table in ("llm_calls", "tool_calls", "spans", "messages")
    }

    storage.init_schema(conn)

    assert storage.schema_version(conn) == 6
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert (
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND name = 'idx_llm_calls_conv'"
        ).fetchone()
        is not None
    )
    for table in ("documents", "chunks"):
        assert (
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone()
            is not None
        ), table

    for table, rows in before.items():
        after = [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
        assert after == rows, table

    # the widened CHECK now admits 'rerank'.
    _add_call(conn, conv_id, purpose="rerank")
    conn.close()


def test_t_v190_sto_02_fresh_database_is_6_and_version_7_is_refused(tmp_path):
    conn = storage.connect(tmp_path / "fresh.db")
    storage.init_schema(conn)
    assert storage.schema_version(conn) == 6
    conn.execute("UPDATE schema_version SET version = 7 WHERE id = 1")
    with pytest.raises(RuntimeError) as raised:
        storage.init_schema(conn)
    assert "7" in str(raised.value)
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-STO-09 (negative) -- a failure injected mid-rebuild rolls back,
# leaving the schema-5 database intact and usable, foreign keys restored.
# ----------------------------------------------------------------------------


def test_t_v190_sto_09_a_failure_mid_migration_rolls_back(tmp_path):
    path = tmp_path / "v5.db"
    seed = _seed_v5_database(path)
    conv_id = storage.get_or_create_active_conversation(seed, 7)
    _add_call(seed, conv_id)
    before = [dict(row) for row in seed.execute("SELECT * FROM llm_calls ORDER BY id")]
    seed.close()

    boom = _reopen_with_failure(path, "INSERT INTO llm_calls_v6")
    with pytest.raises(RuntimeError):
        storage.init_schema(boom)

    assert storage.schema_version(boom) == 5
    after = [dict(row) for row in boom.execute("SELECT * FROM llm_calls ORDER BY id")]
    assert after == before
    assert (
        boom.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'llm_calls_v6'"
        ).fetchone()
        is None
    )
    for table in ("documents", "chunks"):
        assert (
            boom.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", (table,)
            ).fetchone()
            is None
        ), table
    assert boom.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert boom.execute("PRAGMA foreign_key_check").fetchall() == []
    boom.close()


def test_t_v190_sto_09_a_base_exception_mid_migration_rolls_back_the_same_way(tmp_path):
    path = tmp_path / "v5.db"
    seed = _seed_v5_database(path)
    conv_id = storage.get_or_create_active_conversation(seed, 7)
    _add_call(seed, conv_id)
    before = [dict(row) for row in seed.execute("SELECT * FROM llm_calls ORDER BY id")]
    seed.close()

    boom = _reopen_with_failure(path, "INSERT INTO llm_calls_v6", exception=KeyboardInterrupt)
    with pytest.raises(KeyboardInterrupt):
        storage.init_schema(boom)

    assert storage.schema_version(boom) == 5
    after = [dict(row) for row in boom.execute("SELECT * FROM llm_calls ORDER BY id")]
    assert after == before
    assert boom.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert boom.execute("PRAGMA foreign_key_check").fetchall() == []
    boom.close()


# ----------------------------------------------------------------------------
# T-V190-STO-03 -- delete_document removes vectors, chunks and the row in one
# transaction; a search afterwards returns nothing; a failing vector delete
# rolls the row back.
# ----------------------------------------------------------------------------


def test_t_v190_sto_03_delete_document_removes_vectors_chunks_and_row(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    doc_id, chunk_id = _document_with_vector(conn)

    assert storage.delete_document(conn, user_id=1, document_id=doc_id) is True

    assert storage.document_id_for(conn, user_id=1, filename="a.txt") is None
    assert (
        conn.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (doc_id,)).fetchone()[0]
        == 0
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM vec_chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()[
            0
        ]
        == 0
    )
    vector = sqlite_vec.serialize_float32([0.1] * 16)
    assert storage.knn_chunk_ids(conn, user_id=1, vector=vector, k=5) == []
    assert storage.user_chunks(conn, user_id=1) == []
    conn.close()


def test_t_v190_sto_03_deleting_an_unowned_document_is_a_no_op(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    doc_id, _ = _document_with_vector(conn, user_id=1)

    assert storage.delete_document(conn, user_id=2, document_id=doc_id) is False
    assert storage.document_id_for(conn, user_id=1, filename="a.txt") == doc_id
    conn.close()


def test_t_v190_sto_03_a_failing_vector_delete_rolls_back(tmp_path):
    path = tmp_path / "a.db"
    conn = storage.connect(path)
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    doc_id, chunk_id = _document_with_vector(conn)
    conn.close()

    boom = _reopen_with_failure(path, "DELETE FROM vec_chunks WHERE chunk_id = ?")
    with pytest.raises(RuntimeError):
        storage.delete_document(boom, user_id=1, document_id=doc_id)
    boom.close()

    check = storage.connect(path)
    assert storage.document_id_for(check, user_id=1, filename="a.txt") == doc_id
    assert (
        check.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (doc_id,)).fetchone()[0]
        == 1
    )
    assert (
        check.execute("SELECT COUNT(*) FROM vec_chunks WHERE chunk_id = ?", (chunk_id,)).fetchone()[
            0
        ]
        == 1
    )
    check.close()


# ----------------------------------------------------------------------------
# T-V190-STO-04 (negative half) -- a differing pair with an indexed document
# raises ConfigError before any DDL, nothing altered; a matching pair starts
# idempotently; no config with a stored pair still starts.
# ----------------------------------------------------------------------------


def test_t_v190_sto_04_differing_pair_with_a_document_raises_and_touches_nothing(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    _add_document(conn, 1, "a.txt")

    with pytest.raises(config.ConfigError):
        storage.init_schema(conn, embedding_dim=32, embedding_model="m")

    assert storage.get_state(conn, "rag.embedding") == "m:16"
    vector16 = sqlite_vec.serialize_float32([0.1] * 16)
    doc2 = _add_document(conn, 1, "b.txt")
    [chunk_id] = storage.add_chunks(
        conn, user_id=1, document_id=doc2, chunks=[(0, "x", None, 0, 1)]
    )
    storage.add_vectors(conn, user_id=1, rows=[(chunk_id, vector16)])
    conn.close()


def test_t_v190_sto_04_matching_pair_is_idempotent(tmp_path):
    conn = storage.connect(tmp_path / "b.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    assert storage.get_state(conn, "rag.embedding") == "m:16"
    conn.close()


def test_t_v190_sto_04_no_config_with_a_stored_pair_still_starts(tmp_path):
    path = tmp_path / "c.db"
    conn = storage.connect(path)
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    conn.close()

    conn2 = storage.connect(path)
    storage.init_schema(conn2)  # no embedding_dim -- the "not configured" start
    assert storage.get_state(conn2, "rag.embedding") == "m:16"
    assert storage.schema_version(conn2) == 6
    conn2.close()


# ----------------------------------------------------------------------------
# T-V190-STO-06 -- the empty-index rebind, model change.
# ----------------------------------------------------------------------------


def test_t_v190_sto_06_empty_index_rebind_model_change(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m1")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m2")

    assert storage.get_state(conn, "rag.embedding") == "m2:16"
    doc_id, _chunk_id = _document_with_vector(conn, dim=16)
    assert storage.document_id_for(conn, user_id=1, filename="a.txt") == doc_id
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-STO-07 -- the empty-index rebind, dimension change: the stale table
# can never survive `CREATE VIRTUAL TABLE IF NOT EXISTS`.
# ----------------------------------------------------------------------------


def test_t_v190_sto_07_empty_index_rebind_dimension_change(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    storage.init_schema(conn, embedding_dim=32, embedding_model="m")
    assert storage.get_state(conn, "rag.embedding") == "m:32"

    doc_id = _add_document(conn, 1, "a.txt")
    [chunk_id] = storage.add_chunks(
        conn, user_id=1, document_id=doc_id, chunks=[(0, "x", None, 0, 1)]
    )
    bad16 = sqlite_vec.serialize_float32([0.1] * 16)
    with pytest.raises(sqlite3.Error):
        storage.add_vectors(conn, user_id=1, rows=[(chunk_id, bad16)])

    good32 = sqlite_vec.serialize_float32([0.1] * 32)
    storage.add_vectors(conn, user_id=1, rows=[(chunk_id, good32)])
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-STO-08 (negative) -- the orphan vec_chunks table (a crash between
# CREATE VIRTUAL TABLE and the bot_state write) is recovered at first
# creation when empty; refused, untouched, when a document exists.
# ----------------------------------------------------------------------------


def test_t_v190_sto_08_orphan_vec_chunks_recovered_when_empty(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn)  # lands at 6, no vec_chunks
    conn.execute(storage._vec_chunks_ddl(16))  # simulate the crash-orphaned table
    assert storage.get_state(conn, "rag.embedding") is None

    storage.init_schema(conn, embedding_dim=32, embedding_model="m")
    assert storage.get_state(conn, "rag.embedding") == "m:32"

    doc_id = _add_document(conn, 1, "a.txt")
    [chunk_id] = storage.add_chunks(
        conn, user_id=1, document_id=doc_id, chunks=[(0, "x", None, 0, 1)]
    )
    good32 = sqlite_vec.serialize_float32([0.1] * 32)
    storage.add_vectors(conn, user_id=1, rows=[(chunk_id, good32)])

    doc2 = _add_document(conn, 1, "b.txt")
    [chunk2] = storage.add_chunks(conn, user_id=1, document_id=doc2, chunks=[(0, "y", None, 0, 1)])
    bad16 = sqlite_vec.serialize_float32([0.1] * 16)
    with pytest.raises(sqlite3.Error):
        storage.add_vectors(conn, user_id=1, rows=[(chunk2, bad16)])
    conn.close()


def test_t_v190_sto_08_orphan_vec_chunks_with_a_document_raises_untouched(tmp_path):
    conn = storage.connect(tmp_path / "b.db")
    storage.init_schema(conn)
    conn.execute(storage._vec_chunks_ddl(16))
    doc_id = _add_document(conn, 1, "a.txt")

    with pytest.raises(config.ConfigError):
        storage.init_schema(conn, embedding_dim=32, embedding_model="m")

    assert storage.get_state(conn, "rag.embedding") is None
    assert storage.document_id_for(conn, user_id=1, filename="a.txt") == doc_id
    # the orphan table is untouched -- still at dim 16.
    [chunk_id] = storage.add_chunks(
        conn, user_id=1, document_id=doc_id, chunks=[(1, "y", None, 0, 1)]
    )
    good16 = sqlite_vec.serialize_float32([0.1] * 16)
    storage.add_vectors(conn, user_id=1, rows=[(chunk_id, good16)])
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-STO-05 (storage half) -- add_chunks returns one id per chunk in
# order, one INSERT per row, and raises for a document_id the user_id does
# not own. The `index_document` replace-on-reupload half is T4's.
# ----------------------------------------------------------------------------


def test_t_v190_sto_05_add_chunks_returns_ids_in_chunk_order(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn)
    doc_id = _add_document(conn, 1, "a.txt", chunk_count=3)

    ids = storage.add_chunks(
        conn,
        user_id=1,
        document_id=doc_id,
        chunks=[
            (0, "aaa", None, 0, 3),
            (1, "bbb", None, 3, 6),
            (2, "ccc", None, 6, 9),
        ],
    )

    assert len(ids) == 3
    rows = conn.execute(
        "SELECT id, text FROM chunks WHERE document_id = ? ORDER BY chunk_index", (doc_id,)
    ).fetchall()
    assert [row["id"] for row in rows] == ids
    assert [row["text"] for row in rows] == ["aaa", "bbb", "ccc"]
    conn.close()


def test_t_v190_sto_05_add_chunks_raises_for_an_unowned_document(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn)
    doc_id = _add_document(conn, 1, "a.txt")

    with pytest.raises(ValueError):
        storage.add_chunks(conn, user_id=2, document_id=doc_id, chunks=[(0, "x", None, 0, 1)])
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-STO-05 (index_document half) -- documents.index_document (T4): the
# classify -> extract -> chunk -> embed -> store pipeline, its three-string
# progress contract, the one storage transaction and replace-on-reupload.
# Error-matrix / budget / zero-rows-on-failure coverage lives in
# tests/test_v190_errors.py.
# ----------------------------------------------------------------------------


def _index(conn, embedder, **overrides):
    fields = {
        "user_id": 1,
        "filename": "a.txt",
        "data": b"hello world. " * 5,
        "embedder": embedder,
        "progress": lambda s: None,
        "now": NOW,
        "started_at": 0.0,
        "monotonic": lambda: 0.0,
    }
    fields.update(overrides)
    return documents.index_document(conn, **fields)


def test_t_v190_sto_05_index_document_txt_stores_and_reports_progress(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    embedder = FakeEmbedder(dim=16)
    data = b"hello world. " * 5
    calls: list[str] = []

    result = _index(conn, embedder, data=data, progress=calls.append)

    assert isinstance(result, documents.IndexResult)
    assert result.replaced is False
    assert result.page_count is None
    assert result.text_chars == len(data)
    assert result.chunk_count == len(documents.chunk_text(data.decode()))

    assert calls[0] == f"📄 extracted: {len(data)} chars"
    assert calls[1] == f"📄 chunked: {result.chunk_count}"
    assert calls[2:] == ["📄 embedding: 1/1"]

    doc_id = storage.document_id_for(conn, user_id=1, filename="a.txt")
    assert doc_id is not None
    row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    assert row["file_type"] == "txt"
    assert row["chunk_count"] == result.chunk_count
    assert row["text_chars"] == len(data)
    assert row["page_count"] is None
    assert row["size_bytes"] == len(data)
    assert row["sha256"] == hashlib.sha256(data).hexdigest()
    assert row["created_at"] == NOW
    assert (
        conn.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (doc_id,)).fetchone()[0]
        == result.chunk_count
    )
    vector = sqlite_vec.serialize_float32([0.0] * 16)
    hits = storage.knn_chunk_ids(conn, user_id=1, vector=vector, k=5)
    assert len(hits) == result.chunk_count
    assert len(embedder.calls) == 1
    conn.close()


def test_t_v190_sto_05_index_document_pdf_reports_pages_and_attributes_them(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    embedder = FakeEmbedder(dim=16)
    data = write_pdf(
        [
            "Page one has plenty of readable text on it.",
            "",
            "Page three also has plenty of readable text on it.",
        ]
    )
    calls: list[str] = []

    result = _index(conn, embedder, filename="a.pdf", data=data, progress=calls.append)

    assert result.page_count == 2  # the blank page is skipped (DOC-02)
    assert calls[0] == f"📄 extracted: 2 pages, {result.text_chars} chars"

    doc_id = storage.document_id_for(conn, user_id=1, filename="a.pdf")
    pages = {
        row["page"]
        for row in conn.execute(
            "SELECT DISTINCT page FROM chunks WHERE document_id = ?", (doc_id,)
        ).fetchall()
    }
    assert pages == {1, 3}  # physical page numbers, never a running count
    conn.close()


def test_t_v190_sto_05_index_document_embeds_in_batches_of_32(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    embedder = FakeEmbedder(dim=16)
    paragraph = "word " * 260  # well over `target`, no sentence breaks: one chunk
    text = "\n\n".join(f"para {i} {paragraph}" for i in range(40))
    expected_chunks = len(documents.chunk_text(text))
    assert expected_chunks > 32  # the point of this test
    calls: list[str] = []

    result = _index(conn, embedder, data=text.encode(), progress=calls.append)

    expected_batches = -(-expected_chunks // 32)  # ceiling division
    assert result.chunk_count == expected_chunks
    assert all(len(texts) <= 32 for texts, _ in embedder.calls)
    assert len(embedder.calls) == expected_batches
    embedding_progress = [c for c in calls if c.startswith("📄 embedding:")]
    assert embedding_progress == [
        f"📄 embedding: {i}/{expected_batches}" for i in range(1, expected_batches + 1)
    ]
    conn.close()


def test_t_v190_sto_05_index_document_replace_on_reupload(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    embedder = FakeEmbedder(dim=16)

    first = _index(conn, embedder, data=b"first version of the document text.")
    first_id = storage.document_id_for(conn, user_id=1, filename="a.txt")
    assert first.replaced is False

    second = _index(conn, embedder, data=b"second, quite different document text.")
    second_id = storage.document_id_for(conn, user_id=1, filename="a.txt")

    assert second.replaced is True
    assert second_id != first_id  # AUTOINCREMENT: no row identity carried over
    assert storage.document_count(conn, user_id=1) == 1
    assert (
        conn.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (first_id,)).fetchone()[0]
        == 0
    )
    vector = sqlite_vec.serialize_float32([0.0] * 16)
    hits = storage.knn_chunk_ids(conn, user_id=1, vector=vector, k=100)
    assert len(hits) == second.chunk_count  # no leftover vectors from the replaced doc
    conn.close()
