"""Apply payment outcomes to the database and side effects (email, UI state)."""

from __future__ import annotations

import sqlite3
from typing import Any

import streamlit as st

from safia.emailer import send_contribution_thank_you
from safia.models import WishlistItem
from safia.persistence import confirm_contribution, fail_contribution, get_contribution


def clear_item_panel_state(item_id: str) -> None:
    st.session_state.pop(f"open_form_{item_id}", None)
    st.session_state.pop(f"pending_payment_{item_id}", None)


def thank_you_payload(row: dict[str, Any], item_name: str) -> dict[str, Any]:
    return {
        "donor_name": str(row["donor_name"]),
        "amount_eur": float(row["amount_eur"]),
        "item_name": item_name,
    }


def finalize_payment_success(
    conn: sqlite3.Connection,
    contribution_id: str,
    *,
    items: list[WishlistItem],
    debug: bool,
) -> dict[str, Any] | None:
    """Confirm contribution, send thank-you email, close panel state. Idempotent."""

    row = get_contribution(conn, contribution_id)
    if row is None:
        return None

    item_id = str(row["item_id"])
    names = {i.id: i.name for i in items}
    item_name = names.get(item_id, "Wishlist item")
    status = str(row["status"])

    if status == "confirmed":
        clear_item_panel_state(item_id)
        return thank_you_payload(row, item_name)

    if status != "pending":
        return None

    if confirm_contribution(conn, contribution_id):
        try:
            send_contribution_thank_you(
                to_email=str(row["donor_email"]),
                donor_name=str(row["donor_name"]),
                item_name=item_name,
                amount_eur=float(row["amount_eur"]),
            )
        except Exception as exc:  # noqa: BLE001
            if debug:
                st.exception(exc)
            st.warning(f"Payment recorded, but the thank-you email could not be sent: {exc}")

    row = get_contribution(conn, contribution_id)
    if row is None or str(row["status"]) != "confirmed":
        return None

    clear_item_panel_state(item_id)
    return thank_you_payload(row, item_name)


def finalize_payment_failure(
    conn: sqlite3.Connection,
    contribution_id: str,
) -> bool:
    """Mark contribution failed and close panel state. Idempotent."""

    row = get_contribution(conn, contribution_id)
    if row is None:
        return False

    item_id = str(row["item_id"])
    status = str(row["status"])

    if status == "failed":
        clear_item_panel_state(item_id)
        return True

    if status != "pending":
        return False

    fail_contribution(conn, contribution_id)
    clear_item_panel_state(item_id)
    return True
