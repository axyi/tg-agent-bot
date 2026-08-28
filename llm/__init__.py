"""Inference behind one swappable interface: a two-branch provider switch."""

import httpx

from config import Config, ConfigError
from llm.base import LLMClient, LLMError, LLMResponse, ToolCall
from llm.lmstudio import LMStudioClient
from llm.openrouter import OpenRouterClient

__all__ = [
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "ToolCall",
    "build_llm_client",
]


def build_llm_client(cfg: Config, *, client: httpx.Client) -> LLMClient:
    if cfg.llm_provider == "lmstudio":
        return LMStudioClient(
            cfg.lmstudio_base_url, cfg.lmstudio_model, cfg.llm_timeout_s, client
        )
    if cfg.llm_provider == "openrouter":
        return OpenRouterClient(
            cfg.openrouter_api_key, cfg.openrouter_model, cfg.llm_timeout_s, client
        )
    raise ConfigError(f"unknown provider: {cfg.llm_provider}")
