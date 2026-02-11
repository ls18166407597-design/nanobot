#!/usr/bin/env python3
"""Lightweight regression smoke suite for core agent flow."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from nanobot.agent.loop import AgentLoop
from nanobot.bus.events import InboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class SequencedProvider(LLMProvider):
    """Deterministic provider used to drive predictable smoke scenarios."""

    def __init__(self, responses):
        super().__init__(api_key="smoke", api_base="http://local-smoke")
        self.responses = list(responses)

    async def chat(self, *args, **kwargs):
        if not self.responses:
            return LLMResponse(content="[no-more-responses]")
        current = self.responses.pop(0)
        if isinstance(current, tuple) and current[0] == "sleep":
            await asyncio.sleep(current[1])
            return LLMResponse(content=current[2])
        return current

    def get_default_model(self) -> str:
        return "smoke-model"


@dataclass
class Scenario:
    name: str
    fn: Callable[[Path], "asyncio.Future[bool]"]


async def scenario_normal_qa(workspace: Path) -> bool:
    bus = MessageBus()
    provider = SequencedProvider([LLMResponse(content="收到测试1")])
    loop = AgentLoop(bus=bus, provider=provider, workspace=workspace)
    out = await loop.process_direct(
        "测试1：你好，请回复“收到测试1”",
        session_key="cli:smoke-qa",
        channel="cli",
        chat_id="direct",
    )
    return "收到测试1" in out


async def scenario_tool_success(workspace: Path) -> bool:
    bus = MessageBus()
    provider = SequencedProvider(
        [
            LLMResponse(
                content=None,
                tool_calls=[ToolCallRequest(id="smk_1", name="list_dir", arguments={"path": "."})],
            ),
            LLMResponse(content="目录读取完成"),
        ]
    )
    loop = AgentLoop(bus=bus, provider=provider, workspace=workspace)
    out = await loop.process_direct(
        "测试2：请列出当前目录",
        session_key="cli:smoke-tool-ok",
        channel="cli",
        chat_id="direct",
    )
    return "完成" in out


async def scenario_tool_failure(workspace: Path) -> bool:
    bus = MessageBus()
    provider = SequencedProvider(
        [
            LLMResponse(
                content=None,
                tool_calls=[
                    ToolCallRequest(
                        id="smk_2",
                        name="read_file",
                        arguments={"path": "no_such_file_abc.txt"},
                    )
                ],
            ),
            LLMResponse(content="已收到失败结果并结束"),
        ]
    )
    loop = AgentLoop(bus=bus, provider=provider, workspace=workspace)
    out = await loop.process_direct(
        "测试3：请读取不存在文件",
        session_key="cli:smoke-tool-fail",
        channel="cli",
        chat_id="direct",
    )
    return "结束" in out


async def scenario_system_origin_route(workspace: Path) -> bool:
    bus = MessageBus()
    provider = SequencedProvider([LLMResponse(content="system done")])
    loop = AgentLoop(bus=bus, provider=provider, workspace=workspace)
    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="direct",
        content="后台任务完成",
        metadata={"origin": {"channel": "telegram", "chat_id": "12345"}},
    )
    out = await loop._inner_process_message(msg)
    return bool(out and out.channel == "telegram" and out.chat_id == "12345")


async def scenario_busy_notice(workspace: Path) -> bool:
    bus = MessageBus()
    provider = SequencedProvider(
        [
            ("sleep", 0.7, "first done"),
            ("sleep", 0.1, "second done"),
        ]
    )
    loop = AgentLoop(bus=bus, provider=provider, workspace=workspace)

    msg1 = InboundMessage(channel="telegram", sender_id="u", chat_id="111", content="smoke-a")
    msg2 = InboundMessage(channel="telegram", sender_id="u", chat_id="111", content="smoke-b")

    t1 = asyncio.create_task(loop._process_message_wrapper(msg1))
    await asyncio.sleep(0.05)
    t2 = asyncio.create_task(loop._process_message_wrapper(msg2))

    outs = []
    for _ in range(3):
        outs.append(await asyncio.wait_for(bus.consume_outbound(), timeout=4))

    await t1
    await t2

    return any("正在全力处理您之前的指令" in o.content for o in outs)


async def run_smoke(workspace: Path) -> tuple[bool, list[dict[str, str]]]:
    scenarios = [
        Scenario(name="normal_qa", fn=scenario_normal_qa),
        Scenario(name="tool_success", fn=scenario_tool_success),
        Scenario(name="tool_failure", fn=scenario_tool_failure),
        Scenario(name="system_origin_route", fn=scenario_system_origin_route),
        Scenario(name="busy_notice", fn=scenario_busy_notice),
    ]
    results = []
    ok_all = True
    for sc in scenarios:
        try:
            ok = await sc.fn(workspace)
        except Exception as exc:
            ok = False
            results.append({"scenario": sc.name, "status": "FAIL", "detail": str(exc)})
            ok_all = False
            continue
        status = "PASS" if ok else "FAIL"
        results.append({"scenario": sc.name, "status": status, "detail": ""})
        if not ok:
            ok_all = False
    return ok_all, results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run nanobot smoke regression suite.")
    parser.add_argument(
        "--workspace",
        default=str(Path(__file__).resolve().parent.parent / "workspace"),
        help="Workspace path used by AgentLoop",
    )
    parser.add_argument(
        "--report",
        default="",
        help="Optional report file path (JSON)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    ok, results = asyncio.run(run_smoke(workspace))
    for row in results:
        line = f"{row['scenario']}: {row['status']}"
        if row["detail"]:
            line += f" ({row['detail']})"
        print(line)

    if args.report:
        report_path = Path(args.report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({"ok": ok, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
