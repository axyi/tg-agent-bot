"""Provider failover and the `/model` override."""

import httpx
import pytest

import bot
import config
import storage
from llm import build_llm_client
from llm.base import LLMError, LLMResponse
from llm.failover import FAILOVER_COOLDOWN_S, FAILOVER_THRESHOLD, FailoverLLMClient
from llm.lmstudio import LMStudioClient
from llm.openrouter import OpenRouterClient
from tests.fakes import RecordingRunner, mock_llm_transport

TOKEN = "123456789:sentinel-telegram-token-for-failover-tests"
USER_ID = 424242
BOT_USERNAME = "ThisBot"


class StubClient:
    """One provider side: raises the scripted `LLMError`s, then answers."""

    def __init__(self, name, *, failures=0, context_length=4096, error=None):
        self.name = name
        self.remaining_failures = failures
        self.context_length = context_length
        self.calls = 0
        self._error = error

    def complete(self, messages, tools, *, max_tokens=None):
        self.calls += 1
        if self.remaining_failures > 0:
            self.remaining_failures -= 1
            raise self._error or LLMError(f"{self.name} down", retryable=True)
        return LLMResponse(f"answer from {self.name}", [], "stop")


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def wrapper(primary, secondary, clock=None):
    return FailoverLLMClient(
        primary,
        secondary,
        primary_name=primary.name,
        secondary_name=secondary.name,
        clock=clock or Clock(),
    )


def make_cfg(tmp_path, *, openrouter=True, failover="auto"):
    return config.Config(
        telegram_bot_token=TOKEN,
        allowed_tg_ids=frozenset({USER_ID}),
        llm_provider="lmstudio",
        lmstudio_base_url="http://localhost:1234/v1",
        lmstudio_model="local-model",
        openrouter_api_key="sk-or-test-key-value" if openrouter else "",
        openrouter_model="vendor/remote-model" if openrouter else "",
        llm_timeout_s=120.0,
        exec_workdir=tmp_path / "sandbox",
        db_path=tmp_path / "bot.db",
        llm_failover=failover,
        audit_log_path=tmp_path / "audit.jsonl",
    )


def command(text, update_id=1):
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


class RecordingTelegram:
    def __init__(self):
        self.sent = []

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))
        return {"message_id": len(self.sent)}


def test_t_v1_fo_01_three_failures_switch_to_the_secondary():
    primary = StubClient("lmstudio", failures=FAILOVER_THRESHOLD)
    secondary = StubClient("openrouter")
    client = wrapper(primary, secondary)

    for _ in range(FAILOVER_THRESHOLD - 1):
        with pytest.raises(LLMError):
            client.complete([], None)
    assert client.active_provider_name == "lmstudio"
    assert secondary.calls == 0

    # The third failure is re-issued on the secondary inside the same call.
    assert client.complete([], None).content == "answer from openrouter"
    assert client.active_provider_name == "openrouter"
    assert primary.calls == FAILOVER_THRESHOLD
    assert secondary.calls == 1

    assert client.complete([], None).content == "answer from openrouter"
    assert client.active_provider_name == "openrouter"
    assert primary.calls == FAILOVER_THRESHOLD


def test_t_v1_fo_01_a_success_resets_the_failure_count():
    primary = StubClient("lmstudio", failures=2)
    secondary = StubClient("openrouter")
    client = wrapper(primary, secondary)
    for _ in range(2):
        with pytest.raises(LLMError):
            client.complete([], None)
    assert client.failure_counts["lmstudio"] == 2
    client.complete([], None)
    assert client.failure_counts["lmstudio"] == 0
    assert secondary.calls == 0


def test_t_v1_fo_02_cooldown_expiry_returns_to_the_primary():
    clock = Clock()
    primary = StubClient("lmstudio", failures=FAILOVER_THRESHOLD)
    secondary = StubClient("openrouter")
    client = wrapper(primary, secondary, clock=clock)
    for _ in range(FAILOVER_THRESHOLD - 1):
        with pytest.raises(LLMError):
            client.complete([], None)
    client.complete([], None)
    assert client.active_provider_name == "openrouter"

    clock.advance(FAILOVER_COOLDOWN_S - 1)
    client.complete([], None)
    assert client.active_provider_name == "openrouter"

    clock.advance(2)
    before = primary.calls
    assert client.complete([], None).content == "answer from lmstudio"
    assert client.active_provider_name == "lmstudio"
    assert primary.calls == before + 1


