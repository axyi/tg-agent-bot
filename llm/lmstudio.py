"""LM Studio adapter — a local OpenAI-compatible server, no authentication."""

import httpx

from llm.base import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_MAX_TOKENS,
    LLMResponse,
    build_payload,
    post_completion,
)


class LMStudioClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float,
        client: httpx.Client,
        *,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        context_length: int = DEFAULT_CONTEXT_LENGTH,
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self.context_length = context_length
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
            url=f"{self.base_url}/chat/completions",
            headers={"Content-Type": "application/json"},
            payload=build_payload(
                self.model,
                messages,
                tools,
                max_tokens=self.max_tokens if max_tokens is None else max_tokens,
            ),
            timeout_s=self.timeout_s,
        )
