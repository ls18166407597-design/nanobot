"""OpenAI-compatible LLM provider implementation."""

import json
from typing import Any

from openai import AsyncOpenAI
from loguru import logger

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class OpenAIProvider(LLMProvider):
    """
    LLM provider for OpenAI-compatible APIs.

    Directly uses the OpenAI SDK for maximum compatibility and stability
    on standard endpoints (SiliconFlow, DeepSeek, Local proxies, etc.).
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_base: str | None = None,
        default_model: str = "gpt-4o",
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        
        # Initialize client
        self.client = AsyncOpenAI(
            api_key=api_key or "no-key",  # SDK requires a string
            base_url=api_base,
            timeout=60.0,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """
        Send a chat completion request to the OpenAI-compatible API.
        """
        run_model = model or self.default_model
        
        kwargs: dict[str, Any] = {
            "model": run_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "timeout": timeout,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = await self.client.chat.completions.create(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"OpenAIProvider error: {e}")
            return LLMResponse(
                content=f"Error calling OpenAI-compatible LLM: {str(e)}",
                finish_reason="error",
            )

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse OpenAI response into our standard format."""
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string
                args_str = tc.function.arguments
                try:
                    args = json.loads(args_str)
                except json.JSONDecodeError:
                    args = {"raw": args_str}

                tool_calls.append(
                    ToolCallRequest(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    )
                )

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }

        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )

    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model
