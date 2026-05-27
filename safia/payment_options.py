"""Manual payment methods shown on the post-contribution success page."""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass
from pathlib import Path

import streamlit as st

from safia import texts as t
from safia.models import format_eur


@dataclass(frozen=True, slots=True)
class PaymentOptions:
    lydia_phone: str | None
    wero_phone: str | None
    wero_qr_url: str | None
    paypal_url: str | None
    iban: str | None
    bic: str | None
    account_holder: str | None

    def has_any(self) -> bool:
        return bool(
            self.lydia_phone
            or self.wero_phone
            or self.wero_qr_url
            or self.paypal_url
            or self.iban
        )


def _secret_str(section: str, key: str) -> str | None:
    try:
        sec = st.secrets[section]
        raw = str(sec.get(key, "")).strip()
        return raw or None
    except (FileNotFoundError, KeyError, TypeError, AttributeError):
        return None


def _env_or_payment_secret(env_name: str, secret_key: str) -> str | None:
    raw = os.getenv(env_name, "").strip()
    if raw:
        return raw
    return _secret_str("payment", secret_key)


def _resolve_wero_qr_url(data_dir: Path | None) -> str | None:
    url = _env_or_payment_secret("SAFIA_WERO_QR_URL", "wero_qr_url")
    if url:
        return url
    if data_dir is None:
        return None
    for name in ("wero-qr.png", "wero-qr.jpg", "wero-qr.webp"):
        path = data_dir / name
        if path.is_file():
            return str(path)
    return None


def load_payment_options(*, data_dir: Path | None = None) -> PaymentOptions:
    return PaymentOptions(
        lydia_phone=_env_or_payment_secret("SAFIA_LYDIA_PHONE", "lydia_phone"),
        wero_phone=_env_or_payment_secret("SAFIA_WERO_PHONE", "wero_phone"),
        wero_qr_url=_resolve_wero_qr_url(data_dir),
        paypal_url=_env_or_payment_secret("SAFIA_PAYPAL_URL", "paypal_url"),
        iban=_env_or_payment_secret("SAFIA_IBAN", "iban"),
        bic=_env_or_payment_secret("SAFIA_BIC", "bic"),
        account_holder=_env_or_payment_secret("SAFIA_ACCOUNT_HOLDER", "account_holder"),
    )


def payment_reference(*, donor_name: str, item_name: str, amount_eur: int) -> str:
    return f"{donor_name} — {item_name} — {format_eur(amount_eur)}"


def _render_payment_detail(
    key: str,
    *,
    options: PaymentOptions,
    amount_eur: int,
) -> None:
    if key == "lydia_phone" and options.lydia_phone:
        st.write(f"Envoyer au **{options.lydia_phone}**")
    elif key == "wero_phone" and options.wero_phone:
        st.write(f"Envoyer au **{options.wero_phone}**")
    elif key == "paypal" and options.paypal_url:
        link = paypal_link(options.paypal_url, amount_eur)
        st.link_button(t.PAYMENT_PAYPAL_OPEN, link, type="primary")
    elif key == "iban" and options.iban:
        st.write(f"IBAN : **{options.iban}**")


def paypal_link(base_url: str, amount_eur: int) -> str:
    """Build a PayPal.me link with amount when the base URL has no amount segment."""

    url = base_url.strip().rstrip("/")
    if re.search(r"/\d", url.split("?")[0].split("/")[-1] or ""):
        return url
    if url.lower().endswith("eur"):
        return url
    return f"{url}/{amount_eur}EUR"