def test_t_v1_fo_03_both_down_propagates_the_last_error():
    last = LLMError("openrouter http 503", retryable=True)
    primary = StubClient("lmstudio", failures=FAILOVER_THRESHOLD)
    secondary = StubClient("openrouter", failures=1, error=last)
    client = wrapper(primary, secondary)
    for _ in range(FAILOVER_THRESHOLD - 1):
        with pytest.raises(LLMError):
            client.complete([], None)
    with pytest.raises(LLMError) as raised:
        client.complete([], None)
    assert raised.value is last
    assert client.active_provider_name == "lmstudio"


def test_t_v1_fo_04_single_provider_or_failover_off_returns_a_bare_client(tmp_path):
    transport = mock_llm_transport(lambda request: httpx.Response(200, json={}))
    with httpx.Client(transport=transport) as http:
        off = build_llm_client(make_cfg(tmp_path, failover="off"), client=http)
        assert isinstance(off, LMStudioClient)
        assert off.context_length == 42496

        single = build_llm_client(make_cfg(tmp_path, openrouter=False), client=http)
        assert isinstance(single, LMStudioClient)

        both = build_llm_client(make_cfg(tmp_path), client=http)
        assert isinstance(both, FailoverLLMClient)
        assert both.active_provider_name == "lmstudio"

        overridden = build_llm_client(make_cfg(tmp_path), client=http, override="openrouter")
        assert overridden.active_provider_name == "openrouter"

        or_only = build_llm_client(
            make_cfg(tmp_path, failover="off"), client=http, override="openrouter"
        )
        assert isinstance(or_only, OpenRouterClient)
        assert or_only.context_length == 131072


def test_t_v1_fo_05_model_command(conn, tmp_path):
    cfg = make_cfg(tmp_path)
    installed = []

    def set_provider(name):
        installed.append(name)
        return StubClient(name or "lmstudio")

    def process(text, llm, update_id):
        tg = RecordingTelegram()
        bot.process_update(
            command(text, update_id),
            conn=conn, tg=tg, cfg=cfg, llm=llm, skills={},
            runner=RecordingRunner(), bot_username=BOT_USERNAME,
            set_provider=set_provider,
        )
        return tg.sent

    active = wrapper(StubClient("lmstudio"), StubClient("openrouter"))
    assert process("/model", active, 1) == [
        (USER_ID, "Provider: lmstudio (override: none, "
                  "failures: lmstudio=0, openrouter=0)")
    ]

    assert process("/model openrouter", active, 2) == [
        (USER_ID, "Provider switched to openrouter.")
    ]
    assert installed == ["openrouter"]
    assert storage.get_state(conn, "provider_override") == "openrouter"

    # A restart reads the override back out of bot_state.
    assert bot.load_provider_override(conn) == "openrouter"

    switched = wrapper(StubClient("openrouter"), StubClient("lmstudio"))
    switched.failure_counts["openrouter"] = 2
    assert process("/model", switched, 3) == [
        (USER_ID, "Provider: openrouter (override: openrouter, "
                  "failures: lmstudio=0, openrouter=2)")
    ]

    assert process("/model auto", active, 4) == [(USER_ID, "Provider override cleared.")]
    assert storage.get_state(conn, "provider_override") is None
    assert bot.load_provider_override(conn) is None
    assert installed == ["openrouter", None]

    assert process("/model ollama", active, 5) == [
        (USER_ID, "Usage: /model [lmstudio|openrouter|auto]")
    ]

    bare = make_cfg(tmp_path, openrouter=False)
    tg = RecordingTelegram()
    bot.process_update(
        command("/model openrouter", 6),
        conn=conn, tg=tg, cfg=bare, llm=active, skills={},
        runner=RecordingRunner(), bot_username=BOT_USERNAME,
        set_provider=set_provider,
    )
    assert tg.sent == [(USER_ID, "Provider openrouter is not configured.")]
    assert installed == ["openrouter", None]

    # No command reached the model and none of them was stored.
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 0


def test_t_v1_fo_06_context_length_follows_the_active_provider():
    primary = StubClient("lmstudio", failures=FAILOVER_THRESHOLD, context_length=42496)
    secondary = StubClient("openrouter", context_length=131072)
    client = wrapper(primary, secondary)
    assert client.context_length == 42496
    for _ in range(FAILOVER_THRESHOLD - 1):
        with pytest.raises(LLMError):
            client.complete([], None)
    client.complete([], None)
    assert client.context_length == 131072


def test_max_tokens_is_forwarded_to_the_active_side():
    class Recorder(StubClient):
        def __init__(self, name):
            super().__init__(name)
            self.max_tokens_calls = []

        def complete(self, messages, tools, *, max_tokens=None):
            self.max_tokens_calls.append(max_tokens)
            return super().complete(messages, tools, max_tokens=max_tokens)

    primary = Recorder("lmstudio")
    client = wrapper(primary, StubClient("openrouter"))
    client.complete([], None, max_tokens=512)
    assert primary.max_tokens_calls == [512]
