from typing import Any
from loguru import logger
from nanobot.providers.base import LLMProvider
from nanobot.providers.litellm_provider import LiteLLMProvider

class ProviderFactory:
    """Factory for creating LLM provider instances."""

    @staticmethod
    def get_provider(
        model: str,
        api_key: str | None = None,
        api_base: str | None = None,
        **kwargs: Any
    ) -> LLMProvider:
        """
        Create a provider instance based on the model and configuration.
        
        Currently uses LiteLLMProvider as the unified implementation.
        """
        from nanobot.providers.openai_provider import OpenAIProvider
        
        if api_base:
            # If api_base is present, it's likely an OpenAI-compatible proxy (SiliconFlow, etc.)
            # OpenAIProvider is often more stable for these than LiteLLM
            logger.debug(f"Routing to OpenAIProvider for OpenAI-compatible endpoint: {model}")
            return OpenAIProvider(
                api_key=api_key,
                api_base=api_base,
                default_model=model,
            )

        logger.debug(f"Routing to LiteLLMProvider for native model: {model}")
        return LiteLLMProvider(
            api_key=api_key,
            default_model=model,
            **kwargs
        )
