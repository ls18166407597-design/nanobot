"""Minimal MCP stdio client for one-shot requests."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MCPServerConfig:
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    startup_timeout: float = 8.0
    request_timeout: float = 20.0
    enabled: bool = True
    allowed_tools: list[str] = field(default_factory=list)


class MCPStdioClient:
    """Line-delimited JSON-RPC client for MCP stdio transport."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._proc: asyncio.subprocess.Process | None = None
        self._next_id = 1

    async def __aenter__(self) -> "MCPStdioClient":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        env = os.environ.copy()
        env.update({k: str(v) for k, v in (self.config.env or {}).items()})
        cwd = str(Path(self.config.cwd).expanduser()) if self.config.cwd else None
        self._proc = await asyncio.create_subprocess_exec(
            self.config.command,
            *(self.config.args or []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=cwd,
        )

    async def initialize(self) -> None:
        payload = {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "clientInfo": {"name": "nanobot", "version": "0.1.0"},
        }
        await self.request("initialize", payload, timeout=self.config.startup_timeout)
        await self.notify("notifications/initialized", {})

    async def request(self, method: str, params: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        req_id = self._next_id
        self._next_id += 1
        await self._send_json({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})
        msg = await self._read_response(req_id, timeout=timeout or self.config.request_timeout)
        if "error" in msg:
            err = msg["error"]
            raise RuntimeError(f"MCP error {err.get('code')}: {err.get('message')}")
        return msg.get("result", {})

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self._send_json(
            {
                "jsonrpc": "2.0",
                "method": method,
                "params": params or {},
            }
        )

    async def close(self) -> None:
        if not self._proc:
            return
        try:
            await self.notify("shutdown", {})
        except Exception:
            pass
        try:
            await self.notify("exit", {})
        except Exception:
            pass
        if self._proc.returncode is None:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=0.5)
            except TimeoutError:
                self._proc.kill()
        self._proc = None

    async def _send_json(self, payload: dict[str, Any]) -> None:
        if not self._proc or not self._proc.stdin:
            raise RuntimeError("MCP process is not running")
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        self._proc.stdin.write(line.encode("utf-8"))
        await self._proc.stdin.drain()

    async def _read_response(self, expected_id: int, timeout: float) -> dict[str, Any]:
        if not self._proc or not self._proc.stdout:
            raise RuntimeError("MCP process is not running")
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise TimeoutError(f"MCP request timed out waiting for id={expected_id}")
            raw = await asyncio.wait_for(self._proc.stdout.readline(), timeout=remaining)
            if not raw:
                stderr_text = await self._read_stderr_tail()
                raise RuntimeError(f"MCP server exited before response (id={expected_id}). {stderr_text}")
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            message = self._parse_message(line)
            if message is None:
                continue
            if "id" not in message:
                continue
            if message.get("id") == expected_id:
                return message

    async def _read_stderr_tail(self) -> str:
        if not self._proc or not self._proc.stderr:
            return ""
        try:
            chunk = await asyncio.wait_for(self._proc.stderr.read(1000), timeout=0.1)
        except Exception:
            return ""
        text = chunk.decode("utf-8", errors="replace").strip()
        return f"stderr={text}" if text else ""

    def _parse_message(self, line: str) -> dict[str, Any] | None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return None
        if isinstance(msg, dict):
            return msg
        if isinstance(msg, list):
            for item in msg:
                if isinstance(item, dict) and "id" in item:
                    return item
        return None
