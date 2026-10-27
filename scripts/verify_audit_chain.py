#!/usr/bin/env python3
"""Verify BrandGuard audit chains directly against the configured database."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.utils.audit_chain import verify_all_chains


def database_url(value: str | None) -> str:
    url = value or get_settings().database_url_sync
    if not url:
        raise ValueError("Set DATABASE_URL in .env or pass --database.")
    return url


def verify_database(url: str) -> list[dict]:
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            return verify_all_chains(db)
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", help="SQLAlchemy database URL (defaults to DATABASE_URL from .env)")
    args = parser.parse_args()
    try:
        url = database_url(args.database)
        make_url(url)
        chains = verify_database(url)
    except Exception as exc:
        print(f"Audit verification could not run: {exc}", file=sys.stderr)
        print("Apply migrations with `python -m alembic upgrade head` and check DATABASE_URL.", file=sys.stderr)
        return 2

    invalid = [chain for chain in chains if not chain["valid"]]
    print(json.dumps({
        "valid": not invalid,
        "total_chains": len(chains),
        "valid_chains": len(chains) - len(invalid),
        "invalid_chains": len(invalid),
        "total_entries": sum(chain["entry_count"] for chain in chains),
        "chains": chains,
    }, indent=2, sort_keys=True))
    if invalid:
        print("TAMPERING OR CHAIN DAMAGE DETECTED", file=sys.stderr)
        return 1
    print("All audit chains are valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
