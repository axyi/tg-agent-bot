"""Provider-independent parts of the inference plugin.

Both adapters share the payload builder, the response parser and the HTTP error
mapping; only the URL and the headers differ.
"""

import json
from dataclasses import dataclass
from typing import Protocol

import httpx

import config


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: str            # raw JSON text as returned by the provider


@dataclass(frozen=True)
class LLMResponse:
    content: str              # "" when the provider returns null/absent
    tool_calls: list[ToolCall]
    finish_reason: str        # "" when absent


class LLMError(Exception):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None,
    ) -> LLMResponse: ...


def build_payload(model: str, messages: list[dict], tools: list[dict] | None) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 1024,
        "stream": False,
    }
    if tools is not None:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"
    return payload


def parse_response(data: object) -> LLMResponse:
    if not isinstance(data, dict):
        raise _malformed("the response body is not an object")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise _malformed("'choices' is missing or empty")
    choice = choices[0]
    if not isinstance(choice, dict):
        raise _malformed("'choices[0]' is not an object")
    message = choice.get("message")
    if not isinstance(message, dict):
        raise _malformed("'choices[0].message' is not an object")

    tool_calls = []
    for entry in message.get("tool_calls") or []:
        entry = entry if isinstance(entry, dict) else {}
        function = entry.get("function")
        function = function if isinstance(function, dict) else {}
        raw_arguments = function.get("arguments")
        if raw_arguments is None:
            arguments = ""
        elif isinstance(raw_arguments, str):
            arguments = raw_arguments
        else:
            # Some servers return a JSON object instead of a JSON string.
            arguments = json.dumps(raw_arguments, ensure_ascii=False)
        tool_calls.append(
            ToolCall(
                id=str(entry.get("id") or ""),
                name=str(function.get("name") or ""),
                arguments=arguments,
            )
        )

    return LLMResponse(
        content=str(message.get("content") or ""),
        tool_calls=tool_calls,
        finish_reason=str(choice.get("finish_reason") or ""),
    )


def post_completion(
    *,
    client: httpx.Client,
    url: str,
    headers: dict,
    payload: dict,
    timeout_s: float,
) -> LLMResponse:
    """Perform one chat-completions request and map every failure to `LLMError`."""
    try:
        response = client.post(url, json=payload, headers=headers, timeout=timeout_s)
    except httpx.TimeoutException:
        # TimeoutException is a TransportError subclass; it must be checked first.
        raise _error("llm request timed out", retryable=True) from None
    except httpx.TransportError as exc:
        raise _error(
            f"llm transport error: {exc.__class__.__name__}", retryable=True
        ) from None

    status = response.status_code
    if status == 429:
        raise _error("llm http 429", retryable=True)
    if 500 <= status <= 599:
        raise _error(f"llm http {status}", retryable=True)
    if 400 <= status <= 499:
        raise _error(f"llm http {status}: {response.text[:200]}", retryable=False)

    try:
        data = response.json()
    except ValueError:
        raise _error("llm response is not json", retryable=False) from None
    return parse_response(data)


def _error(message: str, *, retryable: bool) -> LLMError:
    return LLMError(config.redact(message), retryable=retryable)


def _malformed(detail: str) -> LLMError:
    return _error(f"malformed provider response: {detail}", retryable=False)
