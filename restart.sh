#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

export NANOBOT_HOME="${NANOBOT_HOME:-$ROOT_DIR/.home}"

# Stop first (ignore if not running), then start using the unified gateway script.
if [ -x ".venv/bin/nanobot" ]; then
  NANOBOT_HOME="$NANOBOT_HOME" .venv/bin/nanobot stop || true
fi

exec "$ROOT_DIR/scripts/run_gateway.sh"