def render_payment_methods(
    *,
    options: PaymentOptions,
    amount_eur: int,
    donor_name: str,
    item_name: str,
) -> None:
    if not options.has_any():
        st.warning(t.WARN_PAYMENT_METHODS_NOT_CONFIGURED)
        return

    methods: list[tuple[str, str]] = []
    # Fixed order: Lydia → Wero → PayPal → IBAN
    if options.lydia_phone:
        methods.append(("lydia_phone", f"🟣 {t.PAYMENT_METHOD_LYDIA}"))
    if options.wero_phone:
        methods.append(("wero_phone", f"💠 {t.PAYMENT_METHOD_WERO_PHONE}"))
    if options.paypal_url:
        methods.append(("paypal", f"🟦 {t.PAYMENT_METHOD_PAYPAL}"))
    if options.iban:
        methods.append(("iban", f"🏦 {t.PAYMENT_METHOD_IBAN}"))

    selected_key = "payment_method_selected"
    option_keys = [key for key, _ in methods]
    current = st.session_state.get(selected_key)
    if current not in option_keys:
        current = option_keys[0]
        st.session_state[selected_key] = current

    st.markdown(
        """
        <style>
          section[data-testid="stMain"] #safia-payment-picker-anchor {
            display: none;
          }
          section[data-testid="stMain"] .safia-payment-method-caption {
            margin: 0 0 0.25rem 0 !important;
            line-height: 1.2;
            color: rgba(49, 51, 63, 0.72);
            font-size: 0.95rem;
          }
          section[data-testid="stMain"]
            div[data-testid="column"]:has(.safia-pay-option) {
            flex: 0 0 12rem !important;
            width: 12rem !important;
            max-width: 12rem !important;
            min-width: 12rem !important;
          }
          section[data-testid="stMain"]
            div[data-testid="stHorizontalBlock"]:has(.safia-pay-option) {
            margin-top: 0 !important;
            margin-bottom: 0.075rem !important;
            column-gap: 0.8rem !important;
            gap: 0.8rem !important;
          }
          section[data-testid="stMain"]
            div[data-testid="stHorizontalBlock"]:has(.safia-pay-option)
            > div[data-testid="column"]:nth-child(2) {
            padding-left: 0 !important;
          }
          section[data-testid="stMain"]
            div[data-testid="column"]:has(.safia-pay-option)
            [data-testid="stVerticalBlock"] {
            gap: 0 !important;
          }
          section[data-testid="stMain"] div.element-container:has(.safia-pay-option) {
            width: 12rem !important;
            max-width: 12rem !important;
            margin-bottom: 0 !important;
            padding-bottom: 0 !important;
          }
          section[data-testid="stMain"] .safia-pay-option {
            box-sizing: border-box;
            width: 100%;
            text-align: left;
            padding: 0.45rem 0.7rem;
            border: 1px solid rgba(49, 51, 63, 0.2);
            border-radius: 0.5rem;
            background: #fff;
            margin: 0 !important;
            line-height: 1.35;
            pointer-events: none;
            position: relative;
            z-index: 1;
          }
          section[data-testid="stMain"] .safia-pay-option.is-selected {
            border-color: rgba(49, 51, 63, 0.55);
          }
          section[data-testid="stMain"]
            div.element-container:has(.safia-pay-option)
            + div.element-container:has([data-testid="stButton"]) {
            width: 12rem !important;
            max-width: 12rem !important;
            margin-top: -2.65rem !important;
            margin-bottom: 0 !important;
            height: 2.65rem;
          }
          section[data-testid="stMain"]
            div.element-container:has(.safia-pay-option)
            + div.element-container
            [data-testid="stButton"]
            > button {
            opacity: 0 !important;
            width: 100% !important;
            height: 2.65rem !important;
            min-height: 2.65rem !important;
            cursor: pointer !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown(
            '<div id="safia-payment-picker-anchor" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<p class="safia-payment-method-caption">{html.escape(t.PAYMENT_METHOD_PICK_LABEL)}</p>',
            unsafe_allow_html=True,
        )

        for key, label in methods:
            is_selected = st.session_state.get(selected_key) == key
            opt_col, detail_col = st.columns(
                [0.18, 0.82],
                gap="medium",
                vertical_alignment="center",
            )

            with opt_col:
                marker = "●" if is_selected else "○"
                option_class = (
                    "safia-pay-option is-selected"
                    if is_selected
                    else "safia-pay-option"
                )
                st.markdown(
                    f'<div class="{option_class}">{html.escape(f"{marker} {label}")}</div>',
                    unsafe_allow_html=True,
                )
                clicked = st.button(
                    "\u200b",
                    key=f"payment_method_btn_{key}",
                    type="secondary",
                    width="stretch",
                )
                if clicked and not is_selected:
                    st.session_state[selected_key] = key
                    st.rerun()

            with detail_col:
                if is_selected:
                    _render_payment_detail(key, options=options, amount_eur=amount_eur)
