"""spec-v1.9.0 T1 (docs/spec/spec-v1.9.0.md §4, REQ-V190-SEC-05; the storage
half of SEC-02/-03/-06): the user-scoping discipline over `storage.py`'s new
RAG statements.

`rag.py` does not exist until T5. The spec's `T-V190-SEC-05` reads "AST walk
over `storage.py`/`rag.py`" -- the walk below is scoped to `storage.py` only
and MUST be widened once `rag.py` lands.

`T-V190-SEC-02`/`-03` here cover only what T1 owns directly (`list_documents`,
`document_count`/`document_count_all`, `document_id_for`, `delete_document`);
their `/documents` and `/delete` command-surface halves belong to later tasks.

Offline, deterministic, `tmp_path` databases only.
"""

from __future__ import annotations

import ast
import inspect

import pytest
import sqlite_vec

import storage


def _document(conn, user_id, filename, **overrides):
    fields = {
        "user_id": user_id, "filename": filename, "file_type": "txt",
        "created_at": "x", "size_bytes": 1, "text_chars": 5,
        "page_count": None, "chunk_count": 1, "sha256": "x" * 8,
    }
    fields.update(overrides)
    return storage.add_document(conn, **fields)


def _document_with_chunk(conn, user_id, filename):
    doc_id = _document(conn, user_id, filename)
    [chunk_id] = storage.add_chunks(
        conn, user_id=user_id, document_id=doc_id, chunks=[(0, "hello", None, 0, 5)]
    )
    return doc_id, chunk_id


# ----------------------------------------------------------------------------
# T-V190-SEC-02 (storage half): list_documents/document_count are per user;
# document_count_all is the one cross-user exemption.
# ----------------------------------------------------------------------------


def test_t_v190_sec_02_list_documents_and_document_count_are_per_user(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn)
    _document(conn, 1, "a.txt")
    _document(conn, 1, "b.txt")
    _document(conn, 2, "c.txt")

    a_docs = storage.list_documents(conn, user_id=1)
    b_docs = storage.list_documents(conn, user_id=2)

    assert {row["filename"] for row in a_docs} == {"a.txt", "b.txt"}
    assert {row["filename"] for row in b_docs} == {"c.txt"}
    assert storage.document_count(conn, user_id=1) == 2
    assert storage.document_count(conn, user_id=2) == 1
    assert storage.document_count_all(conn) == 3
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-SEC-03 (storage half): document_id_for and delete_document never
# resolve or touch another user's row, even under a same-filename collision
# across owners.
# ----------------------------------------------------------------------------


def test_t_v190_sec_03_document_id_for_is_scoped_to_owner(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn)
    doc_id = _document(conn, 1, "a.txt")

    assert storage.document_id_for(conn, user_id=1, filename="a.txt") == doc_id
    assert storage.document_id_for(conn, user_id=2, filename="a.txt") is None
    conn.close()


def test_t_v190_sec_03_delete_document_never_touches_another_users_row(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn)
    a_id = _document(conn, 1, "a.txt")
    b_id = _document(conn, 2, "a.txt")  # same filename, different owner

    assert storage.delete_document(conn, user_id=1, document_id=b_id) is False
    assert storage.document_id_for(conn, user_id=2, filename="a.txt") == b_id
    assert storage.document_id_for(conn, user_id=1, filename="a.txt") == a_id
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-SEC-06 (negative): add_vectors refuses another user's chunk ids,
# before any insert.
# ----------------------------------------------------------------------------


