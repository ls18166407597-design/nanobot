"""Provider failover router for LLM calls."""

from typing import Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.models import ModelRegistry
from nanobot.providers.base import LLMProvider, LLMResponse
from nanobot.providers.factory import ProviderFactory


class ProviderRouter:
    """Route chat requests with provider failover."""

    def __init__(
        self,
        *,
        provider: LLMProvider,
        model: str,
        model_registry: ModelRegistry | None,
        max_tokens: int,
        temperature: float,
        pulse_callback: Callable[[str], Awaitable[None]] | None = None,
    ):
        self.provider = provider
        self.model = model
        self.model_registry = model_registry
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.pulse_callback = pulse_callback

    async def chat_with_failover(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> LLMResponse:
        """Call LLM with automatic failover to other registered providers."""
        candidates = []

        primary_provider = self.provider
        primary_model = self.model
        primary_name = "primary"

        if self.model_registry:
            registry_match = None
            for p_info in self.model_registry.providers.values():
                if p_info.default_model == self.model or self.model in p_info.models or p_info.name == self.model:
                    registry_match = p_info
                    break

            if registry_match and registry_match.base_url != self.provider.api_base:
                logger.debug(f"Switching primary provider to registry match '{registry_match.name}' for model '{self.model}'")
                try:
                    primary_provider = ProviderFactory.get_provider(
                        model=registry_match.default_model or self.model,
                        api_key=registry_match.api_key,
                        api_base=registry_match.base_url,
                    )
                    primary_name = registry_match.name
                except Exception as e:
                    logger.warning(f"Failed to switch to specific provider for {self.model}: {e}")

        candidates.append({"name": primary_name, "provider": primary_provider, "model": primary_model})

        if self.model_registry:
            active_infos = self.model_registry.get_active_providers(model=self.model)
            for p_info in active_infos:
                if p_info.base_url == self.provider.api_base and p_info.default_model == self.model:
                    continue
                try:
                    fallback_provider = ProviderFactory.get_provider(
                        model=p_info.default_model or (p_info.models[0] if p_info.models else self.model),
                        api_key=p_info.api_key,
                        api_base=p_info.base_url,
                    )
                    candidates.append(
                        {
                            "name": p_info.name,
                            "provider": fallback_provider,
                            "model": fallback_provider.default_model,
                        }
                    )
                except Exception as e:
                    logger.warning(f"Failed to create fallback provider {p_info.name}: {e}")

        last_error = None
        for i, candidate in enumerate(candidates):
            try:
                if i > 0 and self.pulse_callback:
                    await self.pulse_callback(f"主模型响应异常，正在尝试备用大脑 ({candidate['name']})，请稍等...")

                response = await candidate["provider"].chat(
                    messages=messages,
                    tools=tools,
                    model=candidate.get("model", self.model),
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout=45.0,
                )

                if response.finish_reason == "error":
                    raise Exception(response.content)

                return response
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {candidate['name']} failed: {e}")
                if self.model_registry:
                    self.model_registry.report_failure(candidate["name"])
                continue

        error_msg = f"抱歉老板，所有可用的大脑（共 {len(candidates)} 个）都暂时无法响应。最后一次错误：{last_error}"
        return LLMResponse(content=error_msg, finish_reason="error")
