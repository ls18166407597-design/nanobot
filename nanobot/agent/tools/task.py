"""
Task Tool - Agent interface for task management
"""
import os
import shlex
from pathlib import Path
from typing import Any
from loguru import logger

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.agent.task_manager import TaskManager
from nanobot.agent.tools.shell import ExecTool


class TaskTool(Tool):
    """Tool for managing named, reusable tasks."""
    
    def __init__(self, task_manager: TaskManager, exec_tool: ExecTool):
        self._manager = task_manager
        self._exec = exec_tool
    
    @property
    def name(self) -> str:
        return "task"
    
    @property
    def description(self) -> str:
        return (
            "管理可重复使用的任务。支持创建、列出、执行和删除任务。"
            "任务可以有友好的别名(如'1号任务'、'签到任务'),并可随时执行或定时调度。"
        )
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["create", "list", "run", "delete", "show", "update"],
                    "description": "操作类型",
                },
                "name": {
                    "type": "string",
                    "description": "任务名称(别名),如'1号任务'、'签到任务'",
                },
                "description": {
                    "type": "string",
                    "description": "任务描述(用于create/update)",
                },
                "command": {
                    "type": "string",
                    "description": "要执行的命令(用于create/update)",
                },
                "working_dir": {
                    "type": "string",
                    "description": "执行命令的工作目录(仅用于run)",
                },
                "timeout": {
                    "type": "integer",
                    "description": "命令超时时间(秒, 仅用于run)",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "是否确认执行危险命令(仅用于run)",
                },
            },
            "required": ["action"],
        }
    
    async def execute(
        self,
        action: str,
        name: str | None = None,
        description: str | None = None,
        command: str | None = None,
        working_dir: str | None = None,
        timeout: int | None = None,
        confirm: bool | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute task management action."""
        try:
            if action == "create":
                return await self._create(name, description, command)
            elif action == "list":
                return self._list()
            elif action == "run":
                return await self._run(name, working_dir=working_dir, timeout=timeout, confirm=confirm)
            elif action == "delete":
                return self._delete(name)
            elif action == "show":
                return self._show(name)
            elif action == "update":
                return self._update(name, description, command)
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}")

        except Exception as e:
            logger.error(f"TaskTool error: {e}")
            return ToolResult(success=False, output=f"❌ Error: {str(e)}")
    
    async def _create(self, name: str | None, description: str | None, command: str | None) -> ToolResult:
        """Create a new task."""
        if not name:
            return ToolResult(success=False, output="❌ Error: 'name' is required for create")
        if not description:
            return ToolResult(success=False, output="❌ Error: 'description' is required for create")
        if not command:
            return ToolResult(success=False, output="❌ Error: 'command' is required for create")
        
        try:
            normalized_command = self._normalize_command(command)
            task = self._manager.create(name=name, description=description, command=normalized_command)
            return ToolResult(success=True, output=f"✅ 已创建任务 '{task.name}'\n📝 描述: {task.description}\n💻 命令: {task.command}")
        except ValueError as e:
            return ToolResult(success=False, output=f"❌ {str(e)}")
    
    def _list(self) -> ToolResult:
        """List all tasks."""
        tasks = self._manager.list()
        if not tasks:
            return ToolResult(success=True, output="📋 暂无任务")
        
        lines = ["📋 任务列表:"]
        for i, task in enumerate(tasks, 1):
            lines.append(f"{i}. **{task.name}** - {task.description}")
        
        return ToolResult(success=True, output="\n".join(lines))
    
    async def _run(
        self,
        name: str | None,
        working_dir: str | None = None,
        timeout: int | None = None,
        confirm: bool | None = None,
    ) -> ToolResult:
        """Run a task by name."""
        if not name:
            return ToolResult(success=False, output="❌ Error: 'name' is required for run")
        
        task = self._manager.get(name)
        if not task:
            return ToolResult(success=False, output=f"❌ 任务 '{name}' 不存在")
        
        logger.info(f"Executing task '{name}': {task.command}")
        preflight_error = self._preflight_command(task.command)
        if preflight_error:
            return ToolResult(success=False, output=f"❌ 执行前检查失败: {preflight_error}")
        
        # Execute the command using ExecTool
        try:
            # Override exec timeout temporarily if provided
            orig_timeout = self._exec.timeout
            if timeout and timeout > 0:
                self._exec.timeout = timeout
            try:
                result = await self._exec.execute(
                    command=task.command,
                    working_dir=working_dir,
                    confirm=bool(confirm) if confirm is not None else False,
                )
            finally:
                self._exec.timeout = orig_timeout
            
            # ExecTool.execute returns ToolResult
            if isinstance(result, ToolResult):
                result.output = f"🚀 执行任务 '{name}':\n\n{result.output}"
                return result
            
            return ToolResult(success=True, output=f"🚀 执行任务 '{name}':\n\n{result}")
        except Exception as e:
            return ToolResult(success=False, output=f"❌ 执行失败: {str(e)}")
    
    def _delete(self, name: str | None) -> ToolResult:
        """Delete a task."""
        if not name:
            return ToolResult(success=False, output="❌ Error: 'name' is required for delete")
        
        if self._manager.delete(name):
            return ToolResult(success=True, output=f"✅ 已删除任务 '{name}'")
        else:
            return ToolResult(success=False, output=f"❌ 任务 '{name}' 不存在")
    
    def _show(self, name: str | None) -> ToolResult:
        """Show task details."""
        if not name:
            return ToolResult(success=False, output="❌ Error: 'name' is required for show")
        
        task = self._manager.get(name)
        if not task:
            return ToolResult(success=False, output=f"❌ 任务 '{name}' 不存在")
        
        return ToolResult(success=True, output=(
            f"📋 任务详情:\n"
            f"名称: {task.name}\n"
            f"描述: {task.description}\n"
            f"命令: {task.command}\n"
            f"创建时间: {task.created_at}"
        ))
    
    def _update(self, name: str | None, description: str | None, command: str | None) -> ToolResult:
        """Update a task."""
        if not name:
            return ToolResult(success=False, output="❌ Error: 'name' is required for update")
        
        if not description and not command:
            return ToolResult(success=False, output="❌ Error: at least one of 'description' or 'command' is required for update")
        
        normalized_command = self._normalize_command(command) if command else None
        if self._manager.update(name, description=description, command=normalized_command):
            return ToolResult(success=True, output=f"✅ 已更新任务 '{name}'")
        else:
            return ToolResult(success=False, output=f"❌ 任务 '{name}' 不存在")

    def _normalize_command(self, command: str) -> str:
        """
        Normalize task command to reduce environment-related failures.
        - Remove fragile PYTHONPATH prefixes.
        - Inject NANOBOT_HOME for python script commands when missing.
        """
        cmd = (command or "").strip()
        if not cmd:
            return cmd

        # Remove common fragile pattern created during self-repair loops.
        if "PYTHONPATH=$PYTHONPATH" in cmd:
            parts = [p.strip() for p in cmd.split("&&") if p.strip()]
            parts = [p for p in parts if "PYTHONPATH=$PYTHONPATH" not in p]
            cmd = " && ".join(parts).strip() or cmd

        home_dir = Path(os.getenv("NANOBOT_HOME", Path.cwd() / ".home")).expanduser()
        home_prefix = f"NANOBOT_HOME={home_dir}"

        lower = cmd.lower()
        is_python_cmd = lower.startswith("python ") or lower.startswith("python3 ")
        if is_python_cmd and "nanobot_home=" not in lower:
            cmd = f"{home_prefix} {cmd}"
        return cmd

    def _preflight_command(self, command: str) -> str | None:
        """
        Basic sanity checks before task execution.
        Fail fast with actionable errors for missing script files.
        """
        try:
            tokens = shlex.split(command)
        except Exception:
            return None

        if not tokens:
            return "任务命令为空"

        # Skip leading env assignments.
        i = 0
        while i < len(tokens) and "=" in tokens[i] and not tokens[i].startswith("-"):
            i += 1
        if i >= len(tokens):
            return None

        exe = tokens[i]
        if exe not in {"python", "python3"}:
            return None
        if i + 1 >= len(tokens):
            return "Python 命令缺少脚本路径"

        script = tokens[i + 1]
        if script.startswith("-"):
            return None

        p = Path(script)
        if not p.is_absolute():
            p = Path.cwd() / p
        if not p.exists():
            return f"脚本不存在: {script}"
        return None
