"""REQ-V13-RTE-01 — model routing by purpose (section 10.6), configuration only.

The routed client is deliberately not enabled during the v1.3 benchmark, so
every assertion here is offline: fakes for the clients, a mapping for the
environment, and no transport is ever asked for a response.
"""

import httpx
import pytest

import bot
import config
import storage
from config import ConfigError, load_config
from llm import build_llm_client
from llm.base import LLMResponse
from llm.failover import FailoverLLMClient
from llm.lmstudio import LMStudioClient
from llm.openrouter import OpenRouterClient
from tests.fakes import FakeLLM, RecordingRunner

TOKEN = "123456789:sentinel-telegram-token-for-routing-tests"
OR_KEY = "sk-or-sentinel-openrouter-key-for-routing-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"
SUMMARY_JSON = (
    '{"goal": "g", "files": [], "decisions": [], "errors": [], "next_action": ""}'
)


def base_env(**overrides):
    env = {
        "TELEGRAM_BOT_TOKEN": TOKEN,
        "ALLOWED_TG_IDS": str(USER_ID),
        "LMSTUDIO_MODEL": "local-model",
        "OPENROUTER_API_KEY": OR_KEY,
        "OPENROUTER_MODEL": "cloud/model",
    }
    env.update(overrides)
    return {k: v for k, v in env.items() if v is not None}


def make_cfg(tmp_path, **overrides):
    fields = {
        "telegram_bot_token": TOKEN,
        "allowed_tg_ids": frozenset({USER_ID}),
        "llm_provider": "lmstudio",
        "lmstudio_base_url": "http://localhost:1234/v1",
        "lmstudio_model": "local-model",
        "openrouter_api_key": OR_KEY,
        "openrouter_model": "cloud/model",
        "llm_timeout_s": 120.0,
        "exec_workdir": tmp_path / "sandbox",
        "db_path": tmp_path / "bot.db",
        "audit_log_path": tmp_path / "audit.jsonl",
    }
    fields.update(overrides)
    return config.Config(**fields)


class RoutedFakeLLM(FakeLLM):
    """A fake that names the routed model, so `llm_calls.model` can be read back."""

    def describe(self):
        return ("openrouter", "cheap/model")


class RecordingTelegram:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))
        return {"message_id": len(self.sent)}


def update(text, update_id=1):
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": USER_ID, "type": "private"},
            "from": {"id": USER_ID, "is_bot": False},
            "text": text,
        },
    }


def seed(conn):
    conv = storage.get_or_create_active_conversation(conn, USER_ID)
    storage.add_user_message(conn, conv, "one")
    storage.add_assistant_message(conn, conv, "two")
    return conv


def process(conn, cfg, text, llm, summary_llm):
    tg = RecordingTelegram()
    bot.process_update(
        update(text),
        conn=conn, tg=tg, cfg=cfg, llm=llm, skills={},
        runner=RecordingRunner(), bot_username=BOT_USERNAME,
        summary_llm=summary_llm,
    )
    return tg


# --------------------------------------------------------------------------
# Validation (config.py)
# --------------------------------------------------------------------------

def test_rte_01_the_default_is_no_routing():
    cfg = load_config(env=base_env(), load_env_file=False)
    assert cfg.llm_summary_model == ""
    assert config.parse_summary_model("") is None


def test_rte_01_a_configured_provider_and_model_are_accepted():
    cfg = load_config(
        env=base_env(LLM_SUMMARY_MODEL=" OpenRouter:cheap/model "), load_env_file=False
    )
    # The provider half is normalised the way LLM_PROVIDER is; the model half is
    # a provider-side id and keeps its case.
    assert cfg.llm_summary_model == "openrouter:cheap/model"
    assert config.parse_summary_model(cfg.llm_summary_model) == ("openrouter", "cheap/model")


