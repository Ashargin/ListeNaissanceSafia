"""Streamlit entrypoint for the Safia birth wishlist."""

from __future__ import annotations

import streamlit as st

from safia import texts as t
from safia.config import Settings, load_settings
from safia.payment_options import (
    load_payment_options,
    render_thank_you_payment_instructions,
)
from safia.content import load_site_content, load_wishlist_items
from safia.models import WishlistItem, format_eur
from safia.payments.service import finalize_payment_success
from safia.persistence import (
    db_connect,
    ensure_db_initialized,
    get_cached_confirmed_totals,
    insert_pending_contribution,
    invalidate_confirmed_totals,
)
from safia.ui import (
    inject_global_css,
    render_hero,
    render_intro,
    render_item_card,
    render_outcome_top_spacer,
    render_success_message,
)


def _ensure_amount_integer_field(amt_key: str, *, default: int = 1) -> None:
    """Ensure ``amt_key`` holds an int for ``st.number_input`` (migrate legacy strings)."""

    if amt_key not in st.session_state:
        st.session_state[amt_key] = default
        return
    raw = st.session_state[amt_key]
    if isinstance(raw, bool):
        st.session_state[amt_key] = default
        return
    if isinstance(raw, int):
        return
    if isinstance(raw, float) and raw == int(raw):
        st.session_state[amt_key] = int(raw)
        return
    if isinstance(raw, str):
        s = raw.strip()
        if s.isdigit():
            st.session_state[amt_key] = int(s)
        else:
            st.session_state[amt_key] = default
        return
    st.session_state[amt_key] = default


def _amount_from_session(amt_key: str) -> int | None:
    raw = st.session_state.get(amt_key)
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw == int(raw):
        return int(raw)
    if isinstance(raw, str) and raw.strip().isdigit():
        return int(raw.strip())
    return None


def _render_thank_you(
    *,
    donor_name: str,
    amount_eur: int,
    item_name: str,
    data_dir,
) -> None:
    render_outcome_top_spacer()
    render_success_message(
        t.THANK_YOU_BODY.format(
            donor_name=donor_name,
            amount=format_eur(amount_eur),
            item_name=item_name,
        )
    )
    render_thank_you_payment_instructions(
        options=load_payment_options(data_dir=data_dir),
        amount_eur=amount_eur,
    )
    render_success_message(t.THANK_YOU_EMAIL_CONFIRMATION)

    if st.button(t.BTN_BACK_WISHLIST, type="primary"):
        st.session_state.pop("thank_you", None)
        st.rerun()


