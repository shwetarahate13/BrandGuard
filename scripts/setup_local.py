#!/usr/bin/env python3
"""Create a complete local BrandGuard environment on macOS, Linux, or Windows."""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINIMUM_PYTHON = (3, 11)
LARGE_REQUIREMENTS = {
    "sentence-transformers",
    "opencv-python",
    "opencv-python-headless",
    "rapidocr-onnxruntime",
    "rapidocr",
    "onnxruntime",
}


def venv_python() -> Path:
    return ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def set_env_value(text: str, key: str, value: str, *, replace: bool = True) -> str:
    pattern = re.compile(rf"^\s*#?\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    if pattern.search(text):
        current = parse_env(text).get(key, "")
        if not replace and current:
            return text
        return pattern.sub(f"{key}={value}", text, count=1)
    return text.rstrip() + f"\n{key}={value}\n"


def write_local_env() -> dict[str, str]:
    env_path = ROOT / ".env"
    content = env_path.read_text(encoding="utf-8") if env_path.exists() else (ROOT / ".env.example").read_text(encoding="utf-8")
    values = parse_env(content)
    if len(values.get("JWT_SECRET", "").encode("utf-8")) < 32:
        content = set_env_value(content, "JWT_SECRET", secrets.token_urlsafe(48))

    # Set safe local defaults without replacing explicit user choices.
    content = set_env_value(content, "ENVIRONMENT", "development")
    defaults = {
        "LLM_PROVIDER": "mock",
        "DEMO_MODE": "true",
        "IMAGE_REVIEW_ENABLED": "true",
        "OCR_BACKEND": "rapidocr",
        "EMBEDDING_MODEL_PATH": "./data/models/all-MiniLM-L6-v2",
    }
    for key, value in defaults.items():
        content = set_env_value(content, key, value, replace=False)

    env_path.write_text(content.rstrip() + "\n", encoding="utf-8")
    try:
        env_path.chmod(0o600)
    except OSError:
        pass
    return parse_env(content)


def command_env(values: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("PIP_DEFAULT_TIMEOUT", "120")
    env.setdefault("PIP_RETRIES", "5")
    env.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "120")
    env.setdefault("HF_HUB_ETAG_TIMEOUT", "30")
    for key, value in values.items():
        env.setdefault(key, value)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def partition_requirements(text: str) -> tuple[list[str], list[str]]:
    """Install ordinary dependencies before the larger model/OCR wheels.

    Splitting the pip transaction reduces peak temporary disk use on a judge's
    laptop while preserving the same pinned requirements and markers.
    """
    base: list[str] = []
    large: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            (large if line.startswith("#") else base).append(raw_line)
            continue
        package = line.split(";", 1)[0].strip().split("[", 1)[0]
        package = package.split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0].lower()
        (large if package in LARGE_REQUIREMENTS else base).append(raw_line)
    return base, large


def run(command: list[str], env: dict[str, str]) -> None:
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def main() -> int:
    if sys.version_info < MINIMUM_PYTHON:
        print(f"BrandGuard needs Python 3.11 or newer; found {sys.version.split()[0]}.", file=sys.stderr)
        return 2

    os.chdir(ROOT)
    env_values = write_local_env()
    python = venv_python()
    if not python.exists():
        print(f"Creating virtual environment at {ROOT / '.venv'}")
        venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
    if not python.exists():
        print("Virtual environment creation failed.", file=sys.stderr)
        return 2

    env = command_env(env_values)
    requirements = ROOT / "backend" / "requirements.txt"
    base_requirements, large_requirements = partition_requirements(requirements.read_text(encoding="utf-8"))
    print("Installing the pinned local runtime in two disk-conscious batches...")
    with tempfile.TemporaryDirectory(prefix="brandguard-setup-") as temp_dir:
        temp_root = Path(temp_dir)
        base_file = temp_root / "requirements-base.txt"
        large_file = temp_root / "requirements-large.txt"
        base_file.write_text("\n".join(base_requirements) + "\n", encoding="utf-8")
        large_file.write_text("\n".join(large_requirements) + "\n", encoding="utf-8")
        pip = [str(python), "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir"]
        print("Installing application and database dependencies...")
        run([*pip, "-r", str(base_file)], env)
        print("Installing OCR and neural retrieval dependencies...")
        run([*pip, "-r", str(large_file)], env)

    model_path = Path(env.get("EMBEDDING_MODEL_PATH", "./data/models/all-MiniLM-L6-v2")).expanduser()
    if not model_path.is_absolute():
        model_path = ROOT / model_path
    if not (model_path / "modules.json").is_file():
        print("Downloading all-MiniLM-L6-v2 for later offline startup (about 100 MB)...")
        download = (
            "from sentence_transformers import SentenceTransformer; "
            f"SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2').save({str(model_path)!r})"
        )
        run([str(python), "-c", download], env)

    print("Applying Alembic migrations...")
    run([str(python), "-m", "alembic", "upgrade", "head"], env)

    print("Seeding local demo accounts and sample content when needed...")
    seed = (
        "from backend.app.config import get_settings; "
        "from backend.app.database import get_session_factory; "
        "from backend.app.seed import run_seed; "
        "settings=get_settings(); db=get_session_factory()(); "
        "(run_seed(db) if settings.DEMO_MODE else None); db.commit(); db.close()"
    )
    run([str(python), "-c", seed], env)

    if not (ROOT / "backend" / "app" / "static" / "index.html").is_file():
        print("The committed frontend bundle is missing; restore backend/app/static before running.", file=sys.stderr)
        return 2

    print("\nSetup complete. Start BrandGuard with: python scripts/run_local.py")
    print("Open http://localhost:8000. Node.js is not required to run the app.")
    print("Local mode uses the mock LLM. Demo logins are available only when DEMO_MODE=true.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode or 1)
