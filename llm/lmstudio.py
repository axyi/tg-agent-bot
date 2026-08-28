"""LM Studio adapter — a local OpenAI-compatible server, no authentication."""

import httpx

from llm.base import LLMResponse, build_payload, post_completion


class LMStudioClient:
    def __init__(
        self, base_url: str, model: str, timeout_s: float, client: httpx.Client
    ) -> None:
        self.base_url = base_url
        self.model = model
        self.timeout_s = timeout_s
        self._client = client

    def complete(self, messages: list[dict], tools: list[dict] | None) -> LLMResponse:
        return post_completion(
            client=self._client,
            url=f"{self.base_url}/chat/completions",
            headers={"Content-Type": "application/json"},
            payload=build_payload(self.model, messages, tools),
            timeout_s=self.timeout_s,
        )
