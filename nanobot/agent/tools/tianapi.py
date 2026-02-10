import json
from typing import Any, Dict, List, Optional

import httpx
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.config.loader import get_data_dir


class TianAPITool(Tool):
    """Tool for retrieving social media trends and hot lists from TianAPI."""

    name = "tianapi"
    description = """
    Access Chinese social media trends and hot lists (Weibo, etc.) using TianAPI.
    
    Actions:
    - 'network_hot': Get aggregated trends from across the Chinese internet.
    - 'weibo_hot': Get real-time Weibo hot search list.
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["network_hot", "weibo_hot"],
                "default": "network_hot",
                "description": "The specific hot list to retrieve.",
            }
        },
        "required": ["action"],
    }

    def _load_config(self) -> Optional[Dict[str, str]]:
        config_path = get_data_dir() / "tianapi_config.json"
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    async def execute(self, action: str = "network_hot", **kwargs: Any) -> ToolResult:
        config = self._load_config()
        if not config:
            return ToolResult(
                success=False,
                output="Error: TianAPI Key not found.",
                remedy="请在 tianapi_config.json 中配置 key 字段。"
            )

        key = config.get("key")
        if not key:
            return ToolResult(
                success=False,
                output="Error: TianAPI key is missing.",
                remedy="请在 tianapi_config.json 中添加 key 字段。"
            )
        
        # Map actions to TianAPI endpoints
        endpoint_map = {
            "network_hot": "networkhot",
            "weibo_hot": "weibohot"
        }
        
        api_name = endpoint_map.get(action, "networkhot")
        url = f"https://apis.tianapi.com/{api_name}/index"
        params = {"key": key}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Some TianAPI endpoints prefer POST data, others work with params
                resp = await client.post(url, data=params)
                if resp.status_code != 200:
                    return ToolResult(success=False, output=f"TianAPI connection error ({resp.status_code})")
                
                data = resp.json()
                if data.get("code") != 200:
                    msg = data.get("msg", "Unknown error")
                    return ToolResult(success=False, output=f"TianAPI error: {msg}")

                res_list = data.get("result", {}).get("list", [])
                if not res_list:
                    return ToolResult(success=True, output=f"No {action} data found at the moment.")

                # Format results with flexible field mapping
                output = [f"### TianAPI {action.replace('_', ' ').title()} Result\n"]
                for i, item in enumerate(res_list[:20], 1):
                    # TianAPI uses different field names for different APIs
                    title = item.get("title") or item.get("hotword") or item.get("word") or "No Title"
                    hot_score = item.get("hotnum") or item.get("hotwordnum") or item.get("index") or ""
                    desc = item.get("digest") or item.get("content") or ""
                    
                    line = f"{i}. **{title}**"
                    if hot_score:
                        line += f" (Hot: {hot_score})"
                    output.append(line)
                    if desc and len(desc) > 5:
                        output.append(f"   _{desc.strip()}_")

                return ToolResult(success=True, output="\n".join(output))

            except Exception as e:
                return ToolResult(success=False, output=f"TianAPI Tool Error: {str(e)}")
