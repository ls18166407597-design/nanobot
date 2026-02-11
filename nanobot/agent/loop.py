import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
if TYPE_CHECKING:
    from nanobot.session.manager import Session

if TYPE_CHECKING:
    from nanobot.config.schema import BrainConfig, ExecToolConfig, ProvidersConfig, ToolsConfig
    from nanobot.cron.service import CronService

from loguru import logger

from nanobot.agent.context import ContextBuilder
from nanobot.providers.factory import ProviderFactory
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.models import ModelRegistry
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.session.manager import SessionManager
from nanobot.process import CommandQueue, CommandLane
from nanobot.agent.context_guard import ContextGuard, TokenCounter
from nanobot.agent.executor import ToolExecutor
from nanobot.agent.context import SILENT_REPLY_TOKEN
from nanobot.agent.turn_engine import TurnEngine
from nanobot.agent.provider_router import ProviderRouter
from nanobot.agent.tool_bootstrapper import ToolBootstrapper


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
    SELF_CORRECTION_PROMPT = (
        "系统检测到你正在重复执行相同的工具调用且未取得进展。可能原因是之前的工具输出未满足预期。"
        "请不要再次尝试相同操作，改用其他思路（例如检查文件是否存在、调整搜索词、或向用户确认需求）。"
    )
    LOOP_BREAK_REPLY = "抱歉，我陷入了重复执行的循环并未能恢复。请检查当前指令是否超出权限，或提供更明确的需求。"

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
        self.executor = ToolExecutor(self.tools)
        self.turn_engine = TurnEngine(
            context=self.context,
            executor=self.executor,
            model=self.model,
            max_iterations=self.max_iterations,
            get_tools_definitions=self.tools.get_definitions,
            chat_with_failover=self._chat_with_failover,
            parse_tool_calls_from_text=self._parse_tool_calls_from_text,
            summarize_messages=self._summarize_messages,
            self_correction_prompt=self.SELF_CORRECTION_PROMPT,
            loop_break_reply=self.LOOP_BREAK_REPLY,
        )
        
        # Initialize Model Registry
        self.model_registry = ModelRegistry()
        self.providers_config = providers_config
        self.provider_router = ProviderRouter(
            provider=self.provider,
            model=self.model,
            model_registry=self.model_registry,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            pulse_callback=self._send_pulse_message,
        )

        self._last_busy_notice_time: float = 0
        self._busy_debounce_seconds: float = self.tools_config.busy_notice_debounce_seconds

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
                            default_model=p.get("default_model") or p.get("model"),
                            is_free=True
                        )

        await register_all()

    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        ToolBootstrapper(
            tools=self.tools,
            workspace=self.workspace,
            restrict_to_workspace=self.restrict_to_workspace,
            exec_config=self.exec_config,
            provider=self.provider,
            brain_config=self.brain_config,
            web_proxy=self.web_proxy,
            bus_publish_outbound=self.bus.publish_outbound,
            cron_service=self.cron_service,
            model_registry=self.model_registry,
            tools_config=self.tools_config,
            mac_confirm_mode=self.mac_confirm_mode,
        ).register_default_tools()

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
                
                # Use origin from metadata if available (safer than split for single-value chat_ids)
                origin = msg.metadata.get("origin", {})
                if ":" in msg.chat_id:
                    fallback_channel = msg.chat_id.split(":", 1)[0]
                    fallback_chat_id = msg.chat_id.split(":", 1)[1]
                else:
                    if msg.channel == "system":
                        fallback_channel = self.tools_config.error_fallback_channel
                        fallback_chat_id = self.tools_config.error_fallback_chat_id
                    else:
                        fallback_channel = msg.channel
                        fallback_chat_id = msg.chat_id
                
                await self.bus.publish_outbound(
                    OutboundMessage(
                        channel=origin.get("channel") or fallback_channel,
                        chat_id=origin.get("chat_id") or fallback_chat_id,
                        content=f"抱歉，我在处理指令时遇到了错误: {str(e)}",
                        trace_id=msg.trace_id
                    )
                )

        # Determine lane based on message type/content
        # Subagent announcements and system messages go to BACKGROUND
        if msg.channel == "system":
            lane = CommandLane.BACKGROUND
        else:
            lane = CommandLane.MAIN

        # Busy detection: If MAIN lane is already occupied, notify the user.
        if lane == CommandLane.MAIN:
            queue_stats = CommandQueue.get_lane(lane)
            queued_total = queue_stats.active + len(queue_stats.queue)
            if queued_total >= self.tools_config.busy_notice_threshold:
                 # Inform user of busy status (non-blocking) with debounce
                 now = time.time()
                 if now - self._last_busy_notice_time > self._busy_debounce_seconds:
                     self._last_busy_notice_time = now
                     asyncio.create_task(self.bus.publish_outbound(
                         OutboundMessage(
                             channel=msg.channel,
                             chat_id=msg.chat_id,
                             content="老板，我正在全力处理您之前的指令，请稍等片刻，新指令已加入队列。"
                         )
                     ))

        await CommandQueue.enqueue(lane, task)

    async def _inner_process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.

        Args:
            msg: The inbound message to process.

        Returns:
            The response message, or None if no response needed.
        """
        # Handle system messages (cron signals, etc.)
        # The chat_id contains the original "channel:chat_id" to route back to
        if msg.channel == "system":
            result = await self._process_system_message(msg)
            if result:
                result.content = self._filter_reasoning(result.content)
                if self._is_silent_reply(result.content):
                    return None
            return result

        if msg.trace_id:
            logger.info(f"[TraceID: {msg.trace_id}] Processing message from {msg.channel}:{msg.sender_id}")
        else:
            logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")

        # Get or create session (explicit override is supported at InboundMessage level).
        session = self.sessions.get_or_create(msg.session_key)

        # Auto-compact history if needed
        await self._compact_history(session)

        # Update tool contexts
        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)

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

        final_content = await self.turn_engine.run(
            messages=messages,
            trace_id=msg.trace_id,
            parse_calls_from_text=True,
            include_severity=True,
            parallel_tool_exec=True,
            compact_after_tools=True,
        )

        if final_content is None:
            final_content = "我已经完成了处理，但暂时没有需要回复的具体内容。"

        # Final check: if context is still too large, we might want to flag it
        # but for now we just finish.

        # Filter reasoning before saving/sending
        final_content = self._filter_reasoning(str(final_content))
        if self._is_silent_reply(final_content):
            session.add_message("user", msg.content)
            self.sessions.save(session)
            return None

        # Save to session
        session.add_message("user", msg.content)
        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(
            channel=msg.channel, 
            chat_id=msg.chat_id, 
            content=final_content,
            trace_id=msg.trace_id
        )

    async def _chat_with_failover(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]] | None = None
    ) -> "LLMResponse":
        return await self.provider_router.chat_with_failover(messages=messages, tools=tools)

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
        Process a system message (e.g., cron signals).

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

        final_content = await self.turn_engine.run(
            messages=messages,
            trace_id=msg.trace_id,
            parse_calls_from_text=False,
            include_severity=False,
            parallel_tool_exec=False,
            compact_after_tools=False,
        )

        if final_content is None:
            final_content = "Background task completed."

        # Save to session (mark as system message in history)
        final_content = self._filter_reasoning(str(final_content))
        if self._is_silent_reply(final_content):
            session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")
            self.sessions.save(session)
            return None

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
        msg = InboundMessage(
            channel=channel,
            sender_id="user",
            chat_id=chat_id,
            content=content,
            session_key_override=session_key,
        )

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

        def _is_valid_tool_call(obj: dict) -> bool:
            if not isinstance(obj, dict):
                return False
            name = obj.get("name")
            args = obj.get("arguments")
            if not isinstance(name, str) or not name:
                return False
            if args is None or not isinstance(args, dict):
                return False
            # Only allow registered tools to avoid accidental JSON parsing
            return self.tools.get(name) is not None

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
                            if _is_valid_tool_call(item):
                                results.append(ToolCallRequest(
                                    id=f"call_{uuid.uuid4().hex[:8]}",
                                    name=item["name"],
                                    arguments=item.get("arguments", {})
                                ))
                    elif _is_valid_tool_call(data):
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
        filtered = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        filtered = re.sub(r"<think>.*$", "", filtered, flags=re.DOTALL).strip()
        
        if not filtered and content:
            # Never leak hidden reasoning even if model returned only <think> blocks.
            return "我已完成处理。"
            
        return filtered

    def _is_silent_reply(self, content: str) -> bool:
        """Whether content indicates no outbound user message should be sent."""
        return isinstance(content, str) and content.strip() == SILENT_REPLY_TOKEN
