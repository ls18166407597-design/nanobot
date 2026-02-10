from pathlib import Path
from typing import Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import safe_resolve_path


class MemoryTool(Tool):
    """Tool for active memory management (long-term facts and daily notes)."""

    name = "memory"
    description = """
    Manage Nanobot's memory. Use this to remember facts, user preferences,
    important decisions, or to search past notes.

    Actions:
    - append_daily: Add a dated note to the persistent daily log.
    - update_long_term: Update the core MEMORY.md with durable facts.
    - search: Keyword search through all memory files.
    - read: Read specific memory files.
    """

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["append_daily", "update_long_term", "search", "read"],
                "description": "Memory action to perform.",
            },
            "content": {"type": "string", "description": "Content to store or append."},
            "query": {"type": "string", "description": "Keyword to search for."},
            "filename": {
                "type": "string",
                "description": "Specific memory file to read (e.g., 'MEMORY.md' or '2024-05-20.md').",
            },
        },
        "required": ["action"],
    }

    def __init__(self, workspace: Path):
        self.store = MemoryStore(workspace)

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        try:
            if action == "append_daily":
                content = kwargs.get("content")
                if not content:
                    return ToolResult(success=False, output="Error: 'content' required.", remedy="请提供 content 参数以追加每日笔记。")
                self.store.append_today(content)
                return ToolResult(success=True, output="Successfully added to today's daily note.")

            elif action == "update_long_term":
                content = kwargs.get("content")
                if not content:
                    return ToolResult(success=False, output="Error: 'content' required.", remedy="请提供 content 参数以更新长期记忆（MEMORY.md）。")
                # Overwrite long term memory with new consolidated content
                self.store.write_long_term(content)
                return ToolResult(success=True, output="Long-term memory (MEMORY.md) updated.")

            elif action == "read":
                filename = kwargs.get("filename", "MEMORY.md")
                if filename == "MEMORY.md":
                    output = self.store.read_long_term() or "Long-term memory is empty."
                    return ToolResult(success=True, output=output)
                else:
                    try:
                        target_file = safe_resolve_path(self.store.memory_dir / filename, self.store.memory_dir)
                        if target_file.exists():
                            output = target_file.read_text(encoding="utf-8")
                            return ToolResult(success=True, output=output)
                        return ToolResult(success=False, output=f"Error: Memory file '{filename}' not found.", remedy="请检查文件名是否正确。")
                    except PermissionError as e:
                        return ToolResult(success=False, output=str(e))

            elif action == "search":
                query = kwargs.get("query")
                if not query:
                    return ToolResult(success=False, output="Error: 'query' required.", remedy="搜索记忆需要提供 query 参数。")
                output = self._search_memory(query)
                return ToolResult(success=True, output=output)

            else:
                return ToolResult(success=False, output=f"Unknown action: {action}", remedy="请检查 action 参数（append_daily, update_long_term, read, search）。")
        except Exception as e:
            return ToolResult(success=False, output=f"Memory Tool Error: {str(e)}")

    def _search_memory(self, query: str) -> str:
        matches = []
        query = query.lower()

        # Search long term
        lt = self.store.read_long_term()
        if query in lt.lower():
            matches.append("[MEMORY.md] matches your query.")

        # Search daily files
        files = self.store.list_memory_files()
        for f in files[:30]:  # Limit to last 30 days for speed
            content = f.read_text(encoding="utf-8")
            if query in content.lower():
                matches.append(f"[{f.name}] matches your query.")

        if not matches:
            return "No matches found in memory."
        return "Memory matches:\n" + "\n".join(matches)
