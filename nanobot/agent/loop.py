import asyncio
import hashlib
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
from nanobot.agent.tools.filesystem import (
    EditFileTool,
    ListDirTool,
    ReadFileTool,
    WriteFileTool,
)
from nanobot.agent.tools.github import GitHubTool
from nanobot.agent.tools.gmail import GmailTool
from nanobot.agent.tools.qq_mail import QQMailTool
from nanobot.agent.tools.knowledge import KnowledgeTool
from nanobot.agent.tools.mac import MacTool
from nanobot.agent.tools.mac_vision import MacVisionTool
from nanobot.agent.tools.memory import MemoryTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.registry import ToolRegistry
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.skills import SkillsTool
from nanobot.agent.tools.browser import BrowserTool
from nanobot.agent.tools.task import TaskTool
from nanobot.agent.task_manager import TaskManager
from nanobot.agent.models import ModelRegistry
from nanobot.agent.tools.provider import ProviderTool
from nanobot.agent.tools.weather import WeatherTool
from nanobot.agent.tools.tavily import TavilyTool
from nanobot.agent.tools.tianapi import TianAPITool
from nanobot.agent.tools.tushare import TushareTool
from nanobot.agent.tools.feishu import FeishuTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest
from nanobot.session.manager import SessionManager
from nanobot.process import CommandQueue, CommandLane
from nanobot.agent.context_guard import ContextGuard, TokenCounter
from nanobot.agent.executor import ToolExecutor
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
        self.executor = ToolExecutor(self.tools)
        
        # Initialize Model Registry
        self.model_registry = ModelRegistry()
        self.providers_config = providers_config

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
        def _tool_enabled(name: str) -> bool:
            if self.tools_config.enabled_tools is not None:
                return name in self.tools_config.enabled_tools
            if self.tools_config.disabled_tools:
                return name not in self.tools_config.disabled_tools
            return True

        # File tools (restrict to workspace if configured)
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        if _tool_enabled("read_file"):
            self.tools.register(ReadFileTool(allowed_dir=allowed_dir))
        if _tool_enabled("write_file"):
            self.tools.register(WriteFileTool(allowed_dir=allowed_dir))
        if _tool_enabled("edit_file"):
            self.tools.register(EditFileTool(allowed_dir=allowed_dir))
        if _tool_enabled("list_dir"):
            self.tools.register(ListDirTool(allowed_dir=allowed_dir))

        # Shell tool
        if _tool_enabled("exec"):
            self.tools.register(
                ExecTool(
                    working_dir=str(self.workspace),
                    timeout=self.exec_config.timeout,
                    restrict_to_workspace=self.restrict_to_workspace,
                    provider=self.provider,
                    brain_config=self.brain_config,
                )
            )

        # Web tools - Re-enabled for single-agent use
        if _tool_enabled("browser"):
            self.tools.register(BrowserTool(proxy=self.web_proxy))

        # Message tool
        if _tool_enabled("message"):
            message_tool = MessageTool(send_callback=self.bus.publish_outbound)
            self.tools.register(message_tool)

        # Task storage path (used by both CronTool and TaskTool)
        from nanobot.config.loader import get_data_dir
        task_storage_path = get_data_dir() / "tasks.json"

        # Cron tool (for scheduling)
        if self.cron_service and _tool_enabled("cron"):
            self.tools.register(CronTool(self.cron_service, task_storage_path=task_storage_path))

        # Mail tools
        if _tool_enabled("gmail"):
            self.tools.register(GmailTool())
        if _tool_enabled("qq_mail"):
            self.tools.register(QQMailTool())

        # Mac tool
        if _tool_enabled("mac_control"):
            self.tools.register(MacTool(confirm_mode=self.mac_confirm_mode))
        if _tool_enabled("mac_vision"):
            self.tools.register(MacVisionTool(confirm_mode=self.mac_confirm_mode))

        # GitHub tool
        if _tool_enabled("github"):
            self.tools.register(GitHubTool())

        # Knowledge tool
        if _tool_enabled("knowledge_base"):
            self.tools.register(KnowledgeTool())

        # Memory tool (active management)
        if _tool_enabled("memory"):
            self.tools.register(MemoryTool(workspace=self.workspace))

        # Provider tool (manage LLM providers)
        if _tool_enabled("provider"):
            self.tools.register(ProviderTool(registry=self.model_registry))

        # Weather tool
        if _tool_enabled("weather"):
            self.tools.register(WeatherTool())

        # Tavily tool
        if _tool_enabled("tavily"):
            self.tools.register(TavilyTool())

        # TianAPI tool
        if _tool_enabled("tianapi"):
            self.tools.register(TianAPITool())

        # Tushare tool
        if _tool_enabled("tushare"):
            self.tools.register(TushareTool())

        # Feishu tool
        if _tool_enabled("feishu"):
            self.tools.register(FeishuTool())

        # Skills tool (Plaza/management)
        if _tool_enabled("skills"):
            self.tools.register(
                SkillsTool(
                    workspace=self.workspace,
                    search_func=None,
                )
            )

        # Task tool (named task management)
        task_manager = TaskManager(storage_path=task_storage_path)
        exec_tool = self.tools.get("exec")
        if exec_tool and _tool_enabled("task"):
            self.tools.register(TaskTool(task_manager=task_manager, exec_tool=exec_tool))

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

        cron_tool = self.tools.get("cron")

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
        seen_tool_call_ids: set[str] = set()
        seen_tool_call_hashes: set[str] = set()

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
                # Loop detection: check if we are repeating the exact same tool calls
                # This often happens with Gemini proxies when they lose context
                current_ids = [tc.id for tc in tool_calls if tc.id]
                
                # SHA-256 hash of tool name + arguments for content-based detection
                current_hashes = []
                for tc in tool_calls:
                    # Sort arguments to ensure consistent hashing
                    args_json = json.dumps(tc.arguments, sort_keys=True)
                    tc_hash = hashlib.sha256(f"{tc.name}:{args_json}".encode()).hexdigest()
                    current_hashes.append(tc_hash)

                # Check for strict loops (repetitive tool calls)
                # We block if ALL current calls have been seen before in this turn
                id_loop = len([tid for tid in current_ids if tid in seen_tool_call_ids]) == len(current_ids)
                hash_loop = len([h for h in current_hashes if h in seen_tool_call_hashes]) == len(current_hashes)
                
                # Allow some progress but block fixed patterns
                is_strict_loop = iteration > 3 and (id_loop or hash_loop)

                if is_strict_loop:
                    logger.warning(f"[TraceID: {msg.trace_id}] Loop detected! LLM repeated tool calls. IDs: {current_ids}, Hashes: {current_hashes}. Breaking turn.")
                    final_content = response.content or "抱歉老板，系统检测到消息处理进入了死循环（重复请求相同内容），已强制中止。建议您简化当前指令或稍后再试。🐾"
                    break
                
                # Add to seen
                for tid in current_ids:
                    if tid:
                        seen_tool_call_ids.add(tid)
                for h in current_hashes:
                    seen_tool_call_hashes.add(h)

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
                    messages, response.content, tool_call_dicts
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
                    tool_coros.append(self.executor.execute(tool_call.name, tool_call.arguments))

                # Wait for all tools to complete
                results = await asyncio.gather(*tool_coros, return_exceptions=True)

                from nanobot.agent.tools.base import ToolResult, ToolSeverity

                # Add results to messages
                for tool_call, result in zip(tool_calls, results):
                    if isinstance(result, Exception):
                        import traceback
                        tb = traceback.format_exc()
                        logger.error(f"[TraceID: {msg.trace_id}] Tool {tool_call.name} failed with traceback:\n{tb}")
                        result_str = f"Error executing tool {tool_call.name}: {str(result)}"
                    elif isinstance(result, ToolResult):
                        result_str = result.output
                        # Append remedy to help the model recover
                        if result.remedy:
                            result_str = f"{result_str}\n\n[系统及工具建议: {result.remedy}]"
                        # Surface severity / retry / confirmation hints
                        if result.severity in (ToolSeverity.WARN, ToolSeverity.ERROR, ToolSeverity.FATAL):
                            result_str = f"[severity:{result.severity}]\n{result_str}"
                        if result.should_retry:
                            result_str = f"{result_str}\n\n[系统提示: 建议重试该工具调用，或调整参数后重试。]"
                        if result.requires_user_confirmation:
                            result_str = f"{result_str}\n\n[系统提示: 该操作需要用户确认后再执行。]"
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
                            # CRITICAL: Strip old summaries from prefix messages before adding new one
                            new_prefix = []
                            for m in prefix_msgs:
                                content = m.get("content", "")
                                if isinstance(content, str) and "Previous conversation summary:" in content:
                                    continue
                                new_prefix.append(m)

                            messages = new_prefix + [
                                {"role": "system", "content": f"Previous conversation summary: {summary}"}
                            ] + recent_msgs
                            logger.info(f"[TraceID: {msg.trace_id}] Context compacted via LLM summary (and deduped).")
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

        # List of candidate providers
        candidates = []

        # 1. Determine the "Real" Primary Provider for THIS model
        primary_provider = self.provider
        primary_model = self.model
        primary_name = "primary"

        if self.model_registry:
            # Check if there's a specialized provider in the registry for this model
            # that's better than our default 'primary' one.
            registry_match = None
            for p_info in self.model_registry.providers.values():
                if p_info.default_model == self.model or self.model in p_info.models or p_info.name == self.model:
                    registry_match = p_info
                    break
            
            if registry_match and registry_match.base_url != self.provider.api_base:
                logger.debug(f"Switching primary provider to registry match '{registry_match.name}' for model '{self.model}'")
                try:
                    primary_provider = ProviderFactory.get_provider(
                        model=registry_match.default_model or self.model,
                        api_key=registry_match.api_key,
                        api_base=registry_match.base_url
                    )
                    primary_name = registry_match.name
                except Exception as e:
                    logger.warning(f"Failed to switch to specific provider for {self.model}: {e}")

        candidates.append({
            "name": primary_name,
            "provider": primary_provider,
            "model": primary_model
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
                        f"主模型响应异常，正在尝试备用大脑 ({candidate['name']})，请稍等..."
                    )

                response = await candidate["provider"].chat(
                    messages=messages,
                    tools=tools,
                    model=candidate.get("model", self.model),
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    timeout=45.0, # Fail fast (45s) to allow rotation
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

        # Agent loop (limited for system message handling)
        iteration = 0
        final_content = None

        while iteration < self.max_iterations:
            iteration += 1

            response = await self._chat_with_failover(
                messages=messages, tools=self.tools.get_definitions()
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
        filtered = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        filtered = re.sub(r"<think>.*$", "", filtered, flags=re.DOTALL).strip()
        
        if not filtered and content:
            # If everything was filtered out, return the raw content to avoid silence
            # This happens if the model puts its entire response in <think> tags
            return f"[Thinking Process]\n{content}"
            
        return filtered
