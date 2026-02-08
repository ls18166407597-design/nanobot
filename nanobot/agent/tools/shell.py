"""Shell execution tool."""

import asyncio
import os
import re
from pathlib import Path
from typing import Any, TYPE_CHECKING
if TYPE_CHECKING:
    from nanobot.providers.base import LLMProvider
    from nanobot.config.schema import BrainConfig

from nanobot.agent.tools.base import Tool
from nanobot.utils.helpers import safe_resolve_path


class ExecTool(Tool):
    """Tool to execute shell commands."""

    def __init__(
        self,
        timeout: int = 60,
        working_dir: str | None = None,
        deny_patterns: list[str] | None = None,
        allow_patterns: list[str] | None = None,
        restrict_to_workspace: bool = False,
        provider: "LLMProvider | None" = None,
        brain_config: "BrainConfig | None" = None,
    ):
        self.timeout = timeout
        self.working_dir = working_dir
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
            },
            "required": ["command"],
        }

    async def execute(self, command: str, working_dir: str | None = None, **kwargs: Any) -> str:
        cwd = working_dir or self.working_dir or os.getcwd()
        
        # Static guard first
        guard_error = self._static_guard(command, cwd)
        if guard_error:
            return guard_error

        # LLM guard second (if enabled)
        llm_warning: str | None = None
        if self.provider and self.brain_config and self.brain_config.safety_guard:
            llm_error = await self._llm_guard(command)
            if llm_error:
                if llm_error.startswith("WARN:"):
                    llm_warning = llm_error
                else:
                    return llm_error

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout)
            except asyncio.TimeoutError:
                process.kill()
                return f"Error: Command timed out after {self.timeout} seconds"

            output_parts = []

            if stdout:
                output_parts.append(stdout.decode("utf-8", errors="replace"))

            if stderr:
                stderr_text = stderr.decode("utf-8", errors="replace")
                if stderr_text.strip():
                    output_parts.append(f"STDERR:\n{stderr_text}")

            if process.returncode != 0:
                output_parts.append(f"\nExit code: {process.returncode}")

            result = "\n".join(output_parts) if output_parts else "(no output)"
            if llm_warning:
                result = f"{llm_warning}\n{result}"
            
            # Add safety status if guard is disabled
            if self.brain_config and not self.brain_config.safety_guard:
                result = f"[Safety Guard: Disabled]\n{result}"

            # Truncate very long output
            max_len = 10000
            if len(result) > max_len:
                result = result[:max_len] + f"\n... (truncated, {len(result) - max_len} more chars)"

            return result

        except Exception as e:
            return f"Error executing command: {str(e)}"

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
            if "..\\" in cmd or "../" in cmd:
                return "Error: Command blocked by safety guard (path traversal detected)"

            try:
                # Try to find potential paths in the command and validate them
                # This is a heuristic, but we check the CWD at least
                safe_resolve_path(cwd, Path(self.working_dir) if self.working_dir else Path.cwd())
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
