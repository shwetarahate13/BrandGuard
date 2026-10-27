#!/usr/bin/env python3
"""Prepare a cross-platform, one-command local BrandGuard installation."""
from __future__ import annotations

import argparse
import os
import re
import secrets
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MINIMUM_PYTHON = (3, 11)


def venv_python() -> Path:
    if os.name == "nt":
        return ROOT / ".venv" / "Scripts" / "python.exe"
    return ROOT / ".venv" / "bin" / "python"


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def set_env_value(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^\s*#?\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    replacement = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(replacement, text, count=1)
    return text.rstrip() + f"\n{replacement}\n"


def write_local_env(full: bool) -> dict[str, str]:
    env_path = ROOT / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
    else:
        content = (ROOT / ".env.example").read_text(encoding="utf-8")

    values = parse_env(content)
    secret = values.get("JWT_SECRET", "")
    if not secret:
        content = set_env_value(content, "JWT_SECRET", secrets.token_urlsafe(48))

    # Setup is explicitly for a local judge/demo run: use the offline engine,
    # local demo accounts, and the selected dependency profile.
    local_values = {
        "ENVIRONMENT": "development",
        "LLM_PROVIDER": "mock",
        "DEMO_MODE": "true",
        "BRANDGUARD_LITE": "false" if full else "true",
        "IMAGE_REVIEW_ENABLED": "true" if full else "false",
    }
    if full:
        local_values["OCR_BACKEND"] = "rapidocr"
    for key, value in local_values.items():
        content = set_env_value(content, key, value)

    env_path.write_text(content.rstrip() + "\n", encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    return parse_env(content)


def command_env(env_values: dict[str, str]) -> dict[str, str]:
    result = os.environ.copy()
    # Match normal settings precedence: shell variables override .env. Keep the
    # local demo profile explicit so seeding and image dependency mode agree.
    for key, value in env_values.items():
        result.setdefault(key, value)
    for key in ("ENVIRONMENT", "LLM_PROVIDER", "DEMO_MODE", "BRANDGUARD_LITE", "IMAGE_REVIEW_ENABLED", "OCR_BACKEND"):
        if key in env_values:
            result[key] = env_values[key]
    result["PYTHONPATH"] = str(ROOT) + os.pathsep + result.get("PYTHONPATH", "")
    return result


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up BrandGuard for local use.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Install image/OCR/OpenCV dependencies and enable image review (default: lite).",
    )
    args = parser.parse_args()

    if sys.version_info < MINIMUM_PYTHON:
        print(
            f"BrandGuard setup needs Python 3.11 or newer; found {sys.version.split()[0]}. "
            "Install Python 3.11+ and run this command again.",
            file=sys.stderr,
        )
        return 2

    os.chdir(ROOT)
    existing_env = (ROOT / ".env").read_text(encoding="utf-8") if (ROOT / ".env").is_file() else (ROOT / ".env.example").read_text(encoding="utf-8")
    existing_values = parse_env(existing_env)
    database_url = os.environ.get("DATABASE_URL", existing_values.get("DATABASE_URL", "sqlite:///./brandguard.db"))
    if not database_url.startswith("sqlite:"):
        print(
            "Refusing to run local setup against a non-SQLite database. Set DATABASE_URL to a local SQLite URL "
            "in .env before running setup_local.py.",
            file=sys.stderr,
        )
        return 2
    env_values = write_local_env(args.full)

    python_path = venv_python()
    if not python_path.exists():
        print(f"Creating virtual environment at {ROOT / '.venv'}")
        venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
    if not python_path.exists():
        print("Virtual environment creation did not produce a Python executable.", file=sys.stderr)
        return 2

    env = command_env(env_values)
    requirements = ROOT / "backend" / ("requirements.txt" if args.full else "requirements-lite.txt")
    mode = "full" if args.full else "lite"
    print(f"Installing pinned {mode} dependencies...")
    run([str(python_path), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)], env)

    print("Applying Alembic migrations...")
    run([str(python_path), "-m", "alembic", "upgrade", "head"], env)

    print("Seeding local demo data...")
    seed_code = (
        "from backend.app.database import get_session_factory; "
        "from backend.app.models.models import User; "
        "from backend.app.seed import ensure_demo_users, run_seed; "
        "db=get_session_factory()(); "
        "(run_seed(db) if db.query(User.id).first() is None else ensure_demo_users(db)); "
        "db.commit(); db.close()"
    )
    run([str(python_path), "-c", seed_code], env)

    print("\nSetup complete.")
    print("Start BrandGuard with: python scripts/run_local.py")
    print("Open: http://127.0.0.1:8000")
    print(f"Mode: {mode}; offline mock LLM; DEMO_MODE=true; SQLite")
    if not args.full:
        print("Image review is disabled in lite mode. Use --full to install image-processing dependencies.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode or 1)
