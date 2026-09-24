"""spec-v1.11.0 T2: `/documents` as a table, `/delete #<id>`, the refusal
wording split (REQ-V1110-DOC-01..-03).

Mirrors `tests/test_v190_commands.py`'s `/documents`/`/delete` test
conventions (`new_conn`, `make_cfg`, `text_update`, `process`, `_raise`,
`_assert_failure_kept`) -- self-contained, not imported, the same pattern
`tests/test_v1110_out.py` already uses for T1.
"""

from __future__ import annotations

import html

import pytest
import sqlite_vec

import bot
import config
import documents
import storage
import tables
from tests.fakes import FakeEmbedder, FakeLLM, FakeTelegram, RecordingRunner

TOKEN = "123456789:sentinel-telegram-token-for-v1110-doc-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
NOW = "2026-09-11T00:00:00Z"


@pytest.fixture(autouse=True)
def reset_shutdown(monkeypatch):
    monkeypatch.setattr(bot, "_shutdown", False)


@pytest.fixture(autouse=True)
def isolated_secret_registry():
    before = set(config._secrets)
    yield
    config._secrets.clear()
    config._secrets.update(before)


def make_cfg(tmp_path, **overrides):
    fields = {
        "telegram_bot_token": TOKEN,
        "allowed_tg_ids": frozenset({USER_ID}),
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "m",
        "openrouter_api_key": "",
        "openrouter_model": "",
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "test.db",
        "audit_log_path": tmp_path / "exec_audit.jsonl",
        "embedding_base_url": "http://localhost:1234/v1",
        "embedding_model": "embed-m",
        "embedding_dim": 16,
    }
    fields.update(overrides)
    return config.Config(**fields)


def new_conn(tmp_path, name="a.db", *, dim=16):
    conn = storage.connect(tmp_path / name)
    storage.init_schema(conn, embedding_dim=dim, embedding_model="embed-m")
    return conn


def text_update(text, update_id=1, user_id=USER_ID):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 0,
            "chat": {"id": user_id, "type": "private"},
            "from": {"id": user_id, "is_bot": False},
            "text": text,
        },
    }


def process(conn, cfg, upd, *, tg=None, llm=None, embedder=None, worker=None):
    tg = tg if tg is not None else FakeTelegram()
    llm = llm if llm is not None else FakeLLM([])
    bot.process_update(
        upd,
        conn=conn,
        tg=tg,
        cfg=cfg,
        llm=llm,
        skills={},
        runner=RecordingRunner(),
        bot_username=BOT_USERNAME,
        embedder=embedder,
        worker=worker,
    )
    return tg


def _run_document(document, *, conn, tg, cfg, chat_id, from_id, embedder, worker=None, **kwargs):
    """v1.11.0 T5 (REQ-V1110-ING-02): `_handle_document` only reserves and
    enqueues on the loop thread now -- this drives the one enqueued job (if
    any) to completion with `worker.run_one(conn=conn)`, synchronously, on
    the same thread, mirroring `tests/test_v190_commands.py`'s own helper
    of the same name (self-contained, not imported, per this file's own
    convention)."""
    w = worker if worker is not None else bot.IngestWorker(cfg, tg, embedder, cfg.db_path)
    bot._handle_document(
        document,
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=chat_id,
        from_id=from_id,
        embedder=embedder,
        worker=w,
        **kwargs,
    )
    if w.in_flight(from_id) is not None:
        w.run_one(conn=conn)
    return w


