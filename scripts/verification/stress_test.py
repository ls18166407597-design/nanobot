import asyncio
import os
import sys
from pathlib import Path
from loguru import logger

# Add project root to sys.path
sys.path.append(os.getcwd())

from nanobot.agent.loop import AgentLoop
from nanobot.agent.subagent import SubagentManager
from nanobot.providers.factory import ProviderFactory
from nanobot.bus.queue import MessageBus
from nanobot.bus.events import InboundMessage
from nanobot.config.loader import load_config
from nanobot.agent.models import ModelRegistry

async def run_stress_test():
    # Setup environment
    os.environ["NANOBOT_HOME"] = os.path.join(os.getcwd(), ".home")
    config = load_config()
    
    bus = MessageBus()
    
    # Initialize Provider
    model_registry = ModelRegistry()
    default_model = config.agents.defaults.model or "Qwen/Qwen2.5-7B-Instruct"
    api_key = config.get_api_key(default_model)
    api_base = config.get_api_base(default_model)
    
    provider = ProviderFactory.get_provider(
        model=default_model,
        api_key=api_key,
        api_base=api_base
    )
    
    workspace = Path(".").resolve()
    
    # Initialize SubagentManager
    manager = SubagentManager(
        provider=provider,
        workspace=workspace,
        bus=bus,
        model_registry=model_registry,
        web_proxy=config.tools.web.proxy if config.tools.web else None
    )
    
    # Initialize AgentLoop
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=workspace,
        model=default_model,
        web_proxy=config.tools.web.proxy if config.tools.web else None
    )
    
    # Get the subagent manager from the loop
    manager = loop.subagents
    
    # Start the loop in the background
    asyncio.create_task(loop.run())
    
    # Send the coordination task
    task_content = """请严格执行以下多智能体协作任务，每个子任务必须通过调用 spawn 工具来启动独立的子智能体（Sub-agent）：
1. 市场情报组：调研 iPhone 17 的最新传闻；
2. 系统审计组：运行 nanobot/skills/system-health-check/scripts/regression_suite.py 脚本逻辑（可以直接调用 exec 工具运行 python3）；
3. GitHub 动态组：拉取 nanobot 项目的最近 5 条 github 提交记录。
请确保你在回复中包含 3 个具体的 spawn 工具调用。在所有子任务完成后，请整合它们的结果，为我输出一份结构清晰、包含专业洞察的综合报告。"""

    msg = InboundMessage(
        channel="cli",
        sender_id="user",
        chat_id="stress_test",
        content=task_content
    )
    
    print("🚀 Triggering Stress Test Coordination...")
    await bus.publish_inbound(msg)
    
    # Wait for the coordination to finish
    # We basically wait until the loop has processed the synthesis
    # For simplicity, we'll wait for a certain time or until no more subagents are running
    
    timeout = 300  # 5 minutes
    start_time = asyncio.get_event_loop().time()
    
    while asyncio.get_event_loop().time() - start_time < timeout:
        await asyncio.sleep(5)
        running_count = manager.get_running_count()
        # Find if the "synthesis" has happened
        # We can check the session log or just wait for subagents to drop to 0
        if running_count == 0 and asyncio.get_event_loop().time() - start_time > 30:
            # Check if synthesis is done (Wait a bit more for LLM to synthesize)
            print("✅ All subagents finished. Waiting for final synthesis...")
            await asyncio.sleep(30)
            break
        print(f"⏳ Waiting... {running_count} subagents still active.")

    print("🏁 Stress Test Finished.")
    await loop.stop()

if __name__ == "__main__":
    asyncio.run(run_stress_test())
