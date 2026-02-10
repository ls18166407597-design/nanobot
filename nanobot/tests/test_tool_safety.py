import pytest

from nanobot.agent.tools.shell import ExecTool


def test_exec_tool_blocks_dangerous_commands():
    tool = ExecTool()
    assert tool._static_guard("rm -rf /", "/") is not None
    assert tool._static_guard("rmdir /s", "C:\\") is not None


def test_exec_tool_allows_safe_commands():
    tool = ExecTool()
    assert tool._static_guard("echo hello", ".") is None


def test_exec_tool_blocks_path_traversal_when_restricted():
    tool = ExecTool(restrict_to_workspace=True, working_dir="/tmp")
    assert tool._static_guard("cat ../secrets.txt", "/tmp") is not None
