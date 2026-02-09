#!/usr/bin/env python3
"""
Minimal Antigravity OAuth login for nanobot (local callback).

Flow:
1) Start localhost callback server.
2) Open browser to Google OAuth consent.
3) Exchange code for tokens (PKCE).
4) Fetch projectId via loadCodeAssist.
5) Save NANOBOT_HOME/antigravity_auth.json.
6) Update nanobot config providerRegistry + set default model.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
import ssl
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Optional, Tuple

# OAuth constants (aligned with OpenClaw google-antigravity-auth plugin)
CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "http://localhost:51121/oauth-callback"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_PROJECT_ID = "rising-fact-p41fc"

SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]

CODE_ASSIST_ENDPOINTS = [
    "https://cloudcode-pa.googleapis.com",
    "https://daily-cloudcode-pa.sandbox.googleapis.com",
]


def _base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _generate_pkce() -> Tuple[str, str]:
    verifier = secrets.token_urlsafe(32)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = _base64url(digest)
    return verifier, challenge


def _build_auth_url(state: str, challenge: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


@dataclass
class CallbackResult:
    code: str
    state: str


class _CallbackHandler(BaseHTTPRequestHandler):
    server_version = "AntigravityOAuth/1.0"
    callback_result: Optional[CallbackResult] = None
    callback_error: Optional[str] = None

    def do_GET(self):  # noqa: N802 (HTTP handler naming)
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != urllib.parse.urlparse(REDIRECT_URI).path:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return

        params = urllib.parse.parse_qs(parsed.query)
        code = (params.get("code") or [""])[0]
        state = (params.get("state") or [""])[0]

        if not code or not state:
            _CallbackHandler.callback_error = "Missing code or state"
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code/state")
            return

        _CallbackHandler.callback_result = CallbackResult(code=code, state=state)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(
            b"<html><body><h1>Authentication complete</h1>"
            b"<p>You can return to the terminal.</p></body></html>"
        )

    def log_message(self, format: str, *args: Any) -> None:  # silence
        return


def _start_callback_server(timeout_s: int = 300) -> CallbackResult:
    parsed = urllib.parse.urlparse(REDIRECT_URI)
    port = int(parsed.port or 51121)
    server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = 1

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        server.handle_request()
        if _CallbackHandler.callback_result:
            server.server_close()
            return _CallbackHandler.callback_result
        if _CallbackHandler.callback_error:
            server.server_close()
            raise RuntimeError(_CallbackHandler.callback_error)
    server.server_close()
    raise TimeoutError("Timed out waiting for OAuth callback")


def _parse_redirect_url(url: str) -> CallbackResult:
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception as exc:
        raise RuntimeError(f"Invalid URL: {exc}") from exc
    if not parsed.query:
        raise RuntimeError("Redirect URL missing query parameters")
    params = urllib.parse.parse_qs(parsed.query)
    code = (params.get("code") or [""])[0]
    state = (params.get("state") or [""])[0]
    if not code or not state:
        raise RuntimeError("Redirect URL missing code/state")
    return CallbackResult(code=code, state=state)


def _ssl_context() -> ssl.SSLContext:
    # Prefer certifi if available (common fix for macOS Python SSL issues)
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _exchange_code(code: str, verifier: str) -> dict[str, Any]:
    data = urllib.parse.urlencode(
        {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        }
    ).encode("utf-8")
    req = urllib.request.Request(TOKEN_URL, data=data, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    expires_in = int(payload.get("expires_in", 0))
    if not access or not refresh:
        raise RuntimeError("Token exchange returned no access/refresh token")
    expires = int(time.time() * 1000) + expires_in * 1000 - 5 * 60 * 1000
    return {"access": access, "refresh": refresh, "expires": expires}


def _fetch_user_email(access_token: str) -> Optional[str]:
    req = urllib.request.Request(
        "https://www.googleapis.com/oauth2/v1/userinfo?alt=json",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_ssl_context()) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("email")
    except Exception:
        return None


def _fetch_project_id(access_token: str) -> str:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "google-api-nodejs-client/9.15.1",
        "X-Goog-Api-Client": "google-cloud-sdk vscode_cloudshelleditor/0.1",
        "Client-Metadata": json.dumps(
            {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        ),
    }
    body = json.dumps(
        {
            "metadata": {
                "ideType": "IDE_UNSPECIFIED",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        }
    ).encode("utf-8")

    for endpoint in CODE_ASSIST_ENDPOINTS:
        try:
            req = urllib.request.Request(
                f"{endpoint}/v1internal:loadCodeAssist",
                data=body,
                method="POST",
                headers=headers,
            )
            with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                proj = payload.get("cloudaicompanionProject")
                if isinstance(proj, str):
                    return proj
                if isinstance(proj, dict) and proj.get("id"):
                    return proj["id"]
        except Exception:
            continue
    return DEFAULT_PROJECT_ID


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _get_nanobot_config_path() -> Path:
    root = os.environ.get("NANOBOT_HOME")
    if root:
        return Path(root).expanduser() / "config.json"
    # Prefer repo .home (start.sh default), then repo .nanobot, then ~/.nanobot
    repo = _repo_root()
    local_home = repo / ".home" / "config.json"
    if local_home.exists():
        return local_home
    local = repo / ".nanobot" / "config.json"
    if local.exists():
        return local
    return Path("~/.nanobot/config.json").expanduser()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _upsert_provider_registry(
    config: dict[str, Any],
    name: str,
    model: str,
    base_url: str,
    api_key: str,
) -> None:
    brain = config.setdefault("brain", {})
    registry = brain.setdefault("providerRegistry", [])
    if not isinstance(registry, list):
        raise ValueError("brain.providerRegistry must be a list")

    for entry in registry:
        if isinstance(entry, dict) and (entry.get("name") == name or entry.get("model") == model):
            entry["name"] = name
            entry["model"] = model
            entry["base_url"] = base_url
            entry["api_key"] = api_key
            return

    registry.append(
        {"name": name, "model": model, "base_url": base_url, "api_key": api_key}
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity OAuth login for nanobot.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8045/v1")
    parser.add_argument("--model", default="gemini-3-flash")
    parser.add_argument("--name", default="antigravity-local")
    parser.add_argument("--set-default-model", action="store_true")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Skip localhost callback and paste redirect URL manually.",
    )
    args = parser.parse_args()

    verifier, challenge = _generate_pkce()
    state = secrets.token_hex(16)
    auth_url = _build_auth_url(state, challenge)

    print("Opening browser for Antigravity OAuth...")
    try:
        webbrowser.open(auth_url)
    except Exception:
        print("Failed to open browser. Please open this URL manually:")
        print(auth_url)
    if args.manual:
        print("Manual mode enabled.")
        print("Please paste the full redirect URL from the browser:")
        redirect = input("Redirect URL: ").strip()
        callback = _parse_redirect_url(redirect)
    else:
        try:
            callback = _start_callback_server(timeout_s=5 * 60)
        except Exception as exc:
            print(f"Local callback failed: {exc}")
            print("Please paste the full redirect URL from the browser:")
            redirect = input("Redirect URL: ").strip()
            callback = _parse_redirect_url(redirect)
    if callback.state != state:
        raise RuntimeError("OAuth state mismatch. Please retry.")

    tokens = _exchange_code(callback.code, verifier)
    email = _fetch_user_email(tokens["access"])
    project_id = _fetch_project_id(tokens["access"])

    auth_payload = {
        "provider": "google-antigravity",
        "type": "oauth",
        "access": tokens["access"],
        "refresh": tokens["refresh"],
        "expires": tokens["expires"],
        "email": email,
        "projectId": project_id,
        "createdAt": int(time.time() * 1000),
    }

    # Save antigravity_auth.json
    if os.environ.get("NANOBOT_HOME"):
        nanobot_home = Path(os.environ["NANOBOT_HOME"]).expanduser()
    else:
        repo = _repo_root()
        if (repo / ".home").exists():
            nanobot_home = repo / ".home"
        else:
            nanobot_home = repo / ".nanobot"
    auth_path = nanobot_home / "antigravity_auth.json"
    _save_json(auth_path, auth_payload)
    print(f"Saved auth: {auth_path}")

    # Update nanobot config
    config_path = _get_nanobot_config_path()
    config = _load_json(config_path)
    api_key = json.dumps({"token": tokens["access"], "projectId": project_id})
    _upsert_provider_registry(config, args.name, args.model, args.base_url, api_key)
    if args.set_default_model:
        agents = config.setdefault("agents", {})
        defaults = agents.setdefault("defaults", {})
        defaults["model"] = args.model
    _save_json(config_path, config)
    print(f"Updated config: {config_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
