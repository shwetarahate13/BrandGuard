#!/usr/bin/env python3
"""Check local prerequisites without requiring third-party Python packages."""
from __future__ import annotations

import importlib.metadata
import os
import re
import socket
import sqlite3
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if path.is_file():
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
    for key in ("DATABASE_URL", "BRANDGUARD_LITE", "CHROMA_PERSIST_DIR", "ASSET_STORAGE_DIR"):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def print_check(label: str, ok: bool, detail: str, warning: bool = False) -> bool:
    state = "WARN" if warning else ("PASS" if ok else "FAIL")
    print(f"[{state}] {label}: {detail}")
    return ok or warning


def dependency_check(lite: bool) -> tuple[bool, str]:
    requirements = ROOT / "backend" / ("requirements-lite.txt" if lite else "requirements.txt")
    names: list[str] = []
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        match = re.match(r"([A-Za-z0-9_.-]+)", line)
        if match:
            names.append(match.group(1))
    missing = []
    for name in names:
        try:
            importlib.metadata.distribution(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    if missing:
        return False, f"Missing: {', '.join(missing)}. Run `python scripts/setup_local.py{' --full' if not lite else ''}`."
    return True, f"All {len(names)} pinned {'lite' if lite else 'full'} dependencies are installed."


def port_check(port: int = 8000) -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", port))
        return True, f"Port {port} is available."
    except OSError:
        return False, f"Port {port} is busy. Stop its process or run `python scripts/run_local.py --port 8001`."
    finally:
        sock.close()


def database_check(values: dict[str, str]) -> tuple[bool, str]:
    url = values.get("DATABASE_URL", "sqlite:///./brandguard.db")
    if url.startswith("sqlite:"):
        raw = url.split("?", 1)[0].removeprefix("sqlite:///")
        if raw in {"", ":memory:"}:
            with sqlite3.connect(":memory:") as conn:
                conn.execute("CREATE TABLE doctor_write_check (value INTEGER)")
                conn.rollback()
            return True, "SQLite in-memory database accepts writes."
        path = Path(unquote(raw)).expanduser()
        if not path.is_absolute():
            path = ROOT / path
        path = path.resolve()
        if not path.parent.exists():
            return False, f"Database folder does not exist: {path.parent}. Run setup_local.py first."
        created_probe = not path.exists()
        target = path
        try:
            if created_probe:
                handle = tempfile.NamedTemporaryFile(prefix=".brandguard-doctor-", suffix=".db", dir=path.parent, delete=False)
                target = Path(handle.name)
                handle.close()
            connection = sqlite3.connect(str(target), timeout=3)
            table = "doctor_write_check_" + str(os.getpid())
            try:
                connection.execute("BEGIN")
                connection.execute(f'CREATE TABLE "{table}" (value INTEGER)')
                connection.execute(f'INSERT INTO "{table}" VALUES (1)')
                connection.execute(f'DROP TABLE "{table}"')
                connection.commit()
            finally:
                connection.close()
            return True, f"SQLite database is writable: {path}"
        except Exception as exc:
            return False, f"Cannot write to {path}: {exc}. Check folder/file permissions."
        finally:
            if created_probe:
                try:
                    target.unlink()
                except OSError:
                    pass

    try:
        import psycopg2

        dsn = url.replace("postgresql+psycopg2://", "postgresql://", 1).replace("postgres://", "postgresql://", 1)
        connection = psycopg2.connect(dsn, connect_timeout=3)
        try:
            with connection.cursor() as cursor:
                cursor.execute("CREATE TEMP TABLE brandguard_doctor_write_check (value integer)")
                cursor.execute("INSERT INTO brandguard_doctor_write_check VALUES (1)")
            connection.rollback()
        finally:
            connection.close()
        return True, "Configured PostgreSQL database accepts writes."
    except Exception as exc:
        return False, f"Cannot write to the configured database: {exc}. For a judge run, use the default SQLite URL."


def frontend_check() -> tuple[bool, str]:
    candidates = [ROOT / "frontend" / "dist", ROOT / "backend" / "app" / "static"]
    build_dir = next((path for path in candidates if (path / "index.html").is_file()), None)
    if build_dir is None:
        return False, "No prebuilt frontend found. Use Node.js 18+ and run `npm ci --prefix frontend && npm run build --prefix frontend`."
    html = (build_dir / "index.html").read_text(encoding="utf-8")
    assets = re.findall(r'''(?:src|href)=["'](/assets/[^"']+)["']''', html)
    missing = [asset for asset in assets if not (build_dir / asset.lstrip("/")).is_file()]
    if missing:
        return False, f"Frontend bundle is missing {missing[0]}. Rebuild with Node.js 18+ or restore backend/app/static."
    return True, f"Prebuilt frontend is ready in {build_dir.relative_to(ROOT)}; local serving does not need Node.js."


def main() -> int:
    values = read_env()
    lite = values.get("BRANDGUARD_LITE", "true").lower() == "true"
    passed = 0
    total = 5
    version_ok = sys.version_info >= (3, 11)
    if print_check(
        "Python",
        version_ok,
        f"{sys.version.split()[0]}" if version_ok else f"{sys.version.split()[0]} found; install Python 3.11 or newer.",
    ):
        passed += 1
    if print_check("Dependencies", *dependency_check(lite)):
        passed += 1
    port_ok, port_detail = port_check()
    if print_check("Port", port_ok, port_detail, warning=not port_ok):
        passed += 1
    if print_check("Database write access", *database_check(values)):
        passed += 1
    if print_check("Frontend build", *frontend_check()):
        passed += 1
    print(f"\n{passed}/{total} checks passed.")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
