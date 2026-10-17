#!/usr/bin/env python3
"""Operator tool: claim ownerless (legacy, null user_id) records.

Step 01 quarantines ownerless rows — they are invisible via the API and are
NEVER adopted automatically. This script is the ONLY sanctioned way to
re-own them. Run it by an operator on the server, never in app code.

Usage:
    .venv/bin/python scripts/claim_legacy_records.py --dry-run
    .venv/bin/python scripts/claim_legacy_records.py --apply --user-id <uuid>
    .venv/bin/python scripts/claim_legacy_records.py --dry-run --table jobs

Env: DATABASE_URL (same as the backend). Requires an applied migration set;
this script refuses to run against an unmigrated database.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

USER_OWNED_TABLES: list[str] = ["resumes", "jobs", "applications", "resume_versions"]


def main() -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", default=True,
                        help="count rows that would be claimed (default)")
    parser.add_argument("--apply", action="store_true",
                        help="actually set user_id; requires --user-id")
    parser.add_argument("--user-id", help="the owning user's id (users.id)")
    parser.add_argument("--table", action="append", choices=USER_OWNED_TABLES,
                        help="restrict to specific tables (repeatable)")
    args = parser.parse_args()

    if args.apply and not args.user_id:
        parser.error("--apply requires --user-id")

    from sqlalchemy import text

    from app.core.config import get_settings

    s = get_settings()
    if not s.is_postgres:
        print("refusing: only PostgreSQL databases are supported (source of truth)")
        return 2
    from sqlalchemy import create_engine

    eng = create_engine(s.database_url)
    from app.db.database import require_migrated

    require_migrated(eng)  # sanity: engine-agnostic gate works against PG too

    tables = args.table or USER_OWNED_TABLES
    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"claim_legacy_records [{mode}] target_user={args.user_id or '-'} tables={tables}")
    total = 0
    with eng.begin() as conn:
        for t in tables:
            n = conn.execute(
                text(f"select count(*) from {t} where user_id is null")
            ).scalar_one()
            total += n
            print(f"  {t}: {n} ownerless rows")
    if total == 0:
        print("nothing to claim")
        return 0
    if not args.apply:
        print(f"would claim {total} rows. Re-run with --apply --user-id <uuid> to proceed.")
        return 0
    with eng.begin() as conn:
        # sanity: target user must exist
        exists = conn.execute(
            text("select count(*) from users where id = :uid"),
            {"uid": args.user_id or ""},
        ).scalar_one()
        if not exists:
            print(f"refusing: user {args.user_id} not found")
            return 2
        for t in tables:
            res = conn.execute(
                text(f"update {t} set user_id = :uid where user_id is null"),
                {"uid": args.user_id},
            )
            print(f"  {t}: claimed {res.rowcount} rows")
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
