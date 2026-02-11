from typing import Callable

from loguru import logger

from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.message import MessageTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.session.manager import Session
from nanobot.session.manager import SessionManager


class UserTurnService:
    """Handles normal user-channel message turns and session persistence."""

    def __init__(
        self,
        *,
        sessions: SessionManager,
        context,
        tools,
        turn_engine,
        compact_history: Callable[[Session], object],
        filter_reasoning: Callable[[str], str],
        is_silent_reply: Callable[[str], bool],
    ) -> None:
        self.sessions = sessions
        self.context = context
        self.tools = tools
        self.turn_engine = turn_engine
        self.compact_history = compact_history
        self.filter_reasoning = filter_reasoning
        self.is_silent_reply = is_silent_reply

    async def process(self, msg: InboundMessage) -> OutboundMessage | None:
        if msg.trace_id:
            logger.info(f"[TraceID: {msg.trace_id}] Processing message from {msg.channel}:{msg.sender_id}")
        else:
            logger.info(f"Processing message from {msg.channel}:{msg.sender_id}")

        session = self.sessions.get_or_create(msg.session_key)
        await self.compact_history(session)

        message_tool = self.tools.get("message")
        if isinstance(message_tool, MessageTool):
            message_tool.set_context(msg.channel, msg.chat_id)

        cron_tool = self.tools.get("cron")
        if isinstance(cron_tool, CronTool):
            cron_tool.set_context(msg.channel, msg.chat_id)

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

        final_content = self.filter_reasoning(str(final_content))
        session.add_message("user", msg.content)

        if self.is_silent_reply(final_content):
            self.sessions.save(session)
            return None

        session.add_message("assistant", final_content)
        self.sessions.save(session)
        return OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=final_content,
            trace_id=msg.trace_id,
        )
