"""Model registry for managing multiple LLM providers and quotas."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
from loguru import logger


@dataclass
class ProviderInfo:
    """Information about a registered LLM provider."""

    name: str
    base_url: str
    api_key: str
    models: list[str] = field(default_factory=list)
    is_free: bool = False
    balance: float = 0.0
    currency: str = "USD"
    error: str | None = None


class ModelRegistry:
    """Registry for managing multiple LLM providers."""

    def __init__(self):
        self.providers: dict[str, ProviderInfo] = {}

    async def register(
        self, base_url: str, api_key: str, name: str | None = None
    ) -> ProviderInfo:
        """
        Register a provider and check its status/quota.
        
        Args:
            base_url: The API base URL (e.g., https://api.openai.com/v1)
            api_key: The API key
            name: Optional name for the provider
            
        Returns:
            ProviderInfo with updated status
        """
        if not name:
            name = f"provider_{len(self.providers) + 1}"

        info = ProviderInfo(name=name, base_url=base_url, api_key=api_key)
        
        # Check quota/models
        await self._check_provider_status(info)
        
        self.providers[name] = info
        return info

    def get_provider(self, strategy: str = "free_first") -> ProviderInfo | None:
        """
        Get a provider based on strategy.
        
        Args:
            strategy: Selection strategy ("free_first", "random", etc.)
            
        Returns:
            ProviderInfo or None if no providers available
        """
        if not self.providers:
            return None
            
        if strategy == "free_first":
            # Try to find a free provider with balance or no error
            for provider in self.providers.values():
                if provider.is_free and (provider.balance > 0 or not provider.error):
                    return provider
            
            # Fallback to any working provider
            for provider in self.providers.values():
                if not provider.error:
                    return provider
                    
        # Default: return first available
        return next(iter(self.providers.values()))

    async def _check_provider_status(self, info: ProviderInfo) -> None:
        """Check provider status, models, and quota."""
        headers = {"Authorization": f"Bearer {info.api_key}"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # 1. Check Subscription/Quota (OpenAI/One API standard)
                # Try billing subscription first
                r = await client.get(f"{info.base_url}/dashboard/billing/subscription", headers=headers)
                if r.status_code == 200:
                    data = r.json()
                    # One API often returns 'hard_limit_usd' or 'system_hard_limit_usd'
                    # and 'has_payment_method'
                    # This varies wildly between implementations, but let's try standard fields
                    if "hard_limit_usd" in data:
                        # Likely One API or OpenAI
                        limit = data.get("hard_limit_usd", 0.0)
                        # Ensure limit is float
                        if isinstance(limit, (int, float)):
                            pass
                        else:
                            limit = 0.0
                    
                    # Try to get balance from credit grants if available
                    # One API often returns remaining quota in a specific way or we calculate it
                    pass
                
                # Check User/Usage to determine if "free" (heuristic)
                # For One API, we can check /v1/models to see if it works
                
                # 2. Check Models
                r_models = await client.get(f"{info.base_url}/models", headers=headers)
                if r_models.status_code == 200:
                    data = r_models.json()
                    info.models = [m["id"] for m in data.get("data", [])]
                    info.error = None
                else:
                    info.error = f"Failed to list models: {r_models.status_code}"
                    
                # 3. Check Balance (One API specific usually /v1/dashboard/billing/usage or credit_grants)
                # One API often uses /dashboard/billing/credit_grants for balance
                r_credits = await client.get(f"{info.base_url}/dashboard/billing/credit_grants", headers=headers)
                if r_credits.status_code == 200:
                    data = r_credits.json()
                    # OpenAI format: total_available
                    # One API format might vary
                    if "total_available" in data:
                        info.balance = float(data["total_available"])
                    elif "grants" in data:
                         # Sum up active grants
                         info.balance = sum(g.get("grant_amount", 0) - g.get("used_amount", 0) for g in data["grants"]["data"])
                         
                    # Heuristic: If balance > 0, we can mark it as useful
                    # If it's a "free" API often the balance is high or fake
                    
                # Heuristic for "is_free":
                # If the user registered it as free, or if we detect "free" in name?
                # For now, we assume if it works and has balance, it's good.
                # We interpret "is_free" as "registered for subagent use" basically.
                info.is_free = True 

            except Exception as e:
                info.error = str(e)
                logger.warning(f"Failed to check provider {info.name}: {e}")
