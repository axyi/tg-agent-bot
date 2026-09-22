"""spec-v1.11.0 T5 (docs/spec/spec-v1.11.0.md Sec.11.1, REQ-V1110-ERR-01):
this file is shared across the release's tasks -- `T-V1110-ERR-01`
(`tests/test_v1110_err.py::test_t_v1110_err_01_error_matrix_strings`) is
the spec's own frozen `module::function` name (sec.11.3's test table,
`T-V1110-INV-01`'s eventual inventory target), a single function
parametrised/extended by whichever task owns each row rather than renamed
per task. T5 owns rows 10 and 17 -- the ones its own `IngestWorker`/
`/cancel` machinery introduces; other tasks' rows land inside this same
function as they're built.

Offline and deterministic: `tests.fakes.FakeTelegram`/`FakeEmbedder`, a
`tmp_path` database.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

import bot
import config
import documents
import storage
from tests.fakes import FakeEmbedder, FakeLLM, FakeTelegram, RecordingRunner

TOKEN = "123456789:sentinel-telegram-token-for-v1110-err-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_README = _REPO_ROOT / "README.md"

_GOOD_TEXT = b"Enough readable text content here to produce exactly one chunk for storage."


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


def process(conn, cfg, upd, *, tg, worker):
    """Drives a command through the real dispatch chain (`process_update`),
    not by calling a handler function directly -- `/cancel`'s own dispatch
    wiring (`process_update`'s `if name == "/cancel":` line) is part of
    what row 17's trigger proves."""
    bot.process_update(
        upd,
        conn=conn,
        tg=tg,
        cfg=cfg,
        llm=FakeLLM([]),
        skills={},
        runner=RecordingRunner(),
        bot_username=BOT_USERNAME,
        worker=worker,
    )


def _error_section() -> str:
    text = _README.read_text(encoding="utf-8")
    start = text.index("## Error behaviour")
    end = text.index("## Versioning")
    return text[start:end]


def test_t_v1110_err_01_error_matrix_strings(tmp_path, monkeypatch):
    """T-V1110-ERR-01, this task's two rows.

    Row 10: `shutdown()` with a job in phase `queued` -> status edited to
    `❌ Interrupted by restart.` by the draining `run_one`, nothing
    stored, slot and token freed.

    Row 17: `/cancel`, driven through `process_update`'s real dispatch
    (not called directly), once the job has entered `committing` ->
    `Indexing is already finishing.`, the event stays unset, the commit
    proceeds to the success reply.
    """
    # -- row 10 --------------------------------------------------------
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
    assert job.phase == "queued"

    worker.shutdown()  # sets cancel_reason="shutdown" and the event
    assert job.cancel_reason == "shutdown"
    assert job.cancel.is_set()

    worker.run_one(conn=conn)  # drains the queued, now-cancelled job
    assert tg.edited and tg.edited[-1][2] == "❌ Interrupted by restart."
    assert tg.get_file_calls == []
    assert storage.document_count(conn, user_id=USER_ID) == 0
    assert worker.in_flight(USER_ID) is None
    assert "❌ Interrupted by restart." in _error_section()
    conn.close()

    # -- row 17 ----------------------------------------------------------
    conn2 = new_conn(tmp_path, name="b.db")
    cfg2 = make_cfg(tmp_path, db_path=tmp_path / "b.db")
    tg2 = FakeTelegram()
    tg2.files["documents/f1"] = _GOOD_TEXT
    worker2 = bot.IngestWorker(cfg2, tg2, FakeEmbedder(dim=16), cfg2.db_path)
    bot._handle_document(
        _doc(),
        conn=conn2,
        tg=tg2,
        cfg=cfg2,
        chat_id=USER_ID,
        from_id=USER_ID,
        embedder=FakeEmbedder(dim=16),
        worker=worker2,
    )
    job2 = worker2.in_flight(USER_ID)

    real_index_document = documents.index_document

    def spy_index_document(*a, before_commit=None, **k):
        def wrapped():
            before_commit()
            assert job2.phase == "committing"
            process(conn2, cfg2, text_update("/cancel"), tg=tg2, worker=worker2)

        return real_index_document(*a, before_commit=wrapped, **k)

    monkeypatch.setattr(documents, "index_document", spy_index_document)

    worker2.run_one(conn=conn2)
    assert (USER_ID, "Indexing is already finishing.") in tg2.sent
    assert job2.cancel.is_set() is False
    assert storage.document_count(conn2, user_id=USER_ID) == 1
    assert any(text.startswith("✅ notes.txt:") for _c, text in tg2.sent)
    assert "Indexing is already finishing." in _error_section()
    conn2.close()


def test_t_v1110_err_01_row_10_a_failed_edit_is_logged_never_raised(tmp_path, caplog):
    """Row 10's own parenthetical: a failed edit during the drain is
    logged, never raised -- `run_one` still completes the job (frees the
    slot, calls `task_done`)."""
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
    worker.shutdown()

    def failing_edit(_chat_id, _message_id, _text):
        raise bot.TelegramError("boom")

    tg.edit_message_text = failing_edit
    caplog.set_level(logging.WARNING, logger="bot")
    worker.run_one(conn=conn)  # must not raise
    assert any("status message disabled" in record.getMessage() for record in caplog.records)
    assert worker.in_flight(USER_ID) is None
    conn.close()
