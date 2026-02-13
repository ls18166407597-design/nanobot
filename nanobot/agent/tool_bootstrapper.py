"""Default tool registration bootstrapper."""

import json
from pathlib import Path
from typing import Any

from nanobot.agent.file_write_policy import FileWritePolicy
from nanobot.agent.task_manager import TaskManager
from nanobot.agent.tools.browser import BrowserTool
from nanobot.agent.tools.amap import AmapTool
from nanobot.agent.tools.cron import CronTool
from nanobot.agent.tools.feishu import FeishuTool
from nanobot.agent.tools.filesystem import EditFileTool, ListDirTool, ReadFileTool, WriteFileTool
from nanobot.agent.tools.github import GitHubTool
from nanobot.agent.tools.gmail import GmailTool
from nanobot.agent.tools.knowledge import KnowledgeTool
from nanobot.agent.tools.mac import MacTool
from nanobot.agent.tools.mac_vision import MacVisionTool
from nanobot.agent.tools.mail import MailTool
from nanobot.agent.tools.mcp import MCPTool
from nanobot.agent.tools.memory import MemoryTool
from nanobot.agent.tools.message import MessageTool
from nanobot.agent.tools.provider import ProviderTool
from nanobot.agent.tools.qq_mail import QQMailTool
from nanobot.agent.tools.shell import ExecTool
from nanobot.agent.tools.skills import SkillsTool
from nanobot.agent.tools.system_status import SystemStatusTool
from nanobot.agent.tools.task import TaskTool
from nanobot.agent.tools.tavily import TavilyTool
from nanobot.agent.tools.tianapi import TianAPITool
from nanobot.agent.tools.train_ticket import TrainTicketTool
from nanobot.agent.tools.tushare import TushareTool
from nanobot.agent.tools.weather import WeatherTool
from nanobot.utils.helpers import get_tool_config_path


