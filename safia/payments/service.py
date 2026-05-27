"""Apply payment outcomes to the database and side effects (email, UI state)."""

from __future__ import annotations

from typing import Any

import streamlit as st

from safia.emailer import (
    owner_notify_email,
    send_contribution_owner_notification,
    send_contribution_thank_you,
    smtp_configured,
)
from safia.texts import (
    CAPTION_NOTIFY_EMAIL,
    WARN_OWNER_EMAIL_FAILED,
    WARN_THANK_YOU_EMAIL_FAILED,
)
from safia.models import WishlistItem
from safia.persistence import (
    DbConnection,
    confirm_contribution,
    get_contribution,
)


def clear_item_panel_state(item_id: str) -> None:
    st.session_state.pop(f"open_form_{item_id}", None)
    st.session_state.pop(f"pending_payment_{item_id}", None)


def _send_payment_emails(row: dict[str, Any], *, item_name: str, debug: bool) -> None:
    if not smtp_configured():
        return

    donor_name = str(row["donor_name"])
    donor_email = str(row["donor_email"])
    amount_eur = int(row["amount_eur"])
    donor_message = str(row.get("donor_message") or "")

    try:
        send_contribution_thank_you(
            to_email=donor_email,
            donor_name=donor_name,
            item_name=item_name,
            amount_eur=amount_eur,
        )
    except Exception as exc:  # noqa: BLE001
        if debug:
            st.exception(exc)
        st.warning(WARN_THANK_YOU_EMAIL_FAILED.format(exc=exc))

    notify_to = owner_notify_email()
    if not notify_to:
        if debug:
            st.caption(CAPTION_NOTIFY_EMAIL)
        return

    try:
        send_contribution_owner_notification(
            to_email=notify_to,
            donor_name=donor_name,
            donor_email=donor_email,
            item_name=item_name,
            amount_eur=amount_eur,
            donor_message=donor_message,
        )
    except Exception as exc:  # noqa: BLE001
        if debug:
            st.exception(exc)
        st.warning(WARN_OWNER_EMAIL_FAILED.format(exc=exc))


def thank_you_payload(row: dict[str, Any], item_name: str) -> dict[str, Any]:
    return {
        "donor_name": str(row["donor_name"]),
        "amount_eur": int(row["amount_eur"]),
        "item_name": item_name,
    }


def finalize_payment_success(
    conn: DbConnection,
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
        row = get_contribution(conn, contribution_id) or row
        _send_payment_emails(row, item_name=item_name, debug=debug)

    row = get_contribution(conn, contribution_id)
    if row is None or str(row["status"]) != "confirmed":
        return None

    clear_item_panel_state(item_id)
    return thank_you_payload(row, item_name)

