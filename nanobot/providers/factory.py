from typing import Any
from loguru import logger
from nanobot.providers.base import LLMProvider
from nanobot.providers.litellm_provider import LiteLLMProvider
from nanobot.providers.gemini_provider import GeminiProvider

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
            # DISABLED: Native GeminiProvider causes tool calling loops
            # The user-role tool response format confuses the model
            # Reverting to OpenAI compatible protocol for better stability
            # if ("gemini" in model.lower() or "flash" in model.lower()) and ("127.0.0.1" in api_base or "localhost" in api_base):
            #     logger.debug(f"Routing to native GeminiProvider for local proxy: {model}")
            #     return GeminiProvider(
            #         api_key=api_key,
            #         api_base=api_base,
            #         default_model=model,
            #     )

            logger.debug(f"Routing to OpenAIProvider for OpenAI-compatible endpoint: {model}")
            return OpenAIProvider(
                api_key=api_key,
                api_base=api_base,
                default_model=model,
            )

        # DISABLED: Native GeminiProvider for direct Gemini API
        # if "gemini" in model.lower() or "flash" in model.lower():
        #     logger.debug(f"Routing to native GeminiProvider for direct model: {model}")
        #     return GeminiProvider(
        #         api_key=api_key,
        #         default_model=model,
        #     )

        logger.debug(f"Routing to LiteLLMProvider for native model: {model}")
        return LiteLLMProvider(
            api_key=api_key,
            default_model=model,
            **kwargs
        )
