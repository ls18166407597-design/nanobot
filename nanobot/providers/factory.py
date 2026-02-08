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
        logger.debug(f"Creating provider for model: {model} (base: {api_base})")
        
        # LiteLLM handles most model routing internally, 
        # but we can add custom provider mapping here if needed.
        return LiteLLMProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=model,
            **kwargs
        )
