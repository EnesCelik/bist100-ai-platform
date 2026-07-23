#!/bin/zsh
set -euo pipefail
cd /Users/ahmetenescelik/Desktop/AiEngineer/bist100-ai-platform
open -a Docker >/dev/null 2>&1 || true
/usr/local/bin/docker compose up -d postgres >/tmp/bist100-docker.log 2>&1 || /opt/homebrew/bin/docker compose up -d postgres >/tmp/bist100-docker.log 2>&1 || docker compose up -d postgres >/tmp/bist100-docker.log 2>&1
exec .venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8000
