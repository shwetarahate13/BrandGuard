#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  export PATH="$ROOT_DIR/.venv/bin:$PATH"
  PYTHON="$ROOT_DIR/.venv/bin/python"
else
  PYTHON="${PYTHON:-python}"
fi

"$PYTHON" -m pip install --disable-pip-version-check -r backend/requirements.txt

NODE_MAJOR="0"
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -p 'Number(process.versions.node.split(".")[0])')"
fi

if command -v npm >/dev/null 2>&1 && [ "$NODE_MAJOR" -ge 18 ]; then
  npm ci --prefix frontend
  npm run build --prefix frontend
else
  echo "Node.js 18+ is unavailable; using the committed SPA bundle in backend/app/static."
  test -s backend/app/static/index.html
  test -d backend/app/static/assets
fi

"$PYTHON" -m alembic upgrade head