def _render_contribution_panel(
    info_parent,
    panel_parent,
    panel_open: bool,
    *,
    item: WishlistItem,
    contributed_eur: int,
    settings: Settings,
    debug: bool,
    items: list[WishlistItem],
) -> None:
    free = item.free_contribution
    remaining = max(0, item.price_eur - contributed_eur)
    open_key = f"open_form_{item.id}"
    amt_key = f"amt_{item.id}"

    with info_parent:
        if not free and remaining <= 0:
            st.markdown(f"**{t.FULLY_FUNDED}**")
            return

        if panel_open:
            if st.button(t.BTN_CLOSE, key=f"close_contrib_{item.id}"):
                st.session_state.pop(open_key, None)
                st.rerun()
        elif st.button(t.BTN_CONTRIBUTE, key=f"toggle_contrib_{item.id}"):
            st.session_state[open_key] = True
            st.rerun()

    if not panel_open:
        return

    with panel_parent:
        with st.container(border=True):
            _ensure_amount_integer_field(amt_key, default=1)
            if not free:
                cur = int(st.session_state[amt_key])
                st.session_state[amt_key] = max(1, min(cur, remaining))
            else:
                cur = int(st.session_state[amt_key])
                st.session_state[amt_key] = max(1, cur)

            name_key = f"name_{item.id}"
            email_key = f"email_{item.id}"
            msg_key = f"msg_{item.id}"

            name_col, email_col = st.columns(2)
            with name_col:
                st.text_input(t.LABEL_NAME, key=name_key)
            with email_col:
                st.text_input(t.LABEL_EMAIL, key=email_key)
            st.text_area(t.LABEL_MESSAGE, height=72, key=msg_key)

            amount_col, pay_col = st.columns(
                [2, 0.7],
                gap="small",
                vertical_alignment="bottom",
            )

            with amount_col:
                st.number_input(
                    t.LABEL_AMOUNT,
                    min_value=1,
                    max_value=None if free else max(1, remaining),
                    step=1,
                    format="%d",
                    key=amt_key,
                )
            with pay_col:
                pay_clicked = st.button(
                    t.BTN_PAY,
                    type="primary",
                    key=f"pay_{item.id}",
                    width="stretch",
                )

            if not pay_clicked:
                return

            donor_name = str(st.session_state.get(name_key, "")).strip()
            donor_email = str(st.session_state.get(email_key, "")).strip()
            donor_message = str(st.session_state.get(msg_key, "")).strip()

            amount = _amount_from_session(amt_key)
            if amount is None:
                st.error(t.ERR_AMOUNT_INVALID)
                return
            if free:
                if amount < 1:
                    st.error(t.ERR_AMOUNT_INVALID)
                    return
            elif amount < 1 or amount > remaining:
                st.error(t.ERR_AMOUNT_RANGE)
                return

            if not donor_name:
                st.error(t.ERR_NAME_REQUIRED)
                return
            if "@" not in donor_email or "." not in donor_email.split("@")[-1]:
                st.error(t.ERR_EMAIL_INVALID)
                return

            with db_connect(
                database_url=settings.database_url, data_dir=settings.data_dir
            ) as conn:
                contribution_id = insert_pending_contribution(
                    conn,
                    item_id=item.id,
                    amount_eur=amount,
                    donor_name=donor_name,
                    donor_email=donor_email,
                    donor_message=donor_message,
                )
                payload = finalize_payment_success(
                    conn,
                    contribution_id,
                    items=items,
                    debug=debug,
                )

            if payload is None:
                st.error("Impossible d'enregistrer votre contribution pour le moment.")
                return

            st.session_state.pop(open_key, None)
            st.session_state["thank_you"] = payload
            invalidate_confirmed_totals()
            st.rerun()


def run() -> None:
    settings = load_settings()
    site = load_site_content(settings.data_dir)

    st.set_page_config(
        page_title=site.page_title,
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get help": None, "Report a bug": None, "About": None},
    )
    inject_global_css()

    items = load_wishlist_items(settings.data_dir)
    ensure_db_initialized(database_url=settings.database_url, data_dir=settings.data_dir)

    if settings.debug:
        st.caption(t.DEBUG_MODE)

    thank = st.session_state.get("thank_you")
    if isinstance(thank, dict) and thank:
        _render_thank_you(
            donor_name=str(thank["donor_name"]),
            amount_eur=int(thank["amount_eur"]),
            item_name=str(thank["item_name"]),
            data_dir=settings.data_dir,
        )
        return

    render_hero(site)
    render_intro(site)
    st.divider()

    totals = get_cached_confirmed_totals(
        database_url=settings.database_url,
        data_dir=settings.data_dir,
    )

    for item in items:
        contributed = totals.get(item.id, 0)

        def make_panel(it: WishlistItem = item, contrib: int = contributed):
            def panel(detail_col, panel_col, is_open: bool):
                _render_contribution_panel(
                    detail_col,
                    panel_col,
                    is_open,
                    item=it,
                    contributed_eur=contrib,
                    settings=settings,
                    debug=settings.debug,
                    items=items,
                )

            return panel

        render_item_card(
            st.container(),
            item,
            contributed_eur=contributed,
            render_contribution_panel=make_panel(),
        )


run()
