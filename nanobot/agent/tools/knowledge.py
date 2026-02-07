import os
import json
import datetime
import glob
from typing import Any
from nanobot.agent.tools.base import Tool

CONFIG_PATH = os.path.expanduser("~/.nanobot/knowledge_config.json")

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
    Requires '~/.nanobot/knowledge_config.json' with:
    { "vault_path": "/path/to/vault", "daily_notes_folder": "Daily" }
    """
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["setup", "search", "read", "create", "append_daily", "list_files"],
                "description": "The action to perform."
            },
            "vault_path": {
                "type": "string",
                "description": "Path to the Obsidian vault (for setup)."
            },
            "daily_notes_folder": {
                "type": "string",
                "description": "Subfolder for daily notes (for setup), e.g. 'Daily'."
            },
            "query": {
                "type": "string",
                "description": "Search query."
            },
            "filename": {
                "type": "string",
                "description": "Filename (relative to vault root) for read/create."
            },
            "content": {
                "type": "string",
                "description": "Content to write or append."
            },
            "folder": {
                "type": "string",
                "description": "Folder to create note in (optional)."
            }
        },
        "required": ["action"]
    }

    def _load_config(self):
        if not os.path.exists(CONFIG_PATH):
            return None
        try:
            with open(CONFIG_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    def _save_config(self, vault_path, daily_notes_folder):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        config = {"vault_path": vault_path}
        if daily_notes_folder:
            config["daily_notes_folder"] = daily_notes_folder
        with open(CONFIG_PATH, 'w') as f:
            json.dump(config, f)

    async def execute(self, action: str, **kwargs: Any) -> str:
        if action == "setup":
            vault_path = kwargs.get("vault_path")
            daily_folder = kwargs.get("daily_notes_folder")
            if not vault_path:
                return "Error: 'vault_path' is required for setup."
            self._save_config(vault_path, daily_folder)
            return "Knowledge base configuration saved successfully."

        config = self._load_config()
        if not config or "vault_path" not in config:
            return "Error: Knowledge base not configured. Please use action='setup' first."

        vault_root = config["vault_path"]
        if not os.path.exists(vault_root):
             return f"Error: Configured vault path '{vault_root}' does not exist on disk."

        try:
            if action == "search":
                return self._search_notes(vault_root, kwargs.get("query"))
            elif action == "read":
                return self._read_note(vault_root, kwargs.get("filename"))
            elif action == "create":
                return self._create_note(vault_root, kwargs.get("filename"), kwargs.get("content"), kwargs.get("folder"))
            elif action == "append_daily":
                daily_subfolder = config.get("daily_notes_folder", "")
                return self._append_daily(vault_root, daily_subfolder, kwargs.get("content"))
            elif action == "list_files":
                return self._list_files(vault_root, kwargs.get("folder", ""))
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Knowledge Tool Error: {str(e)}"

    def _search_notes(self, root, query):
        if not query: return "Error: 'query' required for search."
        matches = []
        # Simple recursive search for .md files
        # For large vaults, 'grep' via subprocess might be faster, but python is safer/portable.
        # Check if 'grep' is available? Mac usually has it. Let's use os.walk for safety first.
        # Limit to 50 matches.
        count = 0
        for dirpath, _, filenames in os.walk(root):
            if ".git" in dirpath: continue
            for f in filenames:
                if f.endswith(".md"):
                    path = os.path.join(dirpath, f)
                    try:
                        with open(path, 'r', errors='ignore') as note_file:
                            content = note_file.read()
                            if query.lower() in content.lower():
                                rel_path = os.path.relpath(path, root)
                                matches.append(f"- {rel_path}")
                                count += 1
                                if count >= 20: break
                    except Exception: pass
            if count >= 20: break
        
        if not matches: return "No matches found."
        return "Found matches:\n" + "\n".join(matches)

    def _read_note(self, root, filename):
        if not filename: return "Error: 'filename' required."
        path = os.path.join(root, filename)
        if not os.path.exists(path):
             return f"Error: File '{filename}' not found."
        with open(path, 'r', errors='ignore') as f:
            return f.read()

    def _create_note(self, root, filename, content, folder):
        if not filename or not content: return "Error: 'filename' and 'content' required."
        if not filename.endswith(".md"): filename += ".md"
        
        target_dir = root
        if folder:
            target_dir = os.path.join(root, folder)
        
        os.makedirs(target_dir, exist_ok=True)
        path = os.path.join(target_dir, filename)
        
        if os.path.exists(path):
            return "Error: File already exists. Use append or different name."
        
        with open(path, 'w') as f:
            f.write(content)
        return f"Created note: {os.path.relpath(path, root)}"

    def _append_daily(self, root, daily_folder, content):
        if not content: return "Error: 'content' required."
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
        
        mode = 'a' if os.path.exists(path) else 'w'
        with open(path, mode) as f:
            f.write(entry)
            
        return f"Appended to daily note: {os.path.relpath(path, root)}"

    def _list_files(self, root, folder):
        target_dir = os.path.join(root, folder) if folder else root
        if not os.path.exists(target_dir): return "Folder not found."
        
        files = []
        for f in os.listdir(target_dir):
            if f.startswith("."): continue
            files.append(f)
        return "\n".join(files[:50])
