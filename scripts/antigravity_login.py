#!/usr/bin/env python3
"""
Minimal Antigravity login helper for nanobot.

Reads OpenClaw auth store and writes a providerRegistry entry that uses a JSON api_key
for the local antigravity OpenAI-compatible proxy (default http://127.0.0.1:8045/v1).
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def _resolve_openclaw_state_dir() -> Path:
    override = os.environ.get("OPENCLAW_STATE_DIR") or os.environ.get("CLAWDBOT_STATE_DIR")
    if override:
        return Path(override).expanduser()
    return Path("~/.openclaw").expanduser()


def _resolve_openclaw_agent_dir(state_dir: Path) -> Path:
    override = os.environ.get("OPENCLAW_AGENT_DIR") or os.environ.get("PI_CODING_AGENT_DIR")
    if override:
        return Path(override).expanduser()
    return state_dir / "agents" / "main" / "agent"


def _load_openclaw_auth_store(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"OpenClaw auth store not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _extract_antigravity_credentials(store: dict[str, Any]) -> tuple[str, str]:
    profiles = store.get("profiles") or {}
    if not isinstance(profiles, dict):
        raise ValueError("Invalid OpenClaw auth store format: profiles is not a dict")

    for profile_id, cred in profiles.items():
        if not isinstance(cred, dict):
            continue
        provider = cred.get("provider")
        if provider != "google-antigravity":
            continue

        cred_type = cred.get("type")
        token = None
        project_id = cred.get("projectId") or cred.get("project_id")
        if cred_type == "oauth":
            token = cred.get("access")
        elif cred_type == "token":
            token = cred.get("token")
        elif cred_type == "api_key":
            token = cred.get("key")

        if token and project_id:
            return token, project_id

    raise ValueError("No valid google-antigravity credentials found in OpenClaw auth store.")


def _load_nanobot_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        raise FileNotFoundError(f"nanobot config not found: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_nanobot_config(config_path: Path, config: dict[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def _get_nanobot_config_path() -> Path:
    # Prefer NANOBOT_HOME, then local ./.nanobot, then ~/.nanobot
    root = os.environ.get("NANOBOT_HOME")
    if root:
        return Path(root).expanduser() / "config.json"
    local = Path(".") / ".nanobot" / "config.json"
    if local.exists():
        return local
    return Path("~/.nanobot/config.json").expanduser()


def _upsert_provider_registry(
    config: dict[str, Any],
    name: str,
    model: str,
    base_url: str,
    api_key: str,
) -> bool:
    brain = config.setdefault("brain", {})
    registry = brain.setdefault("providerRegistry", [])
    if not isinstance(registry, list):
        raise ValueError("Invalid config: brain.providerRegistry must be a list")

    for entry in registry:
        if not isinstance(entry, dict):
            continue
        if entry.get("name") == name or entry.get("model") == model:
            entry["name"] = name
            entry["model"] = model
            entry["base_url"] = base_url
            entry["api_key"] = api_key
            return False

    registry.append(
        {
            "name": name,
            "model": model,
            "base_url": base_url,
            "api_key": api_key,
        }
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal Antigravity login helper for nanobot.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8045/v1",
        help="Antigravity OpenAI-compatible base URL",
    )
    parser.add_argument(
        "--model",
        default="gemini-3-flash",
        help="Default model to bind (used for providerRegistry matching)",
    )
    parser.add_argument(
        "--name",
        default="local-gemini",
        help="Provider registry name",
    )
    parser.add_argument(
        "--set-default-model",
        action="store_true",
        help="Also set agents.defaults.model to the provided --model",
    )
    args = parser.parse_args()

    state_dir = _resolve_openclaw_state_dir()
    agent_dir = _resolve_openclaw_agent_dir(state_dir)
    auth_path = agent_dir / "auth-profiles.json"

    store = _load_openclaw_auth_store(auth_path)
    token, project_id = _extract_antigravity_credentials(store)
    api_key = json.dumps({"token": token, "projectId": project_id})

    config_path = _get_nanobot_config_path()
    config = _load_nanobot_config(config_path)

    created = _upsert_provider_registry(
        config=config,
        name=args.name,
        model=args.model,
        base_url=args.base_url,
        api_key=api_key,
    )
    if args.set_default_model:
        agents = config.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        defaults["model"] = args.model

    _save_nanobot_config(config_path, config)

    action = "Created" if created else "Updated"
    print(f"{action} providerRegistry entry '{args.name}' for model '{args.model}'.")
    print(f"Config path: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
