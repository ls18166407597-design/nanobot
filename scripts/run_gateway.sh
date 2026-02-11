#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export NANOBOT_HOME="${NANOBOT_HOME:-$ROOT_DIR/.home}"
mkdir -p "$NANOBOT_HOME"

if [ "${NANOBOT_KEEP_PROXY:-0}" != "1" ]; then
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
  export NO_PROXY="*"
  export no_proxy="*"
fi

if [ ! -x ".venv/bin/nanobot" ]; then
  echo "Error: .venv/bin/nanobot not found."
  echo "Run: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  exit 1
fi

echo "Starting Nanobot Gateway..."
echo "NANOBOT_HOME: $NANOBOT_HOME"
echo "Logs: $NANOBOT_HOME/gateway.log"

# Do not pipe to the same gateway.log via tee. The gateway process already writes
# to that file internally; dual writers can corrupt log content.
exec .venv/bin/nanobot gateway
