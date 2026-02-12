"""Shell execution tool."""

import asyncio
import os
import re
import shutil
from pathlib import Path
from typing import Any, TYPE_CHECKING
if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider
    from nanobot.config.schema import BrainConfig

from nanobot.agent.tools.base import Tool, ToolResult, ToolSeverity
from nanobot.utils.helpers import safe_resolve_path


class ExecTool(Tool):
    """Tool to execute shell commands."""

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        exec_mode: str = "host",
        sandbox_engine: str = "auto",
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        provider: "LLMProvider | None" = None,
        brain_config: "BrainConfig | None" = None,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
        self.exec_mode = (exec_mode or "host").lower()
        self.sandbox_engine = (sandbox_engine or "auto").lower()
        self.deny_patterns = deny_patterns or [
            r"\brm\s+-[rf]{1,2}\b",  # rm -r, rm -rf, rm -fr
            r"\bdel\s+/[fq]\b",  # del /f, del /q
            r"\brmdir\s+/s\b",  # rmdir /s
            r"\b(format|mkfs|diskpart)\b",  # disk operations
            r"\bdd\s+if=",  # dd
            r">\s*/dev/sd",  # write to disk
            r"\b(shutdown|reboot|poweroff)\b",  # system power
            r":\(\)\s*\{.*\};\s*:",  # fork bomb
        ]
        self.allow_patterns = allow_patterns or []
        self.restrict_to_workspace = restrict_to_workspace
        self.provider = provider
        self.brain_config = brain_config
        self._high_risk_patterns = [
            r"\bsudo\b",
            r"\brm\s+-[rf]{1,2}\b",
            r"\bmv\b.+\s+/(etc|usr|var|bin|sbin)\b",
            r"\b(chmod|chown)\b",
            r"\b(killall|pkill)\b",
            r">\s*/(etc|usr|var|bin|sbin)/",
            r"\b(apt|yum|dnf|brew)\s+(install|upgrade|remove)\b",
        ]

    @property
    def name(self) -> str:
        return "exec"

    @property
    def description(self) -> str:
        return "Execute a shell command and return its output. Use with caution."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "working_dir": {
                    "type": "string",
                    "description": "Optional working directory for the command",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Set to true to bypass safety guard warning for potentially dangerous commands.",
                },
            },
            "required": ["command"],
        }

    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> ToolResult:
        cwd = working_dir or self.working_dir or os.getcwd()
        
        # Static guard first
        confirm = bool(kwargs.get("confirm"))
        guard_error = self._static_guard(command, cwd)
        if guard_error and not confirm:
            return ToolResult(
                success=False,
                output=f"{guard_error}. To bypass this safety guard, re-run with 'confirm': true in tool parameters.",
                remedy="如果该命令确实安全，请在参数中增加 'confirm': true。",
                severity=ToolSeverity.ERROR,
                requires_user_confirmation=True
            )

        # LLM guard second (if enabled)
        llm_warning: str | None = None
        if self.provider and self.brain_config and self.brain_config.safety_guard:
            llm_error = await self._llm_guard(command)
            if llm_error:
                if llm_error.startswith("WARN:"):
                    llm_warning = llm_error
                else:
                    return ToolResult(
                        success=False,
                        output=llm_error,
                        remedy="LLM 安全检查未通过。请确保指令不含有害操作，或联系管理员调整安全策略。",
                        severity=ToolSeverity.ERROR
                    )

        try:
            run_mode, sandbox_note = self._resolve_run_mode(command)
            if run_mode == "sandbox":
                code, output = await self._run_sandbox(command, cwd)
            else:
                code, output = await self._run_host(command, cwd)

            if sandbox_note:
                output = f"{sandbox_note}\n{output}"
            if llm_warning:
                output = f"{llm_warning}\n{output}"
            
            # Add safety status if guard is disabled
            if self.brain_config and not self.brain_config.safety_guard:
                output = f"[Safety Guard: Disabled]\n{output}"

            # Truncate very long output
            max_len = 10000
            if len(output) > max_len:
                output = output[:max_len] + f"\n... (truncated, {len(output) - max_len} more chars)"

            return ToolResult(
                success=code == 0,
                output=output,
                remedy="请检查指令语法、路径权限或环境依赖。" if code != 0 else None,
                severity=ToolSeverity.INFO if code == 0 else ToolSeverity.ERROR,
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Error executing command: {str(e)}",
                severity=ToolSeverity.ERROR
            )

    async def _run_host(self, command: str, cwd: str) -> tuple[int, str]:
        env = os.environ.copy()
        import sys

        python_bin = os.path.dirname(sys.executable)
        if python_bin not in env.get("PATH", ""):
            env["PATH"] = f"{python_bin}:{env.get('PATH', '')}"

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        return await self._collect_process_output(process)

    async def _run_sandbox(self, command: str, cwd: str) -> tuple[int, str]:
        engine = self._detect_sandbox_engine()
        if not engine:
            return (
                1,
                "Error: Sandbox engine is unavailable on this host.\n"
                "建议：安装 bubblewrap(bwrap) 或 Docker，或将 tools.exec.mode 临时切换为 host。",
            )

        if engine == "bwrap":
            # Linux bubblewrap sandbox: read-only system, writable mounted workspace.
            argv = [
                "bwrap",
                "--unshare-all",
                "--new-session",
                "--die-with-parent",
                "--ro-bind",
                "/",
                "/",
                "--bind",
                cwd,
                cwd,
                "--chdir",
                cwd,
                "--proc",
                "/proc",
                "--dev",
                "/dev",
                "sh",
                "-lc",
                command,
            ]
        else:
            # Docker sandbox: no network, limited resources, workspace-only mount.
            argv = [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--cpus=1",
                "--memory=512m",
                "--pids-limit=128",
                "-v",
                f"{cwd}:{cwd}",
                "-w",
                cwd,
                "alpine:3.20",
                "sh",
                "-lc",
                command,
            ]

        process = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        code, output = await self._collect_process_output(process)
        return code, f"[Sandbox:{engine}]\n{output}"

    async def _collect_process_output(self, process: asyncio.subprocess.Process) -> tuple[int, str]:
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
        except asyncio.TimeoutError:
            process.kill()
            return (1, f"Error: Command timed out after {self.timeout} seconds")
        except asyncio.CancelledError:
            process.kill()
            raise

        output_parts = []
        if stdout:
            output_parts.append(stdout.decode("utf-8", errors="replace"))
        if stderr:
            stderr_text = stderr.decode("utf-8", errors="replace")
            if stderr_text.strip():
                output_parts.append(f"STDERR:\n{stderr_text}")
        if process.returncode != 0:
            output_parts.append(f"\nExit code: {process.returncode}")

        output = "\n".join(output_parts) if output_parts else "(no output)"
        return process.returncode, output

    def _resolve_run_mode(self, command: str) -> tuple[str, str | None]:
        if self.exec_mode == "sandbox":
            return "sandbox", None
        if self.exec_mode == "host":
            return "host", None

        if self.exec_mode != "hybrid":
            return "host", f"[Note] Unknown exec mode '{self.exec_mode}', fallback to host."

        if self._is_high_risk(command):
            if self._detect_sandbox_engine():
                return "sandbox", "检测到高风险命令，已自动切换到沙箱执行。"
            return "host", "检测到高风险命令，但沙箱不可用，已回退到宿主执行（请谨慎）。"
        return "host", None

    def _is_high_risk(self, command: str) -> bool:
        lower = command.lower()
        return any(re.search(p, lower) for p in self._high_risk_patterns)

    def _detect_sandbox_engine(self) -> str | None:
        if self.sandbox_engine == "bwrap":
            return "bwrap" if shutil.which("bwrap") else None
        if self.sandbox_engine == "docker":
            return "docker" if shutil.which("docker") else None

        if shutil.which("bwrap"):
            return "bwrap"
        if shutil.which("docker"):
            return "docker"
        return None

    def _static_guard(self, command: str, cwd: str) -> str | None:
        """Best-effort safety guard for potentially destructive commands."""
        cmd = command.strip()
        lower = cmd.lower()

        for pattern in self.deny_patterns:
            if re.search(pattern, lower):
                return "Error: Command blocked by safety guard (dangerous pattern detected)"

        if self.allow_patterns:
            if not any(re.search(p, lower) for p in self.allow_patterns):
                return "Error: Command blocked by safety guard (not in allowlist)"

        if self.restrict_to_workspace:
            # 1. Block explicit traversal
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            # 2. Extract potential paths and validate them
            # We look for absolute paths or relative-looking paths in the command
            potential_paths = re.findall(r'(/[^\s;"\']+|[a-zA-Z]:\\[^\s;"\']+)', cmd)
            allowed_root = (Path(self.working_dir) if self.working_dir else Path.cwd()).resolve()

            for p_str in potential_paths:
                try:
                    p = Path(p_str)
                    if p.is_absolute():
                        safe_resolve_path(p_str, allowed_root)
                except (PermissionError, ValueError):
                    return f"Error: Command blocked by safety guard: Restricted access to '{p_str}'"

            # 3. Validate CWD
            try:
                safe_resolve_path(cwd, allowed_root)
            except PermissionError as e:
                return f"Error: Command blocked by safety guard: {e}"

        return None

    async def _llm_guard(self, command: str) -> str | None:
        """Ask LLM if the command is dangerous."""
        prompt = f"""You are a safety guard for a shell execution tool.
Analyze this command: `{command}`

Is this command potentially destructive (e.g., deleting files, networking, changing system settings) or malicious?
Answer ONLY with "SAFE" or "DANGEROUS".
If DANGEROUS, provide a short reason.
"""
        try:
            messages = [{"role": "user", "content": prompt}]
            # Use a fast model if possible, but here we reuse the main provider
            # We don't want tools for this check
            response = await self.provider.chat(messages=messages, tools=[], model=None) 
            content = response.content.strip()
            
            if "DANGEROUS" in content.upper():
                return f"Error: Command blocked by LLM safety guard. Reason: {content}"
            return None
        except Exception as e:
            # Degrade to static guard only; surface warning to user.
            return f"WARN: LLM safety check failed; falling back to static guard. Reason: {e}"
