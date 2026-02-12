import json
import sys

import pytest

from nanobot.agent.tools.mcp import MCPTool

_FAKE_SERVER = r"""
import json
import sys

for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    try:
        msg = json.loads(line)
    except Exception:
        continue
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize" and msg_id is not None:
        out = {"jsonrpc": "2.0", "id": msg_id, "result": {"capabilities": {"tools": {}}}}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        continue
    if method == "tools/list" and msg_id is not None:
        out = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": [{"name": "echo", "description": "Echo input text"}]},
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        continue
    if method == "tools/call" and msg_id is not None:
        params = msg.get("params", {})
        args = params.get("arguments", {})
        text = str(args.get("text", ""))
        out = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"content": [{"type": "text", "text": f"echo:{text}"}], "isError": False},
        }
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        continue
"""


@pytest.mark.asyncio
async def test_mcp_tool_list_and_call(tmp_path, monkeypatch):
    home = tmp_path / ".home"
    cfg_dir = home / "tool_configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    server_script = tmp_path / "fake_mcp_server.py"
    server_script.write_text(_FAKE_SERVER, encoding="utf-8")

    config = {
        "servers": {
            "fake": {
                "command": sys.executable,
                "args": [str(server_script)],
                "enabled": True,
                "allowed_tools": ["echo"],
            }
        }
    }
    (cfg_dir / "mcp_config.json").write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("NANOBOT_HOME", str(home))

    tool = MCPTool()

    out1 = await tool.execute(action="list_servers")
    assert out1.success is True
    assert "fake" in out1.output

    out2 = await tool.execute(action="list_tools", server="fake")
    assert out2.success is True
    assert "echo" in out2.output

    out3 = await tool.execute(action="call_tool", server="fake", tool="echo", arguments={"text": "hello"})
    assert out3.success is True
    assert "echo:hello" in out3.output
