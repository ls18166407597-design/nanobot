from pathlib import Path
from typing import Any

from nanobot.agent.memory import MemoryStore
from nanobot.agent.tools.base import Tool
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

    async def execute(self, action: str, **kwargs: Any) -> str:
        try:
            if action == "append_daily":
                content = kwargs.get("content")
                if not content:
                    return "Error: 'content' required."
                self.store.append_today(content)
                return "Successfully added to today's daily note."

            elif action == "update_long_term":
                content = kwargs.get("content")
                if not content:
                    return "Error: 'content' required."
                # Overwrite long term memory with new consolidated content
                self.store.write_long_term(content)
                return "Long-term memory (MEMORY.md) updated."

            elif action == "read":
                filename = kwargs.get("filename", "MEMORY.md")
                if filename == "MEMORY.md":
                    return self.store.read_long_term() or "Long-term memory is empty."
                else:
                    try:
                        target_file = safe_resolve_path(self.store.memory_dir / filename, self.store.memory_dir)
                        if target_file.exists():
                            return target_file.read_text(encoding="utf-8")
                        return f"Error: Memory file '{filename}' not found."
                    except PermissionError as e:
                        return str(e)

            elif action == "search":
                query = kwargs.get("query")
                if not query:
                    return "Error: 'query' required."
                return self._search_memory(query)

            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Memory Tool Error: {str(e)}"

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
