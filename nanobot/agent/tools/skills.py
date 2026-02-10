import os
import shutil
from pathlib import Path
from typing import Any

import aiohttp

from nanobot.agent.skills import SkillsLoader
from nanobot.agent.tools.base import Tool, ToolResult
from nanobot.utils.helpers import safe_resolve_path


class SkillsTool(Tool):
    """Tool for managing Nanobot skills (browsing plaza, installing experts)."""

    name = "skills"
    description = """
    管理和探索你工作区及库中的技能。
    使用此工具可以安装新功能、列出已安装的技能或搜索技能广场。
    
    动作:
    - list_installed: 列出当前已激活的技能。
    - list_plaza: 浏览可用的技能广场（库）。
    - search_plaza: 在广场中按查询词搜索技能。
    - install: 将技能从库安装到你的工作区。
    """

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "list_plaza",
                    "browse_online",
                    "search_plaza",
                    "install",
                    "install_url",
                    "list_installed",
                ],
                "description": "Skill management action.",
            },
            "query": {
                "type": "string",
                "description": "Keyword to search for in local or online plaza.",
            },
            "skill_name": {
                "type": "string",
                "description": "Name of the skill.",
            },
            "url": {
                "type": "string",
                "description": "Public URL of the skill's SKILL.md file for installation.",
            },
        },
        "required": ["action"],
    }

    def __init__(self, workspace: Path, search_func: Any = None):
        self.loader = SkillsLoader(workspace)
        self.search_func = search_func

    async def execute(self, action: str, **kwargs: Any) -> ToolResult:
        try:
            if action == "list_plaza":
                output = self._list_plaza()
                return ToolResult(success=True, output=output)
            elif action == "browse_online":
                output = await self._browse_online(kwargs.get("query", ""))
                return ToolResult(success=True, output=output)
            elif action == "search_plaza":
                output = self._search_plaza(kwargs.get("query", ""))
                return ToolResult(success=True, output=output)
            elif action == "install":
                output = self._install_skill(kwargs.get("skill_name", ""))
                # Note: _install_skill returns Error starting string on failure, but we want to be more specific if possible.
                if output.startswith("Error"):
                    return ToolResult(success=False, output=output, remedy="请确认技能名称正确，且该技能存在于库（Plaza）中。")
                return ToolResult(success=True, output=output)
            elif action == "install_url":
                output = await self._install_url(kwargs.get("skill_name", ""), kwargs.get("url", ""))
                if "Error" in output or "Failed" in output:
                     return ToolResult(success=False, output=output, remedy="请检查 URL 是否有效（直接指向 SKILL.md），以及网络连接是否正常。")
                return ToolResult(success=True, output=output)
            elif action == "list_installed":
                output = self._list_installed()
                return ToolResult(success=True, output=output)
            else:
                return ToolResult(success=False, output=f"Unknown action: {action}", remedy="请检查 action 参数（list_plaza, browse_online, search_plaza, install, install_url, list_installed）。")
        except Exception as e:
            return ToolResult(success=False, output=f"Skills Tool Error: {str(e)}")

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
                name = str(s["name"])
                desc = self.loader._get_skill_description(name).lower()
                clean_name = name.replace("lib:", "")
                if query in name.lower() or query in desc:
                    matches.append(f"- {clean_name}: {desc}")

        if not matches:
            return f"No skills matching '{query}' found in the plaza."
        return f"Plaza matches for '{query}':\n" + "\n".join(matches)

    def _install_skill(self, skill_name: str) -> str:
        if not skill_name:
            return "Error: 'skill_name' required for install."

        try:
            # Normalize and validate name (prevent traversal)
            clean_name = skill_name.replace("lib:", "")
            lib_path = safe_resolve_path(self.loader.library_skills / clean_name, self.loader.library_skills)
            dest_path = safe_resolve_path(self.loader.workspace_skills / clean_name, self.loader.workspace_skills)

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
        except PermissionError as e:
            return str(e)
        except Exception as e:
            return f"Error installing skill: {str(e)}"

    async def _browse_online(self, query: str) -> str:
        if not self.search_func:
            return "Error: Web search not configured. Cannot browse online plaza."

        search_query = f"site:clawhub.ai {query}" if query else "site:clawhub.ai"
        results = await self.search_func(query=search_query)
        return f"--- Online Skill Plaza Search Results ---\n\n{results}\n\nNote: To install, use action='install_url' with the specific skill's SKILL.md URL."

    async def _install_url(self, skill_name: str, url: str) -> str:
        if not skill_name or not url:
            return "Error: Both 'skill_name' and 'url' are required for online installation."

        dest_path = self.loader.workspace_skills / skill_name / "SKILL.md"
        if dest_path.exists():
            return f"Skill '{skill_name}' is already installed."

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return (
                            f"Error: Failed to fetch skill from {url} (Status: {response.status})"
                        )
                    content = await response.text()

            os.makedirs(dest_path.parent, exist_ok=True)
            dest_path.write_text(content, encoding="utf-8")
            return f"Successfully installed '{skill_name}' from the online plaza! It is now active."
        except Exception as e:
            return f"Failed to download skill: {str(e)}"

    def _list_installed(self) -> str:
        skills = self.loader.list_skills(filter_unavailable=False)
        installed = [s for s in skills if s["source"] in ["workspace", "builtin"]]
        if not installed:
            return "No skills found in workspace or built-in directories."

        output = ["--- Installed Skills ---"]
        for s in installed:
            desc = self.loader._get_skill_description(s["name"])
            source = f"({s['source']})"
            output.append(f"- {s['name']}: {desc} {source}")
        return "\n".join(output)
