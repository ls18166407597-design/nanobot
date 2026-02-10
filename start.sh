#!/bin/bash
cd "$(dirname "$0")"
export NANOBOT_HOME=$(pwd)/.home
mkdir -p "$NANOBOT_HOME"

if [ "${NANOBOT_KEEP_PROXY:-0}" != "1" ]; then
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
  export NO_PROXY="*"
  export no_proxy="*"
fi

# Note: Gemini is expected to be served on port 8045/8046 via external local bridge.
# Main Nanobot Gateway startup
echo "🐈 Starting Nanobot Gateway..."
echo "Logs are being saved to: $NANOBOT_HOME/gateway.log"
.venv/bin/nanobot gateway 2>&1 | tee "$NANOBOT_HOME/gateway.log"
