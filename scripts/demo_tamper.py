#!/usr/bin/env python3
"""Safely demonstrate tamper detection against a temporary SQLite copy."""
from __future__ import annotations

import argparse
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.utils.audit_chain import verify_all_chains


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", help="SQLite database path or URL (defaults to DATABASE_URL from .env)")
    args = parser.parse_args()
    configured = args.database or get_settings().database_url_sync
    if "://" not in configured:
        configured = f"sqlite:///{Path(configured).expanduser().resolve().as_posix()}"
    try:
        parsed = make_url(configured)
    except Exception as exc:
        print(f"Invalid database URL: {exc}", file=sys.stderr)
        return 2
    if parsed.get_backend_name() != "sqlite" or not parsed.database or parsed.database == ":memory:":
        print("This demonstration needs a file-backed SQLite database; the configured database is unchanged.", file=sys.stderr)
        return 2

    source = Path(parsed.database).expanduser().resolve()
    if not source.is_file():
        print(f"SQLite database not found: {source}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="brandguard-tamper-demo-") as temp_dir:
        copy_path = Path(temp_dir) / "tampered-copy.sqlite3"
        with sqlite3.connect(source) as original, sqlite3.connect(copy_path) as copy:
            original.backup(copy)
        connection = sqlite3.connect(copy_path)
        try:
            row = connection.execute("SELECT id FROM audit_log ORDER BY sequence_no LIMIT 1").fetchone()
            if row is None:
                print("No audit entries exist yet. Run a submission workflow, then try this demonstration again.", file=sys.stderr)
                return 2
            connection.execute("DROP TRIGGER IF EXISTS audit_log_reject_update")
            connection.execute("DROP TRIGGER IF EXISTS audit_log_reject_delete")
            connection.execute("DROP TRIGGER IF EXISTS audit_log_reject_mutation")
            connection.execute("UPDATE audit_log SET action = action || '_tampered' WHERE id = ?", (row[0],))
            connection.commit()
        finally:
            connection.close()

        engine = create_engine(f"sqlite:///{copy_path.as_posix()}")
        try:
            with Session(engine) as db:
                results = verify_all_chains(db)
        finally:
            engine.dispose()

        invalid = [item for item in results if not item["valid"]]
        if not invalid:
            print("Verifier did not catch the demonstration change.", file=sys.stderr)
            return 1
        print(f"The original database was not modified: {source}")
        print("A disposable temporary SQLite copy was modified and then cleaned up.")
        print(f"Verifier caught tampering in {len(invalid)} chain(s):")
        for chain in invalid:
            print(f"- {chain['scope_id']}: {'; '.join(chain['errors'])}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
