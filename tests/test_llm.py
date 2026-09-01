import json

import httpx
import pytest

import config
from llm import build_llm_client
from llm.base import LLMError, LLMResponse, build_payload, parse_response
from llm.lmstudio import LMStudioClient
from llm.openrouter import OpenRouterClient
from tests.fakes import mock_llm_transport

BASE_URL = "http://localhost:1234/v1"
SENTINEL_KEY = "sk-or-sentinel-key-for-redaction-test"


def answer(content="hi", tool_calls=None, finish_reason="stop"):
    message = {"role": "assistant", "content": content}
    if tool_calls is not None:
        message["tool_calls"] = tool_calls
    return {"choices": [{"finish_reason": finish_reason, "message": message}]}


def client_for(handler):
    return httpx.Client(transport=mock_llm_transport(handler))


def capture(body_holder, payload=None, status=200):
    def handler(request):
        body_holder.append(request)
        return httpx.Response(status, json=payload if payload is not None else answer())
    return handler


def test_t_lm_01_lmstudio_request_shape():
    seen = []
    llm = LMStudioClient(BASE_URL, "test-model", 5.0, client_for(capture(seen)))
    llm.complete([{"role": "user", "content": "hi"}], [{"type": "function"}])
    request = seen[0]
    assert str(request.url) == f"{BASE_URL}/chat/completions"
    assert "authorization" not in request.headers
    body = json.loads(request.read())
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert body["max_tokens"] == 1024
    assert body["stream"] is False
    assert body["tool_choice"] == "auto"


def test_t_lm_02_tools_none_omits_keys():
    seen = []
    llm = LMStudioClient(BASE_URL, "m", 5.0, client_for(capture(seen)))
    llm.complete([{"role": "user", "content": "hi"}], None)
    body = json.loads(seen[0].read())
    assert "tools" not in body
    assert "tool_choice" not in body
    assert build_payload("m", [], None).keys() == {
        "model", "messages", "temperature", "max_tokens", "stream"
    }


def test_t_lm_03_tool_calls_parse():
    payload = answer(
        content=None,
        tool_calls=[
            {"id": "call_a", "type": "function",
             "function": {"name": "exec", "arguments": '{"argv": ["uname"]}'}},
            {"id": "call_b", "type": "function",
             "function": {"name": "load_skill", "arguments": {"name": "weather"}}},
            {"function": {"name": "exec"}},
        ],
        finish_reason="tool_calls",
    )
    response = parse_response(payload)
    assert response.content == ""
    assert response.finish_reason == "tool_calls"
    assert [c.id for c in response.tool_calls] == ["call_a", "call_b", ""]
    assert response.tool_calls[1].arguments == '{"name": "weather"}'
    assert response.tool_calls[2].arguments == ""


@pytest.mark.parametrize(
    ("status", "exc", "retryable", "kind"),
    [
        (429, None, True, "http"),
        (500, None, True, "http"),
        (503, None, True, "http"),
        (400, None, False, "http"),
        (404, None, False, "http"),
        (None, httpx.ReadTimeout("slow"), True, "transport"),
        (None, httpx.ConnectError("down"), True, "transport"),
    ],
)
def test_t_lm_04_error_mapping(status, exc, retryable, kind):
    def handler(request):
        if exc is not None:
            raise exc
        return httpx.Response(status, json={"error": "nope"})

    llm = LMStudioClient(BASE_URL, "m", 5.0, client_for(handler))
    with pytest.raises(LLMError) as raised:
        llm.complete([], None)
    assert raised.value.retryable is retryable
    assert raised.value.kind == kind


def test_t_lm_04_timeout_message():
    def handler(request):
        raise httpx.ReadTimeout("slow")

    llm = LMStudioClient(BASE_URL, "m", 5.0, client_for(handler))
    with pytest.raises(LLMError) as raised:
        llm.complete([], None)
    assert str(raised.value) == "llm request timed out"


@pytest.mark.parametrize(
    ("payload", "kind"),
    [
        # REQ-V1-RP-01: a non-JSON body is `http` (the server answered, the payload is
        # garbage); `malformed` is reserved for structurally wrong JSON.
        (None, "http"),
        ({"no_choices": 1}, "malformed"),
        ({"choices": []}, "malformed"),
        ({"choices": [{"message": "text"}]}, "malformed"),
    ],
)
def test_t_lm_05_malformed_responses(payload, kind):
    def handler(request):
        if payload is None:
            return httpx.Response(200, content=b"not json at all")
        return httpx.Response(200, json=payload)

    llm = LMStudioClient(BASE_URL, "m", 5.0, client_for(handler))
    with pytest.raises(LLMError) as raised:
        llm.complete([], None)
    assert raised.value.retryable is False
    assert raised.value.kind == kind


def test_t_lm_06_null_content_is_not_an_error():
    def handler(request):
        return httpx.Response(200, json=answer(content=None))

    llm = LMStudioClient(BASE_URL, "m", 5.0, client_for(handler))
    response = llm.complete([], None)
    assert response == LLMResponse("", [], "stop")


def test_t_lm_07_openrouter_request_shape():
    seen = []
    llm = OpenRouterClient(SENTINEL_KEY, "vendor/model", 5.0, client_for(capture(seen)))
    llm.complete([{"role": "user", "content": "hi"}], None)
    request = seen[0]
    assert str(request.url) == "https://openrouter.ai/api/v1/chat/completions"
    assert request.headers["authorization"] == f"Bearer {SENTINEL_KEY}"
    assert request.headers["x-title"] == "tg-agent-bot"


def test_t_lm_08_api_key_never_leaks_into_errors():
    config.register_secret(SENTINEL_KEY)

    def handler(request):
        return httpx.Response(400, text=f"bad key {SENTINEL_KEY} rejected")

    llm = OpenRouterClient(SENTINEL_KEY, "vendor/model", 5.0, client_for(handler))
    with pytest.raises(LLMError) as raised:
        llm.complete([], None)
    assert SENTINEL_KEY not in str(raised.value)
    assert "***REDACTED***" in str(raised.value)


def test_t_lm_09_provider_switch(tmp_path):
    common = {
        "TELEGRAM_BOT_TOKEN": "123456789:token-value-here",
        "ALLOWED_TG_IDS": "1",
    }
    with httpx.Client(transport=mock_llm_transport(lambda r: httpx.Response(200))) as http:
        cfg = config.load_config(
            env={**common, "LMSTUDIO_MODEL": "m"}, load_env_file=False
        )
        assert isinstance(build_llm_client(cfg, client=http), LMStudioClient)
        cfg = config.load_config(
            env={
                **common,
                "LLM_PROVIDER": "openrouter",
                "OPENROUTER_API_KEY": "key-value-here",
                "OPENROUTER_MODEL": "vendor/model",
            },
            load_env_file=False,
        )
        assert isinstance(build_llm_client(cfg, client=http), OpenRouterClient)


def test_base_url_trailing_slash_is_stripped():
    cfg = config.load_config(
        env={
            "TELEGRAM_BOT_TOKEN": "123456789:token-value-here",
            "ALLOWED_TG_IDS": "1",
            "LMSTUDIO_BASE_URL": "http://localhost:1234/v1/",
            "LMSTUDIO_MODEL": "m",
        },
        load_env_file=False,
    )
    assert cfg.lmstudio_base_url == "http://localhost:1234/v1"
