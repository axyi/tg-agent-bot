"""spec-v1.11.0 T5/T6 (docs/spec/spec-v1.11.0.md Sec.11.2, REQ-V1110-SEC-01):
`T-V1110-SEC-01` (`tests/test_v1110_sec.py::
test_t_v1110_sec_01_nothing_new_executed_written_reached_or_leaked`) is
the spec's own frozen `module::function` name (sec.11.3's test table,
`T-V1110-INV-01`'s eventual inventory target) -- one function extended by
whichever task owns each clause, rather than renamed per task. T5 owns
the worker-related clauses its own code introduces: (4) no new file
writes during `run_one` (document bytes stay in memory, as on the loop
before this task); (6) `IngestWorker.__init__`'s exact, frozen signature
`(cfg, tg, embedder, db_path)`; (7) the worker logs through
`logging.getLogger("bot")`'s root handlers, so a registered secret in a
worker log record is still redacted by `RedactingFormatter`. T6 (this
task) adds clause 1's `/help` angle and a light clause 2 cross-reference;
clauses 1b, 3, 5 and 8 are not covered by this function (1b lives in
`T-V1110-MOD-09`; 3, 5 and 8 remain open for a later task).
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
from tests.fakes import FakeEmbedder, FakeLLM, FakeTelegram, RecordingRunner

TOKEN = "123456789:sentinel-telegram-token-for-v1110-sec-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
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


def _text_update(text, *, user_id=USER_ID, update_id=1):
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


def _callback_update(data, *, user_id=USER_ID, update_id=1, message_id=50):
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "cbq1",
            "from": {"id": user_id, "is_bot": False},
            "message": {
                "message_id": message_id,
                "date": 0,
                "chat": {"id": user_id, "type": "private"},
                "text": "",
            },
            "chat_instance": "ci1",
            "data": data,
        },
    }


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

    # -- clause 1 (T6): every user/env-supplied string reaching a <pre>
    # body is redact()-ed, fitted, then html.escape-d -- the /help angle
    # this task adds. COMMANDS entries are developer-authored constants,
    # not literal user input, but /help's body goes through the exact
    # same `_pre_text` path as every other table body (filenames/session
    # titles/model ids are T1's OUT-02 and T2/T3's own coverage) -- this
    # proves nothing exploitable slips through even if a description ever
    # carried untrusted content.
    help_canary = "CANARY-not-a-credential-t6"
    config.register_secret(help_canary)
    hostile_commands = (*bot.COMMANDS, ("hostile", f"<script>&</script> {help_canary}"))
    monkeypatch.setattr(bot, "COMMANDS", hostile_commands)
    conn3 = new_conn(tmp_path, name="c.db")
    cfg3 = make_cfg(tmp_path, db_path=tmp_path / "c.db")
    tg3 = FakeTelegram()
    bot.process_update(
        _text_update("/help"),
        conn=conn3,
        tg=tg3,
        cfg=cfg3,
        llm=FakeLLM([]),
        skills={},
        runner=RecordingRunner(),
        bot_username=BOT_USERNAME,
    )
    payload_text = tg3.sent_payloads[-1]["text"]
    assert "<script>&</script>" not in payload_text
    assert help_canary not in payload_text
    assert "&lt;script&gt;&amp;" in payload_text
    assert config.REDACTION in payload_text
    conn3.close()

    # -- clause 2 (T6): callback_data is never interpreted as a filename,
    # a path or SQL. CBQ-05 (tests/test_v1110_cbq.py) already covers this
    # behaviourally with a fuller parametrised case list; this is a light
    # direct-call cross-reference over the same two adversarial payloads
    # through the real dispatch chain, not a re-derivation of CBQ-05.
    conn4 = new_conn(tmp_path, name="d.db")
    cfg4 = make_cfg(tmp_path, db_path=tmp_path / "d.db")
    for data in ("ses:switch:../x", "mod:model:1 OR 1=1"):
        tg4 = FakeTelegram()
        bot.process_update(
            _callback_update(data),
            conn=conn4,
            tg=tg4,
            cfg=cfg4,
            llm=FakeLLM([]),
            skills={},
            runner=RecordingRunner(),
            bot_username=BOT_USERNAME,
        )
        assert tg4.callback_answers[-1]["text"] == bot.CALLBACK_EXPIRED_REPLY, data
    conn4.close()
