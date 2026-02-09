"""Spawn tool for creating background subagents."""

from typing import TYPE_CHECKING, Any

from nanobot.agent.tools.base import Tool

if TYPE_CHECKING:
    from nanobot.agent.subagent import SubagentManager


class SpawnTool(Tool):
    """
    Tool to spawn a subagent for background task execution.

    The subagent runs asynchronously and announces its result back
    to the main agent when complete.
    """

    def __init__(self, manager: "SubagentManager"):
        self._manager = manager
        self._origin_channel = "cli"
        self._origin_chat_id = "direct"
        self._trace_id: str | None = None

    def set_context(self, channel: str, chat_id: str, trace_id: str | None = None) -> None:
        """Set the origin context for subagent announcements."""
        self._origin_channel = channel
        self._origin_chat_id = chat_id
        self._trace_id = trace_id

    @property
    def name(self) -> str:
        return "spawn"

    @property
    def description(self) -> str:
        return (
            "Spawn a subagent to handle a task in the background. "
            "Use this for complex or time-consuming tasks that can run independently. "
            "The subagent will complete the task and report back when done."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["spawn", "list", "status", "cancel"],
                    "description": "操作类型（默认 spawn）",
                },
                "task": {
                    "type": "string",
                    "description": "The task for the subagent to complete",
                },
                "label": {
                    "type": "string",
                    "description": "Optional short label for the task (for display)",
                },
                "model": {
                    "type": "string",
                    "description": "Optional model override (e.g. 'gemini-2.0-flash-thinking-exp')",
                },
                "thinking": {
                    "type": "boolean",
                    "description": "Enable internal reasoning for the subagent",
                },
                "use_free_provider": {
                    "type": "boolean",
                    "description": "Try to use a free provider if available (default: true)",
                },
                "task_id": {
                    "type": "string",
                    "description": "Subagent task id for status/cancel",
                },
            },
            "required": [],
        }

    async def execute(
        self,
        task: str | None = None,
        label: str | None = None,
        model: str | None = None,
        thinking: bool = False,
        use_free_provider: bool = True,
        action: str | None = None,
        task_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task."""
        # Backward compatibility: if action not provided, assume spawn
        action = action or "spawn"

        if action == "spawn":
            if not task:
                return "Error: 'task' is required for spawn"
            return await self._manager.spawn(
                task=task,
                label=label,
                model=model,
                thinking=thinking,
                origin_channel=self._origin_channel,
                origin_chat_id=self._origin_chat_id,
                use_free_provider=use_free_provider,
                trace_id=self._trace_id,
            )
        if action == "list":
            tasks = self._manager.list_tasks()
            if not tasks:
                return "No running subagent tasks."
            lines = ["Running subagent tasks:"]
            for t in tasks:
                lines.append(f"- {t.get('label')} (id: {t.get('id')})")
                lines.append(f"  model: {t.get('model')} | status: {t.get('status')}")
            return "\n".join(lines)
        if action == "status":
            if not task_id:
                return "Error: 'task_id' is required for status"
            info = self._manager.get_task_status(task_id)
            if not info:
                return f"Task '{task_id}' not found (may have finished)."
            return (
                f"Task {task_id}\n"
                f"label: {info.get('label')}\n"
                f"model: {info.get('model')}\n"
                f"status: {info.get('status')}"
            )
        if action == "cancel":
            if not task_id:
                return "Error: 'task_id' is required for cancel"
            if self._manager.cancel_task(task_id):
                return f"Cancelled task {task_id}"
            return f"Task '{task_id}' not found or already finished."
        return f"Unknown action: {action}"
