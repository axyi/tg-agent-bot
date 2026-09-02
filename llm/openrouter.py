"""OpenRouter adapter — the same wire format behind a bearer token."""

import httpx

from llm.base import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_MAX_TOKENS,
    LLMResponse,
    build_payload,
    post_completion,
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# REQ-V13-OBS-01: usage accounting is asked for on every request, so that the
# `usage` object (tokens, cached tokens, `cost`) comes back to be recorded. It
# is an observability prerequisite, not an optimization; LM Studio requests are
# unchanged.
USAGE_ACCOUNTING = {"include": True}

# REQ-V13-CCH-03: Anthropic models bill a cached prefix at a discount, but only
# when the request marks a cache breakpoint explicitly. OpenRouter passes the
# Anthropic content-block form through unchanged, so the system message — the
# byte-stable prefix of REQ-V13-CCH-01 — becomes a single text block carrying
# `cache_control`. Field shape verified against
# https://openrouter.ai/docs/guides/best-practices/prompt-caching (REQ-V13-PRE-05).
# Every other provider keeps the plain string form.
ANTHROPIC_PREFIX = "anthropic/"
CACHE_CONTROL = {"type": "ephemeral"}


def cache_system_prompt(messages: list[dict]) -> list[dict]:
    """The first system message as one cache-marked text block.

    Only the first: `run_agent` appends a second system message as a
    request-time nudge, and marking that one would move the breakpoint to the
    end of the volatile tail and cache nothing. Returns new objects — the agent
    reuses its `messages` list across rounds and must not see the rewrite.
    """
    for index, message in enumerate(messages):
        if message.get("role") != "system":
            continue
        content = message.get("content")
        if not isinstance(content, str) or not content:
            return messages
        block = {"type": "text", "text": content, "cache_control": dict(CACHE_CONTROL)}
        return [*messages[:index], {**message, "content": [block]}, *messages[index + 1:]]
    return messages


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: float,
        client: httpx.Client,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        context_length: int = DEFAULT_CONTEXT_LENGTH,
    ) -> None:
        self.model = model
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.context_length = context_length
        self._api_key = api_key
        self._client = client

    def describe(self) -> tuple[str, str]:
        return ("openrouter", self.model)

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        *,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        if self.model.startswith(ANTHROPIC_PREFIX):
            messages = cache_system_prompt(messages)
        payload = build_payload(
            self.model,
            messages,
            tools,
            max_tokens=self.max_tokens if max_tokens is None else max_tokens,
        )
        payload["usage"] = dict(USAGE_ACCOUNTING)
        return post_completion(
            client=self._client,
            url=OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "X-Title": "tg-agent-bot",
            },
            payload=payload,
            timeout_s=self.timeout_s,
        )
