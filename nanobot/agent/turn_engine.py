"""Turn execution engine shared by foreground and system message flows."""

import asyncio
import hashlib
import json
import re
import time
from typing import Any, Awaitable, Callable

from loguru import logger

from nanobot.agent.context_guard import ContextGuard
from nanobot.agent.tools.base import ToolResult, ToolSeverity
from nanobot.providers.base import ToolCallRequest
from nanobot.utils.audit import log_event


class TurnEngine:
    """Execute one conversational turn with tool-calling loop controls."""

    def __init__(
        self,
        *,
        context: Any,
        executor: Any,
        model: str,
        max_iterations: int,
        get_tools_definitions: Callable[[], list[dict[str, Any]]],
        chat_with_failover: Callable[..., Awaitable[Any]],
        parse_tool_calls_from_text: Callable[[str], list[ToolCallRequest]],
        summarize_messages: Callable[[list[dict[str, Any]]], Awaitable[str | None]],
        self_correction_prompt: str,
        loop_break_reply: str,
        max_total_tool_calls: int = 30,
    ):
        self.context = context
        self.executor = executor
        self.model = model
        self.max_iterations = max_iterations
        self.get_tools_definitions = get_tools_definitions
        self.chat_with_failover = chat_with_failover
        self.parse_tool_calls_from_text = parse_tool_calls_from_text
        self.summarize_messages = summarize_messages
        self.self_correction_prompt = self_correction_prompt
        self.loop_break_reply = loop_break_reply
        self.max_total_tool_calls = max_total_tool_calls

    async def run(
        self,
        *,
        messages: list[dict[str, Any]],
        trace_id: str | None,
        parse_calls_from_text: bool,
        include_severity: bool,
        parallel_tool_exec: bool,
        compact_after_tools: bool,
    ) -> str | None:
        iteration = 0
        final_content = None
        seen_tool_call_ids: set[str] = set()
        seen_tool_call_hashes: set[str] = set()
        last_tool_signature: str | None = None
        repeat_count: int = 0
        total_tool_calls: int = 0
        tool_call_counts: dict[str, int] = {}
        max_total_tool_calls = self.max_total_tool_calls
        per_tool_limits: dict[str, int] = {}

        while iteration < self.max_iterations:
            iteration += 1
            if trace_id:
                logger.debug(f"[TraceID: {trace_id}] Starting iteration {iteration}")

            response = await self.chat_with_failover(
                messages=messages,
                tools=self.get_tools_definitions(),
            )

            tool_calls = response.tool_calls
            if not tool_calls and parse_calls_from_text and response.content:
                tool_calls = self.parse_tool_calls_from_text(response.content)

            if not tool_calls:
                final_content = response.content
                break

            clarification = self._clarification_needed(messages=messages, tool_calls=tool_calls)
            if clarification:
                final_content = clarification
                break

            budget_reason = self._tool_budget_reason(
                tool_calls=tool_calls,
                total_tool_calls=total_tool_calls,
                tool_call_counts=tool_call_counts,
                max_total_tool_calls=max_total_tool_calls,
                per_tool_limits=per_tool_limits,
            )
            if budget_reason:
                final_content = await self._finalize_after_budget(messages=messages, reason=budget_reason)
                break

            is_strict_loop, current_ids, current_hashes, last_tool_signature, repeat_count = self._evaluate_loop_repetition(
                iteration=iteration,
                tool_calls=tool_calls,
                seen_tool_call_ids=seen_tool_call_ids,
                seen_tool_call_hashes=seen_tool_call_hashes,
                last_tool_signature=last_tool_signature,
                repeat_count=repeat_count,
            )
            if is_strict_loop:
                if iteration < self.max_iterations - 1:
                    if trace_id:
                        logger.warning(f"[TraceID: {trace_id}] Loop detected! Injecting self-correction prompt.")
                    else:
                        logger.warning("System loop detected. Injecting self-correction prompt.")
                    self._inject_self_correction(messages)
                    seen_tool_call_hashes.clear()
                    seen_tool_call_ids.clear()
                    continue
                if trace_id:
                    logger.error(f"[TraceID: {trace_id}] Permanent loop detected after retry. Breaking turn.")
                else:
                    logger.error("Permanent system loop detected after retry. Breaking turn.")
                final_content = response.content or self.loop_break_reply
                break

            for tid in current_ids:
                if tid:
                    seen_tool_call_ids.add(tid)
            for h in current_hashes:
                seen_tool_call_hashes.add(h)

            tool_call_dicts = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in tool_calls
            ]
            self.context.add_assistant_message(messages, response.content, tool_call_dicts)
            await self._execute_tool_calls(
                messages=messages,
                tool_calls=tool_calls,
                trace_id=trace_id,
                include_severity=include_severity,
                parallel_tool_exec=parallel_tool_exec,
            )
            total_tool_calls += len(tool_calls)
            for tc in tool_calls:
                tool_call_counts[tc.name] = tool_call_counts.get(tc.name, 0) + 1
            if compact_after_tools:
                await self._compact_messages_if_needed(messages, trace_id)

        if self._is_empty_like_response(final_content):
            final_content = await self._finalize_after_budget(
                messages=messages,
                reason="模型未返回有效文本，触发最终总结",
            )
        return final_content

    def _is_empty_like_response(self, content: str | None) -> bool:
        if content is None:
            return True
        text = content.strip()
        return text in {"", "[正在处理中...]", "正在处理中..."}

    def _inject_self_correction(self, messages: list[dict[str, Any]]) -> None:
        messages.append({"role": "system", "content": self.self_correction_prompt})

    def _evaluate_loop_repetition(
        self,
        iteration: int,
        tool_calls: list[ToolCallRequest],
        seen_tool_call_ids: set[str],
        seen_tool_call_hashes: set[str],
        last_tool_signature: str | None,
        repeat_count: int,
    ) -> tuple[bool, list[str], list[str], str | None, int]:
        current_ids = [tc.id for tc in tool_calls if tc.id]
        current_hashes = []
        for tc in tool_calls:
            args_json = json.dumps(tc.arguments, sort_keys=True)
            tc_hash = hashlib.sha256(f"{tc.name}:{args_json}".encode()).hexdigest()
            current_hashes.append(tc_hash)

        id_loop = bool(current_ids) and len([tid for tid in current_ids if tid in seen_tool_call_ids]) == len(current_ids)
        hash_loop = len([h for h in current_hashes if h in seen_tool_call_hashes]) == len(current_hashes)

        current_signature = ",".join(sorted(current_hashes))
        if current_signature == last_tool_signature:
            repeat_count += 1
        else:
            repeat_count = 1
            last_tool_signature = current_signature

        is_strict_loop = iteration > 3 and repeat_count >= 3 and (id_loop or hash_loop)
        return is_strict_loop, current_ids, current_hashes, last_tool_signature, repeat_count

    def _tool_budget_reason(
        self,
        *,
        tool_calls: list[ToolCallRequest],
        total_tool_calls: int,
        tool_call_counts: dict[str, int],
        max_total_tool_calls: int,
        per_tool_limits: dict[str, int],
    ) -> str | None:
        projected_total = total_tool_calls + len(tool_calls)
        if projected_total > max_total_tool_calls:
            return f"总工具调用预算超限（{projected_total}/{max_total_tool_calls}）"

        projected_counts = dict(tool_call_counts)
        for tc in tool_calls:
            projected_counts[tc.name] = projected_counts.get(tc.name, 0) + 1

        for tool_name, limit in per_tool_limits.items():
            count = projected_counts.get(tool_name, 0)
            if count > limit:
                return f"工具 {tool_name} 调用预算超限（{count}/{limit}）"

        return None

    def _build_forced_summary(self, *, messages: list[dict[str, Any]], reason: str) -> str:
        tool_msgs = [m for m in messages if m.get("role") == "tool"]
        tool_name_list = [str(m.get("name", "unknown")) for m in tool_msgs]
        tool_stats: dict[str, int] = {}
        for name in tool_name_list:
            tool_stats[name] = tool_stats.get(name, 0) + 1

        lines = [f"模型已超过工具调用限制，本轮已停止继续试探：{reason}。"]
        if tool_stats:
            stats_text = "，".join(f"{name}×{count}" for name, count in sorted(tool_stats.items()))
            lines.append(f"本轮工具调用统计：{stats_text}")
        else:
            lines.append("本轮未形成有效工具结果。")

        recent_tools = tool_name_list[-6:]
        if recent_tools:
            lines.append(f"最近步骤：{' -> '.join(recent_tools)}")

        return "\n".join(lines)

    async def _finalize_after_budget(self, *, messages: list[dict[str, Any]], reason: str) -> str:
        fallback = self._build_forced_summary(messages=messages, reason=reason)
        try:
            summary_prompt = (
                "你已经触发工具调用预算限制，禁止再调用任何工具。"
                f"限制原因：{reason}。"
                "请基于现有工具结果，直接输出给用户的最终总结："
                "1) 已完成内容 2) 当前明确结论 3) 未完成或不确定项。"
                "要求：简洁、可执行，不要输出内部推理。"
            )
            summary_messages = list(messages) + [{"role": "system", "content": summary_prompt}]
            response = await asyncio.wait_for(
                self.chat_with_failover(messages=summary_messages, tools=[]),
                timeout=12.0,
            )
            content = (response.content or "").strip()
            if content:
                return content
        except Exception:
            pass
        return fallback

    def _clarification_needed(
        self,
        *,
        messages: list[dict[str, Any]],
        tool_calls: list[ToolCallRequest],
    ) -> str | None:
        """
        Generic guard for context-sensitive parameters:
        if model injects values not clearly mentioned by user, ask for confirmation first.
        """
        user_text = self._latest_user_text(messages)
        if not user_text:
            return None
        if self._user_allows_inference(user_text):
            return None
        if not self._is_context_sensitive_request(user_text):
            return None

        # Keep this guard focused on high-risk context fields.
        # Operational fields (chat_id/account/recipient) are handled by the tool itself.
        sensitive_labels = {
            "location": "地点",
            "city": "城市",
            "region": "地区",
            "province": "省份",
            "country": "国家",
            "timezone": "时区",
        }

        for tc in tool_calls:
            args = tc.arguments or {}
            for key, label in sensitive_labels.items():
                value = args.get(key)
                if not isinstance(value, str):
                    continue
                candidate = value.strip()
                if not candidate:
                    continue
                if not self._value_mentioned(user_text, candidate):
                    return f"在继续之前需要你确认：本次{label}是“{candidate}”吗？如果不是，请告诉我正确的{label}。"
        return None

    def _latest_user_text(self, messages: list[dict[str, Any]]) -> str:
        for m in reversed(messages):
            if m.get("role") == "user":
                content = m.get("content")
                if isinstance(content, str):
                    return content
        return ""

    def _user_allows_inference(self, user_text: str) -> bool:
        hints = ("默认", "按上次", "沿用", "你决定", "随便", "任意")
        return any(h in user_text for h in hints)

    def _is_context_sensitive_request(self, user_text: str) -> bool:
        keywords = (
            "天气",
            "温度",
            "降雨",
            "空气质量",
            "穿衣",
            "出行",
            "路线",
            "导航",
            "附近",
            "餐厅",
            "酒店",
            "机票",
            "火车",
        )
        return any(k in user_text for k in keywords)

    def _value_mentioned(self, user_text: str, candidate: str) -> bool:
        if candidate in user_text:
            return True
        # Token overlap fallback: tolerant match for mixed Chinese/English values.
        user_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_+-]{2,}", user_text.lower()))
        cand_tokens = set(re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_+-]{2,}", candidate.lower()))
        if not cand_tokens:
            return False
        return len(user_tokens.intersection(cand_tokens)) > 0

    def _format_tool_result_output(self, result: Any, include_severity: bool) -> str:
        if not isinstance(result, ToolResult):
            return str(result)

        output = result.output
        if result.remedy:
            output = f"{output}\n\n[系统及工具建议: {result.remedy}]"
        if include_severity and result.severity in (ToolSeverity.WARN, ToolSeverity.ERROR, ToolSeverity.FATAL):
            output = f"[severity:{result.severity}]\n{output}"
        if result.should_retry:
            output = f"{output}\n\n[系统提示: 建议重试该工具调用，或调整参数后重试。]"
        if result.requires_user_confirmation:
            output = f"{output}\n\n[系统提示: 该操作需要用户确认后再执行。]"
        return output

    async def _execute_tool_calls(
        self,
        messages: list[dict[str, Any]],
        tool_calls: list[ToolCallRequest],
        trace_id: str | None,
        include_severity: bool,
        parallel_tool_exec: bool,
    ) -> None:
        if parallel_tool_exec:
            tool_coros = []
            tool_starts: dict[str, float] = {}
            for tool_call in tool_calls:
                args_str = json.dumps(tool_call.arguments)
                if trace_id:
                    logger.debug(f"[TraceID: {trace_id}] Executing tool: {tool_call.name} with arguments: {args_str}")
                tool_starts[tool_call.id] = time.perf_counter()
                log_event({
                    "type": "tool_start",
                    "trace_id": trace_id,
                    "tool": tool_call.name,
                    "tool_call_id": tool_call.id,
                    "args_keys": list(tool_call.arguments.keys()),
                })
                tool_coros.append(self.executor.execute(tool_call.name, tool_call.arguments))
            results = await asyncio.gather(*tool_coros, return_exceptions=True)
            for tool_call, result in zip(tool_calls, results):
                if isinstance(result, Exception):
                    result_str = f"Error executing tool {tool_call.name}: {str(result)}"
                elif isinstance(result, ToolResult):
                    result_str = self._format_tool_result_output(result, include_severity=include_severity)
                else:
                    result_str = str(result)
                duration_s = None
                if tool_call.id in tool_starts:
                    duration_s = round(float(time.perf_counter() - tool_starts[tool_call.id]), 4)
                log_event({
                    "type": "tool_end",
                    "trace_id": trace_id,
                    "tool": tool_call.name,
                    "tool_call_id": tool_call.id,
                    "status": "error" if isinstance(result, Exception) else "ok",
                    "duration_s": duration_s,
                    "result_len": len(result_str),
                })
                self.context.add_tool_result(messages, tool_call.id, tool_call.name, result_str)
            return

        for tool_call in tool_calls:
            args_str = json.dumps(tool_call.arguments)
            logger.debug(f"Executing tool: {tool_call.name} with arguments: {args_str}")
            result = await self.executor.execute(tool_call.name, tool_call.arguments)
            if isinstance(result, ToolResult):
                result_str = self._format_tool_result_output(result, include_severity=include_severity)
            else:
                result_str = str(result)
            self.context.add_tool_result(messages, tool_call.id, tool_call.name, result_str)

    async def _compact_messages_if_needed(self, messages: list[dict[str, Any]], trace_id: str | None) -> None:
        guard = ContextGuard(model=self.model)
        evaluation = guard.evaluate(messages)
        if not evaluation["should_compact"]:
            return

        if trace_id:
            logger.info(f"[TraceID: {trace_id}] Context utilization high ({evaluation['utilization']:.2f}). Triggering compaction...")
        keep_recent = 10
        to_sum = [m for m in messages if m.get("role") != "system"]
        if len(to_sum) <= keep_recent:
            return
        prefix_msgs = [m for m in messages if m.get("role") == "system"]
        sum_msgs = messages[len(prefix_msgs):-keep_recent]
        recent_msgs = messages[-keep_recent:]
        summary = await self.summarize_messages(sum_msgs)
        if not summary:
            return
        new_prefix = []
        for m in prefix_msgs:
            content = m.get("content", "")
            if isinstance(content, str) and "Previous conversation summary:" in content:
                continue
            new_prefix.append(m)
        messages[:] = new_prefix + [{"role": "system", "content": f"Previous conversation summary: {summary}"}] + recent_msgs
        if trace_id:
            logger.info(f"[TraceID: {trace_id}] Context compacted via LLM summary (and deduped).")
