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
            },
            "required": ["task"],
        }

    async def execute(
        self,
        task: str,
        label: str | None = None,
        model: str | None = None,
        thinking: bool = False,
        use_free_provider: bool = True,
        **kwargs: Any,
    ) -> str:
        """Spawn a subagent to execute the given task."""
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
