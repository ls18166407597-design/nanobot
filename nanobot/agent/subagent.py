import asyncio
import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from nanobot.config.schema import ExecToolConfig

from loguru import logger

from nanobot.agent.tools.filesystem import ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.github import GitHubTool
from nanobot.agent.tools.gmail import GmailTool
from nanobot.agent.tools.knowledge import KnowledgeTool
from nanobot.agent.tools.mac import MacTool
from nanobot.agent.tools.memory import MemoryTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.browser import BrowserTool
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider
from nanobot.agent.models import ModelRegistry
from nanobot.providers.factory import ProviderFactory


class SubagentManager:
    """
    Manages background subagent execution.

    Subagents are lightweight agent instances that run in the background
    to handle specific tasks. They share the same LLM provider but have
    isolated context and a focused system prompt.
    """

    def __init__(
        self,
        provider: LLMProvider,
        workspace: Path,
        bus: MessageBus,
        model: str | None = None,
        exec_config: "ExecToolConfig | None" = None,
        restrict_to_workspace: bool = False,
        model_registry: "ModelRegistry | None" = None,
        web_proxy: str | None = None,
    ):
        from nanobot.config.schema import ExecToolConfig

        self.provider = provider
        self.workspace = workspace
        self.bus = bus
        self.model = model or provider.get_default_model()
        self.exec_config = exec_config or ExecToolConfig()
        self.restrict_to_workspace = restrict_to_workspace
        self.model_registry = model_registry
        self.web_proxy = web_proxy
        self._running_tasks: dict[str, asyncio.Task[None]] = {}
        self._semaphore = asyncio.Semaphore(10)  # Limit to 10 concurrent subagents

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        model: str | None = None,
        thinking: bool = False,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        use_free_provider: bool = True,
    ) -> str:
        """
        Spawn a subagent to execute a task in the background.

        Args:
            task: The task description for the subagent.
            label: Optional human-readable label for the task.
            origin_channel: The channel to announce results to.
            origin_chat_id: The chat ID to announce results to.
            use_free_provider: If True, try to use a free provider from registry.

        Returns:
            Status message indicating the subagent was started.
        """
        task_id = str(uuid.uuid4())[:8]
        display_label = label or task[:30] + ("..." if len(task) > 30 else "")

        origin = {
            "channel": origin_channel,
            "chat_id": origin_chat_id,
        }
        
        # Determine provider to use
        run_provider = self.provider
        run_model = model or self.model
        
        if use_free_provider and self.model_registry:
            free_info = self.model_registry.get_provider("free_first")
            if free_info:
                logger.info(f"Subagent [{task_id}] using free provider: {free_info.name}")
                # Create a temporary provider instance for this subagent
                # We need to import OpenAIProvider dynamically or use a factory
                # For now, we reuse the existing provider class if it supports base_url switching
                # OR we assume the main provider is OpenAI-compatible and just create a new one.
                # Since we don't have a factory here, let's try to assume OpenAICompatible for now
                # or just modify the run_subagent to use a new provider instance if we can.
                
                # A safer way is to pass the provider_info to _run_subagent and let it create the provider
                pass
        
        # Create background task
        bg_task = asyncio.create_task(
            self._run_subagent(
                task_id, 
                task, 
                display_label, 
                origin, 
                run_model, 
                thinking,
                use_free_provider=use_free_provider
            )
        )
        self._running_tasks[task_id] = bg_task

        # Cleanup when done
        bg_task.add_done_callback(lambda _: self._running_tasks.pop(task_id, None))

        logger.info(f"Spawned subagent [{task_id}]: {display_label}")
        return f"Subagent [{display_label}] started (id: {task_id}). I'll notify you when it completes."

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        model_override: str | None,
        thinking: bool,
        use_free_provider: bool = False,
    ) -> None:
        """Execute the subagent task and announce the result."""
        async with self._semaphore:
            logger.info(f"Subagent [{task_id}] starting task: {label}")

            try:
                # Select provider and model
                run_model = model_override or self.model
                api_key = self.provider.api_key
                api_base = self.provider.api_base

                # 1. Check for explicit provider override based on model prefix
                if model_override and self.model_registry:
                    clean_model = model_override.lower()
                    for p_name, p_info in self.model_registry.providers.items():
                        if clean_model.startswith(f"{p_name}/"):
                             logger.info(f"Subagent [{task_id}] switching to provider '{p_info.name}'")
                             api_key = p_info.api_key
                             api_base = p_info.base_url
                             break
                
                # 2. Check for free provider strategy
                elif use_free_provider and self.model_registry and not model_override:
                    free_info = self.model_registry.get_provider("free_first")
                    if free_info:
                        logger.info(f"Subagent [{task_id}] switching to free provider: {free_info.name}")
                        api_key = free_info.api_key
                        api_base = free_info.base_url
                        if free_info.models:
                            run_model = free_info.models[0]

                # Instantiate provider via factory
                provider = ProviderFactory.get_provider(
                    api_key=api_key,
                    api_base=api_base,
                    model=run_model
                )

                # Build subagent tools
                tools = ToolRegistry()
                allowed_dir = self.workspace if self.restrict_to_workspace else None
                tools.register(ReadFileTool(allowed_dir=allowed_dir))
                tools.register(WriteFileTool(allowed_dir=allowed_dir))
                tools.register(ListDirTool(allowed_dir=allowed_dir))
                tools.register(
                    ExecTool(
                        working_dir=str(self.workspace),
                        timeout=self.exec_config.timeout,
                        restrict_to_workspace=self.restrict_to_workspace,
                    )
                )
                tools.register(BrowserTool(proxy=self.web_proxy))
                tools.register(GmailTool())
                tools.register(MacTool())
                tools.register(GitHubTool())
                tools.register(KnowledgeTool())
                tools.register(MemoryTool(workspace=self.workspace))

                # Build messages
                system_prompt = self._build_subagent_prompt(task, thinking)
                messages: list[dict[str, Any]] = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": task},
                ]

                # Run agent loop (limited iterations)
                max_iterations = 15
                iteration = 0
                final_result: str | None = None

                while iteration < max_iterations:
                    iteration += 1

                    response = await provider.chat(
                        messages=messages,
                        tools=tools.get_definitions(),
                        model=run_model,
                    )

                    if response.has_tool_calls:
                        # Add assistant message with tool calls
                        tool_call_dicts = [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.arguments),
                                },
                            }
                            for tc in response.tool_calls
                        ]
                        messages.append(
                            {
                                "role": "assistant",
                                "content": response.content or "",
                                "tool_calls": tool_call_dicts,
                            }
                        )

                        # Parallel Tool Execution: Execute all tool calls in this turn concurrently
                        tool_coros = []
                        for tool_call in response.tool_calls:
                            logger.debug(f"Subagent [{task_id}] executing: {tool_call.name}")
                            tool_coros.append(tools.execute(tool_call.name, tool_call.arguments))
                        
                        results = await asyncio.gather(*tool_coros, return_exceptions=True)

                        # Add results to messages
                        for tool_call, result in zip(response.tool_calls, results):
                            if isinstance(result, Exception):
                                result_str = f"Error: {str(result)}"
                            else:
                                result_str = str(result)
                            
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": tool_call.name,
                                    "content": result_str,
                                }
                            )
                    else:
                        final_result = response.content
                        break

                if final_result is None:
                    final_result = "Task completed but no final response was generated."

                logger.info(f"Subagent [{task_id}] completed successfully")
                await self._announce_result(task_id, label, task, final_result, origin, "ok")

            except Exception as e:
                error_msg = f"Error: {str(e)}"
                logger.error(f"Subagent [{task_id}] failed: {e}")
                await self._announce_result(task_id, label, task, error_msg, origin, "error")

    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
    ) -> None:
        """Announce the subagent result to the main agent via the message bus."""
        status_text = "completed successfully" if status == "ok" else "failed"

        announce_content = f"""[Subagent '{label}' {status_text}]

Task: {task}

Result:
{result}

Summarize this naturally for the user. Keep it brief (1-2 sentences). Do not mention technical details like "subagent" or task IDs."""

        # Inject as system message to trigger main agent
        msg = InboundMessage(
            channel="system",
            sender_id="subagent",
            chat_id=f"{origin['channel']}:{origin['chat_id']}",
            content=announce_content,
        )

        await self.bus.publish_inbound(msg)
        logger.debug(
            f"Subagent [{task_id}] announced result to {origin['channel']}:{origin['chat_id']}"
        )

    def _build_subagent_prompt(self, task: str, thinking: bool = False) -> str:
        """Build a focused system prompt for the subagent."""
        thinking_instr = ""
        if thinking:
            thinking_instr = """
        IMPORTANT: You must use internal reasoning for every step.
        Wrap your reasoning in <think>...</think> tags.
        Analyze the problem, plan your approach, and verify your findings.
        """

        return f"""# Subagent
        {thinking_instr}
You are a subagent spawned by the main agent to complete a specific task.

## Your Task
{task}

## Rules
1. Stay focused - complete only the assigned task, nothing else
2. Your final response will be reported back to the main agent
3. Do not initiate conversations or take on side tasks
4. Be concise but informative in your findings

## What You Can Do
- Read and write files in the workspace
- Execute shell commands
- Search the web and fetch web pages
- Complete the task thoroughly

## What You Cannot Do
- Send messages directly to users (no message tool available)
- Spawn other subagents
- Access the main agent's conversation history

## Workspace
Your workspace is at: {self.workspace}

When you have completed the task, provide a clear summary of your findings or actions."""

    async def stop_all(self) -> None:
        """Cancel all running subagent tasks."""
        if not self._running_tasks:
            return
            
        logger.info(f"Stopping {len(self._running_tasks)} running subagents...")
        for task_id, task in self._running_tasks.items():
            task.cancel()
        
        # Wait for all tasks to be cancelled
        await asyncio.gather(*self._running_tasks.values(), return_exceptions=True)
        self._running_tasks.clear()

    def get_running_count(self) -> int:
        """Return the number of currently running subagents."""
        return len(self._running_tasks)
