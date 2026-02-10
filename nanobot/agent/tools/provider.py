"""Tool for checking LLM provider status and quota."""

import asyncio
from typing import Any, Literal

from nanobot.agent.models import ModelRegistry
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.config.loader import load_config, save_config


class ProviderTool(Tool):
    """Tool to manage LLM providers (check, add, list, remove)."""

    def __init__(self, registry: ModelRegistry | None = None):
        self.registry = registry or ModelRegistry()

    @property
    def name(self) -> str:
        return "provider"

    @property
    def description(self) -> str:
        return (
            "Manage LLM providers. Actions:\n"
            "- 'check': Check status/balance of a provider (requires api_key or name).\n"
            "- 'add': Register and save a new provider (requires name, base_url, api_key).\n"
            "- 'list': List all configured providers.\n"
            "- 'remove': Remove a provider by name."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["check", "add", "list", "remove"],
                    "description": "The action to perform.",
                },
                "api_key": {
                    "type": "string",
                    "description": "The API key to check or add.",
                },
                "base_url": {
                    "type": "string",
                    "description": "The API base URL (default: https://api.openai.com/v1)",
                },
                "name": {
                    "type": "string",
                    "description": "Name of the provider (required for add/remove/check-by-name).",
                },
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: Literal["check", "add", "list", "remove"],
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        name: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute the provider action."""
        try:
            if action == "check":
                output = await self._check(api_key, base_url, name)
                if "❌ Error" in output:
                    return ToolResult(success=False, output=output, remedy="请检查 API Key 和 Base URL 是否正确。")
                return ToolResult(success=True, output=output)
            elif action == "add":
                output = await self._add(api_key, base_url, name)
                if "failed" in output.lower():
                    return ToolResult(success=False, output=output, remedy="添加失败，请检查参数或网络连接。")
                return ToolResult(success=True, output=output)
            elif action == "list":
                output = self._list()
                return ToolResult(success=True, output=output)
            elif action == "remove":
                output = self._remove(name)
                if "not found" in output.lower():
                    return ToolResult(success=False, output=output, remedy="请检查要删除的供应商名称是否正确。")
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, output=f"Error executing provider action '{action}': {str(e)}")

    async def _check(self, api_key: str | None, base_url: str, name: str | None) -> str:
        if not api_key:
            # If no key provided, try to find by name in registry or config
            if name:
                config = load_config()
                found = next((p for p in config.brain.provider_registry if p.get("name") == name), None)
                if found:
                    api_key = found.get("api_key")
                    base_url = found.get("base_url", base_url)
                else:
                    return f"Provider '{name}' not found in configuration. Please provide api_key."
            else:
                return "Please provide either 'api_key' or 'name' to check."

        # Registering effectively checks it
        info = await self.registry.register(base_url=base_url, api_key=api_key, name=name)
        
        status = "✅ Active" if not info.error else f"❌ Error: {info.error}"
        models_sample = ", ".join(info.models[:5]) + ("..." if len(info.models) > 5 else "")
        
        return (
            f"Provider: {info.name}\n"
            f"Status: {status}\n"
            f"Base URL: {info.base_url}\n"
            f"Balance: ${info.balance:.4f}\n"
            f"Models: {models_sample or 'None found'}\n"
        )

    async def _add(self, api_key: str | None, base_url: str, name: str | None) -> str:
        if not name or not api_key:
            return "Both 'name' and 'api_key' are required to add a provider."

        # Verify first by checking
        check_result = await self._check(api_key, base_url, name)
        if "❌ Error" in check_result:
             return f"verification failed. Provider not added.\n{check_result}"

        # Save to config
        config = load_config()
        
        # Update if exists
        updated = False
        for p in config.brain.provider_registry:
            if p.get("name") == name:
                p["base_url"] = base_url
                p["api_key"] = api_key
                updated = True
                break
        
        if not updated:
            config.brain.provider_registry.append(
                {"name": name, "base_url": base_url, "api_key": api_key}
            )
            
        save_config(config)
        action_str = "Updated" if updated else "Added"
        
        return f"Successfully {action_str} provider '{name}'.\n\n{check_result}"

    def _list(self) -> str:
        config = load_config()
        if not config.brain.provider_registry:
            return "No providers configured."
            
        lines = ["Configured Providers:"]
        for p in config.brain.provider_registry:
            name = p.get("name", "N/A")
            url = p.get("base_url", "N/A")
            lines.append(f"- {name} ({url})")
            
        return "\n".join(lines)

    def _remove(self, name: str | None) -> str:
        if not name:
            return "Name is required to remove a provider."
            
        config = load_config()
        initial_len = len(config.brain.provider_registry)
        config.brain.provider_registry = [
            p for p in config.brain.provider_registry if p.get("name") != name
        ]
        
        if len(config.brain.provider_registry) < initial_len:
            save_config(config)
            return f"Successfully removed provider '{name}'."
        else:
            return f"Provider '{name}' not found."
