import asyncio
import json
import time
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
from nanobot.utils.audit import log_event
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse
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
        self._task_meta: dict[str, dict[str, Any]] = {}
        self._semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent subagents (Hardened)

    async def spawn(
        self,
        task: str,
        label: str | None = None,
        model: str | None = None,
        thinking: bool = False,
        origin_channel: str = "cli",
        origin_chat_id: str = "direct",
        use_free_provider: bool = True,
        trace_id: str | None = None,
    ) -> str:
        """
        Spawn a subagent to execute a task in the background.

        Args:
            task: The task description for the subagent.
            label: Optional human-readable label for the task.
            origin_channel: The channel to announce results to.
            origin_chat_id: The chat ID to announce results to.
            use_free_provider: If True, try to use a free provider from registry.
            trace_id: Optional trace ID for tracking.

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

        # CRITICAL: Enforce brain separation (Boss's rule)
        if model and model == self.model:
             raise ValueError(f"Brain Separation Error: Subagent cannot use the same model as the main agent ({self.model}). Please pick a different model.")
        
        if use_free_provider and self.model_registry:
            free_info = self.model_registry.get_provider("free_first")
            if free_info:
                logger.info(f"Subagent [{task_id}] using free provider: {free_info.name}")
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
                use_free_provider=use_free_provider,
                trace_id=trace_id
            )
        )
        self._running_tasks[task_id] = bg_task
        self._task_meta[task_id] = {
            "id": task_id,
            "label": display_label,
            "task": task,
            "model": model or self.model,
            "started_at": time.time(),
            "status": "running",
        }

        # Cleanup when done
        def _cleanup(_: asyncio.Task[None]) -> None:
            self._running_tasks.pop(task_id, None)
            self._task_meta.pop(task_id, None)
        bg_task.add_done_callback(_cleanup)

        logger.info(f"Spawned subagent [{task_id}]: {display_label} (model: {run_model})")
        return f"Subagent [{display_label}] started (id: {task_id}, model: {run_model}). I'll notify you when it completes."

    async def _run_subagent(
        self,
        task_id: str,
        task: str,
        label: str,
        origin: dict[str, str],
        model_override: str | None,
        thinking: bool,
        use_free_provider: bool = False,
        trace_id: str | None = None,
    ) -> None:
        """Execute the subagent task and announce the result."""
        async with self._semaphore:
            log_prefix = f"[TraceID: {trace_id}] " if trace_id else ""
            logger.info(f"{log_prefix}Subagent [{task_id}] starting task: {label}")

            final_status = "error"
            final_result = "Subagent terminated unexpectedly."

            try:
                # Select provider and model
                run_model = model_override or self.model
                api_key = self.provider.api_key
                api_base = self.provider.api_base

                if model_override and self.model_registry:
                    clean_model = model_override.lower()
                    # 1. Match by provider nickname
                    if clean_model in self.model_registry.providers:
                         p_info = self.model_registry.providers[clean_model]
                         logger.info(f"{log_prefix}Subagent [{task_id}] switching to provider nickname '{p_info.name}'")
                         api_key = p_info.api_key
                         api_base = p_info.base_url
                         run_model = p_info.default_model or (p_info.models[0] if p_info.models else model_override)
                    # 2. Match by model ID in registry
                    else:
                        for p_name, p_info in self.model_registry.providers.items():
                            if model_override in p_info.models or clean_model.startswith(f"{p_name}/"):
                                 logger.info(f"{log_prefix}Subagent [{task_id}] switching to matching provider '{p_info.name}' for model '{model_override}'")
                                 api_key = p_info.api_key
                                 api_base = p_info.base_url
                                 run_model = model_override
                                 break
                
                # 2. Check for free provider strategy
                elif use_free_provider and self.model_registry and not model_override:
                    free_info = self.model_registry.get_provider("free_first", exclude_model=self.model)
                    if free_info:
                        logger.info(f"{log_prefix}Subagent [{task_id}] switching to free provider: {free_info.name}")
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
                
                while iteration < max_iterations:
                    iteration += 1

                    # Call LLM with failover support
                    response = await self._chat_with_failover(
                        messages=messages,
                        tools=tools.get_definitions(),
                        model=run_model,
                        provider=provider
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
                        tool_starts: dict[str, float] = {}
                        for tool_call in response.tool_calls:
                            logger.debug(f"{log_prefix}Subagent [{task_id}] executing: {tool_call.name}")
                            tool_starts[tool_call.id] = time.perf_counter()
                            log_event({
                                "type": "tool_start",
                                "trace_id": trace_id,
                                "tool": tool_call.name,
                                "tool_call_id": tool_call.id,
                                "args_keys": list(tool_call.arguments.keys()),
                                "subagent_task_id": task_id,
                            })
                            tool_coros.append(tools.execute(tool_call.name, tool_call.arguments))
                        
                        results = await asyncio.gather(*tool_coros, return_exceptions=True)

                        # Add results to messages
                        for tool_call, result in zip(response.tool_calls, results):
                            if isinstance(result, Exception):
                                result_str = f"Error: {str(result)}"
                            else:
                                result_str = str(result)
                            duration_s = None
                            if tool_call.id in tool_starts:
                                duration_s = round(time.perf_counter() - tool_starts[tool_call.id], 4)
                            log_event({
                                "type": "tool_end",
                                "trace_id": trace_id,
                                "tool": tool_call.name,
                                "tool_call_id": tool_call.id,
                                "status": "error" if isinstance(result, Exception) else "ok",
                                "duration_s": duration_s,
                                "result_len": len(result_str),
                                "subagent_task_id": task_id,
                            })
                            
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": tool_call.name,
                                    "content": result_str,
                                }
                            )
                    else:
                        final_result = str(response.content)
                        break

                if iteration >= max_iterations and final_result is None:
                    final_result = "Task stopped after maximum iterations without final response."
                
                final_status = "ok"
                logger.info(f"{log_prefix}Subagent [{task_id}] completed successfully")

            except Exception as e:
                final_result = f"Error: {str(e)}"
                final_status = "error"
                logger.error(f"{log_prefix}Subagent [{task_id}] failed: {e}")
            
            finally:
                # GUARANTEE: Always announce the result, even if we crashed
                await self._announce_result(task_id, label, task, final_result, origin, final_status, trace_id)
                if task_id in self._task_meta:
                    self._task_meta[task_id]["status"] = final_status
                    self._task_meta[task_id]["completed_at"] = time.time()

    async def _announce_result(
        self,
        task_id: str,
        label: str,
        task: str,
        result: str,
        origin: dict[str, str],
        status: str,
        trace_id: str | None = None,
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
            chat_id=origin.get("chat_id", "system"),
            content=announce_content,
            metadata={"origin": origin},
            trace_id=trace_id if trace_id else str(uuid.uuid4())[:8],
        )
        await self.bus.publish_inbound(msg)

    async def _chat_with_failover(
        self, 
        messages: list[dict[str, Any]], 
        tools: list[dict[str, Any]] | None,
        model: str,
        provider: "LLMProvider"
    ) -> "LLMResponse":
        """
        Call LLM with automatic failover for subagents.
        """
        from nanobot.providers.factory import ProviderFactory

        # List of candidate providers
        candidates = []
        
        # 1. Primary provider for this subagent
        candidates.append({
            "name": "primary",
            "provider": provider,
            "model": model
        })
        
        # 2. Registry providers (fallbacks) - Filter by model support
        if self.model_registry:
            # Only add providers that claim to support this model
            active_infos = self.model_registry.get_active_providers(model=model)
            
            for p_info in active_infos:
                # Skip duplicate of primary
                if p_info.base_url == provider.api_base and (p_info.default_model == model or model in p_info.models):
                    continue
                
                try:
                    fallback_provider = ProviderFactory.get_provider(
                        model=p_info.default_model or (p_info.models[0] if p_info.models else model),
                        api_key=p_info.api_key,
                        api_base=p_info.base_url
                    )
                    candidates.append({
                        "name": p_info.name,
                        "provider": fallback_provider,
                        "model": fallback_provider.default_model
                    })
                except Exception as e:
                    logger.warning(f"Failed to create subagent fallback {p_info.name}: {e}")

        last_error = None
        for i, candidate in enumerate(candidates):
            try:
                if i > 0:
                    await self._send_pulse_message(
                        f"🐈 子任务 [{candidate['name']}] 正在接力执行，由于主脑响应较慢，已为您切换思考节点... 🐾"
                    )

                response = await candidate["provider"].chat(
                    messages=messages,
                    tools=tools,
                    model=candidate["model"]
                )
                
                if response.finish_reason == "error":
                    raise Exception(response.content)
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"Subagent failover to {candidate['name']} failed: {e}")
                continue

        from nanobot.providers.base import LLMResponse
        return LLMResponse(content=f"Subagent failover failed: {last_error}", finish_reason="error")

    async def _send_pulse_message(self, content: str) -> None:
        """Send a proactive 'pulse' message from the subagent."""
        # Note: Subagents use a different context, but we can publish to bus
        from nanobot.bus.events import OutboundMessage
        # We don't have direct chat_id here easily without passing it down, 
        # but let's assume system channel broadcast for now or skip if too complex.
        # For simplicity, let's just log it if we can't find a destination.
        logger.info(f"[Subagent Pulse] {content}")

        # logger.debug(f"Subagent announced result")

    def _build_subagent_prompt(self, task: str, thinking: bool = False) -> str:
        """Build a focused system prompt for the subagent."""
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        thinking_instr = ""
        if thinking:
            thinking_instr = """
        IMPORTANT: You must use internal reasoning for every step.
        Wrap your reasoning in <think>...</think> tags.
        Analyze the problem, plan your approach, and verify your findings.
        """

        return f"""# Subagent
        {thinking_instr}
Current Time: {now} (You are operating in the present, not the past)
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

    def list_tasks(self) -> list[dict[str, Any]]:
        """List currently running tasks."""
        return list(self._task_meta.values())

    def get_task_status(self, task_id: str) -> dict[str, Any] | None:
        """Get status for a specific task ID."""
        return self._task_meta.get(task_id)

    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task by ID."""
        task = self._running_tasks.get(task_id)
        if not task:
            return False
        task.cancel()
        if task_id in self._task_meta:
            self._task_meta[task_id]["status"] = "cancelled"
            self._task_meta[task_id]["completed_at"] = time.time()
        return True
