"""OpenRouter adapter — the same wire format behind a bearer token."""

import httpx

from llm.base import LLMResponse, build_payload, post_completion

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterClient:
    def __init__(
        self, api_key: str, model: str, timeout_s: float, client: httpx.Client
    ) -> None:
        self.model = model
        self.timeout_s = timeout_s
        self._api_key = api_key
        self._client = client

    def complete(self, messages: list[dict], tools: list[dict] | None) -> LLMResponse:
        return post_completion(
            client=self._client,
            url=OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "X-Title": "tg-agent-bot",
            },
            payload=build_payload(self.model, messages, tools),
            timeout_s=self.timeout_s,
        )
