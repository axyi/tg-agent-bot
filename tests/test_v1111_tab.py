"""spec-v1.11.1 T2: table widths, the `/sessions` empty state, the
`DOC_LIMIT_REPLY` refusal string, one embedding batch constant
(REQ-V1111-TAB-01..05). See `docs/spec/spec-v1.11.1.md` sec.3.2 and
`docs/spec/task-briefs/v1111-T2.md`.

Self-contained, not imported (the same pattern `tests/test_v1110_doc.py`/
`tests/test_v1111_out.py` already use) -- `make_cfg`/`new_conn`/
`text_update`/`document_update`/`process`/`_add_document` mirror
`tests/test_v1110_doc.py` and `tests/test_v190_commands.py`'s own
helpers of the same name, extended with both providers configured
(`tests/test_v1110_cbq.py`'s shape) for the `/model` sub-test.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

import httpx
import pytest

import bot
import config
import documents
import storage
import tables
from llm import embeddings
from tests.fakes import FakeEmbedder, FakeLLM, FakeTelegram, RecordingRunner, mock_llm_transport

TOKEN = "123456789:sentinel-telegram-token-for-v1111-tab-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
NOW = "2026-01-01T00:00:00Z"
REPO_ROOT = Path(__file__).resolve().parent.parent


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
        "lmstudio_model": "m-default",
        "lmstudio_models": ("m-default",),
        "openrouter_api_key": "sk-or-sentinel-key-value",
        "openrouter_model": "o-default",
        "openrouter_models": ("o-default", "o-alt"),
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "a.db",
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


def document_update(*, file_id="f1", file_name="notes.txt", file_size=20, update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "date": 0,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False},
            "document": {"file_id": file_id, "file_name": file_name, "file_size": file_size},
        },
    }


def process(conn, cfg, upd, *, tg=None, llm=None, embedder=None, worker=None, **kwargs):
    """Mirrors `tests/test_v190_commands.py`'s `process`: a document update
    is auto-drained through `worker.run_one` (nothing this file's own
    tests rely on beyond text commands ever hits that branch)."""
    tg = tg if tg is not None else FakeTelegram()
    llm = llm if llm is not None else FakeLLM([])
    if worker is None:
        worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)
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
        **kwargs,
    )
    message = upd.get("message")
    if isinstance(message, dict) and isinstance(message.get("document"), dict):
        sender = message.get("from") or {}
        from_id = sender.get("id")
        if worker.in_flight(from_id) is not None:
            worker.run_one(conn=conn)
    return tg


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


def _add_document_with_id(conn, doc_id, user_id, **overrides):
    """T-V1111-TAB-01's own mechanism: `storage.add_document` has no `id=`
    parameter (it always trusts `cursor.lastrowid`), so pinning a specific
    5-digit id without inserting 12344 filler rows means one raw `INSERT`
    naming `documents.id` explicitly -- SQLite honours an explicit rowid on
    an `INTEGER PRIMARY KEY AUTOINCREMENT` column."""
    fields = {
        "filename": "third.txt",
        "file_type": "txt",
        "created_at": NOW,
        "size_bytes": 100,
        "text_chars": 100,
        "page_count": None,
        "chunk_count": 1,
        "sha256": "y" * 8,
    }
    fields.update(overrides)
    conn.execute(
        "INSERT INTO documents "
        "(id, user_id, filename, file_type, created_at, size_bytes, text_chars, "
        " page_count, chunk_count, sha256) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            doc_id,
            user_id,
            fields["filename"],
            fields["file_type"],
            fields["created_at"],
            fields["size_bytes"],
            fields["text_chars"],
            fields["page_count"],
            fields["chunk_count"],
            fields["sha256"],
        ),
    )


def _read_readme() -> str:
    return (REPO_ROOT / "README.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# T-V1111-TAB-01 -- /documents ids render whole up to 99,999
# --------------------------------------------------------------------------


def test_t_v1111_tab_01_documents_id_width_five_round_trip(tmp_path):
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
    long_name = "f" * 37 + ".md"
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
    _add_document_with_id(conn, 12345, USER_ID, created_at="2026-01-07T00:00:00Z")

    tg = process(conn, cfg, text_update("/documents"))
    assert len(tg.sent) == 1
    assert tg.sent_payloads[-1].get("parse_mode") == "HTML"
    raw = tg.sent[0][1]
    assert raw.startswith("<pre>") and raw.endswith("</pre>")
    body = html.unescape(raw[len("<pre>") : -len("</pre>")])

    assert "12345" in body
    truncated = "f" * 21 + "…"
    assert truncated in body
    assert "f" * 23 + "…" not in body
    for line in body.splitlines():
        assert tables.utf16_length(line) <= 72

    before_count = storage.document_count(conn, user_id=USER_ID)
    tg2 = process(conn, cfg, text_update("/delete #12345", update_id=2))
    assert tg2.sent == [(USER_ID, "Deleted #12345.")]
    assert storage.document_count(conn, user_id=USER_ID) == before_count - 1
    conn.close()


# --------------------------------------------------------------------------
# T-V1111-TAB-02 -- README's /documents sample, byte-equal
# --------------------------------------------------------------------------


def test_t_v1111_tab_02_readme_documents_sample_byte_equal():
    readme_text = _read_readme()
    assert "cut to 21 UTF-16 units" in readme_text
    assert "23 UTF-16 units" not in readme_text

    heading_idx = readme_text.index("### `/documents`")
    fence_start = readme_text.index("```", heading_idx)
    fence_body_start = fence_start + 3
    fence_end = readme_text.index("```", fence_body_start)
    sample = readme_text[fence_body_start:fence_end].strip("\n")

    rows = [
        (1, "report.pdf", "pdf", "1.5 MB", 7, 42, "2026-01-05"),
        (2, "f" * 37 + ".md", "md", "12.3 KB", 3, None, "2026-01-06"),
    ]
    table = tables.render_table(
        ["#", "file", "type", "size", "chunks", "pages", "added"],
        rows,
        max_width=[5, 22, 4, 8, 6, 5, 10],
    )
    expected = f"Your documents (2 of {documents.DOCUMENT_LIMIT}):\n\n{table}"
    assert sample == expected


# --------------------------------------------------------------------------
# T-V1111-TAB-03 -- /model status label never truncates
# --------------------------------------------------------------------------


def test_t_v1111_tab_03_model_status_label_whole(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = process(conn, cfg, text_update("/model"))
    payload = tg.sent_payloads[0]
    body = payload["text"]
    assert body.startswith("<pre>") and body.endswith("</pre>")
    inner = body[len("<pre>") : -len("</pre>")]

    assert "openrouter model" in inner
    assert "lmstudio model" in inner
    for line in inner.splitlines():
        assert "…" not in line[:16]  # the field column, never truncated
        assert tables.utf16_length(line) <= 72
    conn.close()

    long_model = "o" * 45
    conn2 = new_conn(tmp_path, name="b.db")
    cfg2 = make_cfg(tmp_path, openrouter_model=long_model, db_path=tmp_path / "b.db")
    tg2 = process(conn2, cfg2, text_update("/model", update_id=2))
    inner2 = tg2.sent_payloads[0]["text"][len("<pre>") : -len("</pre>")]
    assert "openrouter model" in inner2
    assert "o" * 39 + "…" in inner2
    assert "o" * 40 not in inner2
    for line in inner2.splitlines():
        assert "…" not in line[:16]
        assert tables.utf16_length(line) <= 72
    conn2.close()


# --------------------------------------------------------------------------
# T-V1111-TAB-04 -- /sessions with no sessions replies on the plain path
# --------------------------------------------------------------------------


def test_t_v1111_tab_04_sessions_empty_plain(tmp_path):
    assert bot.SESSIONS_EMPTY_REPLY == "No sessions yet. Send me a message to start one."

    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = process(conn, cfg, text_update("/sessions"))
    assert tg.sent == [(USER_ID, bot.SESSIONS_EMPTY_REPLY)]
    assert "parse_mode" not in tg.sent_payloads[0]

    conv_id = storage.start_new_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv_id, "hello there")
    tg2 = process(conn, cfg, text_update("/sessions", update_id=2))
    assert tg2.sent_payloads[-1].get("parse_mode") == "HTML"
    raw = tg2.sent[-1][1]
    assert raw.startswith("<pre>") and raw.endswith("</pre>")
    body = html.unescape(raw[len("<pre>") : -len("</pre>")])
    lines = body.splitlines()
    assert len(lines) == 3  # header, rule, one data row
    conn.close()

    readme_text = _read_readme()
    assert bot.SESSIONS_EMPTY_REPLY in readme_text


# --------------------------------------------------------------------------
# T-V1111-TAB-05 -- DOC_LIMIT_REPLY names both /delete forms
# --------------------------------------------------------------------------


def test_t_v1111_tab_05_doc_limit_reply_names_both_forms(tmp_path):
    assert bot.DOC_LIMIT_REPLY == (
        "Limit of 20 documents reached. Use /delete <filename> or /delete #<id>."
    )

    # (a) pre-admission: a caller already at 20 documents uploading a 21st
    # -- `_handle_document`'s own `at_limit` check, before any enqueue.
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    for i in range(20):
        _add_document(conn, USER_ID, filename=f"doc{i}.txt")
    before_count = storage.document_count(conn, user_id=USER_ID)
    tg = FakeTelegram()
    embedder = FakeEmbedder(dim=16)
    worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)
    bot.process_update(
        document_update(file_name="new.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        llm=FakeLLM([]),
        skills={},
        runner=RecordingRunner(),
        bot_username=BOT_USERNAME,
        embedder=embedder,
        worker=worker,
    )
    assert tg.sent == [(USER_ID, bot.DOC_LIMIT_REPLY)]
    assert tg.edited == []
    assert worker.in_flight(USER_ID) is None
    assert storage.document_count(conn, user_id=USER_ID) == before_count
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
    conn.close()

    # (b) admitted at 19 documents; the 20th lands via `storage` directly
    # (another upload's own commit) strictly between this job's admission
    # and its own commit -- `IngestWorker`'s `DocumentLimitExceededError`
    # branch (the executor's mechanism this task records: no thread race,
    # a plain out-of-band `storage.add_document` call between `reserve`/
    # `enqueue` and `run_one`).
    conn2 = new_conn(tmp_path, name="b.db")
    cfg2 = make_cfg(tmp_path, db_path=tmp_path / "b.db")
    for i in range(19):
        _add_document(conn2, USER_ID, filename=f"pre{i}.txt")
    before_count2 = storage.document_count(conn2, user_id=USER_ID)
    tg2 = FakeTelegram()
    tg2.files["documents/f1"] = b"Some readable document text, well over twenty chars."
    embedder2 = FakeEmbedder(dim=16)
    worker2 = bot.IngestWorker(cfg2, tg2, embedder2, cfg2.db_path)
    bot.process_update(
        document_update(file_name="race.txt"),
        conn=conn2,
        tg=tg2,
        cfg=cfg2,
        llm=FakeLLM([]),
        skills={},
        runner=RecordingRunner(),
        bot_username=BOT_USERNAME,
        embedder=embedder2,
        worker=worker2,
    )
    assert worker2.in_flight(USER_ID) is not None  # admitted: 19 < 20

    _add_document(conn2, USER_ID, filename="raced-in.txt")  # the 20th, out of band
    worker2.run_one(conn=conn2)
    assert tg2.edited and tg2.edited[-1][2] == bot.DOC_LIMIT_REPLY
    assert worker2.in_flight(USER_ID) is None
    assert storage.document_count(conn2, user_id=USER_ID) == before_count2 + 1  # only the race doc
    assert conn2.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    assert conn2.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
    conn2.close()

    readme_text = _read_readme()
    assert bot.DOC_LIMIT_REPLY in readme_text


# --------------------------------------------------------------------------
# T-V1111-TAB-06 -- one embedding batch constant
# --------------------------------------------------------------------------


def _sixty_five_chunk_text() -> str:
    # Same shape as `tests/test_v1110_ing.py`'s own `EMBED_BATCH_SIZE`-patch
    # fixture (3 paragraphs -> 3 chunks), scaled to 65 paragraphs -> 65
    # chunks -- each paragraph is just under `chunk_text`'s own `target`
    # (1000 chars) so no two merge, and well over its `minimum` (50 chars)
    # so the last one never merges backward either.
    base = "Sentence number with enough words to take up real space in the paragraph. "
    paragraphs = [f"Section {i}: " + (base * 12)[:900] for i in range(65)]
    return "\n\n".join(paragraphs)


def test_t_v1111_tab_06_single_batch_constant(tmp_path):
    assert not hasattr(documents, "EMBED_BATCH_SIZE")
    assert documents.BATCH_SIZE is embeddings.BATCH_SIZE
    assert documents.BATCH_SIZE == 32

    text = _sixty_five_chunk_text()
    assert len(documents.chunk_text(text)) == 65

    # (a) a size-recording FakeEmbedder, through IngestWorker.run_one.
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = text.encode("utf-8")
    embedder = FakeEmbedder(dim=16)
    worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)
    bot._handle_document(
        document_update(file_name="big.txt")["message"]["document"],
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=embedder,
        worker=worker,
    )
    worker.run_one(conn=conn)
    assert [len(texts) for texts, _conv_id in embedder.calls] == [32, 32, 1]
    progress_texts = [edit_text for _chat, _mid, edit_text in tg.edited]
    assert "📄 embedding: 1/3" in progress_texts
    assert "📄 embedding: 2/3" in progress_texts
    assert "📄 embedding: 3/3" in progress_texts
    conn.close()

    # (b) the HTTP-call invariant, not inferred: a real EmbeddingsClient
    # over httpx.MockTransport, through the ingest pipeline directly
    # (`documents.index_document`).
    seen_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        inputs = body["input"]
        seen_sizes.append(len(inputs))
        entries = [{"index": i, "embedding": [0.0] * 16} for i in range(len(inputs))]
        return httpx.Response(200, json={"data": entries})

    client = embeddings.EmbeddingsClient(
        "http://localhost:1234/v1",
        "embed-m",
        16,
        5.0,
        httpx.Client(transport=mock_llm_transport(handler)),
    )
    conn2 = new_conn(tmp_path, name="b.db")
    progress_calls: list[str] = []
    documents.index_document(
        conn2,
        user_id=USER_ID,
        filename="big2.txt",
        data=text.encode("utf-8"),
        embedder=client,
        progress=progress_calls.append,
        now=NOW,
        started_at=0.0,
        monotonic=lambda: 0.0,
    )
    assert seen_sizes == [32, 32, 1]
    assert "📄 embedding: 1/3" in progress_calls
    assert "📄 embedding: 2/3" in progress_calls
    assert "📄 embedding: 3/3" in progress_calls
    conn2.close()

    readme_text = _read_readme()
    assert "llm.embeddings.BATCH_SIZE" in readme_text
    assert "documents.EMBED_BATCH_SIZE" not in readme_text
