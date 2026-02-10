"""Cron tool for scheduling reminders and tasks."""

from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult
from pathlib import Path

from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule
from nanobot.agent.task_manager import TaskManager


class CronTool(Tool):
    """Tool to schedule reminders and recurring tasks."""

    def __init__(self, cron_service: CronService, task_storage_path: Path | None = None):
        self._cron = cron_service
        self._channel = ""
        self._chat_id = ""
        self._task_storage_path = task_storage_path

    def set_context(self, channel: str, chat_id: str) -> None:
        """Set the current session context for delivery."""
        self._channel = channel
        self._chat_id = chat_id

    @property
    def name(self) -> str:
        return "cron"

    @property
    def description(self) -> str:
        return "Schedule reminders and recurring tasks. Actions: add, list, remove."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "list", "remove"],
                    "description": "Action to perform",
                },
                "message": {"type": "string", "description": "Reminder message (for add)"},
                "task_name": {
                    "type": "string",
                    "description": "任务名称(如果提供, 将调度该任务的执行)",
                },
                "every_seconds": {
                    "type": "integer",
                    "description": "Interval in seconds (for recurring tasks)",
                },
                "cron_expr": {
                    "type": "string",
                    "description": "Cron expression like '0 9 * * *' (for scheduled tasks)",
                },
                "in_seconds": {
                    "type": "integer",
                    "description": "Run once after X seconds (for one-off reminders)",
                },
                "job_id": {"type": "string", "description": "Job ID (for remove)"},
            },
            "required": ["action"],
        }

    async def execute(
        self,
        action: str,
        message: str = "",
        task_name: str | None = None,
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        in_seconds: int | None = None,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        try:
            if action == "add":
                output = self._add_job(message, task_name, every_seconds, cron_expr, in_seconds)
                if output.startswith("Error"):
                    return ToolResult(success=False, output=output, remedy="请检查参数，确保提供了 message 或 task_name，且有且只有一个时间调度参数。")
                return ToolResult(success=True, output=output)
            elif action == "list":
                output = self._list_jobs()
                return ToolResult(success=True, output=output)
            elif action == "remove":
                output = self._remove_job(job_id)
                if "not found" in output.lower():
                    return ToolResult(success=False, output=output, remedy="请检查 job_id 是否正确。")
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, output=f"Cron Tool Error: {str(e)}")

    def _add_job(
        self,
        message: str,
        task_name: str | None,
        every_seconds: int | None,
        cron_expr: str | None,
        in_seconds: int | None,
    ) -> str:
        if not message and not task_name:
            return "Error: message or task_name is required for add"
        if not self._channel or not self._chat_id:
            return "Error: no session context (channel/chat_id)"
        # Validate schedule inputs (must provide exactly one)
        provided = [v is not None for v in (every_seconds, cron_expr, in_seconds)]
        if sum(provided) != 1:
            return "Error: exactly one of every_seconds, cron_expr, or in_seconds is required"
        if every_seconds is not None and every_seconds <= 0:
            return "Error: every_seconds must be > 0"
        if in_seconds is not None and in_seconds <= 0:
            return "Error: in_seconds must be > 0"

        # If task_name provided, convert to a task run command
        if task_name:
            if not self._task_storage_path:
                return "Error: task storage not configured"
            manager = TaskManager(storage_path=self._task_storage_path)
            if not manager.get(task_name):
                return f"Error: task '{task_name}' not found"
            message = f"请调用 task 工具执行任务，name=\"{task_name}\""

        # Build schedule
        delete_after_run = False
        if every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr)
        elif in_seconds:
            import time
            schedule = CronSchedule(kind="at", at_ms=int(time.time() * 1000) + (in_seconds * 1000))
            delete_after_run = True
        else:
            return "Error: one of every_seconds, cron_expr, or in_seconds is required"

        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            task_name=task_name,
            deliver=True,
            channel=self._channel,
            to=self._chat_id,
            delete_after_run=delete_after_run,
        )
        return f"Created job '{job.name}' (id: {job.id})"

    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        import time

        def _fmt_ts(ms: int | None) -> str:
            if not ms:
                return "-"
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(ms / 1000))

        lines = ["Scheduled jobs:"]
        for j in jobs:
            sched = j.schedule.kind
            if j.schedule.kind == "every":
                sched = f"every {int((j.schedule.every_ms or 0) / 1000)}s"
            elif j.schedule.kind == "cron":
                sched = f"cron {j.schedule.expr or ''}".strip()
            elif j.schedule.kind == "at":
                sched = f"at {_fmt_ts(j.schedule.at_ms)}"

            lines.append(
                f"- {j.name} (id: {j.id})"
            )
            lines.append(f"  enabled: {j.enabled} | schedule: {sched}")
            lines.append(
                f"  next_run: {_fmt_ts(j.state.next_run_at_ms)} | last_run: {_fmt_ts(j.state.last_run_at_ms)}"
            )
            lines.append(
                f"  deliver: {j.payload.deliver} | channel: {j.payload.channel or '-'} | to: {j.payload.to or '-'}"
            )
            if j.payload.task_name:
                lines.append(f"  task: {j.payload.task_name}")
        return "\n".join(lines)

    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
