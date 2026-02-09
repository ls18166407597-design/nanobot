#!/bin/bash
cd "$(dirname "$0")"
export NANOBOT_HOME=$(pwd)/.home
mkdir -p "$NANOBOT_HOME"
if [ "${NANOBOT_KEEP_PROXY:-0}" != "1" ]; then
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
  export NO_PROXY="*"
  export no_proxy="*"
fi
if [ ! -f "$NANOBOT_HOME/antigravity_auth.json" ]; then
  python3 scripts/antigravity_oauth_login.py --set-default-model
fi
ANTIGRAVITY_BRIDGE_PORT=${ANTIGRAVITY_BRIDGE_PORT:-8046}
export ANTIGRAVITY_BRIDGE_DISABLE_TOOLS=${ANTIGRAVITY_BRIDGE_DISABLE_TOOLS:-1}
PYTHONUNBUFFERED=1 python3 scripts/antigravity_bridge.py --port "$ANTIGRAVITY_BRIDGE_PORT" > "$NANOBOT_HOME/antigravity_bridge.log" 2>&1 &
.venv/bin/nanobot gateway -v > "$NANOBOT_HOME/gateway.log" 2>&1