@pytest.mark.parametrize("value", ["anthropic:some/model", "cheap/model", ":cheap/model"])
def test_rte_01_an_unknown_provider_is_refused(value):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_SUMMARY_MODEL=value), load_env_file=False)
    assert "LLM_SUMMARY_MODEL" in str(exc.value)


@pytest.mark.parametrize("value", ["openrouter:", "lmstudio:   "])
def test_rte_01_an_empty_model_is_refused(value):
    with pytest.raises(ConfigError) as exc:
        load_config(env=base_env(LLM_SUMMARY_MODEL=value), load_env_file=False)
    assert "LLM_SUMMARY_MODEL" in str(exc.value)


def test_rte_01_an_unconfigured_openrouter_is_refused():
    env = base_env(
        OPENROUTER_API_KEY=None, OPENROUTER_MODEL=None,
        LLM_SUMMARY_MODEL="openrouter:cheap/model",
    )
    with pytest.raises(ConfigError) as exc:
        load_config(env=env, load_env_file=False)
    assert "LLM_SUMMARY_MODEL" in str(exc.value)
    assert "openrouter" in str(exc.value)


def test_rte_01_an_unconfigured_lmstudio_is_refused():
    env = base_env(
        LLM_PROVIDER="openrouter", LMSTUDIO_MODEL=None,
        LLM_SUMMARY_MODEL="lmstudio:small",
    )
    with pytest.raises(ConfigError) as exc:
        load_config(env=env, load_env_file=False)
    assert "LLM_SUMMARY_MODEL" in str(exc.value)
    assert "lmstudio" in str(exc.value)


# --------------------------------------------------------------------------
# The second client (llm/__init__.py)
# --------------------------------------------------------------------------

def test_rte_01_the_summary_purpose_gets_the_routed_client_and_no_failover(tmp_path):
    cfg = make_cfg(tmp_path, llm_summary_model="openrouter:cheap/model")
    with httpx.Client() as http:
        main = build_llm_client(cfg, client=http)
        routed = build_llm_client(cfg, client=http, purpose="summary")
        # LLM_FAILOVER stays `auto` for the main client and never applies to the
        # summary one, whatever the second provider offers.
        assert isinstance(main, FailoverLLMClient)
        assert isinstance(routed, OpenRouterClient)
        assert routed.describe() == ("openrouter", "cheap/model")
        # The same `httpx.Client`: one connection pool, one place that closes it.
        assert routed._client is http


def test_rte_01_the_summary_purpose_can_route_to_lmstudio(tmp_path):
    cfg = make_cfg(tmp_path, llm_summary_model="lmstudio:small-local")
    with httpx.Client() as http:
        routed = build_llm_client(cfg, client=http, purpose="summary")
    assert isinstance(routed, LMStudioClient)
    assert routed.describe() == ("lmstudio", "small-local")


def test_rte_01_an_unset_variable_leaves_the_summary_purpose_on_the_main_client(tmp_path):
    cfg = make_cfg(tmp_path)
    with httpx.Client() as http:
        main = build_llm_client(cfg, client=http)
        summary = build_llm_client(cfg, client=http, purpose="summary")
    assert isinstance(main, FailoverLLMClient)
    assert isinstance(summary, FailoverLLMClient)


def test_rte_01_the_main_purpose_ignores_the_variable(tmp_path):
    cfg = make_cfg(tmp_path, llm_failover="off", llm_summary_model="openrouter:cheap/model")
    with httpx.Client() as http:
        main = build_llm_client(cfg, client=http)
    assert isinstance(main, LMStudioClient)
    assert main.describe() == ("lmstudio", "local-model")


# --------------------------------------------------------------------------
# Routing the summary call, and only it (bot.py)
# --------------------------------------------------------------------------

