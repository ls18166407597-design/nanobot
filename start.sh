#!/bin/bash
# export NANOBOT_HOME=$(pwd)/.home
.venv/bin/nanobot gateway 2>&1 | tee gateway.log
