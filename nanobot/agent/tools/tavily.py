import json
from typing import Any, Dict, List, Optional

import httpx
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import get_tool_config_path


class TavilyTool(Tool):
    """Tool for conducting high-quality searches using Tavily with multi-key support."""

    name = "tavily"
    description = """
    Conduct search and research using the Tavily API. Use this when you need accurate, 
    AI-optimized search results from the web.
    
    Actions:
    - 'search': Quick search with basic results and snippets.
    - 'research': In-depth research that extracts content from top results (Markdown friendly).
    """
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to perform.",
            },
            "action": {
                "type": "string",
                "enum": ["search", "research"],
                "default": "search",
                "description": "The type of search action (search for quick results, research for deeper content).",
            },
            "max_results": {
                "type": "integer",
                "default": 5,
                "description": "The maximum number of results to return.",
            },
        },
        "required": ["query"],
    }

    def _load_config(self) -> Optional[Dict[str, Any]]:
        config_path = get_tool_config_path("tavily_config.json")
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    async def execute(self, query: str, action: str = "search", max_results: int = 5, **kwargs: Any) -> ToolResult:
        config = self._load_config()
        if not config:
            return ToolResult(
                success=False,
                output="Error: Tavily API Key not found.",
                remedy="请在 tavily_config.json 中配置 keys（数组）或 key（单个）。"
            )

        keys = config.get("keys", [])
        # Support single key format
        if not keys and config.get("key"):
            keys = [config.get("key")]

        if not keys:
            return ToolResult(
                success=False,
                output="Error: No Tavily API keys configured.",
                remedy="请在 tavily_config.json 中配置 keys（数组）或 key（单个）。"
            )

        url = "https://api.tavily.com/search"
        
        last_error = ""
        for api_key in keys:
            payload = {
                "api_key": api_key,
                "query": query,
                "search_depth": "advanced" if action == "research" else "basic",
                "include_content": True if action == "research" else False,
                "max_results": max_results
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                try:
                    resp = await client.post(url, json=payload)
                    
                    # 429 is Rate Limit or Credits Depleted
                    if resp.status_code == 429:
                        last_error = f"Key (ends with {api_key[-4:]}) rate limited or exhausted."
                        continue
                    
                    if resp.status_code != 200:
                        last_error = f"Tavily API error ({resp.status_code}) with key {api_key[-4:]}: {resp.text}"
                        continue
                    
                    data = resp.json()
                    results = data.get("results", [])
                    
                    if not results:
                        return ToolResult(success=True, output=f"No results found for '{query}'.")

                    output = [f"### Tavily Search Results for: {query}\n"]
                    for i, res in enumerate(results, 1):
                        title = res.get("title", "No Title")
                        res_url = res.get("url", "#")
                        content = res.get("content", "")
                        raw_content = res.get("raw_content", "")
                        
                        output.append(f"**{i}. [{title}]({res_url})**")
                        if action == "research" and raw_content:
                            output.append(f"{raw_content[:800]}...\n")
                        else:
                            output.append(f"{content}\n")

                    return ToolResult(success=True, output="\n".join(output))

                except Exception as e:
                    last_error = f"Tavily Tool Error with key {api_key[-4:]}: {str(e)}"
                    continue
        
        return ToolResult(success=False, output=f"All Tavily API keys failed. Last error: {last_error}")
