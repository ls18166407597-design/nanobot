#!/usr/bin/env bash
set -euo pipefail
exec "$(cd "$(dirname "$0")" && pwd)/scripts/run_gateway.sh"
