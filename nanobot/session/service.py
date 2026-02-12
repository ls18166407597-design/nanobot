"""Session routing and lightweight session operations for channels."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from uuid import uuid4

from nanobot.utils.helpers import get_sessions_path, safe_filename


class SessionService:
    """Provide active-session routing and simple session file operations."""

    def __init__(self, channel_name: str):
        self.channel_name = channel_name
        self._active_sessions: Dict[str, str] = {}

    def get_active_session_key(self, chat_id: str) -> str:
        """Return the active session key for this chat."""
        if chat_id in self._active_sessions:
            return self._active_sessions[chat_id]

        # Migrate legacy key (channel:chat_id) to readable default (channel:chat_id#main).
        self._migrate_legacy_session_key(chat_id)
        return self._default_session_key(chat_id)

    def open_new_session(self, chat_id: str) -> str:
        """Rotate to a new session key and return it."""
        new_key = self._new_session_key(chat_id)
        self._active_sessions[chat_id] = new_key
        return new_key

    def clear_current_session(self, chat_id: str) -> tuple[bool, str]:
        """Delete current session file if present and rotate to a new session key."""
        current_key = self.get_active_session_key(chat_id)
        path = self._session_file_path(current_key)
        deleted = False
        if path.exists():
            path.unlink()
            deleted = True
        new_key = self.open_new_session(chat_id)
        return deleted, new_key

    def list_recent_sessions(self, chat_id: str, limit: int = 10) -> List[Tuple[str, str]]:
        """List recent sessions for this chat as (session_key, updated_at)."""
        base = safe_filename(f"{self.channel_name}_{chat_id}")
        sessions_dir = get_sessions_path()
        entries: list[tuple[str, str]] = []
        for path in sessions_dir.glob(f"{base}*.jsonl"):
            key = path.stem
            updated = ""
            try:
                with open(path, "r", encoding="utf-8") as f:
                    first = f.readline().strip()
                if first:
                    data = json.loads(first)
                    if data.get("_type") == "metadata":
                        key = data.get("key") or key
                        updated = data.get("updated_at") or ""
            except Exception:
                pass
            entries.append((str(key), str(updated)))
        entries.sort(key=lambda x: x[1], reverse=True)
        return entries[:limit]

    def use_session(self, chat_id: str, session_key: str) -> bool:
        """Switch active session to an existing session key for this chat."""
        if not session_key:
            return False
        if not session_key.startswith(f"{self.channel_name}:{chat_id}"):
            return False
        if not self._session_file_path(session_key).exists():
            return False
        self._active_sessions[chat_id] = session_key
        return True

    def rewind_last_turn(self, chat_id: str) -> tuple[bool, str, str]:
        """
        Roll back one user turn by creating a new trimmed session and switching to it.

        Returns:
            (ok, new_or_current_session_key, message)
        """
        current_key = self.get_active_session_key(chat_id)
        path = self._session_file_path(current_key)
        if not path.exists():
            new_key = self.open_new_session(chat_id)
            return False, new_key, "当前会话文件不存在，已切换到新会话。"

        try:
            metadata: dict[str, Any] = {}
            messages: list[dict[str, Any]] = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        metadata = data
                    else:
                        messages.append(data)
        except Exception:
            return False, current_key, "读取会话失败，未执行回退。"

        last_user_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "user":
                last_user_idx = i
                break

        if last_user_idx < 0:
            return False, current_key, "当前会话没有可回退的用户消息。"

        trimmed_messages = messages[:last_user_idx]
        removed_count = len(messages) - len(trimmed_messages)
        new_key = self._new_session_key(chat_id)
        new_path = self._session_file_path(new_key)
        new_path.parent.mkdir(parents=True, exist_ok=True)

        created_at = metadata.get("created_at") or datetime.now().isoformat()
        metadata_payload = metadata.get("metadata", {})
        meta_line = {
            "_type": "metadata",
            "key": new_key,
            "created_at": created_at,
            "updated_at": datetime.now().isoformat(),
            "metadata": metadata_payload if isinstance(metadata_payload, dict) else {},
        }

        with open(new_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta_line) + "\n")
            for msg in trimmed_messages:
                f.write(json.dumps(msg) + "\n")

        self._active_sessions[chat_id] = new_key
        return True, new_key, f"已回退 1 轮对话，移除 {removed_count} 条最近消息并切换到新会话。"

    def _new_session_key(self, chat_id: str) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{self.channel_name}:{chat_id}#s{ts}_{uuid4().hex[:6]}"

    def _default_session_key(self, chat_id: str) -> str:
        return f"{self.channel_name}:{chat_id}#main"

    def _legacy_session_key(self, chat_id: str) -> str:
        return f"{self.channel_name}:{chat_id}"

    def _session_file_path(self, session_key: str) -> Path:
        safe_key = safe_filename(session_key.replace(":", "_"))
        return get_sessions_path() / f"{safe_key}.jsonl"

    def _migrate_legacy_session_key(self, chat_id: str) -> None:
        """Rename legacy session file/key to new readable '#main' format."""
        new_key = self._default_session_key(chat_id)
        old_key = self._legacy_session_key(chat_id)
        new_path = self._session_file_path(new_key)
        old_path = self._session_file_path(old_key)

        if new_path.exists() or not old_path.exists():
            return

        try:
            lines = old_path.read_text(encoding="utf-8").splitlines()
            if lines:
                first = json.loads(lines[0])
                if first.get("_type") == "metadata":
                    first["key"] = new_key
                    first["updated_at"] = datetime.now().isoformat()
                    lines[0] = json.dumps(first)
            new_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            old_path.unlink()
        except Exception:
            # Best-effort migration; fallback keeps using new key and starts fresh if needed.
            return
