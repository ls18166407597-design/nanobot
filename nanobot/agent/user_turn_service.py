from typing import Callable
import re

from loguru import logger

from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.message import MessageTool
from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.session.manager import Session
from nanobot.session.manager import SessionManager
from nanobot.agent.honesty import audit_and_mark_hallucinations


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

        system_status_tool = self.tools.get("system_status")
        if system_status_tool and hasattr(system_status_tool, "set_context"):
            system_status_tool.set_context(msg.channel, msg.chat_id, msg.session_key)

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
        used_tools = self._pop_used_tools(msg.trace_id)
        exec_report = self._pop_execution_report(msg.trace_id)

        # 诚信审计：检测并标记动作幻觉 (Hallucination Policing)
        all_tools_meta = self.tools.get_all_metadata() if hasattr(self.tools, "get_all_metadata") else []
        final_content, hallucination_detected = audit_and_mark_hallucinations(
            final_content, used_tools, all_tools_meta
        )

        final_content = self._enforce_execution_truth(final_content, exec_report)
        final_content = self._add_query_source_line(final_content, used_tools)

        if final_content.strip() == "":
            final_content = "本次未产出有效结果，可能模型或工具链暂时不可用。请重试一次。"

        session.add_message("user", msg.content)

        if hallucination_detected:
            # 向会话注入纠偏反馈，防止模型在后续对话中基于幻觉事实进行推理
            session.add_message(
                "system",
                "[诚信审计] 警告：你的上一条回复中包含了未实际执行的工具动作声明，已被内核物理拦截说明或标记为删除线。请根据 Tool 执行记录诚实汇报！"
            )

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

    def _pop_used_tools(self, trace_id: str | None) -> list[str]:
        pop_fn = getattr(self.turn_engine, "pop_used_tools", None)
        if not callable(pop_fn):
            return []
        return pop_fn(trace_id)

    def _pop_execution_report(self, trace_id: str | None) -> dict:
        pop_fn = getattr(self.turn_engine, "pop_execution_report", None)
        if not callable(pop_fn):
            return {}
        report = pop_fn(trace_id)
        return report if isinstance(report, dict) else {}

    def _add_query_source_line(self, content: str, tools: list[str]) -> str:
        body = self._strip_source_headers(content)
        if not tools:
            return body
        source_map = {
            "train_ticket": "12306",
            "github": "GitHub",
            "tavily": "Tavily API",
            "mcp:amap": "高德地图",
            "mcp:12306": "12306",
            "mcp:github": "GitHub",
            "mcp:puppeteer": "Browser",
            "browser": "Browser",
            "weather": "和风天气 API",
            "tianapi": "天行 API",
            "tushare": "Tushare API",
        }
        sources: list[str] = []
        for t in tools:
            src = source_map.get(t)
            if src and src not in sources:
                sources.append(src)
        if not sources:
            return body
        return f"查询来源: {' + '.join(sources)}\n\n{body}"

    def _strip_source_headers(self, content: str) -> str:
        """
        Keep source headers system-owned:
        - Drop model-generated '查询来源:' and '联网策略:' lines.
        - The final '查询来源:' is injected only from actual used tools.
        """
        lines = content.splitlines()
        normalized: list[str] = []
        for line in lines:
            if re.match(r"^\s*查询来源\s*:", line):
                continue
            if re.match(r"^\s*联网策略\s*:", line):
                continue
            normalized.append(line)
        return "\n".join(normalized).strip()

    def _enforce_execution_truth(self, content: str, report: dict) -> str:
        total = int(report.get("total_tool_calls", 0) or 0)
        success = int(report.get("success_tool_calls", 0) or 0)
        failed = int(report.get("failed_tool_calls", 0) or 0)
        if total <= 0:
            return content

        text = (content or "").strip()
        completion_claim = re.search(r"(已完成|已经完成|处理完成|执行完成|已处理完)", text)
        if success == 0:
            # 所有工具均失败时，禁止“已完成”话术，避免对用户造成误导。
            return (
                f"本次尝试调用了 {total} 次工具，但均未成功执行，当前无法确认任务已完成。\n"
                "请允许我调整方案后重试，或你提供更明确的参数/权限范围。"
            )

        if completion_claim and failed > 0:
            return (
                f"{text}\n\n"
                f"执行说明：本轮工具调用共 {total} 次，成功 {success} 次，失败 {failed} 次。"
            )
        return text
