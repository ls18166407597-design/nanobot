import os
import shutil
from pathlib import Path
from typing import Any

from nanobot.agent.skills import SkillsLoader
from nanobot.agent.tools.base import Tool


class SkillsTool(Tool):
    """Tool for managing Nanobot skills (browsing plaza, installing experts)."""

    name = "skills"
    description = """
    Manage Nanobot's skills and explore the OpenClaw Skill Plaza.

    Actions:
    - list_plaza: Browse all expert skills available in the library.
    - search_plaza: Search for skills matching a keyword.
    - install: Install a skill from the library to your workspace.
    - list_installed: List skills currently active in your workspace.
    """

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_plaza", "search_plaza", "install", "list_installed"],
                "description": "Skill management action.",
            },
            "query": {"type": "string", "description": "Keyword to search for in the plaza."},
            "skill_name": {
                "type": "string",
                "description": "Name of the skill (e.g., 'lib:summarize' or just 'summarize').",
            },
        },
        "required": ["action"],
    }

    def __init__(self, workspace: Path):
        self.loader = SkillsLoader(workspace)

    async def execute(self, action: str, **kwargs: Any) -> str:
        try:
            if action == "list_plaza":
                return self._list_plaza()
            elif action == "search_plaza":
                return self._search_plaza(kwargs.get("query", ""))
            elif action == "install":
                return self._install_skill(kwargs.get("skill_name", ""))
            elif action == "list_installed":
                return self._list_installed()
            else:
                return f"Unknown action: {action}"
        except Exception as e:
            return f"Skills Tool Error: {str(e)}"

    def _list_plaza(self) -> str:
        skills = self.loader.list_skills(filter_unavailable=False)
        lib_skills = [s for s in skills if s["source"] == "library"]
        if not lib_skills:
            return "No skills found in the library/plaza."

        output = ["--- OpenClaw Skill Plaza ---"]
        for s in lib_skills:
            name = s["name"].replace("lib:", "")
            desc = self.loader._get_skill_description(s["name"])
            output.append(f"- {name}: {desc}")
        return "\n".join(output)

    def _search_plaza(self, query: str) -> str:
        if not query:
            return "Error: 'query' required for search."
        skills = self.loader.list_skills(filter_unavailable=False)
        query = query.lower()
        matches = []
        for s in skills:
            if s["source"] == "library":
                name = s["name"].lower()
                desc = self.loader._get_skill_description(s["name"]).lower()
                if query in name or query in desc:
                    matches.append(f"- {s['name'].replace('lib:', '')}: {desc}")

        if not matches:
            return f"No skills matching '{query}' found in the plaza."
        return f"Plaza matches for '{query}':\n" + "\n".join(matches)

    def _install_skill(self, skill_name: str) -> str:
        if not skill_name:
            return "Error: 'skill_name' required for install."

        # Normalize name
        clean_name = skill_name.replace("lib:", "")
        lib_path = self.loader.library_skills / clean_name
        dest_path = self.loader.workspace_skills / clean_name

        if not lib_path.exists():
            return f"Error: Skill '{clean_name}' not found in library."

        if dest_path.exists():
            return f"Skill '{clean_name}' is already installed in workspace."

        os.makedirs(dest_path.parent, exist_ok=True)
        shutil.copytree(lib_path, dest_path)
        return (
            f"Successfully installed '{clean_name}' to workspace. "
            "It is now active and its patterns will be followed."
        )

    def _list_installed(self) -> str:
        skills = self.loader.list_skills(filter_unavailable=False)
        installed = [s for s in skills if s["source"] == "workspace"]
        if not installed:
            return "No custom skills installed in workspace."

        output = ["--- Installed Workspace Skills ---"]
        for s in installed:
            desc = self.loader._get_skill_description(s["name"])
            output.append(f"- {s['name']}: {desc}")
        return "\n".join(output)
