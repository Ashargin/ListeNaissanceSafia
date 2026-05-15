"""Streamlit entrypoint for the Safia birth wishlist."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import html
import json

import streamlit as st
import streamlit.components.v1 as components

from safia.config import load_settings
from safia.content import load_site_content, load_wishlist_items
from safia.models import WishlistItem
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
from safia.ui import inject_global_css, render_hero, render_intro, render_item_card


def _clear_payment_query_params() -> None:
    for key in ("payment_status", "payment_result", "contribution_id", "session_id", "thank_you"):
        if key in st.query_params:
            del st.query_params[key]


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
                        st.warning("This payment could not be confirmed.")
                        return True
                    st.session_state["thank_you"] = payload
                    st.rerun()

                if finalize_payment_failure(conn, contribution_id):
                    _clear_payment_query_params()
                    st.session_state["payment_failed"] = True
                    st.rerun()

        _clear_payment_query_params()
        st.info("Your payment is still processing. If you completed checkout, wait a moment and refresh.")
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
                st.warning("This payment could not be confirmed.")
                return True
            st.session_state["thank_you"] = payload
            st.rerun()

        if finalize_payment_failure(conn, parsed.contribution_id):
            _clear_payment_query_params()
            st.session_state["payment_failed"] = True
            st.rerun()

    _clear_payment_query_params()
    st.warning("This payment return link is not valid.")
    return True


def _render_thank_you(
    *,
    donor_name: str,
    amount_eur: float,
    item_name: str,
    show_back: bool,
) -> None:
    st.success(
        f"Thank you so much, {donor_name}! "
        f"Your contribution of €{amount_eur:.2f} toward “{item_name}” means a lot to us."
    )
    st.caption(
        "If outgoing email is configured, you should also receive a confirmation message in your inbox."
    )
    if show_back and st.button("Back to wishlist", type="primary"):
        st.session_state.pop("thank_you", None)
        st.rerun()


def _render_payment_failed() -> None:
    st.error("Your payment did not go through. You can try again whenever you like.")
    if st.button("Back to wishlist", type="primary"):
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


def _open_payment_in_new_tab(url: str) -> None:
    """Best-effort: open payment URL in a new tab (may require allowing pop-ups)."""

    safe_url = json.dumps(url)
    components.html(
        f"<script>window.open({safe_url}, '_blank', 'noopener,noreferrer');</script>",
        height=0,
    )


def _render_contribution_panel(
    info_parent,
    panel_parent,
    panel_open: bool,
    *,
    item: WishlistItem,
    contributed_eur: float,
    path: Path,
    app_base_url: str,
    debug: bool,
    items: list[WishlistItem],
) -> None:
    remaining = max(0.0, float(item.price_eur) - float(contributed_eur))
    open_key = f"open_form_{item.id}"
    pending_key = f"pending_payment_{item.id}"
    amt_key = f"amt_{item.id}"
    entire_key = f"entire_{item.id}"

    with info_parent:
        if remaining <= 0:
            st.markdown("**Fully funded — thank you!**")
            return

        if panel_open:
            if st.button("Close", key=f"close_contrib_{item.id}"):
                st.session_state.pop(open_key, None)
                st.session_state.pop(pending_key, None)
                st.rerun()
        elif st.button("Contribute", key=f"toggle_contrib_{item.id}"):
            st.session_state[open_key] = True
            st.rerun()

    if not panel_open:
        return

    with panel_parent:
        with st.container(border=True):
            pending = st.session_state.get(pending_key)
            is_pending = pending is not None

            if not is_pending and amt_key not in st.session_state:
                st.session_state[amt_key] = float(min(50.0, remaining))

            name_key = f"name_{item.id}"
            email_key = f"email_{item.id}"
            msg_key = f"msg_{item.id}"

            def on_gift_entire_toggle() -> None:
                if st.session_state.get(entire_key):
                    st.session_state[amt_key] = round(remaining, 2)

            def on_amount_change() -> None:
                current = round(float(st.session_state[amt_key]), 2)
                st.session_state[entire_key] = current == round(remaining, 2)

            name_col, email_col = st.columns(2)
            with name_col:
                st.text_input("Name", key=name_key, disabled=is_pending)
            with email_col:
                st.text_input("Email", key=email_key, disabled=is_pending)
            st.text_area("Message (optional)", height=72, key=msg_key, disabled=is_pending)

            amount_col, gift_col, pay_col = st.columns(
                [1, 1.1, 0.7],
                gap="small",
                vertical_alignment="bottom",
            )
            with amount_col:
                st.number_input(
                    "Amount (€)",
                    min_value=0.01,
                    max_value=float(remaining),
                    step=1.0,
                    format="%.2f",
                    key=amt_key,
                    on_change=on_amount_change,
                    disabled=is_pending,
                )
            with gift_col:
                st.checkbox(
                    "Gift full remaining",
                    key=entire_key,
                    on_change=on_gift_entire_toggle,
                    disabled=is_pending,
                )
            with pay_col:
                if is_pending:
                    btn_col, spin_col = st.columns([5, 1], gap="small")
                    with btn_col:
                        st.button(
                            "Pending...",
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
                        "Pay",
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
                    "If the link doesn't open, "
                    f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">'
                    "click here</a>.</p>",
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
                        f"[Dev] [Simulate success]({success_url}) · "
                        f"[Simulate failure]({fail_url})"
                    )
                return

            if not pay_clicked:
                return

            donor_name = str(st.session_state.get(name_key, "")).strip()
            donor_email = str(st.session_state.get(email_key, "")).strip()
            donor_message = str(st.session_state.get(msg_key, "")).strip()

            amount = (
                round(remaining, 2)
                if st.session_state.get(entire_key)
                else float(st.session_state.get(amt_key, 0.0))
            )
            if amount <= 0 or amount > remaining + 1e-6:
                st.error("Pick an amount between €0.01 and the remaining balance.")
                return

            if not donor_name:
                st.error("Please enter your name.")
                return
            if "@" not in donor_email or "." not in donor_email.split("@")[-1]:
                st.error("Please enter a valid email address.")
                return
            if not stripe_configured():
                st.error(
                    "Payments are not configured. Set STRIPE_SECRET_KEY in the environment "
                    "or [stripe] in .streamlit/secrets.toml."
                )
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

            st.session_state[pending_key] = {
                "url": payment_url,
                "amount_eur": amount,
                "donor_name": donor_name,
                "contribution_id": contribution_id,
                "item_id": item.id,
            }
            st.session_state[open_key] = True
            _open_payment_in_new_tab(payment_url)
            st.rerun()


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
        st.caption("Debug mode (`SAFIA_DEBUG`)")
    if not stripe_configured():
        st.warning("Stripe is not configured — Pay will not work until STRIPE_SECRET_KEY is set.")

    if _handle_payment_return(items=items, path=path, debug=settings.debug):
        return

    if st.session_state.get("payment_failed"):
        _render_payment_failed()
        return

    thank = st.session_state.get("thank_you")
    if isinstance(thank, dict) and thank:
        _render_thank_you(
            donor_name=str(thank["donor_name"]),
            amount_eur=float(thank["amount_eur"]),
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
        contributed = float(totals.get(item.id, 0.0))

        def make_panel(it: WishlistItem = item, contrib: float = contributed):
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
