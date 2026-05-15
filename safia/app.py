"""Streamlit entrypoint for the Safia birth wishlist."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import html

import streamlit as st

from safia.config import load_settings
from safia.content import load_site_content, load_wishlist_items
from safia.models import WishlistItem, format_eur
import stripe

from safia.payments.return_url import PaymentOutcome, build_return_urls, parse_payment_return, query_param_first
from safia.payments.service import finalize_payment_failure, finalize_payment_success
from safia.payments.stripe_checkout import (
    create_checkout_session,
    stripe_configured,
    verify_checkout_return,
)
from safia.persistence import (
    confirmed_totals_by_item,
    db_path,
    get_contribution,
    init_db,
    insert_pending_contribution,
)
from safia import texts as t
from safia.ui import (
    inject_global_css,
    render_hero,
    render_intro,
    render_item_card,
    render_outcome_top_spacer,
    render_success_message,
)


def _parse_amount_field(raw: object) -> int | None:
    value = str(raw or "").strip()
    if not value.isdigit():
        return None
    return int(value)


def _ensure_amount_field_str(amt_key: str) -> None:
    """``st.text_input`` requires a string; migrate legacy numeric session values."""

    if amt_key not in st.session_state:
        st.session_state[amt_key] = ""
    elif not isinstance(st.session_state[amt_key], str):
        st.session_state[amt_key] = ""


def _clear_payment_query_params() -> None:
    for key in (
        "payment_status",
        "payment_result",
        "contribution_id",
        "session_id",
        "checkout_popup",
        "thank_you",
    ):
        if key in st.query_params:
            del st.query_params[key]


def _redirect_to_checkout(url: str) -> None:
    """Open Stripe Checkout in this tab (no popup — one tab for the whole flow)."""

    safe_url = html.escape(url, quote=True)
    st.markdown(
        f'<meta http-equiv="refresh" content="0;url={safe_url}">',
        unsafe_allow_html=True,
    )


def _handle_payment_return(
    *,
    items: list[WishlistItem],
    path: Path,
    debug: bool,
) -> bool:
    """Process Stripe or generic return URLs after checkout."""

    contribution_id = query_param_first(st.query_params, "contribution_id")
    session_id = query_param_first(st.query_params, "session_id")

    if session_id and contribution_id:
        stripe_outcome = verify_checkout_return(session_id, contribution_id)
        if stripe_outcome is not None:
            with sqlite3.connect(path) as conn:
                if stripe_outcome == PaymentOutcome.SUCCESS:
                    payload = finalize_payment_success(
                        conn,
                        contribution_id,
                        items=items,
                        debug=debug,
                    )
                    _clear_payment_query_params()
                    if payload is None:
                        st.warning(t.PAYMENT_NOT_CONFIRMED)
                        return True
                    st.session_state["thank_you"] = payload
                    st.rerun()

                if finalize_payment_failure(conn, contribution_id):
                    _clear_payment_query_params()
                    st.session_state["payment_failed"] = True
                    st.rerun()

        st.markdown(t.CONFIRMING_PAYMENT)
        if st.button(t.BTN_REFRESH, key="payment_return_refresh"):
            st.rerun()
        return True

    parsed = parse_payment_return(st.query_params)
    if parsed is None:
        return False

    with sqlite3.connect(path) as conn:
        if parsed.outcome == PaymentOutcome.SUCCESS:
            payload = finalize_payment_success(
                conn,
                parsed.contribution_id,
                items=items,
                debug=debug,
            )
            _clear_payment_query_params()
            if payload is None:
                st.warning(t.PAYMENT_NOT_CONFIRMED)
                return True
            st.session_state["thank_you"] = payload
            st.rerun()

        if finalize_payment_failure(conn, parsed.contribution_id):
            _clear_payment_query_params()
            st.session_state["payment_failed"] = True
            st.rerun()

    _clear_payment_query_params()
    st.warning(t.INVALID_RETURN_LINK)
    return True


def _render_thank_you(
    *,
    donor_name: str,
    amount_eur: int,
    item_name: str,
    show_back: bool,
) -> None:
    render_outcome_top_spacer()
    render_success_message(
        t.THANK_YOU_BODY.format(
            donor_name=donor_name,
            amount=format_eur(amount_eur),
            item_name=item_name,
        )
    )
    if show_back:
        if st.button(t.BTN_BACK_WISHLIST, type="primary"):
            st.session_state.pop("thank_you", None)
            st.rerun()


def _render_payment_failed() -> None:
    render_outcome_top_spacer()
    st.error(t.PAYMENT_FAILED)
    if st.button(t.BTN_BACK_WISHLIST, type="primary"):
        st.session_state.pop("payment_failed", None)
        st.rerun()


@st.fragment(run_every=2)
def _poll_pending_payment(
    contribution_id: str,
    *,
    path: Path,
    items: list[WishlistItem],
    debug: bool,
) -> None:
    """While the panel shows pending, watch the DB for a return-URL or webhook update."""

    with sqlite3.connect(path) as conn:
        row = get_contribution(conn, contribution_id)
    if row is None:
        return

    status = str(row["status"])
    if status == "pending":
        return

    if status == "confirmed":
        with sqlite3.connect(path) as conn:
            payload = finalize_payment_success(
                conn,
                contribution_id,
                items=items,
                debug=debug,
            )
        if payload:
            st.session_state["thank_you"] = payload
            st.rerun()
        return

    if status == "failed":
        with sqlite3.connect(path) as conn:
            finalize_payment_failure(conn, contribution_id)
        st.session_state["payment_failed"] = True
        st.rerun()


def _render_contribution_panel(
    info_parent,
    panel_parent,
    panel_open: bool,
    *,
    item: WishlistItem,
    contributed_eur: int,
    path: Path,
    app_base_url: str,
    debug: bool,
    items: list[WishlistItem],
) -> None:
    free = item.free_contribution
    remaining = max(0, item.price_eur - contributed_eur)
    open_key = f"open_form_{item.id}"
    pending_key = f"pending_payment_{item.id}"
    amt_key = f"amt_{item.id}"
    entire_key = f"entire_{item.id}"

    with info_parent:
        if not free and remaining <= 0:
            st.markdown(f"**{t.FULLY_FUNDED}**")
            return

        if panel_open:
            if st.button(t.BTN_CLOSE, key=f"close_contrib_{item.id}"):
                st.session_state.pop(open_key, None)
                st.session_state.pop(pending_key, None)
                st.rerun()
        elif st.button(t.BTN_CONTRIBUTE, key=f"toggle_contrib_{item.id}"):
            st.session_state[open_key] = True
            st.rerun()

    if not panel_open:
        return

    with panel_parent:
        with st.container(border=True):
            pending = st.session_state.get(pending_key)
            is_pending = pending is not None

            if not is_pending:
                _ensure_amount_field_str(amt_key)

            name_key = f"name_{item.id}"
            email_key = f"email_{item.id}"
            msg_key = f"msg_{item.id}"

            name_col, email_col = st.columns(2)
            with name_col:
                st.text_input(t.LABEL_NAME, key=name_key, disabled=is_pending)
            with email_col:
                st.text_input(t.LABEL_EMAIL, key=email_key, disabled=is_pending)
            st.text_area(t.LABEL_MESSAGE, height=72, key=msg_key, disabled=is_pending)

            if free:
                amount_col, pay_col = st.columns(
                    [2, 0.7],
                    gap="small",
                    vertical_alignment="bottom",
                )
            else:
                amount_col, gift_col, pay_col = st.columns(
                    [1, 1.1, 0.7],
                    gap="small",
                    vertical_alignment="bottom",
                )

            with amount_col:
                st.text_input(
                    t.LABEL_AMOUNT,
                    key=amt_key,
                    placeholder=t.AMOUNT_PLACEHOLDER,
                    disabled=is_pending,
                )

            if not free:

                def on_gift_entire_toggle() -> None:
                    if st.session_state.get(entire_key):
                        st.session_state[amt_key] = str(remaining)

                with gift_col:
                    st.checkbox(
                        t.GIFT_FULL_REMAINING,
                        key=entire_key,
                        on_change=on_gift_entire_toggle,
                        disabled=is_pending,
                    )

            with pay_col:
                if is_pending:
                    btn_col, spin_col = st.columns([5, 1], gap="small")
                    with btn_col:
                        st.button(
                            t.BTN_PENDING,
                            disabled=True,
                            type="secondary",
                            width="stretch",
                            key=f"pending_pay_{item.id}",
                        )
                    with spin_col:
                        st.markdown(
                            '<div style="display:block;margin-top:0.55rem;width:16px;height:16px;'
                            "border:2px solid #ddd;border-top-color:#888;border-radius:50%;"
                            'animation:safiaSpin 0.7s linear infinite;"></div>',
                            unsafe_allow_html=True,
                        )
                    pay_clicked = False
                else:
                    pay_clicked = st.button(
                        t.BTN_PAY,
                        type="primary",
                        key=f"pay_{item.id}",
                        width="stretch",
                    )

            if is_pending:
                payment_url = str(pending["url"])
                contribution_id = str(pending["contribution_id"])
                safe_href = html.escape(payment_url, quote=True)
                st.markdown(
                    '<p style="font-size:0.8rem;color:#666;margin:0.35rem 0 0 0;">'
                    f"{t.PENDING_LINK_PREFIX}"
                    f'<a href="{safe_href}">{t.PENDING_LINK_TEXT}</a>.</p>',
                    unsafe_allow_html=True,
                )
                _poll_pending_payment(
                    contribution_id,
                    path=path,
                    items=items,
                    debug=debug,
                )
                if debug:
                    success_url, fail_url = build_return_urls(app_base_url, contribution_id)
                    st.caption(
                        f"[Dev] [{t.DEV_SIMULATE_SUCCESS}]({success_url}) · "
                        f"[{t.DEV_SIMULATE_FAILURE}]({fail_url})"
                    )
                return

            if not pay_clicked:
                return

            donor_name = str(st.session_state.get(name_key, "")).strip()
            donor_email = str(st.session_state.get(email_key, "")).strip()
            donor_message = str(st.session_state.get(msg_key, "")).strip()

            if free:
                amount = _parse_amount_field(st.session_state.get(amt_key))
                if amount is None:
                    st.error(t.ERR_AMOUNT_INVALID)
                    return
                if amount < 1:
                    st.error(t.ERR_AMOUNT_MIN)
                    return
            else:
                if st.session_state.get(entire_key):
                    amount = remaining
                else:
                    amount = _parse_amount_field(st.session_state.get(amt_key))
                    if amount is None:
                        st.error(t.ERR_AMOUNT_INVALID)
                        return
                    if amount < 1 or amount > remaining:
                        st.error(t.ERR_AMOUNT_RANGE)
                        return

            if not donor_name:
                st.error(t.ERR_NAME_REQUIRED)
                return
            if "@" not in donor_email or "." not in donor_email.split("@")[-1]:
                st.error(t.ERR_EMAIL_INVALID)
                return
            if not stripe_configured():
                st.error(t.ERR_STRIPE_NOT_CONFIGURED)
                return

            with sqlite3.connect(path) as conn:
                contribution_id = insert_pending_contribution(
                    conn,
                    item_id=item.id,
                    amount_eur=amount,
                    donor_name=donor_name,
                    donor_email=donor_email,
                    donor_message=donor_message,
                )

            try:
                payment_url = create_checkout_session(
                    contribution_id=contribution_id,
                    item_id=item.id,
                    item_name=item.name,
                    amount_eur=amount,
                    donor_email=donor_email,
                    app_base_url=app_base_url,
                )
            except ValueError as exc:
                st.error(str(exc))
                return
            except stripe.StripeError as exc:
                detail = getattr(exc, "user_message", None) or str(exc)
                st.error(f"Could not start Stripe checkout: {detail}")
                if debug:
                    st.exception(exc)
                return

            st.session_state.pop(open_key, None)
            st.session_state.pop(pending_key, None)
            _redirect_to_checkout(payment_url)
            st.stop()


def run() -> None:
    settings = load_settings()
    site = load_site_content(settings.data_dir)
    items = load_wishlist_items(settings.data_dir)
    path = db_path(settings.data_dir)
    init_db(path)

    st.set_page_config(
        page_title=site.page_title,
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get help": None, "Report a bug": None, "About": None},
    )
    inject_global_css()

    if settings.debug:
        st.caption(t.DEBUG_MODE)
    if not stripe_configured():
        st.warning(t.WARN_STRIPE_NOT_CONFIGURED)

    if _handle_payment_return(items=items, path=path, debug=settings.debug):
        return

    if st.session_state.get("payment_failed"):
        _render_payment_failed()
        return

    thank = st.session_state.get("thank_you")
    if isinstance(thank, dict) and thank:
        _render_thank_you(
            donor_name=str(thank["donor_name"]),
            amount_eur=int(thank["amount_eur"]),
            item_name=str(thank["item_name"]),
            show_back=True,
        )
        return

    render_hero(site)
    render_intro(site)
    st.divider()

    with sqlite3.connect(path) as conn:
        totals = confirmed_totals_by_item(conn)

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
                    path=path,
                    app_base_url=settings.app_base_url,
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
