import pytest

from nanobot.agent.executor import ToolExecutor
from nanobot.agent.tools.base import ToolResult
from nanobot.agent.turn_engine import TurnEngine
from nanobot.hooks import HookRegistry
from nanobot.providers.base import LLMResponse


class _FakeContext:
    def add_assistant_message(self, messages, content, tool_calls):
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
        return messages

    def add_tool_result(self, messages, tool_call_id, tool_name, result):
        messages.append({"role": "tool", "tool_call_id": tool_call_id, "name": tool_name, "content": result})
        return messages


class _FakeToolRegistry:
    def get(self, name: str):
        return None

    async def execute(self, name: str, params: dict):
        return ToolResult(success=True, output="ok")


@pytest.mark.asyncio
async def test_hook_registry_isolation_and_async_callbacks():
    hooks = HookRegistry()
    events = []

    def _broken(payload):
        raise RuntimeError("boom")

    async def _ok_async(payload):
        events.append(payload["id"])

    hooks.register_hook("evt", _broken)
    hooks.register_hook("evt", _ok_async)
    await hooks.trigger_hook("evt", {"id": 1})

    assert events == [1]


@pytest.mark.asyncio
async def test_tool_executor_emits_hooks():
    hooks = HookRegistry()
    seen = []

    async def _capture(payload):
        seen.append((payload.get("tool"), payload.get("success")))

    hooks.register_hook("tool_before", _capture)
    hooks.register_hook("tool_after", _capture)

    executor = ToolExecutor(_FakeToolRegistry(), hook_registry=hooks)
    out = await executor.execute("echo", {"q": "hi"})

    assert out.success is True
    assert seen[0] == ("echo", None)
    assert seen[1] == ("echo", True)


@pytest.mark.asyncio
async def test_turn_engine_emits_turn_hooks():
    hooks = HookRegistry()
    seen = []

    async def _on_iter_start(payload):
        seen.append(("start", payload["iteration"]))

    async def _on_iter_end(payload):
        seen.append(("end", payload["status"]))

    async def _on_turn_end(payload):
        seen.append(("turn_end", payload["has_content"]))

    hooks.register_hook("turn_iteration_start", _on_iter_start)
    hooks.register_hook("turn_iteration_end", _on_iter_end)
    hooks.register_hook("turn_end", _on_turn_end)

    async def _chat_with_failover(messages, tools):
        return LLMResponse(content="done")

    async def _summarize(messages):
        return "summary"

    engine = TurnEngine(
        context=_FakeContext(),
        executor=None,
        model="test-model",
        max_iterations=3,
        get_tools_definitions=lambda: [],
        chat_with_failover=_chat_with_failover,
        parse_tool_calls_from_text=lambda text: [],
        summarize_messages=_summarize,
        self_correction_prompt="self-correct",
        loop_break_reply="loop-broken",
        hook_registry=hooks,
    )

    out = await engine.run(
        messages=[{"role": "system", "content": "s"}, {"role": "user", "content": "hi"}],
        trace_id="t-hook",
        parse_calls_from_text=False,
        include_severity=False,
        parallel_tool_exec=False,
        compact_after_tools=False,
    )

    assert out == "done"
    assert ("start", 1) in seen
    assert ("end", "final_text") in seen
    assert ("turn_end", True) in seen
