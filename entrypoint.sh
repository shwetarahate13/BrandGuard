#!/usr/bin/env bash
set -e

echo "=== BrandGuard Startup ==="
echo "Running database migrations..."
alembic upgrade head || {
    echo "Warning: Alembic upgrade encountered issue. Falling back to SQLAlchemy create_all on app init."
}

PORT="${PORT:-8000}"
echo "Starting uvicorn on port ${PORT}..."
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT}" --workers 1 --timeout-keep-alive 65
