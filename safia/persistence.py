"""Contribution storage: PostgreSQL when configured, else local SQLite."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DbConnection = Any

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS contributions (
    id TEXT PRIMARY KEY,
    item_id TEXT NOT NULL,
    amount_eur INTEGER NOT NULL,
    donor_name TEXT NOT NULL,
    donor_email TEXT NOT NULL,
    donor_message TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
)
"""


def db_path(data_dir: Path) -> Path:
    return data_dir / "app.db"


def _is_postgres(conn: DbConnection) -> bool:
    return type(conn).__module__.startswith("psycopg")


def _adapt_sql(sql: str, conn: DbConnection) -> str:
    if _is_postgres(conn):
        return sql.replace("?", "%s")
    return sql


def _commit(conn: DbConnection) -> None:
    conn.commit()


def _row_to_mapping(row: Any) -> Mapping[str, object]:
    if isinstance(row, Mapping):
        return row
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    keys = (
        "id",
        "item_id",
        "amount_eur",
        "donor_name",
        "donor_email",
        "donor_message",
        "status",
        "created_at",
    )
    return dict(zip(keys, row, strict=True))


@contextmanager
def db_connect(
    *,
    database_url: str | None,
    data_dir: Path,
) -> Generator[DbConnection, None, None]:
    """Open a DB connection (PostgreSQL when ``database_url`` is set)."""

    if database_url:
        import psycopg
        from psycopg.rows import dict_row

        with psycopg.connect(database_url, row_factory=dict_row) as conn:
            yield conn
        return

    path = db_path(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        yield conn


def init_db(*, database_url: str | None, data_dir: Path) -> None:
    with db_connect(database_url=database_url, data_dir=data_dir) as conn:
        conn.execute(_adapt_sql(_CREATE_TABLE_SQL, conn))
        _commit(conn)
        if not _is_postgres(conn):
            conn.execute(
                """
                UPDATE contributions
                SET amount_eur = CAST(ROUND(amount_eur) AS INTEGER)
                WHERE amount_eur != CAST(ROUND(amount_eur) AS INTEGER)
                """
            )
            _commit(conn)


def confirmed_totals_by_item(conn: DbConnection) -> dict[str, int]:
    cur = conn.execute(
        _adapt_sql(
            """
        SELECT item_id, COALESCE(SUM(amount_eur), 0)
        FROM contributions
        WHERE status = 'confirmed'
        GROUP BY item_id
        """,
            conn,
        )
    )
    return {str(row[0]): int(row[1]) for row in cur.fetchall()}


def insert_pending_contribution(
    conn: DbConnection,
    *,
    item_id: str,
    amount_eur: int,
    donor_name: str,
    donor_email: str,
    donor_message: str,
) -> str:
    cid = str(uuid.uuid4())
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    conn.execute(
        _adapt_sql(
            """
        INSERT INTO contributions (
            id, item_id, amount_eur, donor_name, donor_email, donor_message, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
            conn,
        ),
        (cid, item_id, amount_eur, donor_name, donor_email, donor_message, created_at),
    )
    _commit(conn)
    return cid


def confirm_contribution(conn: DbConnection, contribution_id: str) -> bool:
    cur = conn.execute(
        _adapt_sql(
            """
        UPDATE contributions
        SET status = 'confirmed'
        WHERE id = ? AND status = 'pending'
        """,
            conn,
        ),
        (contribution_id,),
    )
    _commit(conn)
    return cur.rowcount == 1


def fail_contribution(conn: DbConnection, contribution_id: str) -> bool:
    cur = conn.execute(
        _adapt_sql(
            """
        UPDATE contributions
        SET status = 'failed'
        WHERE id = ? AND status = 'pending'
        """,
            conn,
        ),
        (contribution_id,),
    )
    _commit(conn)
    return cur.rowcount == 1


def get_contribution(conn: DbConnection, contribution_id: str) -> Mapping[str, object] | None:
    cur = conn.execute(
        _adapt_sql(
            """
        SELECT id, item_id, amount_eur, donor_name, donor_email, donor_message, status, created_at
        FROM contributions
        WHERE id = ?
        """,
            conn,
        ),
        (contribution_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    return _row_to_mapping(row)
