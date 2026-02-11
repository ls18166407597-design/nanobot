import json
from typing import Any, Dict, List, Optional

import httpx
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import get_tool_config_path


class FeishuTool(Tool):
    """Tool for interacting with Feishu (Lark) Open Platform."""

    name = "feishu"
    description = """
    Automate Feishu (Lark) tasks like sending messages and writing to spreadsheets.
    
    Actions:
    - 'send_message': Send a message to a user or group.
    - 'spreadsheet_write': Write data to a range in a spreadsheet.
    - 'bitable_add_record': Add a record (row) to a multi-dimensional table (Bitable).
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["send_message", "spreadsheet_write", "bitable_add_record"],
                "description": "The action to perform.",
            },
            "receive_id": {
                "type": "string",
                "description": "Recipient ID (open_id, chat_id, or email). Required for 'send_message'.",
            },
            "receive_id_type": {
                "type": "string",
                "enum": ["open_id", "chat_id", "email"],
                "default": "open_id",
                "description": "The type of ID used in receive_id.",
            },
            "content": {
                "type": "string",
                "description": "Message content (string or JSON string) for 'send_message'.",
            },
            "spreadsheet_token": {
                "type": "string",
                "description": "The token (ID) of the spreadsheet.",
            },
            "range": {
                "type": "string",
                "description": "Target range (e.g., 'Sheet1!A1:B2') for 'spreadsheet_write'.",
            },
            "values": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "string"}},
                "description": "2D array of values for 'spreadsheet_write'.",
            },
            "table_id": {
                "type": "string",
                "description": "The ID of the table in a Bitable.",
            },
            "fields": {
                "type": "object",
                "description": "Dictionary of fields to add for 'bitable_add_record'.",
            }
        },
        "required": ["action"],
    }

    def _load_config(self) -> Optional[Dict[str, str]]:
        config_path = get_tool_config_path("feishu_config.json")
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    async def _get_tenant_access_token(self) -> Optional[str]:
        config = self._load_config()
        if not config:
            return None
        
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": config.get("app_id"),
            "app_secret": config.get("app_secret")
        }
        
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(url, json=payload)
                if resp.status_code == 200:
                    return resp.json().get("tenant_access_token")
            except Exception:
                pass
        return None

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        token = await self._get_tenant_access_token()
        if not token:
            return ToolResult(
                success=False,
                output="Error: Failed to obtain Feishu access token.",
                remedy="请检查 feishu_config.json 中的 app_id 和 app_secret 是否正确。"
            )

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                if action == "send_message":
                    return await self._send_message(client, headers, **kwargs)
                elif action == "spreadsheet_write":
                    return await self._spreadsheet_write(client, headers, **kwargs)
                elif action == "bitable_add_record":
                    return await self._bitable_add_record(client, headers, **kwargs)
                else:
                    return ToolResult(success=False, output=f"Unknown action: {action}")
            except Exception as e:
                return ToolResult(success=False, output=f"Feishu Tool Error: {str(e)}")

    async def _send_message(self, client: httpx.AsyncClient, headers: dict, receive_id: str, content: str, receive_id_type: str = "open_id", **kwargs) -> ToolResult:
        url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
        
        # Ensure content is formatted correctly (JSON string with msg_type key if needed)
        # Feishu expects a JSON object for content inside the request body
        msg_payload = {"receive_id": receive_id, "msg_type": "text", "content": json.dumps({"text": content})}
        
        resp = await client.post(url, json=msg_payload, headers=headers)
        data = resp.json()
        if data.get("code") == 0:
            return ToolResult(success=True, output="Message sent successfully.")
        return ToolResult(success=False, output=f"Feishu Error: {data.get('msg')}")

    async def _spreadsheet_write(self, client: httpx.AsyncClient, headers: dict, spreadsheet_token: str, range: str, values: List[List[str]], **kwargs) -> ToolResult:
        url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values"
        payload = {"valueRange": {"range": range, "values": values}}
        
        resp = await client.put(url, json=payload, headers=headers)
        data = resp.json()
        if data.get("code") == 0:
            return ToolResult(success=True, output="Spreadsheet updated successfully.")
        return ToolResult(success=False, output=f"Feishu Error: {data.get('msg')}")

    async def _bitable_add_record(self, client: httpx.AsyncClient, headers: dict, app_token: str = None, table_id: str = None, fields: dict = None, **kwargs) -> ToolResult:
        # Note: spreadsheet_token is used as app_token for Bitable
        app_token = kwargs.get("spreadsheet_token") or app_token
        if not app_token or not table_id:
            return ToolResult(success=False, output="Error: app_token and table_id are required for Bitable.")
            
        url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        payload = {"fields": fields}
        
        resp = await client.post(url, json=payload, headers=headers)
        data = resp.json()
        if data.get("code") == 0:
            return ToolResult(success=True, output="Bitable record added successfully.")
        return ToolResult(success=False, output=f"Feishu Error: {data.get('msg')}")
