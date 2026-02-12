import json
import sys

import pytest

from nanobot.agent.tools.github import GitHubTool

_FAKE_GITHUB_MCP_SERVER = r"""
import json
import os
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
        sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": {"capabilities": {"tools": {}}}}) + "\n")
        sys.stdout.flush()
        continue
    if method == "tools/list" and msg_id is not None:
        out = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": [{"name": "list_issues", "description": "List repo issues"}]},
        }
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()
        continue
    if method == "tools/call" and msg_id is not None:
        token = os.environ.get("GITHUB_TOKEN", "")
        params = msg.get("params", {})
        name = params.get("name")
        out = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"content": [{"type": "text", "text": f"tool={name};token={bool(token)}"}], "isError": False},
        }
        sys.stdout.write(json.dumps(out) + "\n")
        sys.stdout.flush()
        continue
"""


@pytest.mark.asyncio
async def test_github_tool_uses_mcp_server(tmp_path, monkeypatch):
    home = tmp_path / ".home"
    cfg_dir = home / "tool_configs"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    server_script = tmp_path / "fake_github_mcp_server.py"
    server_script.write_text(_FAKE_GITHUB_MCP_SERVER, encoding="utf-8")

    mcp_cfg = {
        "servers": {
            "github": {
                "command": sys.executable,
                "args": [str(server_script)],
                "enabled": True,
            }
        }
    }
    (cfg_dir / "mcp_config.json").write_text(json.dumps(mcp_cfg), encoding="utf-8")
    monkeypatch.setenv("NANOBOT_HOME", str(home))

    tool = GitHubTool()
    setup = await tool.execute(action="setup", setup_token="ghp_xxx")
    assert setup.success is True

    list_out = await tool.execute(action="list_tools")
    assert list_out.success is True
    assert "list_issues" in list_out.output

    call_out = await tool.execute(action="call_tool", mcp_tool="list_issues", arguments={"repo": "a/b"})
    assert call_out.success is True
    assert "tool=list_issues" in call_out.output
    assert "token=True" in call_out.output