def _add_document(conn, user_id, **overrides):
    fields = {
        "user_id": user_id,
        "filename": "doc.txt",
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


def _raise(exc):
    def _fn(*_a, **_k):
        raise exc

    return _fn


def _assert_failure_kept(tg, reply):
    """CMD-04's failure ending: the status message is edited to `reply` and
    kept (never deleted)."""
    assert tg.deleted == []
    assert tg.edited and tg.edited[-1][2] == reply


# --------------------------------------------------------------------------
# REQ-V1110-DOC-01 -- /documents as a table
# --------------------------------------------------------------------------


def test_t_v1110_doc_01_documents_table(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)

    pdf_id = _add_document(
        conn,
        USER_ID,
        filename="report.pdf",
        file_type="pdf",
        created_at="2026-01-05T00:00:00Z",
        size_bytes=1_500_000,
        page_count=42,
        chunk_count=7,
    )
    long_name = "f" * 37 + ".md"  # 40 UTF-16 units
    md_id = _add_document(
        conn,
        USER_ID,
        filename=long_name,
        file_type="md",
        created_at="2026-01-06T00:00:00Z",
        size_bytes=12_300,
        page_count=None,
        chunk_count=3,
    )
    assert pdf_id != md_id

    tg = process(conn, cfg, text_update("/documents"))
    assert len(tg.sent) == 1
    assert tg.sent_payloads[-1].get("parse_mode") == "HTML"  # the table path
    raw = tg.sent[0][1]
    assert raw.startswith("<pre>") and raw.endswith("</pre>")
    body = html.unescape(raw[len("<pre>") : -len("</pre>")])

    assert body.startswith(f"Your documents (2 of {documents.DOCUMENT_LIMIT}):")
    for col in ["#", "file", "type", "size", "chunks", "pages", "added"]:
        assert col in body
    assert "1.5 MB" in body
    assert "12.3 KB" in body
    assert "n/a" in body  # the .md row's pages cell
    truncated = "f" * 21 + "…"
    assert truncated in body
    assert tables.utf16_length(truncated) == 22
    assert "2026-01-05" in body
    assert "2026-01-06" in body
    # No ingest job in flight this task -- the table is the last thing sent.
    assert "⏳" not in body
    conn.close()


def test_t_v1110_doc_02_documents_empty_reply_plain(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = process(conn, cfg, text_update("/documents"))
    assert tg.sent == [(USER_ID, bot.DOCUMENTS_EMPTY_REPLY)]
    assert "parse_mode" not in tg.sent_payloads[-1]  # the plain path
    conn.close()


# --------------------------------------------------------------------------
# REQ-V1110-DOC-02 -- /delete #<id>
# --------------------------------------------------------------------------


def test_t_v1110_doc_03_delete_by_id_owner_scoped(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)

    own_id = _add_document(conn, USER_ID, filename="mine.txt")
    [chunk_id] = storage.add_chunks(
        conn, user_id=USER_ID, document_id=own_id, chunks=[(0, "hi", None, 0, 2)]
    )
    vector = sqlite_vec.serialize_float32([0.1] * 16)
    storage.add_vectors(conn, user_id=USER_ID, rows=[(chunk_id, vector)])

    other_user = USER_ID + 1
    other_id = _add_document(conn, other_user, filename="theirs.txt")

    # bare /delete -> the new usage string
    tg = process(conn, cfg, text_update("/delete", update_id=1))
    assert tg.sent == [(USER_ID, bot.DELETE_USAGE_REPLY)]
    assert bot.DELETE_USAGE_REPLY == "Usage: /delete <filename> | /delete #<id>"

    # own id -> deleted; row and vectors gone
    tg = process(conn, cfg, text_update(f"/delete #{own_id}", update_id=2))
    assert tg.sent == [(USER_ID, f"Deleted #{own_id}.")]
    assert storage.document_id_for(conn, user_id=USER_ID, filename="mine.txt") is None
    remaining_vectors = conn.execute(
        "SELECT COUNT(*) FROM vec_chunks WHERE chunk_id = ?", (chunk_id,)
    ).fetchone()[0]
    assert remaining_vectors == 0

    # a foreign id -> not found, nothing deleted (owner check, not a second one)
    tg = process(conn, cfg, text_update(f"/delete #{other_id}", update_id=3))
    assert tg.sent == [(USER_ID, f"No document named #{other_id}.")]
    assert storage.document_id_for(conn, user_id=other_user, filename="theirs.txt") == other_id

    # non-digit id form -> the same shape, the raw argument echoed
    tg = process(conn, cfg, text_update("/delete #abc", update_id=4))
    assert tg.sent == [(USER_ID, "No document named #abc.")]

    # an id nobody owns -> not found
    tg = process(conn, cfg, text_update("/delete #999999", update_id=5))
    assert tg.sent == [(USER_ID, "No document named #999999.")]

    # a non-ASCII decimal digit `str.isdigit()` alone would accept but
    # `int()` cannot parse (e.g. U+00B2 SUPERSCRIPT TWO) -> no crash, not
    # found; a post-implementation regression guard (ASCII-only digits).
    tg = process(conn, cfg, text_update("/delete #²", update_id=6))
    assert tg.sent == [(USER_ID, "No document named #².")]

    # an id past sqlite3's INTEGER ceiling -> no OverflowError, not found;
    # a post-implementation regression guard for the same reason.
    huge_id = "9" * 25
    tg = process(conn, cfg, text_update(f"/delete #{huge_id}", update_id=7))
    assert tg.sent == [(USER_ID, f"No document named #{huge_id}.")]

    # filename form is unchanged
    _add_document(conn, USER_ID, filename="byname.txt")
    tg = process(conn, cfg, text_update("/delete byname.txt", update_id=8))
    assert tg.sent == [(USER_ID, "Deleted byname.txt.")]
    conn.close()


# --------------------------------------------------------------------------
# REQ-V1110-DOC-03 -- the refusal wording split
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "exc,expected_attr,expected_text",
    [
        (
            documents.ExtractedTextTooLargeError("text too large"),
            "DOC_TEXT_TOO_LARGE_REPLY",
            "Document too large (over 2,000,000 characters).",
        ),
        (
            documents.DocxArchiveTooLargeError("archive too large"),
            "DOC_DOCX_BOUNDS_REPLY",
            "Document too large (DOCX archive bounds).",
        ),
        (
            documents.PdfTooManyPagesError("too many pages"),
            "DOC_PDF_PAGES_REPLY",
            "Document too large (over 2,000 pages).",
        ),
    ],
)
def test_t_v1110_doc_04_refusal_wording_split(
    tmp_path, monkeypatch, exc, expected_attr, expected_text
):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = b"enough bytes to pass the pre-download size check comfortably"
    monkeypatch.setattr(documents, "extract", _raise(exc))
    doc = {"file_id": "f1", "file_name": "a.txt", "file_size": 60}
    _run_document(
        doc,
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
    )
    assert getattr(bot, expected_attr) == expected_text
    _assert_failure_kept(tg, expected_text)
    conn.close()


# --------------------------------------------------------------------------
# REQ-V1110-DOC-05 (T5) -- the in-flight line after the table.
# --------------------------------------------------------------------------


def _table_body(tg) -> str:
    raw = tg.sent[0][1]
    assert raw.startswith("<pre>") and raw.endswith("</pre>")
    return html.unescape(raw[len("<pre>") : -len("</pre>")])


def test_t_v1110_doc_05_inflight_line_after_table(tmp_path, monkeypatch):
    """Drives a real job through `run_one` (`_process`'s own `progress=
    status.update` wiring, not a poked-in stage string) and, mid-flight,
    re-enters `process_update` for `/documents` through the worker's
    `worker=` parameter -- proving both the progress wiring and the
    dispatch-level plumbing DOC-05 depends on, not just the rendering
    function in isolation."""
    conn = new_conn(tmp_path)
    other_id = USER_ID + 1
    cfg = make_cfg(tmp_path, allowed_tg_ids=frozenset({USER_ID, other_id}))
    _add_document(
        conn,
        USER_ID,
        filename="report.pdf",
        file_type="pdf",
        created_at="2026-01-05T00:00:00Z",
        size_bytes=1_500_000,
        page_count=42,
        chunk_count=7,
    )
    _add_document(
        conn,
        other_id,
        filename="other.txt",
        created_at="2026-01-05T00:00:00Z",
    )

    # Three paragraphs, each just under `target` (1000 chars) so no two
    # merge into one chunk -- `chunk_text` produces exactly 3 chunks.
    # `documents.BATCH_SIZE` patched to 1 so each chunk is its own embed()
    # call/batch, matching the real "embedding: i/3" progress strings.
    base = "Sentence number with enough words to take up real space in the paragraph. "
    paragraphs = [f"Section {i}: " + (base * 12)[:900] for i in range(3)]
    text = "\n\n".join(paragraphs)
    assert len(documents.chunk_text(text)) == 3
    monkeypatch.setattr(documents, "BATCH_SIZE", 1)

    tg = FakeTelegram()
    tg.files["documents/f1"] = text.encode("utf-8")
    captured: dict[str, str] = {}

    def hook(call_no):
        if call_no == 2:
            # batch 1/3's progress edit has already landed by now -- the
            # in-flight line should read "embedding: 1/3".
            tg_docs = process(conn, cfg, text_update("/documents"), worker=worker)
            captured["mid_flight"] = _table_body(tg_docs)
            # a different user's own listing shows no line at all.
            tg_other = process(
                conn, cfg, text_update("/documents", user_id=other_id), worker=worker
            )
            captured["other_user"] = _table_body(tg_other)

    embedder = FakeEmbedder(dim=16, hook=hook)
    worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)
    bot._handle_document(
        {"file_id": "f1", "file_name": "uploading.txt", "file_size": len(text)},
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=embedder,
        worker=worker,
    )
    worker.run_one(conn=conn)

    assert captured["mid_flight"].endswith("⏳ indexing uploading.txt — embedding: 1/3")
    assert "⏳" not in captured["other_user"]

    # The job completed normally (the hook never cancelled it) and left
    # the in-flight map -- the line is gone from a fresh /documents call.
    assert worker.in_flight(USER_ID) is None
    assert any(t.startswith("✅ uploading.txt:") for _c, t in tg.sent)
    tg_after = process(conn, cfg, text_update("/documents"), worker=worker)
    body_after = _table_body(tg_after)
    assert "⏳" not in body_after
    conn.close()
