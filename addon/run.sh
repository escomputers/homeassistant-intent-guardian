#!/usr/bin/env sh
set -eu

exec uvicorn addon.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
