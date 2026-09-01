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

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        *,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return post_completion(
            client=self._client,
            url=OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "X-Title": "tg-agent-bot",
            },
            payload=build_payload(
                self.model,
                messages,
                tools,
                max_tokens=self.max_tokens if max_tokens is None else max_tokens,
            ),
            timeout_s=self.timeout_s,
        )
