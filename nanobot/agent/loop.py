import asyncio
import json
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from nanobot.session.manager import Session

if TYPE_CHECKING:
    from nanobot.config.schema import BrainConfig, ExecToolConfig, ProvidersConfig, ToolsConfig
    from nanobot.cron.service import CronService

from loguru import logger

from nanobot.agent.context import SILENT_REPLY_TOKEN, ContextBuilder
from nanobot.agent.context_guard import ContextGuard, TokenCounter
from nanobot.agent.executor import ToolExecutor
from nanobot.agent.message_flow import MessageFlowCoordinator
from nanobot.agent.models import ModelRegistry
from nanobot.agent.provider_router import ProviderRouter
from nanobot.agent.system_turn_service import SystemTurnService
from nanobot.agent.tool_bootstrapper import ToolBootstrapper
from nanobot.agent.tool_policy import ToolPolicy
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.turn_engine import TurnEngine
from nanobot.agent.user_turn_service import UserTurnService
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.hooks import HookRegistry
from nanobot.process import CommandLane, CommandQueue
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.session.manager import SessionManager


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
        from nanobot.config.schema import BrainConfig, ExecToolConfig, ToolsConfig

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
        self.hook_registry = HookRegistry()
        self.executor = ToolExecutor(self.tools, hook_registry=self.hook_registry)
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
            max_total_tool_calls=max(1, int(getattr(self.brain_config, "max_total_tool_calls", 30))),
            max_turn_seconds=max(5, int(getattr(self.brain_config, "max_turn_seconds", 45))),
            hook_registry=self.hook_registry,
            tool_policy=ToolPolicy(
                web_default=getattr(self.tools_config.policy, "web_default", "tavily"),
                enable_mcp_fallback=bool(getattr(self.tools_config.policy, "enable_mcp_fallback", True)),
                allow_explicit_mcp=bool(getattr(self.tools_config.policy, "allow_explicit_mcp", True)),
            ),
        )
        self.system_turn_service = SystemTurnService(
            sessions=self.sessions,
            context=self.context,
            tools=self.tools,
            turn_engine=self.turn_engine,
            filter_reasoning=self._filter_reasoning,
            is_silent_reply=self._is_silent_reply,
        )
        self.user_turn_service = UserTurnService(
            sessions=self.sessions,
            context=self.context,
            tools=self.tools,
            turn_engine=self.turn_engine,
            compact_history=self._compact_history,
            filter_reasoning=self._filter_reasoning,
            is_silent_reply=self._is_silent_reply,
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

        self.message_flow = MessageFlowCoordinator(
            busy_notice_threshold=self.tools_config.busy_notice_threshold,
            busy_notice_debounce_seconds=self.tools_config.busy_notice_debounce_seconds,
            error_fallback_channel=self.tools_config.error_fallback_channel,
            error_fallback_chat_id=self.tools_config.error_fallback_chat_id,
            publish_outbound=self.bus.publish_outbound,
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
                await self.bus.publish_outbound(self.message_flow.build_error_outbound(msg, e))

        lane = self.message_flow.lane_for(msg)
        await self.message_flow.maybe_send_busy_notice(msg, lane)
        await CommandQueue.enqueue(lane, task)

    async def _inner_process_message(self, msg: InboundMessage) -> OutboundMessage | None:
        """
        Process a single inbound message.

        Args:
            msg: The inbound message to process.

        Returns:
            The response message, or None if no response needed.
        """
        if msg.channel == "system":
            return await self._process_system_message(msg)
        return await self.user_turn_service.process(msg)

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
        return await self.system_turn_service.process(msg)

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
                {"role": "system", "content": f"以下是更早对话的摘要：{summary}"}
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

        prompt = f"""请将以下对话历史总结为一段简洁文字。
重点保留：关键事实、用户偏好、后续仍需记住的重要上下文。
忽略：短暂的来回确认、工具底层技术细节、无持续价值的噪音信息。

对话历史：
{conversation_text}
"""
        try:
            summary_msgs = [
                {"role": "system", "content": "你是一个负责对话摘要的助手。请仅输出摘要正文。"},
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
