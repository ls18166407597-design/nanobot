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


def test_exec_tool_hybrid_prefers_sandbox_for_high_risk(monkeypatch):
    tool = ExecTool(exec_mode="hybrid")
    monkeypatch.setattr(tool, "_detect_sandbox_engine", lambda: "docker")
    mode, note = tool._resolve_run_mode("sudo rm -rf /tmp/x")
    assert mode == "sandbox"
    assert note is not None


def test_exec_tool_hybrid_falls_back_to_host_when_no_engine(monkeypatch):
    tool = ExecTool(exec_mode="hybrid")
    monkeypatch.setattr(tool, "_detect_sandbox_engine", lambda: None)
    mode, note = tool._resolve_run_mode("sudo chmod -R 777 /tmp/x")
    assert mode == "host"
    assert note is not None
