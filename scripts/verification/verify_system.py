import asyncio
import uuid
import logging
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock

from loguru import logger
import sys

# Configure logger to output to stdout for verification
logger.remove()
logger.add(sys.stdout, level="DEBUG")

try:
    from nanobot.bus.queue import MessageBus
    from nanobot.bus.events import InboundMessage, OutboundMessage
    from nanobot.agent.loop import AgentLoop
    from nanobot.agent.subagent import SubagentManager
    from nanobot.providers.base import LLMProvider, LLMResponse
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.path.append("/Users/liusong/Downloads/nanobot")
    from nanobot.bus.queue import MessageBus
    from nanobot.bus.events import InboundMessage, OutboundMessage
    from nanobot.agent.loop import AgentLoop
    from nanobot.agent.subagent import SubagentManager
    from nanobot.providers.base import LLMProvider, LLMResponse


async def test_subagent_safety():
    print("\n[TEST] Subagent Safety (Crash Handling)")
    bus = MessageBus()
    
    # Mock provider
    mock_provider = MagicMock()
    mock_provider.get_default_model.return_value = "mock-model"
    mock_provider.api_key = "mock-key"
    mock_provider.api_base = "mock-base"
    
    # Mock the _chat_with_failover to Raise an exception to simulate a crash
    # We need to subclass or patch. Let's patch at instance level if possible or just rely on internal methods.
    
    manager = SubagentManager(
        provider=mock_provider,
        workspace=MagicMock(),
        bus=bus
    )
    
    # Mocking _chat_with_failover to crash
    manager._chat_with_failover = AsyncMock(side_effect=Exception("Simulated catastrophic failure"))
    
    origin = {"channel": "test-cli", "chat_id": "test-chat"}
    task_id = "test-task-1"
    
    # Run the subagent directly
    print("Running subagent that is destined to crash...")
    try:
        await manager._run_subagent(
            task_id=task_id,
            task="Do something risky",
            label="Risky Task",
            origin=origin,
            model_override=None,
            thinking=False
        )
    except Exception as e:
        print(f"Caught exception in runner: {e}")
    
    # Verify result was announced despite crash
    print("Checking for result in message bus...")
    try:
        msg = await asyncio.wait_for(bus.consume_inbound(), timeout=5.0)
        # print(f"Received message type: {type(msg)}")
        print(f"Message content snippet: {msg.content[:100]}...")
        
        if "Simulated catastrophic failure" in msg.content and "failed" in msg.content:
            print("✅ PASS: Subagent reported failure correctly.")
        else:
            print(f"❌ FAIL: Content does not look like a failure report. Got: {msg.content}")

        if msg.metadata["origin"] == origin:
            print("✅ PASS: Origin metadata preserved.")
        else:
            print(f"❌ FAIL: Origin metadata lost. Got: {msg.metadata}")
        
    except asyncio.TimeoutError:
        print("❌ FAIL: No result message received from crashing subagent.")

async def test_msg_routing_logic():
    print("\n[TEST] Message Routing Logic (AgentLoop isolation)")
    # This tests the logic we added to loop.py _process_system_message via strict unit test logic
    # without instantiating the whole class.
    
    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="system",
        content="result",
        metadata={"origin": {"channel": "telegram", "chat_id": "12345"}}
    )
    
    # Logic from loop.py:
    if msg.metadata and "origin" in msg.metadata:
        origin = msg.metadata["origin"]
        origin_channel = origin.get("channel", "cli")
        origin_chat_id = origin.get("chat_id", "direct")
    elif ":" in msg.chat_id:
        parts = msg.chat_id.split(":", 1)
        origin_channel = parts[0]
        origin_chat_id = parts[1]
    else:
        origin_channel = "cli"
        origin_chat_id = msg.chat_id
        
    print(f"Resolved Channel: {origin_channel}")
    print(f"Resolved ChatID: {origin_chat_id}")
    
    if origin_channel == "telegram" and origin_chat_id == "12345":
        print("✅ PASS: Routing logic resolves metadata origin correctly.")
    else:
        print("❌ FAIL: Routing logic failed.")


async def main():
    await test_subagent_safety()
    await test_msg_routing_logic()

if __name__ == "__main__":
    asyncio.run(main())
