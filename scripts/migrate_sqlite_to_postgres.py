#!/usr/bin/env python3
"""Copy contributions from local SQLite (data/app.db) to PostgreSQL.

Usage (from repo root):

    set SAFIA_DATABASE_URL=postgresql://user:pass@host/db?sslmode=require
    python scripts/migrate_sqlite_to_postgres.py

Optional: SAFIA_DATA_DIR if your SQLite file is not in ./data.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from safia.persistence import db_path, init_db  # noqa: E402


def _data_dir() -> Path:
    raw = os.getenv("SAFIA_DATA_DIR", "").strip()
    if raw:
        p = Path(raw).expanduser()
        return p.resolve() if p.is_absolute() else (_REPO_ROOT / p).resolve()
    return (_REPO_ROOT / "data").resolve()


def main() -> None:
    url = os.getenv("SAFIA_DATABASE_URL", "").strip() or os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("Set SAFIA_DATABASE_URL (or DATABASE_URL) to your PostgreSQL connection string.")
        sys.exit(1)

    sqlite_file = db_path(_data_dir())
    if not sqlite_file.is_file():
        print(f"No SQLite database at {sqlite_file}")
        sys.exit(1)

    import psycopg
    from psycopg.rows import dict_row

    init_db(database_url=url, data_dir=_data_dir())

    with sqlite3.connect(sqlite_file) as src:
        src.row_factory = sqlite3.Row
        rows = src.execute(
            """
            SELECT id, item_id, amount_eur, donor_name, donor_email, donor_message, status, created_at
            FROM contributions
            ORDER BY created_at
            """
        ).fetchall()

    if not rows:
        print("No rows to migrate.")
        return

    with psycopg.connect(url, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            for row in rows:
                cur.execute(
                    """
                    INSERT INTO contributions (
                        id, item_id, amount_eur, donor_name, donor_email,
                        donor_message, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        row["id"],
                        row["item_id"],
                        row["amount_eur"],
                        row["donor_name"],
                        row["donor_email"],
                        row["donor_message"],
                        row["status"],
                        row["created_at"],
                    ),
                )
        conn.commit()

    print(f"Migrated {len(rows)} contribution(s) into PostgreSQL.")


if __name__ == "__main__":
    main()
