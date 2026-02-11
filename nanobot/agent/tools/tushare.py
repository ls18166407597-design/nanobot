import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import httpx
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import get_tool_config_path


class TushareTool(Tool):
    """Tool for retrieving Chinese financial data using Tushare API."""

    name = "tushare"
    description = """
    Access Chinese stock market data (A-share) using the Tushare Pro API.
    
    Actions:
    - 'stock_basic': Get listing status and basic info for stocks.
    - 'daily': Get daily quote for a specific stock (e.g., '000001.SZ').
    - 'query': Custom query for advanced users (requires specifying api_name).
    
    Notes for 120-point users:
    - Use 'stock_basic' with list_status='L' to see active stocks.
    - Use 'daily' with a specific 'trade_date' (YYYYMMDD) or rely on the default (yesterday).
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["stock_basic", "daily", "query"],
                "default": "daily",
                "description": "The type of data to retrieve.",
            },
            "ts_code": {
                "type": "string",
                "description": "Stock code (e.g., '000001.SZ', '600000.SH').",
            },
            "trade_date": {
                "type": "string",
                "description": "The trade date in YYYYMMDD format (e.g., '20240119'). Defaults to last weekday if not provided for 'daily'.",
            },
            "api_name": {
                "type": "string",
                "description": "Raw Tushare API name for 'query' action.",
            },
            "params": {
                "type": "object",
                "description": "Additional parameters for the Tushare API call.",
            }
        },
        "required": ["action"],
    }

    def _load_config(self) -> Optional[Dict[str, str]]:
        config_path = get_tool_config_path("tushare_config.json")
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _get_last_weekday(self) -> str:
        dt = datetime.now()
        # If today is Sat or Sun, go back to Fri
        if dt.weekday() == 5: # Saturday
            dt = dt - timedelta(days=1)
        elif dt.weekday() == 6: # Sunday
            dt = dt - timedelta(days=2)
        else:
            # For weekdays, default to yesterday if markets are closed or today
            dt = dt - timedelta(days=1)
        return dt.strftime("%Y%m%d")

    async def execute(self, action: str = "daily", ts_code: Optional[str] = None, trade_date: Optional[str] = None, api_name: Optional[str] = None, params: Optional[Dict[str, Any]] = None, **kwargs: Any) -> ToolResult:
        config = self._load_config()
        if not config:
            return ToolResult(
                success=False,
                output="Error: Tushare Token not found.",
                remedy="请在 tushare_config.json 中配置 token 字段。"
            )

        token = config.get("token")
        if not token:
            return ToolResult(
                success=False,
                output="Error: Tushare token is missing.",
                remedy="请在 tushare_config.json 中添加 token 字段。"
            )
        url = "http://api.tushare.pro"
        
        target_api = ""
        request_params = params or {}
        
        if action == "daily":
            if not ts_code:
                return ToolResult(success=False, output="Error: ts_code is required for 'daily' action.")
            target_api = "daily"
            request_params["ts_code"] = ts_code
            if not trade_date and "trade_date" not in request_params:
                request_params["trade_date"] = self._get_last_weekday()
            elif trade_date:
                request_params["trade_date"] = trade_date

        elif action == "stock_basic":
            target_api = "stock_basic"
            if "list_status" not in request_params:
                request_params["list_status"] = "L" # Default to Listing
            if "fields" not in request_params:
                request_params["fields"] = "ts_code,symbol,name,area,industry,list_date"

        elif action == "query":
            if not api_name:
                return ToolResult(success=False, output="Error: api_name is required for 'query' action.")
            target_api = api_name
        
        payload = {
            "api_name": target_api,
            "token": token,
            "params": request_params,
            "fields": request_params.pop("fields", "")
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code != 200:
                    return ToolResult(success=False, output=f"Tushare API connection error ({resp.status_code})")
                
                data = resp.json()
                if "code" in data and data["code"] != 0:
                    msg = data.get("msg", "Unknown Tushare error")
                    # Append documentation link if it's a permission error
                    if data["code"] == 40203:
                        msg += " (Note: This often means your points are insufficient for this specific query.)"
                    return ToolResult(success=False, output=f"Tushare error (code {data['code']}): {msg}")

                result_data = data.get("data", {})
                items = result_data.get("items", [])
                fields = result_data.get("fields", [])

                if not items:
                    return ToolResult(success=True, output=f"No results found for {target_api} with params: {request_params}")

                output = [f"### Tushare Result: {target_api}\n"]
                formatted_results = []
                for item in items[:15]: # Show top 15
                    row = dict(zip(fields, item))
                    formatted_results.append(row)

                output.append(json.dumps(formatted_results, indent=2, ensure_ascii=False))
                if len(items) > 15:
                    output.append(f"\n(Showing first 15 of {len(items)} results)")

                return ToolResult(success=True, output="\n".join(output))

            except Exception as e:
                return ToolResult(success=False, output=f"Tushare Tool Error: {str(e)}")
