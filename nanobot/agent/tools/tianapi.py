import json
from typing import Any, Dict, Optional

import httpx

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import get_tool_config_path


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
                "enum": ["network_hot", "weibo_hot", "area", "license_plate"],
                "default": "network_hot",
                "description": "Operation: hot lists, administrative divisions (area), or license plate lookup.",
            },
            "word": {
                "type": "string",
                "description": "Query word. For area: search name or code. For license_plate: e.g. '京A'."
            }
        },
        "required": ["action"],
    }

    def _load_config(self) -> Optional[Dict[str, str]]:
        config_path = get_tool_config_path("tianapi_config.json")
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
            "weibo_hot": "weibohot",
            "area": "area",
            "license_plate": "chepai"
        }

        api_name = endpoint_map.get(action, "networkhot")
        url = f"https://apis.tianapi.com/{api_name}/index"
        params = {"key": key}

        # Add query parameters if provided
        word = kwargs.get("word")
        if word:
            if action == "license_plate":
                params["chepai"] = word
            else:
                params["word"] = word

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.post(url, data=params)
                if resp.status_code != 200:
                    return ToolResult(success=False, output=f"TianAPI connection error ({resp.status_code})")

                data = resp.json()
                if data.get("code") != 200:
                    msg = data.get("msg", "Unknown error")
                    return ToolResult(success=False, output=f"TianAPI error: {msg}")

                result_data = data.get("result", {})
                res_list = result_data.get("list") if isinstance(result_data, dict) else None

                # If no list, might be a direct object (common in some TianAPI responses)
                if res_list is None and isinstance(result_data, dict) and result_data:
                    res_list = [result_data]

                if not res_list:
                    return ToolResult(success=True, output=f"No {action} data found for '{word or 'default'}'.")

                # Format results
                output = [f"### TianAPI {action.replace('_', ' ').title()} Result\n"]
                for i, item in enumerate(res_list[:20], 1):
                    if action == "license_plate":
                        province = item.get("province", "")
                        city = item.get("city", "")
                        info = item.get("info", "")
                        output.append(f"{i}. **{word}**: {province} {city} ({info})")
                    elif action == "area":
                        name = item.get("areaname") or item.get("name") or "Unknown"
                        code = item.get("areacode") or item.get("id") or ""
                        output.append(f"{i}. **{name}** (Code: {code})")
                    else:
                        title = item.get("title") or item.get("hotword") or item.get("word") or "No Title"
                        hot_score = item.get("hotnum") or item.get("hotwordnum") or ""
                        line = f"{i}. **{title}**"
                        if hot_score:
                            line += f" (Hot: {hot_score})"
                        output.append(line)

                return ToolResult(success=True, output="\n".join(output))

            except Exception as e:
                return ToolResult(success=False, output=f"TianAPI Tool Error: {str(e)}")
