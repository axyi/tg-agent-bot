"""Provider-independent parts of the inference plugin.

Both adapters share the payload builder, the response parser and the HTTP error
mapping; only the URL and the headers differ.
"""

import json
import re
from collections.abc import Callable
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
class Usage:
    """What the provider reports about one completion (REQ-V13-OBS-01).

    Every field is optional and a missing one is `None`, never 0: usage is
    advisory, and a zero would be indistinguishable from "not reported".
    """

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    reasoning_tokens: int | None = None
    provider_cost_usd: float | None = None


# `(provider, model, usage) -> (cost_usd, cost_basis)`. The agent never computes
# or fetches a price itself; it only stores what the resolver returns, and
# `None` (no resolver) stores NULL/NULL (REQ-V13-OBS-04, REQ-V13-PRC-02).
CostResolver = Callable[[str, str, "Usage | None"], tuple[float | None, str | None]]


@dataclass(frozen=True)
class LLMResponse:
    content: str              # "" when the provider returns null/absent
    tool_calls: list[ToolCall]
    finish_reason: str        # "" when absent
    usage: Usage | None = None            # None when the provider reports nothing
    reasoning_chars: int = 0              # thinking text seen and withheld


class LLMError(Exception):
    """`kind` splits the failures the agent treats differently: a `malformed`
    answer is worth re-asking for, an `http` 4xx is not (REQ-V1-RP-01)."""

    def __init__(self, message: str, *, retryable: bool, kind: str = "http") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.kind = kind


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        *,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    def describe(self) -> tuple[str, str]:
        """`(provider, model)` — a read-only label for the observability row."""
        ...


DEFAULT_MAX_TOKENS = 1024
DEFAULT_CONTEXT_LENGTH = 4096

# The request-control values of spec-v1, unchanged, in one place so that the
# benchmark can lock them in `meta.constants` (spec-v1.3 section 2).
REQUEST_DEFAULTS = {
    "temperature": 0,
    "stream": False,
    "tool_choice": "auto",
}

UNKNOWN_CLIENT = "unknown"

# Only balanced pairs are matched here; an unclosed opener is handled separately
# because it means the answer was cut off mid-thought.
_THINK_BLOCK = re.compile(r"<think>(.*?)</think>", re.DOTALL)
_THINK_OPEN = "<think>"


def describe_client(client: object) -> tuple[str, str]:
    """`describe()` of a client that has one; a safe label for one that has not.

    `provider`/`model` are NOT NULL columns, and test doubles predating
    REQ-V13-OBS-04 expose neither method nor attribute.
    """
    describe = getattr(client, "describe", None)
    if callable(describe):
        provider, model = describe()
        return str(provider), str(model)
    return UNKNOWN_CLIENT, str(getattr(client, "model", "") or UNKNOWN_CLIENT)


def build_payload(
    model: str,
    messages: list[dict],
    tools: list[dict] | None,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": REQUEST_DEFAULTS["temperature"],
        "max_tokens": max_tokens,
        "stream": REQUEST_DEFAULTS["stream"],
    }
    if tools is not None:
        payload["tools"] = tools
        payload["tool_choice"] = REQUEST_DEFAULTS["tool_choice"]
    return payload


def parse_usage(raw: object) -> Usage | None:
    """The OpenAI-compatible `usage` object, plus OpenRouter's `usage.cost`.

    A field of the wrong type is `None`, exactly like a missing one: the row
    records what the provider actually reported and nothing else.
    """
    if not isinstance(raw, dict):
        return None
    prompt_details = raw.get("prompt_tokens_details")
    completion_details = raw.get("completion_tokens_details")
    return Usage(
        prompt_tokens=_as_int(raw.get("prompt_tokens")),
        completion_tokens=_as_int(raw.get("completion_tokens")),
        total_tokens=_as_int(raw.get("total_tokens")),
        cached_tokens=_as_int(
            prompt_details.get("cached_tokens") if isinstance(prompt_details, dict) else None
        ),
        reasoning_tokens=_as_int(
            completion_details.get("reasoning_tokens")
            if isinstance(completion_details, dict)
            else None
        ),
        provider_cost_usd=_as_float(raw.get("cost")),
    )


def split_reasoning(message: dict) -> tuple[str, int]:
    """`(content the user may see, reasoning characters withheld)`.

    REQ-V13-OBS-02: a provider either reports its thinking in its own field or
    inlines it in `<think>` blocks; either way the user never sees it.
    """
    content = str(message.get("content") or "")
    reasoning_chars = 0
    for field in ("reasoning_content", "reasoning"):
        value = message.get(field)
        if isinstance(value, str):
            # The two fields are alternative spellings of one thing; a provider
            # that sends both must not have its thinking counted twice.
            reasoning_chars = len(value)
            break

    reasoning_chars += sum(len(block) for block in _THINK_BLOCK.findall(content))
    content = _THINK_BLOCK.sub("", content)
    opened = content.find(_THINK_OPEN)
    if opened != -1:
        # An answer cut off by the output cap can open a block and never close
        # it; delivering the remainder would hand the user the whole chain.
        reasoning_chars += len(content) - opened - len(_THINK_OPEN)
        content = content[:opened]
    return content, reasoning_chars


def _as_int(value: object) -> int | None:
    # `bool` is an `int` subclass; `True` is not a token count.
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


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

    content, reasoning_chars = split_reasoning(message)
    return LLMResponse(
        content=content,
        tool_calls=tool_calls,
        finish_reason=str(choice.get("finish_reason") or ""),
        usage=parse_usage(data.get("usage")),
        reasoning_chars=reasoning_chars,
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
        raise _error("llm request timed out", retryable=True, kind="transport") from None
    except httpx.TransportError as exc:
        raise _error(
            f"llm transport error: {exc.__class__.__name__}",
            retryable=True,
            kind="transport",
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


def _error(message: str, *, retryable: bool, kind: str = "http") -> LLMError:
    return LLMError(config.redact(message), retryable=retryable, kind=kind)


def _malformed(detail: str) -> LLMError:
    # `malformed` is reserved for structurally wrong JSON. A body that is not JSON
    # at all stays `http`: the server answered, the payload is garbage.
    return _error(f"malformed provider response: {detail}", retryable=False, kind="malformed")
