"""spec-v1.11.0 T5 (docs/spec/spec-v1.11.0.md Sec.9, REQ-V1110-ING-01..05):
the caps rise, `IngestWorker` (its two-phase admission, its own lazily-
acquired connection, cooperative cancel, the job phase, shutdown's drain
and sentinel) and the loop/worker split of the document flow.

Offline and deterministic throughout: `tests.fakes.FakeTelegram`/
`FakeEmbedder` stand in for Telegram and the embeddings endpoint (except
`T-V1110-ING-07`, which proves the streamed-cancel clause at the *real*
`TelegramClient.download_file` boundary through `httpx.MockTransport`, no
socket either way). No test sleeps or asserts timing (ING-02's own
instruction): every job is driven synchronously through `run_one()`, a
`FakeEmbedder` hook parks a job at a precise point when a test needs to
inspect mid-flight state, the `before_commit` callable is wrapped the same
way for the commit-phase pause, and the two tests that do start a real
`_run` thread (`T-V1110-ING-02`, `T-V1110-ING-11`) join it with a bounded
timeout as a hang guard, never a timing assertion.
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

import httpx
import pytest
import sqlite_vec

import bot
import config
import documents
import storage
from tests.fakes import FakeEmbedder, FakeLLM, FakeTelegram, RecordingRunner

TOKEN = "123456789:sentinel-telegram-token-for-v1110-ing-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
_REPO_ROOT = Path(__file__).resolve().parents[1]


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
        "allowed_tg_ids": frozenset({USER_ID, USER_ID + 1, USER_ID + 2, USER_ID + 3, USER_ID + 4}),
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "m",
        "openrouter_api_key": "",
        "openrouter_model": "",
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        # Matches `new_conn`'s own default filename: several tests exercise
        # `run_one(conn=None)`, which acquires its own connection via
        # `storage.connect(cfg.db_path)` -- that must be the same,
        # already-schema-initialized file `new_conn(tmp_path)` built, not
        # a fresh, un-initialized one.
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


_GOOD_TEXT = b"Enough readable text content here to produce exactly one chunk for storage."


def _doc(file_id="f1", filename="notes.txt", file_size=20):
    return {"file_id": file_id, "file_name": filename, "file_size": file_size}


def text_update(text, *, user_id=USER_ID, update_id=1):
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


def process(conn, cfg, upd, *, tg, llm=None, embedder=None, worker=None):
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


class _LockSpy:
    """Wraps a real `threading.Lock` and counts `with spy:` entries, so a
    test can prove a section of code actually acquired the lock (not just
    that it wasn't left held afterward, which every correct -- and every
    lock-free -- implementation satisfies equally)."""

    def __init__(self, real_lock):
        self._real = real_lock
        self.enter_count = 0

    def __enter__(self):
        self.enter_count += 1
        return self._real.__enter__()

    def __exit__(self, *exc_info):
        return self._real.__exit__(*exc_info)

    def locked(self):
        return self._real.locked()


def _tracking_connect(db_path, *, calls):
    """A `storage.connect`-alike that records the acquiring thread and,
    via a `factory=`-supplied `sqlite3.Connection` subclass, the thread
    that later closes it -- `close()` cannot be proven by inspecting the
    connection from the wrong thread (`check_same_thread` would itself
    raise), so this is the only reliable way to observe it."""
    record = {"opened_by": threading.get_ident(), "closed_by": None}
    calls.append(record)

    class _Tracked(sqlite3.Connection):
        def close(self):
            record["closed_by"] = threading.get_ident()
            super().close()

    conn = sqlite3.connect(str(db_path), isolation_level=None, timeout=5.0, factory=_Tracked)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ----------------------------------------------------------------------------
# T-V1110-ING-01 -- the caps and the one surviving `find` line.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_01_caps_and_find_line(tmp_path):
    assert bot.DOCUMENT_MAX_BYTES == 20_000_000
    assert documents.MAX_EXTRACTED_TEXT_CHARS == 2_000_000
    assert documents.PDF_MAX_PAGES == 2_000
    assert documents.INDEX_BUDGET_S_DEFAULT == 1800.0
    assert documents.DOCUMENT_LIMIT == 20
    # DOCX archive bounds: unchanged this task.
    assert documents.DOCX_MAX_MEMBERS == 2_000
    assert documents.DOCX_MAX_TOTAL_UNCOMPRESSED_BYTES == 50 * 1024 * 1024
    assert documents.DOCX_MAX_MEMBER_UNCOMPRESSED_BYTES == 20 * 1024 * 1024
    assert documents.DOCX_MAX_COMPRESSION_RATIO == 100

    bot_py = (_REPO_ROOT / "bot.py").read_text(encoding="utf-8")
    find_line = "    if isinstance(file_size, int) and file_size > DOCUMENT_MAX_BYTES:\n"
    assert bot_py.count(find_line) == 1

    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    worker = bot.IngestWorker(cfg, tg, FakeEmbedder(dim=16), cfg.db_path)

    # 20,000,001 -- refused before getFile, no Telegram call at all.
    bot._handle_document(
        _doc(file_size=bot.DOCUMENT_MAX_BYTES + 1),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )
    assert tg.sent == [(USER_ID, "File too large (over 20 MB).")]
    assert tg.get_file_calls == []
    assert worker.in_flight(USER_ID) is None

    # 20,000,000 -- accepted by the pre-check (proceeds to getFile).
    tg2 = FakeTelegram()
    tg2.files["documents/f1"] = _GOOD_TEXT
    worker2 = bot.IngestWorker(cfg, tg2, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(file_size=bot.DOCUMENT_MAX_BYTES),
        conn=conn,
        tg=tg2,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker2,
    )
    worker2.run_one(conn=conn)
    assert tg2.get_file_calls == ["f1"]
    assert any(text == "File too large (over 20 MB)." for _c, text in tg2.sent) is False

    # A 20,000,001-byte stream (file_size unreported, so the pre-check is
    # skipped) -- the mid-stream cap in `TelegramClient.download_file`
    # fires via `DocumentTooLarge`, mapped to the same string.
    tg3 = FakeTelegram()
    tg3.files["documents/f1"] = b"x" * (bot.DOCUMENT_MAX_BYTES + 1)
    worker3 = bot.IngestWorker(cfg, tg3, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        {"file_id": "f1", "file_name": "big.txt"},
        conn=conn,
        tg=tg3,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker3,
    )
    worker3.run_one(conn=conn)
    # The status message already exists ("📄 received") -- the error ending
    # is an edit, not a new send.
    assert tg3.edited and tg3.edited[-1][2] == "File too large (over 20 MB)."
    conn.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-02 -- the worker split; the worker-owned, thread-affine
# connection; the queue's five physical slots; no typing indicator.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_02_worker_split_and_thread_owned_connection(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    embedder = FakeEmbedder(dim=16)
    tg = FakeTelegram()
    tg.files["documents/f1"] = _GOOD_TEXT
    tg.files["documents/f2"] = _GOOD_TEXT
    worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)

    index_calls = []
    real_index_document = documents.index_document

    def spy_index_document(*a, **k):
        index_calls.append(1)
        return real_index_document(*a, **k)

    monkeypatch.setattr(documents, "index_document", spy_index_document)

    typing_constructed = []
    real_typing_init = bot._TypingIndicator.__init__

    def spy_typing_init(self, *a, **k):
        typing_constructed.append(1)
        real_typing_init(self, *a, **k)

    monkeypatch.setattr(bot._TypingIndicator, "__init__", spy_typing_init)

    lock_spy = _LockSpy(worker._lock)
    worker._lock = lock_spy

    # -- the split: the loop thread only reserves, sends status, enqueues --
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=embedder,
        worker=worker,
    )
    assert tg.sent == [(USER_ID, "📄 received")]
    assert tg.get_file_calls == []
    assert index_calls == []
    assert worker.in_flight(USER_ID) is not None
    assert worker._queue.maxsize == bot.INGEST_QUEUE_MAX + 1
    # reserve()/enqueue() actually acquired the lock (ING-02/-03), not
    # just left it unheld afterward.
    assert lock_spy.enter_count >= 2

    connect_calls: list[dict] = []

    def spy_connect(db_path):
        return _tracking_connect(db_path, calls=connect_calls)

    monkeypatch.setattr(storage, "connect", spy_connect)

    # -- run_one(conn) with a test-supplied connection: storage.connect
    # is never called for this job, and index_document/getFile now run. --
    worker.run_one(conn=conn)
    assert connect_calls == []
    assert tg.get_file_calls == ["f1"]
    assert index_calls == [1]
    assert worker.in_flight(USER_ID) is None
    assert any(text.startswith("✅ notes.txt:") for _c, text in tg.sent)
    assert typing_constructed == []

    # -- run_one(conn=None): acquires the worker-owned connection on the
    # calling (here, the test) thread, and the second job actually
    # completes (not merely "index_document was called"). --
    bot._handle_document(
        _doc(file_id="f2", filename="notes2.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID + 1,
        from_id=USER_ID + 1,
        embedder=embedder,
        worker=worker,
    )
    worker.run_one(conn=None)
    assert len(connect_calls) == 1
    assert connect_calls[0]["opened_by"] == threading.get_ident()
    assert index_calls == [1, 1]
    assert any(text.startswith("✅ notes2.txt:") for _c, text in tg.sent)
    worker.close()
    assert connect_calls[0]["closed_by"] == threading.get_ident()
    conn.close()

    # -- a real `_run` thread: enqueue two jobs, drain both, shutdown(),
    # join with a bounded timeout (a hang guard, never a timing
    # assertion): the thread exits, the connection was acquired exactly
    # once and closed, both on the worker thread, never the test thread. --
    conn3 = new_conn(tmp_path, name="c.db")
    cfg3 = make_cfg(tmp_path, db_path=tmp_path / "c.db")
    tg3 = FakeTelegram()
    tg3.files["documents/f1"] = _GOOD_TEXT
    tg3.files["documents/f2"] = _GOOD_TEXT
    worker3 = bot.IngestWorker(cfg3, tg3, embedder, cfg3.db_path)

    connect_calls3: list[dict] = []

    def spy_connect3(db_path):
        return _tracking_connect(db_path, calls=connect_calls3)

    monkeypatch.setattr(storage, "connect", spy_connect3)

    bot._handle_document(
        _doc(),
        conn=conn3,
        tg=tg3,
        cfg=cfg3,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=embedder,
        worker=worker3,
    )
    bot._handle_document(
        _doc(file_id="f2", filename="notes2.txt"),
        conn=conn3,
        tg=tg3,
        cfg=cfg3,
        chat_id=USER_ID + 1,
        from_id=USER_ID + 1,
        embedder=embedder,
        worker=worker3,
    )
    thread = threading.Thread(target=worker3._run, daemon=True)
    thread.start()
    worker3._queue.join()
    assert worker3.in_flight(USER_ID) is None
    assert worker3.in_flight(USER_ID + 1) is None
    assert any(t.startswith("✅ notes.txt:") for _c, t in tg3.sent)
    assert any(t.startswith("✅ notes2.txt:") for _c, t in tg3.sent)
    worker3.shutdown()  # the sentinel: consumes no user slot, no token
    thread.join(timeout=5.0)
    assert not thread.is_alive()
    assert len(connect_calls3) == 1
    assert connect_calls3[0]["opened_by"] == thread.ident
    assert connect_calls3[0]["closed_by"] == thread.ident  # _run's own finally
    assert thread.ident != threading.get_ident()
    assert typing_constructed == []
    conn3.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-03 -- one in-flight job per user; a second upload refused.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_03_second_upload_refused(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    embedder = FakeEmbedder(dim=16)
    tg = FakeTelegram()
    tg.files["documents/f1"] = _GOOD_TEXT
    tg.files["documents/f2"] = _GOOD_TEXT
    tg.files["documents/v1"] = _GOOD_TEXT
    worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)

    bot._handle_document(
        _doc(filename="first.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=embedder,
        worker=worker,
    )
    assert worker._queue.qsize() == 1

    # Same user, second upload while the first is still queued -- refused.
    bot._handle_document(
        _doc(file_id="f2", filename="second.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=embedder,
        worker=worker,
    )
    assert tg.sent[-1] == (USER_ID, "⏳ Still indexing first.txt; wait for it to finish.")
    assert worker._queue.qsize() == 1  # nothing enqueued for the refusal

    # A different user's upload is accepted normally.
    other_id = USER_ID + 1
    bot._handle_document(
        _doc(file_id="v1", filename="visitor.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=other_id,
        from_id=other_id,
        embedder=embedder,
        worker=worker,
    )
    assert worker.in_flight(other_id) is not None
    assert worker._queue.qsize() == 2

    # After the first job completes, the same user's next upload is
    # accepted again.
    worker.run_one(conn=conn)  # drains first.txt (FIFO)
    assert worker.in_flight(USER_ID) is None
    bot._handle_document(
        _doc(file_id="f2", filename="second.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=embedder,
        worker=worker,
    )
    assert worker.in_flight(USER_ID) is not None
    conn.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-04 -- the four-token queue fills up.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_04_queue_full(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    embedder = FakeEmbedder(dim=16)
    tg = FakeTelegram()
    worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)

    for i in range(bot.INGEST_QUEUE_MAX):
        user = USER_ID + i
        bot._handle_document(
            _doc(file_id=f"f{i}", filename=f"doc{i}.txt"),
            conn=conn,
            tg=tg,
            cfg=cfg,
            chat_id=user,
            from_id=user,
            embedder=embedder,
            worker=worker,
        )
    assert worker._queue.qsize() == bot.INGEST_QUEUE_MAX
    assert worker._queue.maxsize - worker._queue.qsize() >= 1  # the fifth slot is still free

    fifth_user = USER_ID + bot.INGEST_QUEUE_MAX
    bot._handle_document(
        _doc(file_id="last", filename="last.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=fifth_user,
        from_id=fifth_user,
        embedder=embedder,
        worker=worker,
    )
    assert tg.sent[-1] == (fifth_user, "Indexing queue is full; try again later.")
    # No status message for the refused user: the refusal is the *only*
    # thing ever sent to them (row 7 -- "no status message").
    assert [text for chat_id, text in tg.sent if chat_id == fifth_user] == [
        "Indexing queue is full; try again later."
    ]
    assert worker.in_flight(fifth_user) is None
    assert worker._queue.qsize() == bot.INGEST_QUEUE_MAX
    conn.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-05 -- cancel mid-embedding; /cancel's two plain outcomes; a
# `run_one` job that raises ends with DOC_HANDLER_FAILED_REPLY.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_05_cancel_mid_embedding(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    # Three paragraphs, each just under `target` (1000) so no two merge
    # into one chunk -- `chunk_text` produces exactly 3 chunks (verified
    # directly below). `EMBED_BATCH_SIZE` is patched to 1 so each chunk is
    # its own embed() call/batch -- "after batch 1/3" is then a real,
    # distinct checkpoint, not the only batch there is.
    base = "Sentence number with enough words to take up real space in the paragraph. "
    paragraphs = [f"Section {i}: " + (base * 12)[:900] for i in range(3)]
    text = "\n\n".join(paragraphs)
    assert len(documents.chunk_text(text)) == 3
    tg.files["documents/f1"] = text.encode("utf-8")
    monkeypatch.setattr(documents, "EMBED_BATCH_SIZE", 1)

    embedder = FakeEmbedder(dim=16)
    worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=embedder,
        worker=worker,
    )
    job = worker.in_flight(USER_ID)
    assert job is not None

    def hook(call_no):
        if call_no == 1:
            job.cancel.set()

    embedder._hook = hook

    worker.run_one(conn=conn)
    # Exactly one embed() call ran -- batches 2/3 never happened, proving
    # the checkpoint right after batch 1 is what stopped it, not some
    # later, incidental checkpoint.
    assert len(embedder.calls) == 1
    assert storage.document_count(conn, user_id=USER_ID) == 0
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM vec_chunks").fetchone()[0] == 0
    assert tg.edited and tg.edited[-1][2] == "❌ Cancelled."
    assert worker.in_flight(USER_ID) is None

    # `/cancel` with a running job -> "Cancelling <name>...".
    tg2 = FakeTelegram()
    tg2.files["documents/f1"] = _GOOD_TEXT
    worker2 = bot.IngestWorker(cfg, tg2, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg2,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker2,
    )
    running_job = worker2.in_flight(USER_ID)
    running_job.phase = "running"
    process(conn, cfg, text_update("/cancel"), tg=tg2, worker=worker2)
    assert tg2.sent[-1] == (USER_ID, "Cancelling notes.txt…")
    assert running_job.cancel.is_set()

    # `/cancel` with nothing in flight -> "Nothing to cancel."
    tg3 = FakeTelegram()
    worker3 = bot.IngestWorker(cfg, tg3, FakeEmbedder(dim=16), cfg.db_path)
    process(conn, cfg, text_update("/cancel"), tg=tg3, worker=worker3)
    assert tg3.sent == [(USER_ID, "Nothing to cancel.")]

    # A `run_one` whose job raises an unexpected exception: ends with
    # DOC_HANDLER_FAILED_REPLY, slot freed, task_done called, the worker
    # keeps going for the next job.
    tg4 = FakeTelegram()
    tg4.files["documents/f1"] = _GOOD_TEXT
    tg4.files["documents/f2"] = _GOOD_TEXT
    worker4 = bot.IngestWorker(cfg, tg4, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg4,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker4,
    )

    def boom_get_file(_file_id):
        raise RuntimeError("boom")

    real_get_file = tg4.get_file
    tg4.get_file = boom_get_file
    worker4.run_one(conn=conn)
    assert tg4.edited and tg4.edited[-1][2] == "Something went wrong while processing the document."
    assert worker4.in_flight(USER_ID) is None
    assert worker4._queue.unfinished_tasks == 0
    tg4.get_file = real_get_file  # only the first job's getFile call raises

    bot._handle_document(
        _doc(file_id="f2", filename="second.txt"),
        conn=conn,
        tg=tg4,
        cfg=cfg,
        chat_id=USER_ID + 1,
        from_id=USER_ID + 1,
        embedder=FakeEmbedder(dim=16),
        worker=worker4,
    )
    worker4.run_one(conn=conn)
    assert any(text.startswith("✅ second.txt:") for _c, text in tg4.sent)
    conn.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-06 -- cancelled while queued: dequeue edits status directly,
# no Telegram file call.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_06_queued_cancel_no_getfile(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    worker = bot.IngestWorker(cfg, tg, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )
    process(conn, cfg, text_update("/cancel"), tg=tg, worker=worker)
    assert tg.sent[-1] == (USER_ID, "Cancelling notes.txt…")

    worker.run_one(conn=conn)
    assert tg.edited and tg.edited[-1][2] == "❌ Cancelled."
    assert tg.get_file_calls == []
    assert "documents/f1" not in [fp for fp, _mb in tg.downloads]
    assert storage.document_count(conn, user_id=USER_ID) == 0
    assert worker.in_flight(USER_ID) is None
    conn.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-07 -- cancelled during a real streamed download; budget
# exhaustion at the same point.
# ----------------------------------------------------------------------------


def _mock_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_t_v1110_ing_07_cancel_during_download():
    def handler(_request):
        def gen():
            yield b"a" * 1000
            yield b"b" * 1000
            yield b"c" * 1000

        return httpx.Response(200, content=gen())

    tg = bot.TelegramClient(TOKEN, client=_mock_client(handler))
    cancel = threading.Event()
    calls = []

    def should_stop():
        calls.append(1)
        if len(calls) == 1:
            cancel.set()
        return cancel.is_set()

    result = tg.download_file("documents/f1", max_bytes=10_000, should_stop=should_stop)
    assert result is None
    assert len(calls) >= 1

    # Budget exhausted at the same point: `should_stop` reports True when
    # the budget, not the cancel event, has fired -- same outcome (`None`).
    calls2 = []

    def should_stop_budget():
        calls2.append(1)
        return True  # budget exhausted from the first check

    result2 = tg.download_file("documents/f1", max_bytes=10_000, should_stop=should_stop_budget)
    assert result2 is None


def test_t_v1110_ing_07_worker_maps_stream_cancel_to_cancelled_status(tmp_path, monkeypatch):
    """The worker-level half: `download_file` returning `None` leads to
    the post-download `_check_cancel_budget` raising, extraction never
    reached, nothing stored, status `❌ Cancelled.`"""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = _GOOD_TEXT
    worker = bot.IngestWorker(cfg, tg, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )
    job = worker.in_flight(USER_ID)

    real_download = tg.download_file

    def fake_download(*a, **k):
        job.cancel.set()  # simulate should_stop() having fired mid-stream
        return

    tg.download_file = fake_download

    extract_calls = []
    real_extract = documents.extract

    def spy_extract(*a, **k):
        extract_calls.append(1)
        return real_extract(*a, **k)

    monkeypatch.setattr(documents, "extract", spy_extract)

    worker.run_one(conn=conn)
    assert extract_calls == []
    assert storage.document_count(conn, user_id=USER_ID) == 0
    assert tg.edited and tg.edited[-1][2] == "❌ Cancelled."
    tg.download_file = real_download
    conn.close()


def test_t_v1110_ing_07_worker_maps_stream_budget_exceeded_to_timeout_status(tmp_path, monkeypatch):
    """Budget exhausted at the same point (not cancelled): `download_file`
    returning `None` still leads to the post-download `_check_cancel_
    budget` raising -- `IndexBudgetExceeded` this time, not `Index
    Cancelled`, since the job's own cancel event was never set -- and the
    same "extraction never reached, nothing stored" outcome, but with the
    budget-exceeded reply."""
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = _GOOD_TEXT
    worker = bot.IngestWorker(cfg, tg, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )
    job = worker.in_flight(USER_ID)

    real_download = tg.download_file

    def fake_download(*a, **k):
        # simulate should_stop() having fired because the budget, not the
        # cancel event, is exhausted -- push started_at far enough into
        # the past that the post-download checkpoint sees it as spent.
        job.started_at = job.monotonic() - (documents.INDEX_BUDGET_S_DEFAULT + 1.0)
        return

    tg.download_file = fake_download

    extract_calls = []
    real_extract = documents.extract

    def spy_extract(*a, **k):
        extract_calls.append(1)
        return real_extract(*a, **k)

    monkeypatch.setattr(documents, "extract", spy_extract)

    worker.run_one(conn=conn)
    assert extract_calls == []
    assert job.cancel.is_set() is False  # budget, not cancel, is what fired
    assert storage.document_count(conn, user_id=USER_ID) == 0
    assert tg.edited and tg.edited[-1][2] == "Indexing timed out (over 1800 s). Nothing was saved."
    tg.download_file = real_download
    conn.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-08 -- a connection-acquisition failure releases the slot.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_08_connect_failure_releases_slot(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = _GOOD_TEXT
    tg.files["documents/f2"] = _GOOD_TEXT
    worker = bot.IngestWorker(cfg, tg, FakeEmbedder(dim=16), cfg.db_path)

    conn_outer = new_conn(tmp_path)
    bot._handle_document(
        _doc(),
        conn=conn_outer,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )
    bot._handle_document(
        _doc(file_id="f2", filename="second.txt"),
        conn=conn_outer,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID + 1,
        from_id=USER_ID + 1,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )

    real_connect = storage.connect
    attempts = []

    def flaky_connect(db_path):
        attempts.append(1)
        if len(attempts) == 1:
            raise sqlite3.OperationalError("boom")
        return real_connect(db_path)

    monkeypatch.setattr(storage, "connect", flaky_connect)

    worker.run_one(conn=None)  # first job: storage.connect raises
    assert tg.get_file_calls == []
    assert tg.edited and tg.edited[-1][2] == "Something went wrong while processing the document."
    assert worker.in_flight(USER_ID) is None
    assert worker._queue.unfinished_tasks == 1  # second job still pending
    # The freed slot lets USER_ID upload again immediately.
    bot._handle_document(
        _doc(file_id="f3", filename="third.txt"),
        conn=conn_outer,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )
    assert worker.in_flight(USER_ID) is not None

    worker.run_one(conn=None)  # second job: connect succeeds now
    assert tg.get_file_calls == ["f2"]
    assert any(text.startswith("✅ second.txt:") for _c, text in tg.sent)
    assert len(attempts) == 2
    worker.close()
    conn_outer.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-09 -- cancel during the commit phase: too late, the commit
# proceeds; a running job still cancels normally; phase read under lock.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_09_cancel_in_commit_phase(tmp_path, monkeypatch):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = _GOOD_TEXT
    worker = bot.IngestWorker(cfg, tg, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )
    job = worker.in_flight(USER_ID)

    lock_spy = _LockSpy(worker._lock)
    worker._lock = lock_spy

    real_index_document = documents.index_document

    def spy_index_document(*a, before_commit=None, **k):
        def wrapped():
            before_commit()  # the worker's real callable: phase -> committing
            assert job.phase == "committing"
            enter_count_before = lock_spy.enter_count
            # Driven through the real dispatch chain (process_update's own
            # "/cancel" branch), not by calling _handle_cancel directly --
            # this is what proves the dispatch wiring itself, not just the
            # handler function, routes to the worker's cancel().
            process(conn, cfg, text_update("/cancel"), tg=tg, worker=worker)
            # cancel()'s phase read+mutation happened under the lock.
            assert lock_spy.enter_count > enter_count_before

        return real_index_document(*a, before_commit=wrapped, **k)

    monkeypatch.setattr(documents, "index_document", spy_index_document)

    worker.run_one(conn=conn)
    # `/cancel`'s reply lands before the eventual success reply -- both go
    # through `_send`, so membership, not `[-1]`, is what proves it fired.
    assert (USER_ID, "Indexing is already finishing.") in tg.sent
    assert job.cancel.is_set() is False
    assert storage.document_count(conn, user_id=USER_ID) == 1
    assert any(text.startswith("✅ notes.txt:") for _c, text in tg.sent)
    assert tg.edited == [] or tg.edited[-1][2] != "❌ Cancelled."
    assert worker.in_flight(USER_ID) is None
    # cancel() itself does not leave the lock held afterward.
    assert lock_spy.locked() is False

    # A running (not yet committing) job still cancels normally.
    tg2 = FakeTelegram()
    tg2.files["documents/f1"] = _GOOD_TEXT
    worker2 = bot.IngestWorker(cfg, tg2, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg2,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker2,
    )
    running_job = worker2.in_flight(USER_ID)
    running_job.phase = "running"
    process(conn, cfg, text_update("/cancel"), tg=tg2, worker=worker2)
    assert tg2.sent[-1] == (USER_ID, "Cancelling notes.txt…")
    assert running_job.cancel.is_set()
    conn.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-10 -- the reservation race between `reserve` and the status
# send.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_10_reservation_race_before_status_send(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = _GOOD_TEXT
    tg.files["documents/v1"] = _GOOD_TEXT
    worker = bot.IngestWorker(cfg, tg, FakeEmbedder(dim=16), cfg.db_path)

    other_id = USER_ID + 1
    paused = {"active": False}
    real_send_message = tg.send_message

    def hooked_send_message(chat_id, text):
        if paused["active"] and chat_id == USER_ID and text == "📄 received":
            paused["active"] = False
            # A second doc from U during the pause.
            bot._handle_document(
                _doc(file_id="f1", filename="second.txt"),
                conn=conn,
                tg=tg,
                cfg=cfg,
                chat_id=USER_ID,
                from_id=USER_ID,
                embedder=FakeEmbedder(dim=16),
                worker=worker,
            )
            # A doc from V.
            bot._handle_document(
                _doc(file_id="v1", filename="visitor.txt"),
                conn=conn,
                tg=tg,
                cfg=cfg,
                chat_id=other_id,
                from_id=other_id,
                embedder=FakeEmbedder(dim=16),
                worker=worker,
            )
        return real_send_message(chat_id, text)

    tg.send_message = hooked_send_message
    paused["active"] = True
    bot._handle_document(
        _doc(file_id="f1", filename="first.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )
    tg.send_message = real_send_message

    # The nested calls (U's refusal, V's own "📄 received") both complete
    # before the paused, outer "📄 received" send finally returns -- so the
    # refusal is not necessarily the last entry, only a present one.
    assert (USER_ID, "⏳ Still indexing first.txt; wait for it to finish.") in tg.sent
    assert worker.in_flight(other_id) is not None
    assert worker._queue.qsize() == 2  # U's first job + V's job

    # V's job is dequeued and completes -- V's slot/token freed, U's
    # reservation (now a job, "first.txt") is untouched.
    worker.run_one(conn=conn)
    assert worker.in_flight(other_id) is None
    assert worker.in_flight(USER_ID) is not None
    assert worker._queue.qsize() == 1

    # -- a second run: the status send raises `TelegramError` --
    tg2 = FakeTelegram()
    worker2 = bot.IngestWorker(cfg, tg2, FakeEmbedder(dim=16), cfg.db_path)

    def failing_send_message(chat_id, text):
        raise bot.TelegramError("boom")

    tg2.send_message = failing_send_message
    bot._handle_document(
        _doc(file_id="f1", filename="first.txt"),
        conn=conn,
        tg=tg2,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker2,
    )
    assert worker2.in_flight(USER_ID) is None
    assert worker2._queue.qsize() == 0
    assert not any(isinstance(entry, bot.IngestJob) for entry in worker2._in_flight.values())
    bot._handle_document(
        _doc(file_id="f1", filename="retry.txt"),
        conn=conn,
        tg=tg2,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker2,
    )
    conn.close()


# ----------------------------------------------------------------------------
# T-V1110-ING-11 -- shutdown drains queued jobs; a committing job finishes.
# ----------------------------------------------------------------------------


def test_t_v1110_ing_11_shutdown_drains_queued_jobs(tmp_path):
    conn = new_conn(tmp_path, name="a.db")
    cfg = make_cfg(tmp_path, db_path=tmp_path / "a.db")
    tg = FakeTelegram()
    for i in range(6):
        tg.files[f"documents/f{i}"] = _GOOD_TEXT

    park = threading.Event()
    released = threading.Event()

    def hook(call_no):
        if call_no == 1:  # only the first job (users[0], FIFO) ever embeds
            park.set()
            released.wait(timeout=5.0)

    embedder = FakeEmbedder(dim=16, hook=hook)
    worker = bot.IngestWorker(cfg, tg, embedder, cfg.db_path)

    users = [USER_ID + i for i in range(6)]
    # The first four fill the queue to capacity: 4 tokens, 4 queued jobs.
    for i in range(4):
        bot._handle_document(
            _doc(file_id=f"f{i}", filename=f"doc{i}.txt"),
            conn=conn,
            tg=tg,
            cfg=cfg,
            chat_id=users[i],
            from_id=users[i],
            embedder=embedder,
            worker=worker,
        )
    assert worker._queue.qsize() == 4

    thread = threading.Thread(target=worker._run, daemon=True)
    thread.start()
    assert park.wait(timeout=5.0)  # job 0 dequeued, running, parked mid-embed

    # Its token freed at dequeue (REQ-V1110-ING-02) -- a 5th, distinct user
    # can now be admitted even though job 0 is still in flight.
    bot._handle_document(
        _doc(file_id="f4", filename="doc4.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=users[4],
        from_id=users[4],
        embedder=embedder,
        worker=worker,
    )
    assert worker.in_flight(users[4]) is not None
    assert worker._queue.qsize() == 4  # jobs 1-3 still queued, plus the new one

    # A 6th reserve is refused: tokens are back at capacity (4) while the
    # physical queue still has its fifth, reserved slot.
    bot._handle_document(
        _doc(file_id="f5", filename="doc5.txt"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=users[5],
        from_id=users[5],
        embedder=embedder,
        worker=worker,
    )
    assert tg.sent[-1] == (users[5], "Indexing queue is full; try again later.")
    assert worker._queue.maxsize - worker._queue.qsize() >= 1

    worker.shutdown()
    assert worker._queue.qsize() <= worker._queue.maxsize  # put_nowait never raised queue.Full
    released.set()
    thread.join(timeout=5.0)
    assert not thread.is_alive()

    interrupted = [text for _c, _m, text in tg.edited if text == "❌ Interrupted by restart."]
    assert len(interrupted) == 5  # job 0 (running) + jobs 1-4 (queued)
    for user in users[:5]:
        assert worker.in_flight(user) is None
    assert worker._queue.qsize() == 0
    assert storage.document_count(conn, user_id=users[0]) == 0
    conn.close()


def test_t_v1110_ing_11_shutdown_lets_a_committing_job_finish(tmp_path):
    conn = new_conn(tmp_path)
    cfg = make_cfg(tmp_path)
    tg = FakeTelegram()
    tg.files["documents/f1"] = _GOOD_TEXT
    worker = bot.IngestWorker(cfg, tg, FakeEmbedder(dim=16), cfg.db_path)
    bot._handle_document(
        _doc(),
        conn=conn,
        tg=tg,
        cfg=cfg,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker,
    )

    parked = threading.Event()
    release = threading.Event()

    real_mark_committing = worker._mark_committing

    def parking_mark_committing(job):
        real_mark_committing(job)
        parked.set()
        release.wait(timeout=5.0)

    worker._mark_committing = parking_mark_committing

    # `run_one(conn=None)`: the worker acquires its own connection lazily,
    # on the worker thread -- `conn` (opened on the test thread, above) is
    # never handed across threads (sqlite3's `check_same_thread=True`
    # would refuse it). `close()` runs on that same worker thread too
    # (never from the test thread -- the connection belongs to whichever
    # thread acquired it).
    def run_and_close():
        worker.run_one()
        worker.close()

    thread = threading.Thread(target=run_and_close, daemon=True)
    thread.start()
    assert parked.wait(timeout=5.0)
    worker.shutdown()  # must NOT set this job's cancel event -- it is committing
    job = worker._in_flight.get(USER_ID)
    assert job is not None
    assert job.cancel.is_set() is False
    release.set()
    thread.join(timeout=5.0)
    assert not thread.is_alive()
    # Read back through a fresh connection (WAL: readers see committed
    # writes from any connection once the writer has committed and closed).
    verify_conn = storage.connect(cfg.db_path)
    assert storage.document_count(verify_conn, user_id=USER_ID) == 1
    verify_conn.close()
    assert any(text.startswith("✅ notes.txt:") for _c, text in tg.sent)
    conn.close()
