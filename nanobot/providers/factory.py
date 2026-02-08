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
        
        # Route to OpenAIProvider if api_base is provided or model matches general patterns
        # Standard OpenAI-compatible endpoints should use OpenAIProvider
        is_openai_compatible = api_base is not None
        if "gpt" in model.lower() or "deepseek" in model.lower() or "qwen" in model.lower():
             # However, we only use OpenAIProvider for these if they aren't explicit native cloud models
             # For now, if api_base is present, it's almost certainly a proxy/SiliconFlow
             pass

        if api_base:
            logger.debug(f"Routing to OpenAIProvider for: {model}")
            return OpenAIProvider(
                api_key=api_key,
                api_base=api_base,
                default_model=model,
            )

        logger.debug(f"Routing to LiteLLMProvider for: {model}")
        return LiteLLMProvider(
            api_key=api_key,
            api_base=api_base,
            default_model=model,
            **kwargs
        )
