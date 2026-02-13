"""Write policy for filesystem tools (read-only / controlled / open)."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path


@dataclass
class FileWritePolicy:
    project_root: Path
    read_only_patterns: list[str]
    controlled_patterns: list[str]
    workspace_root: Path | None = None
    allow_workspace_root_files: list[str] = field(default_factory=list)
    require_confirm_for_controlled: bool = True
    enabled: bool = True

    def classify(self, path: Path) -> str:
        """Return one of: read_only, controlled, open."""
        if not self.enabled:
            return "open"
        key = self._to_match_key(path)
        if self._matches_any(key, self.read_only_patterns):
            return "read_only"
        if self._matches_any(key, self.controlled_patterns):
            return "controlled"
        return "open"

    def check_write(self, path: Path, *, confirm: bool = False, change_note: str = "") -> tuple[bool, str]:
        if self.workspace_root:
            root = self.workspace_root.resolve()
            try:
                rel = path.resolve().relative_to(root)
                if len(rel.parts) == 1:
                    if rel.name not in set(self.allow_workspace_root_files or []):
                        return False, "禁止在 workspace 根目录写入文件，请写入子目录（如 workspace/scripts/ 或 workspace/skills/）。"
            except Exception:
                pass
        cls = self.classify(path)
        if cls == "read_only":
            return False, "该文件属于受保护只读范围，禁止通过 AI 工具直接修改。"
        if cls == "controlled" and self.require_confirm_for_controlled:
            if not confirm:
                return False, "该文件属于受控修改范围。请显式提供 confirm=true 后再执行。"
            if not str(change_note or "").strip():
                return False, "该文件属于受控修改范围。请同时提供 change_note（修改原因摘要）。"
        return True, ""

    def _to_match_key(self, path: Path) -> str:
        p = path.resolve()
        root = self.project_root.resolve()
        try:
            rel = p.relative_to(root)
            return rel.as_posix()
        except Exception:
            return p.as_posix()

    def _matches_any(self, key: str, patterns: list[str]) -> bool:
        for raw in patterns or []:
            pat = str(raw or "").strip().replace("\\", "/")
            if not pat:
                continue
            if fnmatch(key, pat):
                return True
        return False
