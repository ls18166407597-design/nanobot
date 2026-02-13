"""System status tool for runtime observability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.cli.runtime_commands import collect_health_snapshot, collect_tool_health_snapshot
from nanobot.config.loader import get_config_path, load_config
from nanobot.config.loader import get_data_dir
from nanobot.runtime.failures import list_recent_failures
from nanobot.runtime.state import reset_runtime_state


class SystemStatusTool(Tool):
    name = "system_status"
    description = "读取系统运行状态、工具健康与近期失败事件。"
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["summary", "failures", "reset_runtime"]},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
            "confirm": {"type": "boolean", "description": "执行 reset_runtime 时必须显式确认"},
            "preserve_tasks": {"type": "boolean", "description": "reset_runtime 时是否保留 tasks.json"},
        },
        "required": ["action"],
    }

    async def execute(self, action: str, limit: int = 10, confirm: bool = False, preserve_tasks: bool = True, **kwargs: Any) -> ToolResult:
        if action == "failures":
            return self._failures(limit=max(1, min(50, int(limit or 10))))
        if action == "summary":
            return self._summary()
        if action == "reset_runtime":
            if not bool(confirm):
                return ToolResult(
                    success=False,
                    output="Error: reset_runtime 需要显式确认。",
                    remedy="请携带参数 confirm=true 后再执行。",
                )
            res = reset_runtime_state(
                clear_sessions=True,
                clear_failures=True,
                clear_logs=True,
                preserve_tasks=bool(preserve_tasks),
            )
            return ToolResult(
                success=True,
                output=(
                    "已完成运行态清理：\n"
                    f"- sessions_removed: {res.get('sessions_removed', 0)}\n"
                    f"- failures_removed: {res.get('failures_removed', 0)}\n"
                    f"- logs_removed: {res.get('logs_removed', 0)}\n"
                    f"- tasks_preserved: {res.get('tasks_preserved', True)}"
                ),
            )
        return ToolResult(success=False, output=f"Error: unsupported action '{action}'")

    def _summary(self) -> ToolResult:
        config_path = get_config_path()
        config = load_config(config_path)
        data_dir = get_data_dir()
        snap = collect_health_snapshot(config=config, data_dir=Path(data_dir), config_path=config_path)
        tools = collect_tool_health_snapshot(data_dir=Path(data_dir), lines=2000)
        recent_failures = list_recent_failures(limit=5)
        lines = [
            f"gateway_running: {snap.get('gateway_running')}",
            f"workspace: {snap.get('workspace')}",
            f"recent_errors: {snap.get('recent_errors')}",
            f"empty_reply_rate: {tools.get('turns', {}).get('empty_rate', 0.0):.2f}",
            f"tracked_tools: {len(tools.get('tools', {}))}",
            f"recent_failures: {len(recent_failures)}",
        ]
        return ToolResult(success=True, output="\n".join(lines))

    def _failures(self, limit: int) -> ToolResult:
        items = list_recent_failures(limit=limit)
        if not items:
            return ToolResult(success=True, output="近期无失败事件。")
        lines: list[str] = []
        for i, it in enumerate(items, start=1):
            ts = str(it.get("ts", ""))[:19].replace("T", " ")
            lines.append(
                f"{i}. [{ts}] {it.get('source', '-')}/{it.get('category', '-')}: {it.get('summary', '')}"
            )
        return ToolResult(success=True, output="\n".join(lines))
