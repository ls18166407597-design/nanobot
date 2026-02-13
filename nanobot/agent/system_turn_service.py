from typing import Callable

from loguru import logger

from nanobot.agent.origin_resolver import resolve_system_origin
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.message import MessageTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.session.manager import SessionManager
from nanobot.agent.honesty import audit_and_mark_hallucinations


class SystemTurnService:
    """Handles system-channel message turns with origin-aware routing and session persistence."""

    def __init__(
        self,
        *,
        sessions: SessionManager,
        context,
        tools,
        turn_engine,
        filter_reasoning: Callable[[str], str],
        is_silent_reply: Callable[[str], bool],
    ) -> None:
        self.sessions = sessions
        self.context = context
        self.tools = tools
        self.turn_engine = turn_engine
        self.filter_reasoning = filter_reasoning
        self.is_silent_reply = is_silent_reply

    async def process(self, msg: InboundMessage) -> OutboundMessage | None:
        logger.info(f"Processing system message from {msg.sender_id}")
        origin = resolve_system_origin(msg)

        session = self.sessions.get_or_create(origin.session_key)

        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(origin.channel, origin.chat_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(origin.channel, origin.chat_id)

        system_status_tool = self.tools.get("system_status")
        if system_status_tool and hasattr(system_status_tool, "set_context"):
            system_status_tool.set_context(origin.channel, origin.chat_id, origin.session_key)

        messages = self.context.build_messages(
            history=session.get_history(),
            current_message=msg.content,
            channel=origin.channel,
            chat_id=origin.chat_id,
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

        final_content = self.filter_reasoning(str(final_content))
        used_tools = self._pop_used_tools(msg.trace_id)

        # 诚信审计：检测并标记动作幻觉 (Hallucination Policing)
        all_tools_meta = self.tools.get_all_metadata() if hasattr(self.tools, "get_all_metadata") else []
        final_content, hallucination_detected = audit_and_mark_hallucinations(
            final_content, used_tools, all_tools_meta
        )

        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")

        if hallucination_detected:
            # 向后台会话注入纠偏反馈
            session.add_message(
                "system",
                "[诚信审计] 警告：你的上一条后台指令回复中包含了未实际执行的工具动作声明。请诚实汇报进度！"
            )

        if self.is_silent_reply(final_content):
            self.sessions.save(session)
            return None

        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(channel=origin.channel, chat_id=origin.chat_id, content=final_content)

    def _pop_used_tools(self, trace_id: str | None) -> list[str]:
        pop_fn = getattr(self.turn_engine, "pop_used_tools", None)
        if not callable(pop_fn):
            return []
        return pop_fn(trace_id)
