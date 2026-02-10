from typing import Any
from loguru import logger
from nanobot.providers.base import LLMProvider
from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.providers.gemini_provider import GeminiProvider

class ProviderFactory:
    """Factory for creating LLM provider instances."""
    _cache: dict[str, LLMProvider] = {}

    @classmethod
    def get_provider(
        cls,
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any
    ) -> LLMProvider:
        """
        Create (or reuse) a provider instance based on the model and configuration.
        """
        # Create a cache key based on model, key, and base
        cache_key = f"{model}:{api_key}:{api_base}"
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        from nanobot.providers.openai_provider import OpenAIProvider
        
        if api_base:
            # ...
            logger.debug(f"Routing to OpenAIProvider for OpenAI-compatible endpoint: {model}")
            provider = OpenAIProvider(
                api_key=api_key,
                api_base=api_base,
                default_model=model,
            )
            cls._cache[cache_key] = provider
            return provider

        # ...
        logger.debug(f"Routing to LiteLLMProvider for native model: {model}")
        provider = LiteLLMProvider(
            api_key=api_key,
            default_model=model,
            **kwargs
        )
        cls._cache[cache_key] = provider
        return provider
