#!/usr/bin/env python3
"""Minimal OpenAI-compatible bridge for Google Antigravity (Cloud Code Assist).

Endpoints:
- GET  /v1/models
- POST /v1/chat/completions (non-stream)

Auth:
- Uses NANOBOT_HOME/antigravity_auth.json written by antigravity_oauth_login.py

Notes:
- This is intentionally minimal. It supports text + tool calls, but does not stream.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import ssl

try:
    import certifi  # type: ignore
except Exception:
    certifi = None

CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
CLIENT_SECRET = "GOCSPXK-58FWR486LdLJ1mlLB8sXC4z6qDAf"
TOKEN_URL = "https://oauth2.googleapis.com/token"

ANTIGRAVITY_ENDPOINTS = [
    "https://daily-cloudcode-pa.sandbox.googleapis.com",
    "https://cloudcode-pa.googleapis.com",
]

DEFAULT_MODELS = [
    "gemini-3-flash",
    "gemini-3-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-flash-thinking",
    "claude-opus-4-5-thinking",
    "claude-sonnet-4-5",
]


def _resolve_nanobot_home() -> Path:
    env = os.environ.get("NANOBOT_HOME")
    if env:
        return Path(env).expanduser().resolve()

    repo_root = Path(__file__).resolve().parents[1]
    repo_home = repo_root / ".home"
    if repo_home.exists():
        return repo_home.resolve()

    return (Path.home() / ".nanobot").resolve()


def _load_auth() -> Dict[str, Any]:
    auth_path = _resolve_nanobot_home() / "antigravity_auth.json"
    if not auth_path.exists():
        raise FileNotFoundError(f"Auth not found: {auth_path}")
    with auth_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_auth(auth: Dict[str, Any]) -> None:
    auth_path = _resolve_nanobot_home() / "antigravity_auth.json"
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    with auth_path.open("w", encoding="utf-8") as f:
        json.dump(auth, f, indent=2, ensure_ascii=False)


def _refresh_token(auth: Dict[str, Any]) -> Dict[str, Any]:
    refresh = auth.get("refresh")
    if not refresh:
        raise RuntimeError("Missing refresh token in antigravity_auth.json")

    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh,
        "grant_type": "refresh_token",
    }

    data = "&".join(f"{k}={v}" for k, v in payload.items()).encode("utf-8")
    req = Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    ssl_ctx = None
    if certifi is not None:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    with urlopen(req, timeout=30, context=ssl_ctx) as resp:
        body = resp.read().decode("utf-8")
        parsed = json.loads(body)

    access = parsed.get("access_token")
    expires_in = parsed.get("expires_in", 0)
    if not access:
        raise RuntimeError(f"Token refresh failed: {parsed}")

    auth["access"] = access
    auth["expires"] = int(time.time() * 1000 + expires_in * 1000 - 5 * 60 * 1000)
    auth["updatedAt"] = int(time.time() * 1000)
    _save_auth(auth)
    return auth


def _ensure_token(auth: Dict[str, Any]) -> Dict[str, Any]:
    expires = int(auth.get("expires", 0))
    now_ms = int(time.time() * 1000)
    if expires and now_ms < expires - 60_000:
        return auth
    return _refresh_token(auth)


def _convert_messages(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    system_instruction = None
    contents = []

    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role")
        content = msg.get("content", "")

        if role == "system":
            system_instruction = content
            i += 1
            continue

        if role == "user":
            contents.append({"role": "user", "parts": [{"text": str(content)}]})
            i += 1
            continue

        if role == "assistant":
            parts = []
            if content:
                parts.append({"text": str(content)})

            # OpenAI-style tool calls in assistant history
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    args_raw = fn.get("arguments", "{}")
                    try:
                        args = json.loads(args_raw) if isinstance(args_raw, str) else args_raw
                    except json.JSONDecodeError:
                        args = {"raw": args_raw}
                    parts.append({"functionCall": {"name": fn.get("name"), "args": args}})

            contents.append({"role": "model", "parts": parts})
            i += 1
            continue

        if role == "tool":
            tool_results = []
            while i < len(messages) and messages[i].get("role") == "tool":
                tool_msg = messages[i]
                tool_name = tool_msg.get("name", "unknown")
                tool_content = tool_msg.get("content", "")
                tool_results.append(f"[{tool_name}]: {tool_content}")
                i += 1

            combined = "\n\n".join(tool_results)
            contents.append({
                "role": "user",
                "parts": [{"text": f"Tool execution results:\n{combined}"}],
            })
            continue

        i += 1

    return {
        "contents": contents,
        "system_instruction": system_instruction,
    }


def _convert_tools(tools: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if not tools:
        return None

    decls = []
    for t in tools:
        if t.get("type") != "function":
            continue
        fn = t.get("function", {})
        params = fn.get("parameters", {}) or {}
        params = _clean_schema(json.loads(json.dumps(params)))
        decls.append({
            "name": fn.get("name"),
            "description": fn.get("description", ""),
            "parameters": params,
        })

    if not decls:
        return None
    return [{"functionDeclarations": decls}]


def _clean_schema(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_clean_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    # Normalize type lists like ["string","null"]
    t = schema.get("type")
    if isinstance(t, list):
        non_null = [item for item in t if item != "null"]
        schema["type"] = non_null[0] if non_null else "string"

    # Remove unsupported/optional fields that can break Google API
    schema.pop("default", None)
    schema.pop("title", None)

    # Recurse all nested fields
    for k, v in list(schema.items()):
        if isinstance(v, (dict, list)):
            schema[k] = _clean_schema(v)

    return schema


def _build_request(body: Dict[str, Any], auth: Dict[str, Any]) -> Dict[str, Any]:
    messages = body.get("messages") or []
    model = body.get("model") or "gemini-3-flash"
    temperature = body.get("temperature")
    max_tokens = body.get("max_tokens")
    tools = body.get("tools")
    tool_choice = body.get("tool_choice")

    converted = _convert_messages(messages)
    request: Dict[str, Any] = {"contents": converted["contents"]}

    if converted["system_instruction"]:
        request["systemInstruction"] = {
            "parts": [{"text": str(converted["system_instruction"])}]
        }

    generation_config: Dict[str, Any] = {}
    if temperature is not None:
        generation_config["temperature"] = temperature
    if max_tokens is not None:
        generation_config["maxOutputTokens"] = max_tokens
    if generation_config:
        request["generationConfig"] = generation_config

    if os.environ.get("ANTIGRAVITY_BRIDGE_DISABLE_TOOLS", "0") == "1":
        request_tools = None
    else:
        request_tools = _convert_tools(tools)
    if request_tools:
        request["tools"] = request_tools
        if tool_choice:
            request["toolConfig"] = {
                "functionCallingConfig": {"mode": str(tool_choice).upper()}
            }

    return {
        "project": auth.get("projectId"),
        "model": model,
        "request": request,
        "requestType": "agent",
        "userAgent": "antigravity",
        "requestId": f"agent-{int(time.time())}-{uuid.uuid4().hex[:8]}",
    }


def _call_antigravity(payload: Dict[str, Any], auth: Dict[str, Any]) -> Dict[str, Any]:
    access = auth.get("access")
    if not access:
        raise RuntimeError("Missing access token in antigravity_auth.json")

    body = json.dumps(payload).encode("utf-8")

    last_error: Optional[str] = None
    ssl_ctx = None
    if certifi is not None:
        ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    def build_headers(token: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "antigravity/1.15.8 darwin/arm64",
            "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
            "Client-Metadata": json.dumps({
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }),
        }

    for endpoint in ANTIGRAVITY_ENDPOINTS:
        url = f"{endpoint}/v1internal:streamGenerateContent?alt=sse"
        refreshed = False
        for _ in range(2):
            headers = build_headers(access)
            req = Request(url, data=body, headers=headers, method="POST")
            try:
                with urlopen(req, timeout=90, context=ssl_ctx) as resp:
                    return _parse_sse(resp)
            except HTTPError as e:
                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    err_body = str(e)
                if e.code == 401 and not refreshed:
                    auth = _refresh_token(auth)
                    access = auth.get("access") or access
                    refreshed = True
                    continue
                last_error = f"HTTP {e.code}: {err_body}"
                break
            except Exception as e:
                last_error = str(e)
                break

    raise RuntimeError(last_error or "Antigravity request failed")


def _parse_sse(resp) -> Dict[str, Any]:
    buffer = b""
    text_chunks: List[str] = []
    tool_calls: List[Dict[str, Any]] = []
    finish_reason = "stop"
    usage: Dict[str, Any] = {}

    def handle_chunk(chunk: Dict[str, Any]) -> None:
        nonlocal finish_reason, usage
        response_data = chunk.get("response") or chunk
        candidate = (response_data.get("candidates") or [{}])[0]
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            if "text" in part:
                if part.get("thought") is True:
                    continue
                text_chunks.append(str(part["text"]))
            if "functionCall" in part:
                fc = part.get("functionCall") or {}
                tool_calls.append({
                    "name": fc.get("name") or "",
                    "arguments": fc.get("args") or {},
                })

        if candidate.get("finishReason"):
            finish_reason = "stop"
        if tool_calls:
            finish_reason = "tool_calls"

        usage_meta = response_data.get("usageMetadata") or {}
        if usage_meta:
            prompt = usage_meta.get("promptTokenCount", 0) or 0
            cached = usage_meta.get("cachedContentTokenCount", 0) or 0
            completion = (
                (usage_meta.get("candidatesTokenCount", 0) or 0)
                + (usage_meta.get("thoughtsTokenCount", 0) or 0)
            )
            total = usage_meta.get("totalTokenCount", 0) or (prompt + completion)
            usage.update({
                "prompt_tokens": max(prompt - cached, 0),
                "completion_tokens": completion,
                "total_tokens": total,
            })

    while True:
        chunk = resp.read(4096)
        if not chunk:
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.strip()
            if not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if not data:
                continue
            try:
                payload = json.loads(data.decode("utf-8"))
            except Exception:
                continue
            handle_chunk(payload)

    return {
        "text": "".join(text_chunks).strip(),
        "tool_calls": tool_calls,
        "finish_reason": finish_reason,
        "usage": usage,
    }


def _openai_response(model: str, result: Dict[str, Any]) -> Dict[str, Any]:
    message: Dict[str, Any] = {"role": "assistant", "content": result.get("text", "")}

    tool_calls = []
    for idx, tc in enumerate(result.get("tool_calls") or []):
        call_id = f"call_{idx}_{uuid.uuid4().hex[:8]}"
        tool_calls.append({
            "id": call_id,
            "type": "function",
            "function": {
                "name": tc.get("name", ""),
                "arguments": json.dumps(tc.get("arguments") or {}),
            },
        })

    if tool_calls:
        message["tool_calls"] = tool_calls
        message["content"] = message.get("content") or ""

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": message,
                "finish_reason": "tool_calls" if tool_calls else result.get("finish_reason", "stop"),
            }
        ],
        "usage": result.get("usage", {}),
    }


class AntigravityBridgeHandler(BaseHTTPRequestHandler):
    server_version = "antigravity-bridge/0.1"

    def _send_json(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/v1/models":
            models = [
                {"id": m, "object": "model", "owned_by": "antigravity"}
                for m in DEFAULT_MODELS
            ]
            self._send_json(200, {"object": "list", "data": models})
            return

        self._send_json(404, {"error": {"message": "Not found"}})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._send_json(404, {"error": {"message": "Not found"}})
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send_json(400, {"error": {"message": "Invalid JSON"}})
            return

        if body.get("stream"):
            self._send_json(400, {"error": {"message": "stream=true not supported"}})
            return

        try:
            auth = _ensure_token(_load_auth())
            payload = _build_request(body, auth)
            result = _call_antigravity(payload, auth)
            response = _openai_response(body.get("model") or payload.get("model"), result)
            self._send_json(200, response)
        except Exception as e:
            self._send_json(500, {"error": {"message": str(e)}})


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity OpenAI-compatible bridge")
    parser.add_argument("--host", default=os.environ.get("ANTIGRAVITY_BRIDGE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("ANTIGRAVITY_BRIDGE_PORT", "8046")))
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), AntigravityBridgeHandler)
    print(f"Antigravity bridge listening on http://{args.host}:{args.port}")
    print(f"Using auth from {_resolve_nanobot_home() / 'antigravity_auth.json'}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
