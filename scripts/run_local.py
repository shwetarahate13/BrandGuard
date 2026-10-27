#!/usr/bin/env python3
"""Run the built FastAPI/React application on one local port."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]


def venv_python() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def local_path(value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def ensure_local(path: Path, label: str) -> None:
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as exc:
        raise SystemExit(f"--reset only clears {label} inside the project folder; refusing: {path}") from exc


def reset_local_data() -> None:
    from backend.app.config import get_settings

    settings = get_settings()
    if not settings.DATABASE_URL.startswith("sqlite:"):
        raise SystemExit("--reset only supports a local SQLite database; current DATABASE_URL is not SQLite.")

    database_url = settings.DATABASE_URL.split("?", 1)[0]
    if database_url in {"sqlite://", "sqlite:///:memory:"}:
        database_path = None
    else:
        raw_path = database_url.removeprefix("sqlite:///")
        database_path = local_path(unquote(raw_path))
        ensure_local(database_path, "the database")
        for suffix in ("", "-wal", "-shm"):
            candidate = Path(str(database_path) + suffix)
            if candidate.is_file():
                candidate.unlink()
                print(f"Removed {candidate.relative_to(ROOT)}")

    for configured in (settings.CHROMA_PERSIST_DIR, settings.ASSET_STORAGE_DIR):
        path = local_path(configured)
        ensure_local(path, "local indexes and uploaded assets")
        if path.is_dir():
            shutil.rmtree(path)
            print(f"Removed {path.relative_to(ROOT)}")
        elif path.exists():
            path.unlink()
    if database_path is None:
        print("Using an in-memory database; no SQLite file to remove.")
    print("Local data cleared.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BrandGuard locally with the prebuilt frontend.")
    parser.add_argument("--port", type=int, default=8000, help="Local HTTP port (default: 8000).")
    parser.add_argument("--reset", action="store_true", help="Wipe local SQLite, Chroma, and asset data before starting.")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    python_path = venv_python()
    if python_path.exists() and Path(sys.executable).resolve() != python_path.resolve():
        return subprocess.call([str(python_path), str(Path(__file__).resolve()), *sys.argv[1:]], cwd=ROOT)
    if not python_path.exists():
        print("Local dependencies are missing. Run `python scripts/setup_local.py` first.", file=sys.stderr)
        return 2
    if sys.version_info < (3, 11):
        print("BrandGuard needs Python 3.11 or newer. Re-run with the project's .venv Python.", file=sys.stderr)
        return 2
    if not (ROOT / ".env").is_file():
        print(".env is missing. Run `python scripts/setup_local.py` first.", file=sys.stderr)
        return 2

    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    if args.reset:
        reset_local_data()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUNBUFFERED"] = "1"
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True)

    url = f"http://localhost:{args.port}"
    print(f"BrandGuard is starting at {url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    return subprocess.call(
        [sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", str(args.port)],
        cwd=ROOT,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
