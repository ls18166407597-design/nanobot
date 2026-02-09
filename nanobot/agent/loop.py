import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
if TYPE_CHECKING:
    from nanobot.session.manager import Session

if TYPE_CHECKING:
    from nanobot.config.schema import BrainConfig, ExecToolConfig, ProvidersConfig
    from nanobot.cron.service import CronService

from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.agent.subagent import SubagentManager
from nanobot.providers.factory import ProviderFactory
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.filesystem import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from nanobot.agent.tools.github import GitHubTool
from nanobot.agent.tools.gmail import GmailTool
from nanobot.agent.tools.knowledge import KnowledgeTool
from nanobot.agent.tools.mac import MacTool
from nanobot.agent.tools.mac_vision import MacVisionTool
from nanobot.agent.tools.memory import MemoryTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.skills import SkillsTool
from nanobot.agent.tools.spawn import SpawnTool
from nanobot.agent.tools.browser import BrowserTool
from nanobot.agent.models import ModelRegistry
from nanobot.agent.tools.provider import ProviderTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.session.manager import SessionManager
from nanobot.process import CommandQueue, CommandLane
from nanobot.agent.context_guard import ContextGuard, TokenCounter
from nanobot.utils.audit import log_event


class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 20,
        exec_config: "ExecToolConfig | None" = None,
        cron_service: "CronService | None" = None,
        restrict_to_workspace: bool = False,
        brain_config: "BrainConfig | None" = None,
        providers_config: "ProvidersConfig | None" = None,
        web_proxy: str | None = None,
        max_tokens: int = 8192,
        temperature: float = 0.7,
        mac_confirm_mode: str = "warn",
        tools_config: "ToolsConfig | None" = None,
    ):
        self.bus = bus
        self.provider = provider
        self.workspace = workspace
        self.model = model or provider.get_default_model()
        self.max_iterations = max_iterations
        from nanobot.config.schema import BrainConfig, ExecToolConfig, ProvidersConfig, ToolsConfig
        
        self.tools_config = tools_config or ToolsConfig()

        self.exec_config = exec_config or ExecToolConfig()
        self.cron_service = cron_service
        self.restrict_to_workspace = restrict_to_workspace
        self.brain_config = brain_config or BrainConfig()
        self.web_proxy = web_proxy
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.mac_confirm_mode = mac_confirm_mode

        self.context = ContextBuilder(workspace, model=self.model, brain_config=self.brain_config)
        self.sessions = SessionManager(workspace)
        self.tools = ToolRegistry()
        
        # Initialize Model Registry
        self.model_registry = ModelRegistry()
        self.providers_config = providers_config
        
        self.subagents = SubagentManager(
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
            model_registry=self.model_registry,
            web_proxy=web_proxy,
        )

        self._running = False
        self._register_default_tools()

    async def _populate_registry(self, providers: "ProvidersConfig") -> None:
        """Register configured providers into the registry."""
        async def register_all():
            # OpenRouter
            if providers.openrouter.api_key:
                await self.model_registry.register(
                    base_url=providers.openrouter.api_base or "https://openrouter.ai/api/v1",
                    api_key=providers.openrouter.api_key,
                    name="openrouter"
                )
            # OpenAI
            if providers.openai.api_key:
                await self.model_registry.register(
                    base_url=providers.openai.api_base or "https://api.openai.com/v1",
                    api_key=providers.openai.api_key,
                    name="openai"
                )
            # Anthropic
            if providers.anthropic.api_key:
                await self.model_registry.register(
                    base_url=providers.anthropic.api_base or "https://api.anthropic.com/v1",
                    api_key=providers.anthropic.api_key,
                    name="anthropic"
                )
            # Gemini
            if providers.gemini.api_key:
                await self.model_registry.register(
                    base_url=providers.gemini.api_base or "https://generativelanguage.googleapis.com/v1beta/openai",
                    api_key=providers.gemini.api_key,
                    name="gemini"
                )
            # DeepSeek
            if providers.deepseek.api_key:
                await self.model_registry.register(
                    base_url=providers.deepseek.api_base or "https://api.deepseek.com",
                    api_key=providers.deepseek.api_key,
                    name="deepseek"
                )
            # Add others as needed...
            
            # Also add dynamic providers from brain config (already handled by check command but good to have here)
            if self.brain_config.provider_registry:
                for p in self.brain_config.provider_registry:
                    # Support both snake_case and camelCase config keys
                    api_key = p.get("api_key") or p.get("apiKey")
                    base_url = p.get("base_url") or p.get("baseUrl")
                    if api_key and base_url:
                        await self.model_registry.register(
                            base_url=base_url,
                            api_key=api_key,
                            name=p["name"],
                            default_model=p.get("model")
                        )

        await register_all()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        # File tools (restrict to workspace if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        self.tools.register(EditFileTool(allowed_dir=allowed_dir))
        self.tools.register(ListDirTool(allowed_dir=allowed_dir))

        # Shell tool
        self.tools.register(
            ExecTool(
                working_dir=str(self.workspace),
                timeout=self.exec_config.timeout,
                restrict_to_workspace=self.restrict_to_workspace,
                provider=self.provider,
                brain_config=self.brain_config,
            )
        )

        # Web tools - Main agent delegates all browser tasks to sub-agents
        # self.tools.register(BrowserTool(proxy=self.web_proxy))

        # Message tool
        message_tool = MessageTool(send_callback=self.bus.publish_outbound)
        self.tools.register(message_tool)

        # Spawn tool (for subagents)
        spawn_tool = SpawnTool(manager=self.subagents)
        self.tools.register(spawn_tool)

        # Cron tool (for scheduling)
        if self.cron_service:
            self.tools.register(CronTool(self.cron_service))

        # Gmail tool
        self.tools.register(GmailTool())

        # Mac tool
        self.tools.register(MacTool(confirm_mode=self.mac_confirm_mode))
        self.tools.register(MacVisionTool(confirm_mode=self.mac_confirm_mode))

        # GitHub tool
        self.tools.register(GitHubTool())

        # Knowledge tool
        self.tools.register(KnowledgeTool())

        # Memory tool (active management)
        self.tools.register(MemoryTool(workspace=self.workspace))

        # Provider tool (manage LLM providers)
        self.tools.register(ProviderTool(registry=self.model_registry))

        # Skills tool (Plaza/management)
        self.tools.register(
            SkillsTool(
                workspace=self.workspace,
                search_func=None,
            )
        )

    async def run(self) -> None:
        """Run the agent loop, processing messages from the bus."""
        self._running = True
        logger.info("Agent loop started")

        # Ensure registry is populated when loop is running
        if self.providers_config:
            await self._populate_registry(self.providers_config)

        while self._running:
            try:
                # Wait for next message
                msg = await asyncio.wait_for(self.bus.consume_inbound(), timeout=1.0)

                # Process it asynchronously via CommandQueue (handled in _process_message_wrapper)
                asyncio.create_task(self._process_message_wrapper(msg))

            except asyncio.TimeoutError:
                continue

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
        logger.info("Agent loop stopping")

    async def _process_message_wrapper(self, msg: InboundMessage) -> None:
        """
        Wrapper to process message via CommandQueue and handle response publishing/errors.
        """
        async def task():
            try:
                response = await self._inner_process_message(msg)
                if response:
                    await self.bus.publish_outbound(response)
            except Exception as e:
                logger.error(f"Error processing message in queue: {e}")
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Sorry, I encountered an error: {str(e)}",
                    )
                )

        # Determine lane based on message type/content
        # Subagent announcements and system messages go to BACKGROUND
        if msg.channel == "system":
            lane = CommandLane.BACKGROUND
        else:
            lane = CommandLane.MAIN
        
        await CommandQueue.enqueue(lane, task)

    async def _inner_process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.

        Args:
            msg: The inbound message to process.

        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (subagent announces)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            result = await self._process_system_message(msg)
            if result:
                result.content = self._filter_reasoning(result.content)
            return result

        if msg.trace_id:
            logger.info(f"[TraceID: {msg.trace_id}] Processing message from {msg.channel}:{msg.sender_id}")
        else:
            logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")

        # Get or create session
        session = self.sessions.get_or_create(msg.session_key)

        # Auto-compact history if needed
        await self._compact_history(session)

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(msg.channel, msg.chat_id, trace_id=msg.trace_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)

        # Build initial messages (use get_history for LLM-formatted messages)
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            media=msg.media if msg.media else None,
            channel=msg.channel,
            chat_id=msg.chat_id,
        )

        # Agent loop
        iteration = 0
        final_content = None

        while iteration < self.max_iterations:
            iteration += 1
            logger.debug(f"[TraceID: {msg.trace_id}] Starting iteration {iteration}")

            # Call LLM with failover support
            response = await self._chat_with_failover(
                messages=messages,
                tools=self.tools.get_definitions()
            )

            logger.debug(f"[TraceID: {msg.trace_id}] LLM responded. has_tool_calls: {response.has_tool_calls}, content length: {len(response.content) if response.content else 0}")

            # Handle tool calls (formal or embedded in text)
            tool_calls = response.tool_calls
            if not tool_calls and response.content:
                # Fallback: try to parse tool calls from text content
                tool_calls = self._parse_tool_calls_from_text(response.content)

            if tool_calls:
                # Add assistant message with tool calls
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments),  # Must be JSON string
                        },
                    }
                    for tc in tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content if not response.has_tool_calls else response.content, tool_call_dicts
                )

                # Execute tools in parallel
                tool_coros = []
                tool_starts: dict[str, float] = {}
                for tool_call in tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"[TraceID: {msg.trace_id}] Executing tool: {tool_call.name} with arguments: {args_str}")
                    tool_starts[tool_call.id] = time.perf_counter()
                    log_event({
                        "type": "tool_start",
                        "trace_id": msg.trace_id,
                        "tool": tool_call.name,
                        "tool_call_id": tool_call.id,
                        "args_keys": list(tool_call.arguments.keys()),
                    })
                    tool_coros.append(self.tools.execute(tool_call.name, tool_call.arguments))

                # Wait for all tools to complete
                results = await asyncio.gather(*tool_coros, return_exceptions=True)

                # Add results to messages
                for tool_call, result in zip(tool_calls, results):
                    # Handle exceptions from individual tools
                    if isinstance(result, Exception):
                        result_str = f"Error executing tool {tool_call.name}: {str(result)}"
                    else:
                        result_str = str(result)
                    
                    # Log first 200 chars safely
                    log_content = ""
                    if result_str and isinstance(result_str, str):
                        log_content = str(result_str)[:200]
                    logger.debug(f"Tool {tool_call.name} result: {log_content}...")
                    duration_s = None
                    if tool_call.id in tool_starts:
                        val = time.perf_counter() - tool_starts[tool_call.id]
                        duration_s = round(float(val), 4)
                    log_event({
                        "type": "tool_end",
                        "trace_id": msg.trace_id,
                        "tool": tool_call.name,
                        "tool_call_id": tool_call.id,
                        "status": "error" if isinstance(result, Exception) else "ok",
                        "duration_s": duration_s,
                        "result_len": len(result_str),
                    })
                        
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result_str
                    )

                # TRIGGER COMPACTION: Check context size after tool results
                guard = ContextGuard(model=self.model)
                evaluation = guard.evaluate(messages)
                if evaluation["should_compact"]:
                    logger.info(f"[TraceID: {msg.trace_id}] Context utilization high ({evaluation['utilization']:.2f}). Triggering compaction...")
                    # Identify messages to summarize (system/bootstrap usually at start, we keep them)
                    # For now, we summarize everything except system prompt and last 5 tool results/messages
                    keep_recent = 10
                    to_sum = [m for m in messages if m.get("role") != "system"]
                    if len(to_sum) > keep_recent:
                        prefix_msgs = [m for m in messages if m.get("role") == "system"]
                        sum_msgs = messages[len(prefix_msgs):-keep_recent]
                        recent_msgs = messages[-keep_recent:]
                        
                        summary = await self._summarize_messages(sum_msgs)
                        if summary:
                            messages = prefix_msgs + [
                                {"role": "system", "content": f"Previous conversation summary: {summary}"}
                            ] + recent_msgs
                            logger.info(f"[TraceID: {msg.trace_id}] Context compacted via LLM summary.")
            else:
                # No tool calls, we're done
                final_content = response.content
                break

        if final_content is None:
            final_content = "我已经完成了处理，但暂时没有需要回复的具体内容。"

        # Final check: if context is still too large, we might want to flag it
        # but for now we just finish.

        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        # Filter reasoning before sending to user
        final_content = self._filter_reasoning(str(final_content))

        return OutboundMessage(
            channel=msg.channel, 
            chat_id=msg.chat_id, 
            content=final_content,
            trace_id=msg.trace_id
        )

    async def _chat_with_failover(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> "LLMResponse":
        """
        Call LLM with automatic failover to other registered providers.
        """
        from nanobot.providers.factory import ProviderFactory

        # List of candidate providers: Primary first, then registry fallbacks
        candidates = []
        
        # 1. Primary provider
        candidates.append({
            "name": "primary",
            "provider": self.provider,
            "model": self.model
        })
        
        # 2. Registry providers (excluding primary if duplicated)
        # 2. Registry providers (excluding primary if duplicated)
        if self.model_registry:
            # Use get_active_providers to filter out cooled-down providers
            active_infos = self.model_registry.get_active_providers(model=self.model)
            
            for p_info in active_infos:
                # Avoid re-adding primary if already there (heuristic check)
                if p_info.base_url == self.provider.api_base and p_info.default_model == self.model:
                    # Also check if primary matches this provider to verify cooldown?
                    # For now just skip to avoid duplication
                    continue
                
                # Create a temporary provider for fallback
                try:
                    fallback_provider = ProviderFactory.get_provider(
                        model=p_info.default_model or (p_info.models[0] if p_info.models else self.model),
                        api_key=p_info.api_key,
                        api_base=p_info.base_url
                    )
                    candidates.append({
                        "name": p_info.name,
                        "provider": fallback_provider,
                        "model": fallback_provider.default_model
                    })
                except Exception as e:
                    logger.warning(f"Failed to create fallback provider {p_info.name}: {e}")

        last_error = None
        for i, candidate in enumerate(candidates):
            try:
                if i > 0:
                    await self._send_pulse_message(
                        f"🐈 主模型响应异常，正在尝试备用大脑 ({candidate['name']})，请稍等... 🐾"
                    )

                response = await candidate["provider"].chat(
                    messages=messages,
                    tools=tools,
                    model=candidate.get("model", self.model),
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout=25.0, # Fail fast (25s) to allow rotation
                )
                
                if response.finish_reason == "error":
                    raise Exception(response.content)
                
                return response
                
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {candidate['name']} failed: {e}")
                
                # Report failure to registry to trigger cooldown
                if self.model_registry:
                    self.model_registry.report_failure(candidate["name"])
                    
                continue

        # If all candidates fail
        error_msg = f"抱歉老板，所有可用的大脑（共 {len(candidates)} 个）都暂时无法响应。最后一次错误：{last_error}"
        from nanobot.providers.base import LLMResponse
        return LLMResponse(content=error_msg, finish_reason="error")

    async def _send_pulse_message(self, content: str) -> None:
        """Send a proactive 'pulse' message to the user to show progress."""
        # Use MessageTool context if available
        message_tool = self.tools.get("message")
        if (message_tool and 
            hasattr(message_tool, "current_channel") and 
            message_tool.current_channel and 
            message_tool.current_chat_id):
            
            from nanobot.bus.events import OutboundMessage
            await self.bus.publish_outbound(OutboundMessage(
                channel=message_tool.current_channel,
                chat_id=message_tool.current_chat_id,
                content=content
            ))

    async def _process_system_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a system message (e.g., subagent announce).

        The chat_id field contains "original_channel:original_chat_id" to route
        the response back to the correct destination.
        """
        logger.info(f"Processing system message from {msg.sender_id}")

        # Parse origin from metadata (preferred) or chat_id
        if msg.metadata and "origin" in msg.metadata:
            origin = msg.metadata["origin"]
            origin_channel = origin.get("channel", "cli")
            origin_chat_id = origin.get("chat_id", "direct")
        elif ":" in msg.chat_id:
            parts = msg.chat_id.split(":", 1)
            origin_channel = parts[0]
            origin_chat_id = parts[1]
        else:
            # Fallback
            origin_channel = "cli"
            origin_chat_id = msg.chat_id

        # Use the origin session for context
        session_key = f"{origin_channel}:{origin_chat_id}"
        session = self.sessions.get_or_create(session_key)

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin_channel, origin_chat_id)

        spawn_tool = self.tools.get("spawn")
        if isinstance(spawn_tool, SpawnTool):
            spawn_tool.set_context(origin_channel, origin_chat_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin_channel, origin_chat_id)

        # Build messages with the announce content
        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin_channel,
            chat_id=origin_chat_id,
        )

        # Agent loop (limited for announce handling)
        iteration = 0
        final_content = None

        while iteration < self.max_iterations:
            iteration += 1

            response = await self.provider.chat(
                messages=messages, tools=self.tools.get_definitions(), model=self.model
            )

            if response.has_tool_calls:
                tool_call_dicts = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                    }
                    for tc in response.tool_calls
                ]
                messages = self.context.add_assistant_message(
                    messages, response.content, tool_call_dicts
                )

                for tool_call in response.tool_calls:
                    args_str = json.dumps(tool_call.arguments)
                    logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
                    result = await self.tools.execute(tool_call.name, tool_call.arguments)
                    messages = self.context.add_tool_result(
                        messages, tool_call.id, tool_call.name, result
                    )
            else:
                final_content = response.content
                break

        if final_content is None:
            final_content = "Background task completed."

        # Save to session (mark as system message in history)
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(
            channel=origin_channel, chat_id=origin_chat_id, content=final_content
        )

    async def process_direct(
        self,
        content: str,
        session_key: str = "cli:direct",
        channel: str = "cli",
        chat_id: str = "direct",
        lane: CommandLane = CommandLane.MAIN,
    ) -> str:
        """
        Process a message directly (for CLI or cron usage).

        Args:
            content: The message content.
            session_key: Session identifier.
            channel: Source channel (for context).
            chat_id: Source chat ID (for context).

        Returns:
            The agent's response.
        """
        msg = InboundMessage(channel=channel, sender_id="user", chat_id=chat_id, content=content)

        # For direct access, we wait for result but still use queue for safety
        async def task():
            response = await self._inner_process_message(msg)
            return response.content if response else ""

        return await CommandQueue.enqueue(lane, task)

    async def _compact_history(self, session: "Session") -> None:
        """
        Summarize conversation history if it exceeds the threshold.
        """
        if not self.brain_config.auto_summarize:
            return

        guard = ContextGuard(model=self.model)
        # lower threshold for proactive summarization
        safe_limit = guard.limit * 0.6 
        
        current_usage = TokenCounter.count_messages(session.messages)
        count_threshold = self.brain_config.summary_threshold
        
        if current_usage < safe_limit and len(session.messages) < count_threshold:
            return

        logger.info(f"Auto-compacting session {session.key} (tokens: {current_usage}/{int(safe_limit)}, msgs: {len(session.messages)})")

        summary = await self._summarize_messages(session.messages[:-10])
        if summary:
            # Keep only the last 10 messages and the new summary
            recent = session.messages[-10:]
            session.messages = [
                {"role": "system", "content": f"This is a summary of the earlier conversation: {summary}"}
            ] + recent
            self.sessions.save(session)

    async def _summarize_messages(self, messages: list[dict[str, Any]]) -> str | None:
        """
        Use the LLM to summarize a list of messages.
        """
        if not messages:
            return None

        conversation_text = ""
        for m in messages:
            role = m.get("role", "unknown")
            content = m.get("content", "")
            if isinstance(content, list):
                # Handle complex content (e.g. tool calls results)
                content = json.dumps(content)
            conversation_text += f"{role}: {str(content)[:1000]}\n" # Cap each msg for summary prompt

        prompt = f"""Summarize the following conversation history into a concise paragraph.
Focus on key facts, user preferences, and important context that should be remembered.
Ignore transient interactions or technical tool output details.

Conversation History:
{conversation_text}
"""
        try:
            summary_msgs = [
                {"role": "system", "content": "You are a helpful assistant that summarizes conversations."},
                {"role": "user", "content": prompt}
            ]
            response = await self._chat_with_failover(messages=summary_msgs, tools=[])
            return response.content
        except Exception as e:
            logger.error(f"Failed to summarize messages: {e}")
            return None

    def _parse_tool_calls_from_text(self, text: str) -> List[ToolCallRequest]:
        """
        Attempt to parse tool calls from raw text if the model didn't use the formal API.
        Supports both single JSON object and list of JSON objects.
        """
        if not text:
            return []

        import re
        import uuid

        # Look for JSON-like patterns: { ... } or [ { ... }, ... ]
        # We try to find the largest block that looks like a tool call
        results: List[ToolCallRequest] = []
        
        # Pattern 1: Look for JSON blocks in markdown code blocks
        blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text)
        
        # Pattern 2: If no code blocks, treat the entire text as a potential JSON block if it starts with {
        if not blocks:
            text_strip = text.strip()
            if text_strip.startswith("{") or text_strip.startswith("["):
                blocks = [text_strip]

        # Pattern 3: Look for any { ... } blocks
        if not blocks:
            matches = re.finditer(r"(\{[\s\S]*?\})", text)
            blocks = [m.group(0) for m in matches]

        logger.debug(f"Attempting to parse tool calls from {len(blocks)} potential blocks")

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Try to parse multiple JSON objects if they are concatenated or separated by whitespace
            decoder = json.JSONDecoder()
            pos = 0
            while pos < len(block):
                try:
                    # Skip non-JSON leading characters
                    while pos < len(block) and block[pos] not in '{[':
                        pos += 1
                    if pos >= len(block):
                        break

                    data, next_pos = decoder.raw_decode(block[pos:])
                    pos += next_pos
                    
                    # Process the parsed data
                    if isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and "name" in item:
                                results.append(ToolCallRequest(
                                    id=f"call_{uuid.uuid4().hex[:8]}",
                                    name=item["name"],
                                    arguments=item.get("arguments", {})
                                ))
                    elif isinstance(data, dict) and "name" in data:
                        results.append(ToolCallRequest(
                            id=f"call_{uuid.uuid4().hex[:8]}",
                            name=data["name"],
                            arguments=data.get("arguments", {})
                        ))
                except (json.JSONDecodeError, ValueError) as e:
                    logger.debug(f"Failed to parse JSON segment starting at {pos}: {e}")
                    # Move past current failing char to try again
                    pos += 1

        if results:
            logger.info(f"Successfully parsed {len(results)} tool calls from text content")
        return results

    def _filter_reasoning(self, content: str) -> str:
        """
        Remove internal reasoning within <think> tags.
        
        Args:
            content: The raw response content.
            
        Returns:
            Content with reasoning tags and their contents removed.
        """
        if not content:
            return content
            
        import re
        # Strip <think>...</think> (non-greedy, including newline)
        # Handle cases where the closing tag might be missing at the end
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        content = re.sub(r"<think>.*$", "", content, flags=re.DOTALL)
        
        return content.strip()
