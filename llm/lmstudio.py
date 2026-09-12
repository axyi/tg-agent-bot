"""LM Studio adapter — a local OpenAI-compatible server, no authentication."""

import httpx

from llm.base import (
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_MAX_TOKENS,
    REASONING_DEFAULT,
    LLMResponse,
    ReasoningRequest,
    build_payload,
    json_fields,
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

    def describe(self) -> tuple[str, str]:
        return ("lmstudio", self.model)

    def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        *,
        max_tokens: int | None = None,
        reasoning: ReasoningRequest = REASONING_DEFAULT,
        timeout_s: float | None = None,
        response_format: dict | None = None,
    ) -> LLMResponse:
        # REQ-V170-POL-05: `request.mechanism` alone, never `request.tag` --
        # the per-purpose lookup already happened in `resolve_reasoning`.
        mechanism = reasoning.mechanism
        reasoning_fields = None
        if mechanism is not None:
            if mechanism.fields:
                reasoning_fields = json_fields(mechanism.fields)
            if mechanism.message_patch is not None:
                kind, text = mechanism.message_patch
                messages = list(messages)
                if kind == "append_assistant":
                    messages.append({"role": "assistant", "content": text})
                elif kind == "suffix_last_user":
                    last = dict(messages[-1])
                    last["content"] = last["content"] + text
                    messages[-1] = last
        return post_completion(
            client=self._client,
            url=f"{self.base_url}/chat/completions",
            headers={"Content-Type": "application/json"},
            payload=build_payload(
                self.model,
                messages,
                tools,
                max_tokens=self.max_tokens if max_tokens is None else max_tokens,
                reasoning_fields=reasoning_fields,
                response_format=response_format,
            ),
            timeout_s=self.timeout_s if timeout_s is None else timeout_s,
        )
