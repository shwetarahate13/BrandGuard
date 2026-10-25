#!/usr/bin/env bash
set -e

echo "=== BrandGuard Startup ==="
echo "Running database migrations..."
alembic upgrade head

PORT="${PORT:?PORT environment variable is required}"
echo "Starting uvicorn on port ${PORT}..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 --timeout-keep-alive 65
