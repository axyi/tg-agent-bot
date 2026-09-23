"""spec-v1.11.0 T6 (docs/spec/spec-v1.11.0.md sec.10, REQ-V1110-EXT-01,
-02, -03): `COMMANDS`, `TelegramClient.set_my_commands`, the `main()`
startup call, and `/help`/`/start` -> `_handle_help`. See
`docs/spec/task-briefs/v1110-T6.md`.

Frozen `module::function` names from sec.11.3's test table
(`T-V1110-INV-01`'s eventual inventory target) -- this file was not in
T6's brief's own stage list, which named only `tests/test_v1110_pin.py`
as a new file; created to match the spec's own test table
(spec-v1.11.0.md:1272-1274), disclosed as an amendment in the T6 commit:
- T-V1110-EXT-01 -> test_t_v1110_ext_01_commands_table_and_setmycommands
- T-V1110-EXT-02 -> test_t_v1110_ext_02_help_and_start
- T-V1110-EXT-03 -> test_t_v1110_ext_03_readme_commands_rows

Offline and deterministic throughout: `tests.fakes.FakeLLM`/`FakeTelegram`,
`httpx.MockTransport`, a `tmp_path` database.
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import httpx
import pytest

import bot
import config
import storage
import tables
from tests.fakes import FakeLLM, FakeTelegram, RecordingRunner, mock_llm_transport

TOKEN = "123456789:sentinel-telegram-token-for-v1110-ext-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
_REPO_ROOT = Path(__file__).resolve().parents[1]
_README = _REPO_ROOT / "README.md"
# Captured before any test monkeypatches `bot.httpx.Client` -- `_stub_main_startup`
# is called twice in the same test, so re-reading `httpx.Client` inside it would
# capture its own previous patch on the second call.
_REAL_HTTPX_CLIENT = httpx.Client

_EXPECTED_COMMANDS = (
    "new",
    "status",
    "stats",
    "summary",
    "model",
    "reload_skills",
    "documents",
    "delete",
    "sessions",
    "session",
    "cancel",
    "help",
)


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
    }
    fields.update(overrides)
    return config.Config(**fields)


def new_conn(tmp_path, name="a.db"):
    conn = storage.connect(tmp_path / name)
    storage.init_schema(conn, embedding_dim=16, embedding_model="embed-m")
    return conn


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


def _stub_main_startup(monkeypatch, cfg, *, handler, captured):
    """The shared shape of `tests/test_routing.py`'s `_stub_startup`, plus
    routing the real `httpx.Client()` `main()` constructs through a
    `MockTransport` (rather than monkeypatching `TelegramClient.get_me`
    directly) -- this file needs the real `getMe`/`setMyCommands` HTTP
    round trip, not a bypass of it."""
    monkeypatch.setattr(bot, "load_config", lambda: cfg)
    monkeypatch.setattr(bot.tools, "load_skills", lambda path: {})
    monkeypatch.setattr(
        bot.httpx,
        "Client",
        lambda: _REAL_HTTPX_CLIENT(transport=mock_llm_transport(handler)),
    )
    monkeypatch.setattr(bot, "exec_backend_status", lambda: (None, False))
    monkeypatch.setattr(bot, "_startup_docker_wiring", lambda cfg, docker_ok: (False, None))
    monkeypatch.setattr(bot, "build_cost_resolver", lambda conn, cfg, client: None)
    monkeypatch.setattr(bot.signal, "signal", lambda signum, handler: None)
    monkeypatch.setattr(bot, "poll_loop", lambda **kwargs: captured.update(kwargs) or 0)
    monkeypatch.setattr(
        bot,
        "build_llm_client",
        lambda cfg, *, client, override=None, purpose="agent", model=None: object(),
    )


def test_t_v1110_ext_01_commands_table_and_setmycommands(tmp_path, monkeypatch, caplog):
    # -- shape: names without the slash, <= 32 chars, descriptions
    # <= 256 chars, ASCII, in the README's exact order --------------------
    assert tuple(name for name, _desc in bot.COMMANDS) == _EXPECTED_COMMANDS
    for name, desc in bot.COMMANDS:
        assert not name.startswith("/")
        assert 1 <= len(name) <= 32
        assert name.isascii()
        assert 1 <= len(desc) <= 256
        assert desc.isascii()

    # -- structural completeness: process_update's own `name == "/..."`
    # dispatch literals equal COMMANDS' names plus the /start alias,
    # exactly -- catches a command added to dispatch but never registered
    # (or vice versa) regardless of hand-maintained lists drifting -------
    source = inspect.getsource(bot.process_update)
    dispatched = set(re.findall(r'name == "/(\w+)"', source))
    assert dispatched == set(_EXPECTED_COMMANDS) | {"start"}

    # -- behavioural completeness: a probe update per COMMANDS name
    # reaches its handler, never the model ---------------------------------
    cfg = make_cfg(tmp_path)
    for name in _EXPECTED_COMMANDS:
        conn = new_conn(tmp_path, name=f"probe-{name}.db")
        tg = FakeTelegram()
        llm = FakeLLM([])
        bot.process_update(
            text_update(f"/{name}"),
            conn=conn,
            tg=tg,
            cfg=cfg,
            llm=llm,
            skills={},
            runner=RecordingRunner(),
            bot_username=BOT_USERNAME,
            worker=None,
        )
        assert llm.calls == [], f"/{name} reached the model"
        stored = conn.execute("SELECT COUNT(*) FROM messages WHERE role = 'user'").fetchone()[0]
        assert stored == 0, f"/{name} was stored as a conversation message"
        conn.close()

    # -- /start dispatches to _handle_help and is absent from COMMANDS ----
    assert "start" not in {name for name, _desc in bot.COMMANDS}
    conn = new_conn(tmp_path, name="start.db")
    tg = FakeTelegram()
    llm = FakeLLM([])
    bot.process_update(
        text_update("/start"),
        conn=conn,
        tg=tg,
        cfg=cfg,
        llm=llm,
        skills={},
        runner=RecordingRunner(),
        bot_username=BOT_USERNAME,
        worker=None,
    )
    assert llm.calls == []
    assert len(tg.sent) == 1
    expected_header = tables.render_table(
        ("command", "what it does"), bot.COMMANDS, max_width=(16, 52)
    ).splitlines()[0]
    assert expected_header in tg.sent[0][1]
    conn.close()

    # -- main()-level wiring: set_my_commands payload over MockTransport,
    # right after getMe, in COMMANDS order ---------------------------------
    requests: list[httpx.Request] = []

    def ok_handler(request):
        requests.append(request)
        if request.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"username": BOT_USERNAME}})
        if request.url.path.endswith("/setMyCommands"):
            return httpx.Response(200, json={"ok": True, "result": True})
        raise AssertionError(f"unexpected Telegram method in this test: {request.url.path}")

    cfg2 = make_cfg(tmp_path, db_path=tmp_path / "main-ok.db")
    captured: dict = {}
    _stub_main_startup(monkeypatch, cfg2, handler=ok_handler, captured=captured)
    assert bot.main(["--no-dashboard"]) == 0
    setmycommands_calls = [r for r in requests if r.url.path.endswith("/setMyCommands")]
    assert len(setmycommands_calls) == 1
    body = json.loads(setmycommands_calls[0].content)
    assert body == {
        "commands": [{"command": name, "description": desc} for name, desc in bot.COMMANDS]
    }
    # getMe strictly precedes setMyCommands, in the same client.
    methods = [r.url.path.rsplit("/", 1)[-1] for r in requests]
    assert methods.index("getMe") < methods.index("setMyCommands")

    # -- a 500 from setMyCommands: one warning, startup continues (never
    # fatal) -----------------------------------------------------------
    def failing_handler(request):
        if request.url.path.endswith("/getMe"):
            return httpx.Response(200, json={"ok": True, "result": {"username": BOT_USERNAME}})
        if request.url.path.endswith("/setMyCommands"):
            return httpx.Response(500, json={"ok": False, "description": "boom"})
        raise AssertionError(f"unexpected Telegram method in this test: {request.url.path}")

    cfg3 = make_cfg(tmp_path, db_path=tmp_path / "main-fail.db")
    captured3: dict = {}
    _stub_main_startup(monkeypatch, cfg3, handler=failing_handler, captured=captured3)
    caplog.clear()
    with caplog.at_level("WARNING", logger="bot"):
        assert bot.main(["--no-dashboard"]) == 0
    warnings = [r for r in caplog.records if "setMyCommands failed" in r.getMessage()]
    assert len(warnings) == 1
    # startup reached poll_loop -- never fatal.
    assert captured3.get("bot_username") == BOT_USERNAME

    # -- run_selftest() leaves commands_set empty (EXT-01's carve-out:
    # neither run_selftest() nor run_selftest_live() calls set_my_commands
    # at all) --------------------------------------------------------------
    spy_calls = []
    monkeypatch.setattr(
        bot._SelftestTelegram,
        "set_my_commands",
        lambda self, commands: spy_calls.append(list(commands)),
        raising=False,
    )
    assert bot.run_selftest() == 0
    assert spy_calls == []


def test_t_v1110_ext_02_help_and_start(tmp_path):
    """REQ-V1110-EXT-02: `/help` and `/start` -> one table-path body each,
    header `command  what it does`, one row per `COMMANDS` entry; neither
    is stored in the conversation."""
    cfg = make_cfg(tmp_path)
    expected_table = tables.render_table(
        ("command", "what it does"), bot.COMMANDS, max_width=(16, 52)
    )
    expected_lines = expected_table.splitlines()

    for command_text in ("/help", "/start"):
        conn = new_conn(tmp_path, name=f"{command_text.strip('/')}.db")
        tg = FakeTelegram()
        bot.process_update(
            text_update(command_text),
            conn=conn,
            tg=tg,
            cfg=cfg,
            llm=FakeLLM([]),
            skills={},
            runner=RecordingRunner(),
            bot_username=BOT_USERNAME,
            worker=None,
        )
        assert len(tg.sent) == 1
        chat_id, body = tg.sent[0]
        assert chat_id == USER_ID
        for line in expected_lines:
            assert line in body
        for name, _desc in bot.COMMANDS:
            assert name in body
        # Neither command is stored in the conversation.
        stored = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        assert stored == 0
        conn.close()


def _commands_section() -> str:
    text = _README.read_text(encoding="utf-8")
    start = text.index("## Commands")
    end = text.index("## Sessions")
    return text[start:end]


def test_t_v1110_ext_03_readme_commands_rows():
    """REQ-V1110-EXT-03: README's `## Commands` section has a row for
    every `COMMANDS` name, and `/reload_skills` still precedes
    `/documents` (the amended `tests/test_v190_agents.py:226-235` form)."""
    section = _commands_section()
    for name, _desc in bot.COMMANDS:
        assert f"/{name}" in section, f"README Commands table missing a row for /{name}"
    assert section.index("/reload_skills") < section.index("/documents")