def test_rte_01_the_summary_command_goes_to_the_routed_client(conn, tmp_path):
    cfg = make_cfg(tmp_path, llm_summary_model="openrouter:cheap/model")
    main = FakeLLM([])
    routed = RoutedFakeLLM([LLMResponse(SUMMARY_JSON, [], "stop")])
    conv = seed(conn)

    tg = process(conn, cfg, "/summary", main, routed)

    assert len(routed.calls) == 1
    assert main.calls == []
    assert tg.sent and "Goal: g" in tg.sent[0][1]
    rows = storage.fetch_llm_calls(conn, conv)
    assert [(row["purpose"], row["provider"], row["model"]) for row in rows] == [
        ("summary", "openrouter", "cheap/model")
    ]


def test_rte_01_the_new_command_summarises_on_the_routed_client(conn, tmp_path):
    cfg = make_cfg(tmp_path, llm_summary_model="openrouter:cheap/model")
    main = FakeLLM([])
    routed = RoutedFakeLLM([LLMResponse(SUMMARY_JSON, [], "stop")])
    conv = seed(conn)

    process(conn, cfg, "/new", main, routed)

    assert len(routed.calls) == 1
    assert main.calls == []
    assert storage.get_summary(conn, conv) is not None


def test_rte_01_the_agent_loop_keeps_the_main_client(conn, tmp_path):
    cfg = make_cfg(tmp_path, llm_summary_model="openrouter:cheap/model")
    main = FakeLLM([LLMResponse("hello back", [], "stop")])
    routed = RoutedFakeLLM([])
    seed(conn)

    process(conn, cfg, "hello", main, routed)

    assert len(main.calls) == 1
    assert routed.calls == []
    rows = storage.fetch_llm_calls(conn)
    assert [row["purpose"] for row in rows] == ["agent"]
    assert [row["model"] for row in rows] == ["fake-model"]


def test_rte_01_without_a_routed_client_the_summary_stays_on_the_main_one(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    main = FakeLLM([LLMResponse(SUMMARY_JSON, [], "stop")])
    seed(conn)

    process(conn, cfg, "/summary", main, None)

    assert len(main.calls) == 1


# --------------------------------------------------------------------------
# Startup wiring (bot.main)
# --------------------------------------------------------------------------

def _stub_startup(monkeypatch, cfg, captured, built):
    monkeypatch.setattr(bot, "load_config", lambda: cfg)
    monkeypatch.setattr(bot.tools, "load_skills", lambda path: {})
    monkeypatch.setattr(bot.TelegramClient, "get_me", lambda self: {"username": BOT_USERNAME})
    monkeypatch.setattr(bot, "exec_backend_status", lambda: ("27.1.2", True))
    monkeypatch.setattr(bot, "_startup_docker_wiring", lambda cfg, docker_ok: (True, None))
    # The price snapshot is a startup HTTP call and is not what these tests pin.
    monkeypatch.setattr(bot, "build_cost_resolver", lambda conn, cfg, client: None)
    monkeypatch.setattr(bot.signal, "signal", lambda signum, handler: None)
    monkeypatch.setattr(bot, "poll_loop", lambda **kwargs: captured.update(kwargs) or 0)

    def fake_build(cfg, *, client, override=None, purpose="agent"):
        built.append(purpose)
        return f"client-{purpose}"

    monkeypatch.setattr(bot, "build_llm_client", fake_build)


def test_rte_01_main_builds_a_second_client_for_the_summary_purpose(tmp_path, monkeypatch):
    cfg = make_cfg(
        tmp_path, db_path=tmp_path / "main.db", llm_summary_model="openrouter:cheap/model"
    )
    captured, built = {}, []
    _stub_startup(monkeypatch, cfg, captured, built)

    assert bot.main([]) == 0
    assert built == ["agent", "summary"]
    assert captured["summary_llm"] == "client-summary"
    assert captured["llm"] == "client-agent"


def test_rte_01_main_builds_no_second_client_when_the_variable_is_unset(tmp_path, monkeypatch):
    cfg = make_cfg(tmp_path, db_path=tmp_path / "main.db")
    captured, built = {}, []
    _stub_startup(monkeypatch, cfg, captured, built)

    assert bot.main([]) == 0
    assert built == ["agent"]
    assert captured["summary_llm"] is None
