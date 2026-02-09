"""
Task Tool - Agent interface for task management
"""
from typing import Any
from loguru import logger

from nanobot.agent.tools.base import Tool
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
    ) -> str:
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
                return f"Unknown action: {action}"
        except Exception as e:
            logger.error(f"TaskTool error: {e}")
            return f"❌ Error: {str(e)}"
    
    async def _create(self, name: str | None, description: str | None, command: str | None) -> str:
        """Create a new task."""
        if not name:
            return "❌ Error: 'name' is required for create"
        if not description:
            return "❌ Error: 'description' is required for create"
        if not command:
            return "❌ Error: 'command' is required for create"
        
        try:
            task = self._manager.create(name=name, description=description, command=command)
            return f"✅ 已创建任务 '{task.name}'\n📝 描述: {task.description}\n💻 命令: {task.command}"
        except ValueError as e:
            return f"❌ {str(e)}"
    
    def _list(self) -> str:
        """List all tasks."""
        tasks = self._manager.list()
        if not tasks:
            return "📋 暂无任务"
        
        lines = ["📋 任务列表:"]
        for i, task in enumerate(tasks, 1):
            lines.append(f"{i}. **{task.name}** - {task.description}")
        
        return "\n".join(lines)
    
    async def _run(
        self,
        name: str | None,
        working_dir: str | None = None,
        timeout: int | None = None,
        confirm: bool | None = None,
    ) -> str:
        """Run a task by name."""
        if not name:
            return "❌ Error: 'name' is required for run"
        
        task = self._manager.get(name)
        if not task:
            return f"❌ 任务 '{name}' 不存在"
        
        logger.info(f"Executing task '{name}': {task.command}")
        
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
            return f"🚀 执行任务 '{name}':\n\n{result}"
        except Exception as e:
            return f"❌ 执行失败: {str(e)}"
    
    def _delete(self, name: str | None) -> str:
        """Delete a task."""
        if not name:
            return "❌ Error: 'name' is required for delete"
        
        if self._manager.delete(name):
            return f"✅ 已删除任务 '{name}'"
        else:
            return f"❌ 任务 '{name}' 不存在"
    
    def _show(self, name: str | None) -> str:
        """Show task details."""
        if not name:
            return "❌ Error: 'name' is required for show"
        
        task = self._manager.get(name)
        if not task:
            return f"❌ 任务 '{name}' 不存在"
        
        return (
            f"📋 任务详情:\n"
            f"名称: {task.name}\n"
            f"描述: {task.description}\n"
            f"命令: {task.command}\n"
            f"创建时间: {task.created_at}"
        )
    
    def _update(self, name: str | None, description: str | None, command: str | None) -> str:
        """Update a task."""
        if not name:
            return "❌ Error: 'name' is required for update"
        
        if not description and not command:
            return "❌ Error: at least one of 'description' or 'command' is required for update"
        
        if self._manager.update(name, description=description, command=command):
            return f"✅ 已更新任务 '{name}'"
        else:
            return f"❌ 任务 '{name}' 不存在"
