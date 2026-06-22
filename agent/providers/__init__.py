"""Multi-provider LLM layer: Anthropic (Claude), OpenAI (GPT), Google (Gemini).

Usage:
    provider = create_provider("openai", api_key=..., model="gpt-4o")
    resp = await provider.create(messages, system=..., tools=...)
"""

import logging

from .base import LLMProvider, LLMResponse, ToolCall

logger = logging.getLogger(__name__)

VALID_PROVIDERS = {"anthropic", "openai", "gemini"}

# Default OpenAI-compatible endpoint for Google Gemini.
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"


def detect_provider(model: str) -> str | None:
    """Infer the provider from a model name. Returns None if unknown."""
    m = (model or "").lower()
    if m.startswith("claude") or "claude" in m:
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4", "chatgpt")) or "openai" in m:
        return "openai"
    if m.startswith("gemini") or m.startswith("models/gemini") or "gemini" in m:
        return "gemini"
    return None


def create_provider(
    provider_name: str,
    *,
    api_key: str,
    model: str,
    base_url: str | None = None,
    max_tokens: int = 4096,
    thinking_budget: int = 10000,
) -> LLMProvider:
    """Build a provider instance. Imports SDK lazily so missing optional deps
    only fail when that provider is actually used."""
    provider_name = (provider_name or "").lower()

    if provider_name == "anthropic":
        from .anthropic_provider import AnthropicProvider
        return AnthropicProvider(
            api_key=api_key, model=model, base_url=base_url,
            max_tokens=max_tokens, thinking_budget=thinking_budget,
        )

    if provider_name in ("openai", "gemini"):
        from .openai_provider import OpenAIProvider
        if provider_name == "gemini" and not base_url:
            base_url = DEFAULT_GEMINI_BASE_URL
        return OpenAIProvider(
            api_key=api_key, model=model, base_url=base_url,
            max_tokens=max_tokens, thinking_budget=thinking_budget,
            provider_name=provider_name,
        )

    raise ValueError(
        f"Unknown provider: {provider_name!r}. Valid: {', '.join(sorted(VALID_PROVIDERS))}"
    )


__all__ = [
    "LLMProvider",
    "LLMResponse",
    "ToolCall",
    "create_provider",
    "detect_provider",
    "VALID_PROVIDERS",
    "DEFAULT_GEMINI_BASE_URL",
]
