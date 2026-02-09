"""Utility functions for nanobot."""

import os
from datetime import datetime
from pathlib import Path


def ensure_dir(path: Path) -> Path:
    """Ensure a directory exists, creating it if necessary."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_resolve_path(path: str | Path, allowed_dir: Path | None = None) -> Path:
    """
    Resolve path and optionally enforce directory restriction.
    
    Args:
        path: The path to resolve.
        allowed_dir: Optional root directory to restrict access to.
        
    Returns:
        The resolved Path object.
        
    Raises:
        PermissionError: If the resolved path is outside the allowed directory.
    """
    resolved = Path(path).expanduser().resolve()
    if allowed_dir:
        allowed_dir = allowed_dir.resolve()
        try:
            resolved.relative_to(allowed_dir)
        except ValueError:
            raise PermissionError(f"Path '{path}' is outside allowed directory '{allowed_dir}'")
    return resolved


def get_data_path() -> Path:
    """
    Get the nanobot data directory.
    Priority:
    1. NANOBOT_HOME environment variable
    2. Local ./.nanobot directory (if exists)
    3. Home ~/.nanobot directory (if exists)
    4. Default to local ./.nanobot
    """
    root = os.getenv("NANOBOT_HOME")
    if root:
        return ensure_dir(Path(root).expanduser())
    
    # Check local
    local_path = Path(".") / ".nanobot"
    if local_path.exists() and local_path.is_dir():
        return local_path.resolve()
        
    # Check home
    home_path = Path("~/.nanobot").expanduser()
    if home_path.exists() and home_path.is_dir():
        return home_path.resolve()
        
    return ensure_dir(local_path)


def get_log_path() -> Path:
    """Get the path to the gateway log file."""
    # Prefer data dir (NANOBOT_HOME) to keep logs centralized
    data_log = get_data_path() / "gateway.log"
    if data_log.exists():
        return data_log.resolve()
    # Fallback to local repo log (legacy)
    local_log = Path("gateway.log")
    if local_log.exists():
        return local_log.resolve()
    return data_log


def get_audit_path() -> Path:
    """Get the path to the audit log file."""
    return get_data_path() / "audit.log"


def get_workspace_path(workspace: str | None = None) -> Path:
    """
    Get the workspace path. Prioritizes local 'workspace' if it exists.

    Args:
        workspace: Optional workspace path. Defaults to [data_dir]/workspace.

    Returns:
        Expanded and ensured workspace path.
    """
    if workspace:
        path = Path(workspace).expanduser()
    else:
        # Prioritize local workspace directory in current folder
        local_ws = Path("workspace")
        if local_ws.exists() and local_ws.is_dir():
            return local_ws.resolve()
        path = get_data_path() / "workspace"
    return ensure_dir(path)


def get_sessions_path() -> Path:
    """Get the sessions storage directory."""
    return ensure_dir(get_data_path() / "sessions")


def get_memory_path(workspace: Path | None = None) -> Path:
    """Get the memory directory within the workspace."""
    ws = workspace or get_workspace_path()
    return ensure_dir(ws / "memory")


def get_skills_path(workspace: Path | None = None) -> Path:
    """Get the skills directory within the workspace."""
    ws = workspace or get_workspace_path()
    return ensure_dir(ws / "skills")


def today_date() -> str:
    """Get today's date in YYYY-MM-DD format."""
    return datetime.now().strftime("%Y-%m-%d")


def timestamp() -> str:
    """Get current timestamp in ISO format."""
    return datetime.now().isoformat()


def truncate_string(s: str, max_len: int = 100, suffix: str = "...") -> str:
    """Truncate a string to max length, adding suffix if truncated."""
    if isinstance(s, str) and len(s) > max_len:
        return s[: max_len - len(suffix)] + suffix
    return s


def safe_filename(name: str) -> str:
    """Convert a string to a safe filename."""
    # Replace unsafe characters
    unsafe = '<>:"/\\|?*'
    for char in unsafe:
        name = name.replace(char, "_")
    return name.strip()


def audit_log(event_type: str, details: dict) -> None:
    """Record a structured event to the audit log."""
    import json
    path = get_audit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    
    record = {
        "timestamp": timestamp(),
        "type": event_type,
        "details": details
    }
    
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Setup logging to both console and file using loguru."""
    import sys
    from loguru import logger
    
    # Remove default handler
    logger.remove()
    
    # Add console handler (standard stderr)
    logger.add(
        sys.stderr, 
        level=level, 
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file handler
    actual_log_file = log_file or get_log_path()
    actual_log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(actual_log_file, rotation="10 MB", level=level, retention="7 days", compression="zip")
    
    logger.info(f"Logging initialized. Level: {level}, File: {actual_log_file}")
