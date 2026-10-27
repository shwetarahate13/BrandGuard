#!/usr/bin/env python3
"""Check local Python, dependencies, storage, database, port, and bundled UI."""
from __future__ import annotations

import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def venv_python() -> Path:
    return ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("DATABASE_URL", "EMBEDDING_MODEL_PATH"):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def print_check(label: str, ok: bool, detail: str, *, warning: bool = False) -> bool:
    state = "WARN" if warning else ("PASS" if ok else "FAIL")
    print(f"[{state}] {label}: {detail}")
    return ok or warning


def dependency_check() -> tuple[bool, str]:
    python = venv_python()
    if not python.is_file():
        return False, "Project virtual environment is missing. Run `python scripts/setup_local.py`."
    check = r'''
from importlib.metadata import distribution, PackageNotFoundError
from packaging.requirements import Requirement
from pathlib import Path
import sys
req_file = Path(sys.argv[1])
missing = []
for raw in req_file.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    req = Requirement(line)
    if req.marker and not req.marker.evaluate():
        continue
    try:
        version = distribution(req.name).version
    except PackageNotFoundError:
        missing.append(req.name)
        continue
    if req.specifier and not req.specifier.contains(version):
        missing.append(f"{req.name} (installed {version}, need {req.specifier})")
print("\n".join(missing))
'''
    result = subprocess.run(
        [str(python), "-c", check, str(ROOT / "backend" / "requirements.txt")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        return False, f"Could not inspect the virtual environment: {result.stderr.strip()}"
    missing = [line for line in result.stdout.splitlines() if line.strip()]
    if missing:
        return False, f"Missing or mismatched: {', '.join(missing)}. Run `python scripts/setup_local.py`."
    return True, "All applicable pinned full-runtime dependencies are installed."


def port_check(port: int = 8000) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True, f"Port {port} is available."
    except OSError:
        return False, f"Port {port} is busy; run `python scripts/run_local.py --port 8001` instead."
    finally:
        sock.close()


def disk_check() -> tuple[bool, str, bool]:
    free = shutil.disk_usage(ROOT).free
    gib = free / (1024**3)
    if gib < 5:
        return False, f"Only {gib:.1f} GiB is free; setup needs several GiB for the full Python runtime and model. Free disk space before setup.", True
    return True, f"{gib:.1f} GiB free.", False


def write_check() -> tuple[bool, str]:
    try:
        with tempfile.NamedTemporaryFile(prefix=".brandguard-doctor-", dir=ROOT, delete=True) as handle:
            handle.write(b"ok")
            handle.flush()
        return True, "Project directory accepts temporary writes."
    except OSError as exc:
        return False, f"Cannot write to the project directory: {exc}. Check folder permissions."


def database_check(values: dict[str, str]) -> tuple[bool, str]:
    url = values.get("DATABASE_URL", "sqlite:///./brandguard.db")
    if url.startswith("sqlite:"):
        raw = url.split("?", 1)[0].removeprefix("sqlite:///")
        if raw in {"", ":memory:"}:
            return True, "SQLite in-memory database is available."
        path = Path(unquote(raw)).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        path = path.resolve()
        if not path.parent.exists():
            return False, f"Database folder is missing: {path.parent}. Run setup first."
        target = path
        created = not path.exists()
        try:
            if created:
                probe = tempfile.NamedTemporaryFile(prefix=".brandguard-doctor-", suffix=".sqlite3", dir=path.parent, delete=False)
                target = Path(probe.name)
                probe.close()
            with sqlite3.connect(str(target), timeout=3) as connection:
                connection.execute("CREATE TEMP TABLE doctor_write_check (value INTEGER)")
                connection.execute("INSERT INTO doctor_write_check(value) VALUES (1)")
                connection.execute("DROP TABLE doctor_write_check")
            return True, "Configured SQLite database accepts writes."
        except Exception as exc:
            return False, f"Cannot write to the configured SQLite database: {exc}. Check file permissions."
        finally:
            if created:
                target.unlink(missing_ok=True)

    python = venv_python()
    if not python.is_file():
        return False, "PostgreSQL driver is unavailable until setup installs the project environment."
    script = "import os, psycopg2; c=psycopg2.connect(os.environ['BG_DOCTOR_DSN'], connect_timeout=3); q=c.cursor(); q.execute('CREATE TEMP TABLE doctor_write_check (value integer)'); q.execute('INSERT INTO doctor_write_check VALUES (1)'); c.rollback(); c.close()"
    env = os.environ.copy()
    env["BG_DOCTOR_DSN"] = url.replace("postgres://", "postgresql://", 1).replace("postgresql+psycopg://", "postgresql+psycopg2://", 1)
    result = subprocess.run([str(python), "-c", script], cwd=ROOT, env=env, capture_output=True, text=True, timeout=10)
    if result.returncode:
        return False, "Cannot connect to the configured PostgreSQL server; check the URL and server availability."
    return True, "Configured PostgreSQL database accepts a connection."


def model_check(values: dict[str, str]) -> tuple[bool, str]:
    path = Path(values.get("EMBEDDING_MODEL_PATH", "./data/models/all-MiniLM-L6-v2")).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    if (path / "modules.json").is_file():
        return True, "Neural retrieval model is downloaded for offline startup."
    return False, "Neural model is missing. Run `python scripts/setup_local.py` while online to download it."


def frontend_check() -> tuple[bool, str]:
    build_dir = ROOT / "backend" / "app" / "static"
    index = build_dir / "index.html"
    if not index.is_file():
        return False, "Committed frontend bundle is missing. Restore backend/app/static from Git."
    import re
    html = index.read_text(encoding="utf-8")
    assets = re.findall(r'''(?:src|href)=["'](/assets/[^"']+)["']''', html)
    missing = [asset for asset in assets if not (build_dir / asset.lstrip("/")).is_file()]
    if missing:
        return False, f"Committed frontend asset is missing: {missing[0]}. Rebuild and commit backend/app/static."
    return True, "Committed SPA bundle and referenced assets are ready; Node.js is not needed to run."


def main() -> int:
    values = read_env()
    checks = []
    version_ok = sys.version_info >= (3, 11)
    checks.append(print_check("Python", version_ok, f"{sys.version.split()[0]}" if version_ok else "Install Python 3.11 or newer."))
    checks.append(print_check("Dependencies", *dependency_check()))
    port_ok, port_detail = port_check()
    checks.append(print_check("Port", port_ok, port_detail, warning=not port_ok))
    disk_ok, disk_detail, disk_warning = disk_check()
    checks.append(print_check("Disk space", disk_ok, disk_detail, warning=disk_warning))
    checks.append(print_check("Project write access", *write_check()))
    checks.append(print_check("Database", *database_check(values)))
    checks.append(print_check("Embedding model", *model_check(values)))
    checks.append(print_check("Frontend bundle", *frontend_check()))
    passed = sum(checks)
    print(f"\n{passed}/{len(checks)} checks passed.")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
