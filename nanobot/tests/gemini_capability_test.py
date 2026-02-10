import sys
import os
import json
import asyncio
import logging

import pytest

# Ensure we can import nanobot modules
sys.path.append(os.getcwd())

from nanobot.providers.openai_provider import OpenAIProvider

# Setup logging manually for test clarity
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_BASE = os.environ.get("GEMINI_API_BASE", "http://127.0.0.1:8045/v1")
API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("LOCAL_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3-flash")


@pytest.fixture
def provider():
    if not API_KEY:
        pytest.skip("GEMINI_API_KEY/LOCAL_API_KEY not set for capability tests.")
    return OpenAIProvider(
        api_key=API_KEY,
        api_base=API_BASE,
        default_model=MODEL
    )

@pytest.mark.asyncio
async def test_max_tokens_parameter(provider):
    logger.info("\n--- Testing max_tokens=65536 Parameter ---")
    try:
        # Just a simple prompt to see if the parameter is accepted
        response = await provider.chat(messages=[{"role": "user", "content": "Hi"}], max_tokens=65536)
        logger.info(f"✅ max_tokens=65536 accepted. Response: {response.content}")
    except Exception as e:
        logger.error(f"❌ max_tokens=65536 rejected: {e}")

@pytest.mark.asyncio
async def test_task_tool_schema(provider):
    logger.info("\n--- Diagnosing TaskTool Schema (400 Errors) ---")
    
    # Original problematic schema from nanobot/agent/tools/task.py
    task_tool = [{
        "type": "function",
        "function": {
            "name": "task",
            "description": "管理可重复使用的任务。支持创建、列出、执行和删除任务。",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "list", "run", "delete", "show", "update"],
                        "description": "操作类型",
                    },
                    "name": {
                        "type": "string",
                        "description": "任务名称(别名),如'1号任务'、'签到任务'",
                    },
                    "description": {
                        "type": "string",
                        "description": "任务描述(用于create/update)",
                    },
                    "command": {
                        "type": "string",
                        "description": "要执行的命令(用于create/update)",
                    },
                    "working_dir": {
                        "type": "string",
                        "description": "执行命令的工作目录(仅用于run)",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "命令超时时间(秒, 仅用于run)",
                    },
                    "confirm": {
                        "type": "boolean",
                        "description": "是否确认执行危险命令(仅用于run)",
                    },
                },
                "required": ["action"],
            }
        }
    }]

    # Variant 1: No enum
    no_enum_tool = json.loads(json.dumps(task_tool))
    del no_enum_tool[0]["function"]["parameters"]["properties"]["action"]["enum"]

    # Variant 2: No required
    no_required_tool = json.loads(json.dumps(task_tool))
    del no_required_tool[0]["function"]["parameters"]["required"]

    # Variant 3: Simplified parameters (only one string)
    simple_tool = [{
        "type": "function",
        "function": {
            "name": "task_simple",
            "description": "Simplified task tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"}
                },
                "required": ["action"]
            }
        }
    }]

    tests = [
        ("Original TaskTool", task_tool),
        ("No Enum", no_enum_tool),
        ("No Required", no_required_tool),
        ("Very Simple", simple_tool)
    ]

    for name, tools in tests:
        logger.info(f"Testing Schema: {name}...")
        try:
            # We don't even need to ask it to call it, just sending the tools is enough to trigger 400 if invalid
            await provider.chat(messages=[{"role": "user", "content": "Hi"}], tools=tools)
            logger.info(f"✅ {name} passed.")
        except Exception as e:
            logger.error(f"❌ {name} failed: {e}")

async def main():
    if not API_KEY:
        raise RuntimeError("GEMINI_API_KEY/LOCAL_API_KEY not set.")
    provider = OpenAIProvider(api_key=API_KEY, api_base=API_BASE, default_model=MODEL)

    await test_max_tokens_parameter(provider)
    await test_task_tool_schema(provider)

if __name__ == "__main__":
    asyncio.run(main())
