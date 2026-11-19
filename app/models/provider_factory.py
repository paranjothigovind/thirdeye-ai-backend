"""Selects the active LLM generation provider from configuration.

The provider is created on first use and reused for the life of the process;
``close_llm_provider`` releases its HTTP resources at application shutdown.
"""
from typing import Optional

from app.core.config import Settings, settings as app_settings
from app.core.logging import get_logger
from app.models.base import LLMProvider

logger = get_logger(__name__)

_provider: Optional[LLMProvider] = None


def create_llm_provider(config: Settings) -> LLMProvider:
    """Build a new provider for ``config.LLM_PROVIDER``."""
    if config.LLM_PROVIDER == "anthropic":
        from app.models.anthropic_claude import AnthropicProvider

        api_key = config.ANTHROPIC_API_KEY.get_secret_value() if config.ANTHROPIC_API_KEY else ""
        return AnthropicProvider(
            api_key=api_key,
            model=config.ANTHROPIC_MODEL,
            max_tokens=config.ANTHROPIC_MAX_TOKENS,
            timeout=config.ANTHROPIC_TIMEOUT,
            max_retries=config.ANTHROPIC_MAX_RETRIES,
            effort=config.ANTHROPIC_EFFORT or None,
            refusal_fallback=config.ANTHROPIC_REFUSAL_FALLBACK,
        )

    if config.LLM_PROVIDER == "azure_openai":
        # Reuse the module-level Azure client so there is a single instance.
        from app.models.azure_openai import azure_openai_client

        return azure_openai_client

    raise ValueError(f"Unsupported LLM_PROVIDER: {config.LLM_PROVIDER!r}")


def get_llm_provider() -> LLMProvider:
    """Return the shared provider, creating it on first call."""
    global _provider
    if _provider is None:
        _provider = create_llm_provider(app_settings)
        logger.info(f"LLM provider selected: {_provider.name} (model={_provider.model})")
    return _provider


async def close_llm_provider() -> None:
    """Close the shared provider's network resources (application shutdown)."""
    global _provider
    if _provider is not None:
        provider, _provider = _provider, None
        await provider.aclose()
