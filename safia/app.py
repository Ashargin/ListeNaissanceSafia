"""Streamlit entrypoint for the Safia birth wishlist."""

from __future__ import annotations

import json

import html

import streamlit as st
import streamlit.components.v1 as components

from safia.config import Settings, load_settings
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
    db_connect,
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


def _gift_entire_declined_key(item_id: str) -> str:
    """Session flag: user unchecked « full remaining » while amount still equals remaining."""

    return f"gift_entire_declined_{item_id}"


def _sync_gift_entire_checkbox(
    *,
    amt_key: str,
    entire_key: str,
    remaining: int,
    declined_key: str,
) -> None:
    """Keep « gift full remaining » in sync with the amount (runs after ``number_input``)."""

    amt = _amount_from_session(amt_key)
    if amt is None:
        return
    rem = int(remaining)
    if amt != rem:
        st.session_state.pop(declined_key, None)
        st.session_state[entire_key] = False
    elif not st.session_state.get(declined_key):
        st.session_state[entire_key] = True


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


def _render_checkout_new_tab_handoff(url: str) -> None:
    """Open Stripe Checkout in a new tab and show a short notice on this tab."""

    render_outcome_top_spacer()
    safe_href = html.escape(url, quote=True)
    line1 = html.escape(t.CHECKOUT_HANDOFF_LINE1)
    prefix = html.escape(t.CHECKOUT_HANDOFF_LINK_PREFIX)
    link_label = html.escape(t.CHECKOUT_HANDOFF_LINK_TEXT)
    st.markdown(
        f'<div class="safia-checkout-handoff">'
        f'<p style="margin:0 0 0.75rem 0;line-height:1.55;">{line1}</p>'
        f'<p style="margin:0;line-height:1.55;">{prefix}'
        f'<a href="{safe_href}" target="_blank" rel="noopener noreferrer">{link_label}</a>'
        f"</p></div>",
        unsafe_allow_html=True,
    )
    js_url = json.dumps(url)
    components.html(
        f"<script>try{{var u={js_url};var t=window.top||window;if(u)t.open(u,"
        f'"_blank","noopener,noreferrer");}}catch(e){{}}</script>',
        height=1,
    )


def _handle_payment_return(
    *,
    items: list[WishlistItem],
    settings: Settings,
    debug: bool,
) -> bool:
    """Process Stripe or generic return URLs after checkout."""

    contribution_id = query_param_first(st.query_params, "contribution_id")
    session_id = query_param_first(st.query_params, "session_id")

    if session_id and contribution_id:
        stripe_outcome = verify_checkout_return(session_id, contribution_id)
        if stripe_outcome is not None:
            with db_connect(
                database_url=settings.database_url, data_dir=settings.data_dir
            ) as conn:
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

    with db_connect(database_url=settings.database_url, data_dir=settings.data_dir) as conn:
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
    settings: Settings,
    items: list[WishlistItem],
    debug: bool,
) -> None:
    """While the panel shows pending, watch the DB for a return-URL or webhook update."""

    with db_connect(database_url=settings.database_url, data_dir=settings.data_dir) as conn:
        row = get_contribution(conn, contribution_id)
    if row is None:
        return

    status = str(row["status"])
    if status == "pending":
        return

    if status == "confirmed":
        with db_connect(
            database_url=settings.database_url, data_dir=settings.data_dir
        ) as conn:
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
        with db_connect(
            database_url=settings.database_url, data_dir=settings.data_dir
        ) as conn:
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
    settings: Settings,
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
    declined_key = _gift_entire_declined_key(item.id)

    with info_parent:
        if not free and remaining <= 0:
            st.markdown(f"**{t.FULLY_FUNDED}**")
            return

        if panel_open:
            if st.button(t.BTN_CLOSE, key=f"close_contrib_{item.id}"):
                st.session_state.pop(open_key, None)
                st.session_state.pop(pending_key, None)
                st.session_state.pop(_gift_entire_declined_key(item.id), None)
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
                if free:
                    st.number_input(
                        t.LABEL_AMOUNT,
                        min_value=1,
                        max_value=None,
                        step=1,
                        format="%d",
                        key=amt_key,
                        disabled=is_pending,
                    )
                else:
                    st.number_input(
                        t.LABEL_AMOUNT,
                        min_value=1,
                        max_value=max(1, remaining),
                        step=1,
                        format="%d",
                        key=amt_key,
                        disabled=is_pending,
                    )
                    if not is_pending:
                        _sync_gift_entire_checkbox(
                            amt_key=amt_key,
                            entire_key=entire_key,
                            remaining=remaining,
                            declined_key=declined_key,
                        )

            if not free:

                def on_gift_entire_toggle() -> None:
                    if st.session_state.get(entire_key):
                        st.session_state[amt_key] = int(remaining)
                        st.session_state.pop(declined_key, None)
                    else:
                        amt = _amount_from_session(amt_key)
                        if amt is not None and amt == int(remaining):
                            st.session_state[declined_key] = True

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
                    settings=settings,
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
                amount = _amount_from_session(amt_key)
                if amount is None or amount < 1:
                    st.error(t.ERR_AMOUNT_INVALID)
                    return
            else:
                if st.session_state.get(entire_key):
                    amount = remaining
                else:
                    amount = _amount_from_session(amt_key)
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
            st.session_state["checkout_handoff_url"] = payment_url
            st.rerun()


def run() -> None:
    settings = load_settings()
    site = load_site_content(settings.data_dir)
    items = load_wishlist_items(settings.data_dir)
    init_db(database_url=settings.database_url, data_dir=settings.data_dir)

    st.set_page_config(
        page_title=site.page_title,
        layout="wide",
        initial_sidebar_state="collapsed",
        menu_items={"Get help": None, "Report a bug": None, "About": None},
    )
    inject_global_css()

    if _handle_payment_return(items=items, settings=settings, debug=settings.debug):
        return

    handoff_url = st.session_state.pop("checkout_handoff_url", None)
    if handoff_url:
        _render_checkout_new_tab_handoff(handoff_url)
        st.stop()

    if settings.debug:
        st.caption(t.DEBUG_MODE)
    if not stripe_configured():
        st.warning(t.WARN_STRIPE_NOT_CONFIGURED)

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

    with db_connect(database_url=settings.database_url, data_dir=settings.data_dir) as conn:
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
                    settings=settings,
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