def test_t_v190_sec_06_add_vectors_refuses_a_foreign_chunk_id(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    _, a_chunk = _document_with_chunk(conn, 1, "a.txt")

    vector = sqlite_vec.serialize_float32([0.1] * 16)
    with pytest.raises(ValueError):
        storage.add_vectors(conn, user_id=2, rows=[(a_chunk, vector)])
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
    conn.close()


def test_t_v190_sec_06_one_own_and_one_foreign_id_raises_too(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    _, a_chunk = _document_with_chunk(conn, 1, "a.txt")
    _, b_chunk = _document_with_chunk(conn, 2, "b.txt")

    vector = sqlite_vec.serialize_float32([0.1] * 16)
    with pytest.raises(ValueError):
        storage.add_vectors(conn, user_id=2, rows=[(b_chunk, vector), (a_chunk, vector)])
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
    conn.close()


def test_t_v190_sec_06_all_own_ids_succeed(tmp_path):
    conn = storage.connect(tmp_path / "a.db")
    storage.init_schema(conn, embedding_dim=16, embedding_model="m")
    doc_id = _document(conn, 1, "a.txt")
    chunk_ids = storage.add_chunks(
        conn, user_id=1, document_id=doc_id,
        chunks=[(0, "hello", None, 0, 5), (1, "world", None, 5, 10)],
    )

    vector = sqlite_vec.serialize_float32([0.1] * 16)
    storage.add_vectors(conn, user_id=1, rows=[(cid, vector) for cid in chunk_ids])

    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 2
    conn.close()


# ----------------------------------------------------------------------------
# T-V190-SEC-05: every runtime DML/SELECT over documents/chunks/vec_chunks is
# user-scoped; schema DDL is excluded; document_count_all is the sole
# exemption; the vec_chunks point delete is authorised only alongside the
# user-scoped select in the same function body (delete_document); add_chunks
# and add_vectors each hold an ownership check before their insert.
# ----------------------------------------------------------------------------

_TABLES = ("documents", "chunks", "vec_chunks")
_DDL_MARKERS = (
    "CREATE TABLE", "CREATE INDEX", "CREATE VIRTUAL TABLE", "DROP TABLE",
    "ALTER TABLE", "PRAGMA", "sqlite_master", "BEGIN", "COMMIT", "ROLLBACK",
)
_EXEMPT_FUNCTIONS = {"document_count_all"}


def _resolve_sql_text(source: str, arg_node: ast.expr) -> str | None:
    """The exact SQL text passed as the first positional argument to a
    `conn.execute`/`conn.executemany` call. `ast.get_source_segment` returns
    the literal's full source span in one piece, so fragments joined by
    Python's adjacent-string-literal folding are never split the way a
    line-by-line text scan would split them. A bare `Name` (`_INSERT_CHUNK`)
    is resolved against the module's own globals. Anything else (a loop
    variable, a function-call result -- this module's DDL builders) is
    unresolvable and returns `None`: those are schema DDL, out of scope."""
    if isinstance(arg_node, ast.Name):
        value = getattr(storage, arg_node.id, None)
        return value if isinstance(value, str) else None
    if isinstance(arg_node, (ast.Constant, ast.JoinedStr)):
        return ast.get_source_segment(source, arg_node)
    return None


def test_t_v190_sec_05_every_runtime_statement_is_user_scoped():
    source = inspect.getsource(storage)
    tree = ast.parse(source)

    function_bodies: dict[str, str] = {
        node.name: ast.get_source_segment(source, node) or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name in _EXEMPT_FUNCTIONS:
            continue
        body = function_bodies[node.name]
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if not (isinstance(func, ast.Attribute) and func.attr in ("execute", "executemany")):
                continue
            if not call.args:
                continue
            sql = _resolve_sql_text(source, call.args[0])
            if sql is None or any(marker in sql for marker in _DDL_MARKERS):
                continue
            if not any(table in sql for table in _TABLES):
                continue
            if "user_id" in sql:
                continue
            if (
                node.name == "delete_document"
                and "vec_chunks" in sql
                and "chunk_id = ?" in sql
                and "d.user_id = ?" in body
            ):
                # SEC-05's one point-delete exception: ownership is carried by
                # the user-scoped select earlier in this same function body.
                continue
            if "chunks" in sql and "documents" not in sql and "vec_chunks" not in sql:
                # `chunks` itself carries no `user_id` column; `add_chunks`'s
                # bare per-row INSERT is authorised only because this same
                # function body holds a `documents` ownership check first.
                if "user_id" in body and "documents" in body:
                    continue
            offenders.append((node.name, sql))

    assert offenders == []
    assert "SELECT 1 FROM documents WHERE id = ? AND user_id = ?" in function_bodies["add_chunks"]
    assert "d.user_id = ?" in function_bodies["add_vectors"]
