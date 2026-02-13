from typing import Callable

from loguru import logger

from nanobot.agent.origin_resolver import resolve_system_origin
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.message import MessageTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.session.manager import SessionManager


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
        session.add_message("user", f"[System: {msg.sender_id}] {msg.content}")

        if self.is_silent_reply(final_content):
            self.sessions.save(session)
            return None

        session.add_message("assistant", final_content)
        self.sessions.save(session)

        return OutboundMessage(channel=origin.channel, chat_id=origin.chat_id, content=final_content)
