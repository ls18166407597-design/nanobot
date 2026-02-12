from pathlib import Path
from typing import Any

import aiohttp

from nanobot.agent.skills import SkillsLoader
from nanobot.agent.tools.base import Tool, ToolResult


class SkillsTool(Tool):
    """技能管理工具（已安装技能 + 在线广场检索/安装）。"""

    name = "skills"
    description = """
    管理技能：列出已安装技能、联网检索技能广场、按 URL 安装技能。
    
    动作:
    - list_installed: 列出当前已安装技能（workspace/skills）。
    - browse_online: 联网搜索技能广场（优先 clawhub.com）。
    - install_url: 从 SKILL.md URL 安装到工作区。
    """

    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": [
                    "browse_online",
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
            if action == "browse_online":
                output = await self._browse_online(kwargs.get("query", ""))
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
                return ToolResult(success=False, output=f"Unknown action: {action}", remedy="请检查 action 参数（browse_online, install_url, list_installed）。")
        except Exception as e:
            return ToolResult(success=False, output=f"Skills Tool Error: {str(e)}")

    async def _browse_online(self, query: str) -> str:
        if not self.search_func:
            return (
                "未配置联网搜索工具，无法在线检索技能广场。\n"
                "可直接执行：`clawhub search \"关键词\"`"
            )

        search_query = f"site:clawhub.com {query}" if query else "site:clawhub.com"
        results = await self.search_func(query=search_query)
        return (
            f"--- 技能广场在线搜索结果 ---\n\n{results}\n\n"
            "如需安装，请使用 `install_url` 并传入该技能的 SKILL.md 直链。"
        )

    async def _install_url(self, skill_name: str, url: str) -> str:
        if not skill_name or not url:
            return "Error: online installation requires both 'skill_name' and 'url'."

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
            return f"Successfully installed '{skill_name}' from online source. It is now active."
        except Exception as e:
            return f"Failed to download skill: {str(e)}"

    def _list_installed(self) -> str:
        skills = self.loader.list_skills(filter_unavailable=False)
        if not skills:
            return "未发现已安装技能。"

        output = ["--- 已安装技能 ---"]
        output.append("目录：workspace/skills")
        for s in skills:
            desc = self.loader._get_skill_description(s["name"])
            output.append(f"- {s['name']}: {desc}")
        return "\n".join(output)