class ToolBootstrapper:
    """Register default tools based on config switches."""

    def __init__(
        self,
        *,
        tools: Any,
        workspace: Path,
        restrict_to_workspace: bool,
        exec_config: Any,
        provider: Any,
        brain_config: Any,
        web_proxy: str | None,
        bus_publish_outbound: Any,
        cron_service: Any,
        model_registry: Any,
        tools_config: Any,
        mac_confirm_mode: str,
    ):
        self.tools = tools
        self.workspace = workspace
        self.restrict_to_workspace = restrict_to_workspace
        self.exec_config = exec_config
        self.provider = provider
        self.brain_config = brain_config
        self.web_proxy = web_proxy
        self.bus_publish_outbound = bus_publish_outbound
        self.cron_service = cron_service
        self.model_registry = model_registry
        self.tools_config = tools_config
        self.mac_confirm_mode = mac_confirm_mode

    def register_default_tools(self) -> None:
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        project_root = self.workspace.parent
        wp_cfg = getattr(self.tools_config, "file_write_policy", None)
        write_policy = FileWritePolicy(
            project_root=project_root,
            read_only_patterns=list(getattr(wp_cfg, "read_only_patterns", []) or []),
            controlled_patterns=list(getattr(wp_cfg, "controlled_patterns", []) or []),
            require_confirm_for_controlled=bool(getattr(wp_cfg, "require_confirm_for_controlled", True)),
            enabled=bool(getattr(wp_cfg, "enabled", True)),
        )
        if self._tool_enabled("read_file"):
            self.tools.register(ReadFileTool(allowed_dir=allowed_dir, write_policy=write_policy))
        if self._tool_enabled("write_file"):
            self.tools.register(WriteFileTool(allowed_dir=allowed_dir, write_policy=write_policy))
        if self._tool_enabled("edit_file"):
            self.tools.register(EditFileTool(allowed_dir=allowed_dir, write_policy=write_policy))
        if self._tool_enabled("list_dir"):
            self.tools.register(ListDirTool(allowed_dir=allowed_dir))

        if self._tool_enabled("exec"):
            self.tools.register(
                ExecTool(
                    working_dir=str(self.workspace),
                    timeout=self.exec_config.timeout,
                    exec_mode=getattr(self.exec_config, "mode", "host"),
                    sandbox_engine=getattr(self.exec_config, "sandbox_engine", "auto"),
                    restrict_to_workspace=self.restrict_to_workspace,
                    provider=self.provider,
                    brain_config=self.brain_config,
                )
            )

        if self._tool_enabled("browser"):
            self.tools.register(BrowserTool(proxy=self.web_proxy))

        if self._tool_enabled("message"):
            self.tools.register(MessageTool(send_callback=self.bus_publish_outbound))

        from nanobot.config.loader import get_data_dir

        task_storage_path = get_data_dir() / "tasks.json"
        if self.cron_service and self._tool_enabled("cron"):
            self.tools.register(
                CronTool(
                    self.cron_service,
                    task_storage_path=task_storage_path,
                    default_tz=str(getattr(self.brain_config, "timezone", "Asia/Shanghai") or "Asia/Shanghai"),
                )
            )

        if self._tool_enabled("gmail"):
            self.tools.register(GmailTool())
        if self._tool_enabled("qq_mail"):
            self.tools.register(QQMailTool())
        if self._tool_enabled("mail"):
            self.tools.register(MailTool(self.tools))

        if self._tool_enabled("mac_control"):
            self.tools.register(MacTool(confirm_mode=self.mac_confirm_mode))
        if self._tool_enabled("mac_vision"):
            self.tools.register(MacVisionTool(confirm_mode=self.mac_confirm_mode))

        if self._tool_enabled("github"):
            self.tools.register(GitHubTool())
        if self._tool_enabled("knowledge_base"):
            self.tools.register(KnowledgeTool())
        if self._tool_enabled("memory"):
            self.tools.register(MemoryTool(workspace=self.workspace))
        if self._tool_enabled("system_status"):
            self.tools.register(SystemStatusTool())
        if self._tool_enabled("provider"):
            self.tools.register(ProviderTool(registry=self.model_registry))
        if (
            bool(getattr(self.tools_config.mcp, "expose_direct", False))
            and self._tool_enabled("mcp")
            and self._mcp_has_enabled_servers()
        ):
            self.tools.register(
                MCPTool(
                    startup_timeout=getattr(self.tools_config.mcp, "startup_timeout", 8),
                    request_timeout=getattr(self.tools_config.mcp, "request_timeout", 20),
                    max_output_chars=getattr(self.tools_config.mcp, "max_output_chars", 12000),
                )
            )
        if self._tool_enabled("weather"):
            self.tools.register(WeatherTool())
        if self._tool_enabled("tavily"):
            self.tools.register(TavilyTool())
        if self._tool_enabled("tianapi"):
            self.tools.register(TianAPITool())
        if self._tool_enabled("tushare"):
            self.tools.register(TushareTool())
        if self._tool_enabled("feishu"):
            self.tools.register(FeishuTool())
        if self._tool_enabled("train_ticket"):
            self.tools.register(TrainTicketTool())
        if self._tool_enabled("amap"):
            self.tools.register(AmapTool())

        if self._tool_enabled("skills"):
            self.tools.register(
                SkillsTool(
                    workspace=self.workspace,
                    search_func=None,
                )
            )

        task_manager = TaskManager(storage_path=task_storage_path)
        exec_tool = self.tools.get("exec")
        if exec_tool and self._tool_enabled("task"):
            self.tools.register(TaskTool(task_manager=task_manager, exec_tool=exec_tool))

    def _tool_enabled(self, name: str) -> bool:
        if self.tools_config.enabled_tools is not None:
            return name in self.tools_config.enabled_tools
        if self.tools_config.disabled_tools:
            return name not in self.tools_config.disabled_tools
        return True

    def _mcp_has_enabled_servers(self) -> bool:
        """Register MCP tool only when at least one MCP server is enabled."""
        path = get_tool_config_path("mcp_config.json")
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return False
        servers = cfg.get("servers")
        if not isinstance(servers, dict) or not servers:
            return False
        for item in servers.values():
            if isinstance(item, dict) and bool(item.get("enabled", True)):
                return True
        return False
