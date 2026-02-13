"""File system tools: read, write, edit."""

from pathlib import Path
from typing import Any

from nanobot.agent.file_write_policy import FileWritePolicy
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import safe_resolve_path


class ReadFileTool(Tool):
    """Tool to read file contents."""

    def __init__(self, allowed_dir: Path | None = None, write_policy: FileWritePolicy | None = None):
        self._allowed_dir = allowed_dir
        self._write_policy = write_policy

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file at the given path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "The file path to read"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> ToolResult:
        try:
            file_path = safe_resolve_path(path, self._allowed_dir)
            if not file_path.exists():
                return ToolResult(success=False, output=f"Error: File not found: {path}")
            if not file_path.is_file():
                return ToolResult(success=False, output=f"Error: Not a file: {path}")

            content = file_path.read_text(encoding="utf-8")
            return ToolResult(success=True, output=content)
        except PermissionError as e:
            return ToolResult(success=False, output=f"Error: {e}")
        except Exception as e:
            return ToolResult(success=False, output=f"Error reading file: {str(e)}")


class WriteFileTool(Tool):
    """Tool to write content to a file."""

    def __init__(self, allowed_dir: Path | None = None, write_policy: FileWritePolicy | None = None):
        self._allowed_dir = allowed_dir
        self._write_policy = write_policy

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file at the given path. Creates parent directories if needed."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The file path to write to"},
                "content": {"type": "string", "description": "The content to write"},
                "confirm": {"type": "boolean", "description": "受控文件修改确认标记"},
                "change_note": {"type": "string", "description": "受控文件修改原因摘要"},
            },
            "required": ["path", "content"],
        }

    async def execute(self, path: str, content: str, **kwargs: Any) -> ToolResult:
        try:
            file_path = safe_resolve_path(path, self._allowed_dir)
            if self._write_policy:
                ok, reason = self._write_policy.check_write(
                    file_path,
                    confirm=bool(kwargs.get("confirm", False)),
                    change_note=str(kwargs.get("change_note", "") or ""),
                )
                if not ok:
                    return ToolResult(
                        success=False,
                        output=f"Blocked: {reason}",
                        remedy="请修改目标文件路径，或在受控文件编辑时显式提供 confirm=true 与 change_note。",
                    )
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return ToolResult(success=True, output=f"Successfully wrote {len(content)} bytes to {path}")
        except PermissionError as e:
            return ToolResult(success=False, output=f"Error: {e}")
        except Exception as e:
            return ToolResult(success=False, output=f"Error writing file: {str(e)}")


class EditFileTool(Tool):
    """Tool to edit a file by replacing text."""

    def __init__(self, allowed_dir: Path | None = None, write_policy: FileWritePolicy | None = None):
        self._allowed_dir = allowed_dir
        self._write_policy = write_policy

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return "Edit a file by replacing old_text with new_text. The old_text must exist exactly in the file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The file path to edit"},
                "old_text": {"type": "string", "description": "The exact text to find and replace"},
                "new_text": {"type": "string", "description": "The text to replace with"},
                "confirm": {"type": "boolean", "description": "受控文件修改确认标记"},
                "change_note": {"type": "string", "description": "受控文件修改原因摘要"},
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(self, path: str, old_text: str, new_text: str, **kwargs: Any) -> ToolResult:
        try:
            file_path = safe_resolve_path(path, self._allowed_dir)
            if self._write_policy:
                ok, reason = self._write_policy.check_write(
                    file_path,
                    confirm=bool(kwargs.get("confirm", False)),
                    change_note=str(kwargs.get("change_note", "") or ""),
                )
                if not ok:
                    return ToolResult(
                        success=False,
                        output=f"Blocked: {reason}",
                        remedy="请修改目标文件路径，或在受控文件编辑时显式提供 confirm=true 与 change_note。",
                    )
            if not file_path.exists():
                return ToolResult(success=False, output=f"Error: File not found: {path}")

            content = file_path.read_text(encoding="utf-8")

            if old_text not in content:
                return ToolResult(success=False, output="Error: old_text not found in file. Make sure it matches exactly.")

            # Count occurrences
            count = content.count(old_text)
            if count > 1:
                return ToolResult(success=False, output=f"Warning: old_text appears {count} times. Please provide more context to make it unique.")

            new_content = content.replace(old_text, new_text, 1)
            file_path.write_text(new_content, encoding="utf-8")

            return ToolResult(success=True, output=f"Successfully edited {path}")
        except PermissionError as e:
            return ToolResult(success=False, output=f"Error: {e}")
        except Exception as e:
            return ToolResult(success=False, output=f"Error editing file: {str(e)}")


class ListDirTool(Tool):
    """Tool to list directory contents."""

    def __init__(self, allowed_dir: Path | None = None):
        self._allowed_dir = allowed_dir

    @property
    def name(self) -> str:
        return "list_dir"

    @property
    def description(self) -> str:
        return "List the contents of a directory."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "The directory path to list"}},
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> ToolResult:
        try:
            dir_path = safe_resolve_path(path, self._allowed_dir)
            if not dir_path.exists():
                return ToolResult(success=False, output=f"Error: Directory not found: {path}")
            if not dir_path.is_dir():
                return ToolResult(success=False, output=f"Error: Not a directory: {path}")

            items = []
            for item in sorted(dir_path.iterdir()):
                prefix = "📁 " if item.is_dir() else "📄 "
                items.append(f"{prefix}{item.name}")

            if not items:
                return ToolResult(success=True, output=f"Directory {path} is empty")

            return ToolResult(success=True, output="\n".join(items))
        except PermissionError as e:
            return ToolResult(success=False, output=f"Error: {e}")
        except Exception as e:
            return ToolResult(success=False, output=f"Error listing directory: {str(e)}")
