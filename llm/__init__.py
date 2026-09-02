"""Inference behind one swappable interface: a two-branch provider switch."""

import httpx

from config import Config, ConfigError, parse_summary_model
from llm.base import LLMClient, LLMError, LLMResponse, ToolCall
from llm.failover import FailoverLLMClient
from llm.lmstudio import LMStudioClient
from llm.openrouter import OpenRouterClient

__all__ = [
    "FailoverLLMClient",
    "LLMClient",
    "LLMError",
    "LLMResponse",
    "ToolCall",
    "build_llm_client",
    "provider_is_configured",
]


def provider_is_configured(cfg: Config, provider: str) -> bool:
    if provider == "lmstudio":
        return bool(cfg.lmstudio_base_url and cfg.lmstudio_model)
    if provider == "openrouter":
        return bool(cfg.openrouter_api_key and cfg.openrouter_model)
    return False


def build_llm_client(
    cfg: Config,
    *,
    client: httpx.Client,
    override: str | None = None,
    purpose: str = "agent",
) -> LLMClient:
    """The client for one purpose, on the caller's `httpx.Client`.

    REQ-V13-RTE-01: with `LLM_SUMMARY_MODEL` set, `purpose="summary"` gets its
    own bare client on the routed provider — no failover, and no effect on the
    agent's client, whose `LLM_FAILOVER` semantics are unchanged. Unset, the
    summary purpose falls through to the main client below, so a caller that
    wants one client per purpose must not build the summary one blindly: with
    no routing that would be a second, needlessly independent main client.
    """
    if purpose == "summary":
        routed = parse_summary_model(cfg.llm_summary_model)
        if routed is not None:
            provider, model = routed
            return _client_for(cfg, provider, client, model=model)

    primary = override or cfg.llm_provider
    if primary not in ("lmstudio", "openrouter"):
        raise ConfigError(f"unknown provider: {primary}")

    secondary = "openrouter" if primary == "lmstudio" else "lmstudio"
    if cfg.llm_failover == "auto" and all(
        provider_is_configured(cfg, name) for name in (primary, secondary)
    ):
        return FailoverLLMClient(
            _client_for(cfg, primary, client),
            _client_for(cfg, secondary, client),
            primary_name=primary,
            secondary_name=secondary,
        )
    return _client_for(cfg, primary, client)


def _client_for(
    cfg: Config, provider: str, client: httpx.Client, *, model: str | None = None
) -> LLMClient:
    """`model` overrides the provider's configured model (the routed purpose);
    everything else — timeout, caps, context length — stays the provider's."""
    if provider == "lmstudio":
        return LMStudioClient(
            cfg.lmstudio_base_url,
            model or cfg.lmstudio_model,
            cfg.llm_timeout_s,
            client,
            max_tokens=cfg.llm_max_tokens,
            context_length=cfg.lmstudio_context_length,
        )
    return OpenRouterClient(
        cfg.openrouter_api_key,
        model or cfg.openrouter_model,
        cfg.llm_timeout_s,
        client,
        max_tokens=cfg.llm_max_tokens,
        context_length=cfg.openrouter_context_length,
    )
