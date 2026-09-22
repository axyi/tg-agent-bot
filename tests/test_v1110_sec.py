"""spec-v1.11.0 T5 (docs/spec/spec-v1.11.0.md Sec.11.2, REQ-V1110-SEC-01):
`T-V1110-SEC-01` (`tests/test_v1110_sec.py::
test_t_v1110_sec_01_nothing_new_executed_written_reached_or_leaked`) is
the spec's own frozen `module::function` name (sec.11.3's test table,
`T-V1110-INV-01`'s eventual inventory target) -- one function extended by
whichever task owns each clause, rather than renamed per task. T5 owns
only the worker-related clauses its own code introduces: (4) no new file
writes during `run_one` (document bytes stay in memory, as on the loop
before this task); (6) `IngestWorker.__init__`'s exact, frozen signature
`(cfg, tg, embedder, db_path)`; (7) the worker logs through
`logging.getLogger("bot")`'s root handlers, so a registered secret in a
worker log record is still redacted by `RedactingFormatter`. The other
clauses (1, 1b, 2, 3, 5, 8) are T4's/T6's own additions to this same
function.
"""

from __future__ import annotations

import inspect
import io
import logging
from pathlib import Path

import pytest

import bot
import config
import storage
from tests.fakes import FakeEmbedder, FakeTelegram

TOKEN = "123456789:sentinel-telegram-token-for-v1110-sec-tests"
USER_ID = 424242
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


def test_t_v1110_sec_01_nothing_new_executed_written_reached_or_leaked(tmp_path, monkeypatch):
    """T5's three worker-owned clauses of the combined SEC-01 check --
    clause 6 (the frozen `__init__` signature), clause 4 (no file writes
    during `run_one`) and clause 7 (a redacted worker log record), run in
    that order in one function so other tasks can append their own
    clauses to this same body rather than to a same-named sibling."""
    # -- clause 6: IngestWorker.__init__'s exact, frozen signature --------
    params = list(inspect.signature(bot.IngestWorker.__init__).parameters)
    assert params == ["self", "cfg", "tg", "embedder", "db_path"]

    # -- clause 4: no open()/Path.write_*() call during run_one -----------
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

    import builtins

    real_open = builtins.open

    def forbidden_open(*args, **kwargs):
        raise AssertionError(f"unexpected open() during run_one: {args!r}")

    def forbidden_write_bytes(self, *args, **kwargs):
        raise AssertionError(f"unexpected Path.write_bytes() during run_one: {self!r}")

    def forbidden_write_text(self, *args, **kwargs):
        raise AssertionError(f"unexpected Path.write_text() during run_one: {self!r}")

    monkeypatch.setattr(builtins, "open", forbidden_open)
    monkeypatch.setattr(Path, "write_bytes", forbidden_write_bytes)
    monkeypatch.setattr(Path, "write_text", forbidden_write_text)
    try:
        worker.run_one(conn=conn)
    finally:
        monkeypatch.setattr(builtins, "open", real_open)

    # Proves the run actually exercised the real pipeline (not a run that
    # merely failed before reaching any I/O-shaped code at all).
    assert any(t.startswith("✅ notes.txt:") for _c, t in tg.sent)
    assert storage.document_count(conn, user_id=USER_ID) == 1
    conn.close()

    # -- clause 7: the worker logs through logging.getLogger("bot")'s
    # root handlers; a registered secret in a worker log record is
    # redacted by RedactingFormatter -------------------------------------
    secret = "CANARY-not-a-real-credential-v1110-sec-01-worker-log"
    config.register_secret(secret)

    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    for handler in saved_handlers:
        root.removeHandler(handler)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    config.install_redacting_logging(handler, "%(message)s")
    root.addHandler(handler)
    root.setLevel(logging.WARNING)
    try:
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

        def boom_get_file(_file_id):
            raise RuntimeError(f"boom {secret}")

        tg2.get_file = boom_get_file
        worker2.run_one(conn=conn2)  # `_process`'s catch-all: log.exception(...)
        conn2.close()
    finally:
        for h in list(root.handlers):
            root.removeHandler(h)
        for h in saved_handlers:
            root.addHandler(h)
        root.setLevel(saved_level)

    logged = stream.getvalue()
    assert secret not in logged
    assert config.REDACTION in logged
