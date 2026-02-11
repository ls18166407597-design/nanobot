import datetime
import json
import os
from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import ensure_dir, get_tool_config_path, safe_resolve_path


class KnowledgeTool(Tool):
    """Tool for interacting with a local Knowledge Base (Markdown/Obsidian)."""

    name = "knowledge_base"
    description = """
    Interact with a local Markdown-based knowledge base (e.g. Obsidian).
    Capabilities:
    - Search: Find notes containing keywords.
    - Read: Read the content of a note.
    - Daily: Append thoughts to today's daily note.
    - Create: Create new notes.

    Setup:
    Requires '.home/tool_configs/knowledge_config.json' with:
    { "vault_path": "/path/to/vault", "daily_notes_folder": "Daily" }
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "setup",
                    "search",
                    "read",
                    "create",
                    "append_daily",
                    "list_files",
                ],
                "description": "The action to perform.",
            },
            "vault_path": {
                "type": "string",
                "description": "Path to the Obsidian vault (for setup).",
            },
            "daily_notes_folder": {
                "type": "string",
                "description": "Subfolder for daily notes (for setup), e.g. 'Daily'.",
            },
            "query": {"type": "string", "description": "Search query."},
            "filename": {
                "type": "string",
                "description": "Filename (relative to vault root) for read/create.",
            },
            "content": {"type": "string", "description": "Content to store or append."},
            "folder": {
                "type": "string",
                "description": "Folder to create note in (optional).",
            },
        },
        "required": ["action"],
    }

    def _load_config(self):
        config_path = get_tool_config_path("knowledge_config.json")
        if not config_path.exists():
            return None
        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _save_config(self, vault_path, daily_notes_folder):
        config_path = get_tool_config_path("knowledge_config.json", for_write=True)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {"vault_path": vault_path}
        if daily_notes_folder:
            config["daily_notes_folder"] = daily_notes_folder
        with open(config_path, "w") as f:
            json.dump(config, f)

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        if action == "setup":
            vault_path = kwargs.get("vault_path")
            daily_folder = kwargs.get("daily_notes_folder")
            if not vault_path:
                return ToolResult(success=False, output="Error: 'vault_path' is required for setup.", remedy="请提供 vault_path 参数（例如 Obsidian 库的绝对路径）。")
            self._save_config(vault_path, daily_folder)
            return ToolResult(success=True, output="Knowledge base configuration saved successfully.")

        config = self._load_config()
        if not config or "vault_path" not in config:
            return ToolResult(
                success=False, 
                output="Error: Knowledge base not configured.",
                remedy="知识库未配置。请先调用 setup 动作：action='setup', vault_path='/path/to/your/vault'"
            )

        vault_root = config["vault_path"]
        if not os.path.exists(vault_root):
            return ToolResult(
                success=False, 
                output=f"Error: Configured vault path '{vault_root}' does not exist on disk.",
                remedy="配置的路径不存在。请检查路径是否正确，或者重新调用 setup 更新路径。"
            )

        try:
            if action == "search":
                output = self._search_notes(vault_root, kwargs.get("query"))
                return ToolResult(success=True, output=output)
            elif action == "read":
                output = self._read_note(vault_root, kwargs.get("filename"))
                return ToolResult(success=True, output=output)
            elif action == "create":
                output = self._create_note(
                    vault_root,
                    kwargs.get("filename"),
                    kwargs.get("content"),
                    kwargs.get("folder"),
                )
                return ToolResult(success=True, output=output)
            elif action == "append_daily":
                daily_subfolder = config.get("daily_notes_folder", "")
                output = self._append_daily(vault_root, daily_subfolder, kwargs.get("content"))
                return ToolResult(success=True, output=output)
            elif action == "list_files":
                output = self._list_files(vault_root, kwargs.get("folder", ""))
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}", remedy="请检查 action 参数（search, read, create, append_daily, list_files, setup）。")
        except Exception as e:
            return ToolResult(success=False, output=f"Knowledge Tool Error: {str(e)}")

    def _search_notes(self, root, query):
        if not query:
            return "Error: 'query' required for search."
        matches = []
        # Simple recursive search for .md files
        # For large vaults, 'grep' via subprocess might be faster, but python is safer/portable.
        # Limit to 50 matches.
        count = 0
        for dirpath, _, filenames in os.walk(root):
            if ".git" in dirpath:
                continue
            for f in filenames:
                if f.endswith(".md"):
                    path = os.path.join(dirpath, f)
                    try:
                        with open(path, "r", errors="ignore") as note_file:
                            content = note_file.read()
                            if query.lower() in content.lower():
                                rel_path = os.path.relpath(path, root)
                                matches.append(f"- {rel_path}")
                                count += 1
                                if count >= 20:
                                    break
                    except Exception:
                        pass
            if count >= 20:
                break

        if not matches:
            return "No matches found."
        return "Found matches:\n" + "\n".join(matches)

    def _read_note(self, root, filename):
        if not filename:
            return "Error: 'filename' required."
        try:
            path = safe_resolve_path(os.path.join(root, filename), Path(root))
            if not path.exists():
                return f"Error: File '{filename}' not found."
            return path.read_text(encoding="utf-8", errors="ignore")
        except PermissionError as e:
            return str(e)

    def _create_note(self, root, filename, content, folder):
        if not filename or not content:
            return "Error: 'filename' and 'content' required."
        if not filename.endswith(".md"):
            filename += ".md"

        try:
            target_dir = os.path.join(root, folder) if folder else root
            # First validate the folder
            safe_target_dir = safe_resolve_path(target_dir, Path(root))
            
            # Then validate the file itself
            path = safe_resolve_path(os.path.join(str(safe_target_dir), filename), Path(root))

            if path.exists():
                return "Error: File already exists. Use append or different name."

            ensure_dir(path.parent)
            path.write_text(content, encoding="utf-8")
            return f"Created note: {os.path.relpath(path, root)}"
        except PermissionError as e:
            return str(e)

    def _append_daily(self, root, daily_folder, content):
        if not content:
            return "Error: 'content' required."
        today = datetime.date.today().strftime("%Y-%m-%d")
        filename = f"{today}.md"

        target_dir = root
        if daily_folder:
            target_dir = os.path.join(root, daily_folder)

        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, filename)

        # If exists, append. If not, create.
        timestamp = datetime.datetime.now().strftime("%H:%M")
        entry = f"\n\n- [{timestamp}] {content}"

        mode = "a" if os.path.exists(path) else "w"
        with open(path, mode) as f:
            f.write(entry)

        return f"Appended to daily note: {os.path.relpath(path, root)}"

    def _list_files(self, root, folder):
        try:
            target_dir = safe_resolve_path(os.path.join(root, folder) if folder else root, Path(root))
            if not target_dir.exists():
                return "Folder not found."

            files = []
            for f in os.listdir(target_dir):
                if f.startswith("."):
                    continue
                files.append(f)
            return "\n".join(files[:50])
        except PermissionError as e:
            return str(e)
