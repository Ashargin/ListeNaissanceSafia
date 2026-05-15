"""SQLite persistence for contributions (confirmed totals drive progress)."""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path


def db_path(data_dir: Path) -> Path:
    return data_dir / "app.db"


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
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
        )
        conn.commit()
        conn.execute(
            """
            UPDATE contributions
            SET amount_eur = CAST(ROUND(amount_eur) AS INTEGER)
            WHERE amount_eur != CAST(ROUND(amount_eur) AS INTEGER)
            """
        )
        conn.commit()


def confirmed_totals_by_item(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.execute(
        """
        SELECT item_id, COALESCE(SUM(amount_eur), 0)
        FROM contributions
        WHERE status = 'confirmed'
        GROUP BY item_id
        """
    )
    return {str(row[0]): int(row[1]) for row in cur.fetchall()}


def insert_pending_contribution(
    conn: sqlite3.Connection,
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
        """
        INSERT INTO contributions (
            id, item_id, amount_eur, donor_name, donor_email, donor_message, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
        """,
        (cid, item_id, amount_eur, donor_name, donor_email, donor_message, created_at),
    )
    conn.commit()
    return cid


def confirm_contribution(conn: sqlite3.Connection, contribution_id: str) -> bool:
    cur = conn.execute(
        """
        UPDATE contributions
        SET status = 'confirmed'
        WHERE id = ? AND status = 'pending'
        """,
        (contribution_id,),
    )
    conn.commit()
    return cur.rowcount == 1


def fail_contribution(conn: sqlite3.Connection, contribution_id: str) -> bool:
    cur = conn.execute(
        """
        UPDATE contributions
        SET status = 'failed'
        WHERE id = ? AND status = 'pending'
        """,
        (contribution_id,),
    )
    conn.commit()
    return cur.rowcount == 1


def get_contribution(conn: sqlite3.Connection, contribution_id: str) -> Mapping[str, object] | None:
    cur = conn.execute(
        """
        SELECT id, item_id, amount_eur, donor_name, donor_email, donor_message, status, created_at
        FROM contributions
        WHERE id = ?
        """,
        (contribution_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    keys = ("id", "item_id", "amount_eur", "donor_name", "donor_email", "donor_message", "status", "created_at")
    return dict(zip(keys, row, strict=True))
