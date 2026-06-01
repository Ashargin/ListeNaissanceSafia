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
    phone_number: str | None
    wero_qr_url: str | None
    paypal_url: str | None
    iban: str | None
    bic: str | None
    account_holder: str | None

    def has_any(self) -> bool:
        return bool(
            self.phone_number
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


def _resolve_phone_number() -> str | None:
    for env_name, secret_key in (
        ("SAFIA_PHONE_NUMBER", "phone_number"),
        ("SAFIA_LYDIA_PHONE", "lydia_phone"),
        ("SAFIA_WERO_PHONE", "wero_phone"),
    ):
        value = _env_or_payment_secret(env_name, secret_key)
        if value:
            return value
    return None


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
        phone_number=_resolve_phone_number(),
        wero_qr_url=_resolve_wero_qr_url(data_dir),
        paypal_url=_env_or_payment_secret("SAFIA_PAYPAL_URL", "paypal_url"),
        iban=_env_or_payment_secret("SAFIA_IBAN", "iban"),
        bic=_env_or_payment_secret("SAFIA_BIC", "bic"),
        account_holder=_env_or_payment_secret("SAFIA_ACCOUNT_HOLDER", "account_holder"),
    )


def payment_reference(*, donor_name: str, item_name: str, amount_eur: int) -> str:
    return f"{donor_name} — {item_name} — {format_eur(amount_eur)}"


def paypal_link(base_url: str, amount_eur: int) -> str:
    """Build a PayPal.me link with amount when the base URL has no amount segment."""

    url = base_url.strip().rstrip("/")
    if re.search(r"/\d", url.split("?")[0].split("/")[-1] or ""):
        return url
    if url.lower().endswith("eur"):
        return url
    return f"{url}/{amount_eur}EUR"


def _payment_instruction_bullets(
    options: PaymentOptions,
    *,
    amount_eur: int,
) -> tuple[list[str], list[str]]:
    """Plain and HTML bullet lines (IBAN → PayPal → Lydia/Wero)."""

    lines_plain: list[str] = []
    lines_html: list[str] = []

    if options.iban:
        lines_plain.append(f"- Virement bancaire à l'IBAN : {options.iban}")
        lines_html.append(
            "- Virement bancaire à l'IBAN : "
            f"<strong>{html.escape(options.iban)}</strong>"
        )

    if options.paypal_url:
        link = paypal_link(options.paypal_url, amount_eur)
        lines_plain.append(f"- PayPal avec ce lien : {link}")
        safe_link = html.escape(link, quote=True)
        lines_html.append(
            f'- PayPal avec <strong><a href="{safe_link}">ce lien</a></strong>'
        )

    if options.phone_number:
        lines_plain.append(f"- Lydia ou Wero au {options.phone_number}")
        lines_html.append(
            "- Lydia ou Wero au "
            f"<strong>{html.escape(options.phone_number)}</strong>"
        )

    return (lines_plain, lines_html)


def format_donor_email_payment_instructions(
    options: PaymentOptions,
    *,
    amount_eur: int,
) -> tuple[str, str]:
    """
    Build the payment reminder block for donor emails.

    Returns ``(plain_text, html_fragment)``. Either may be empty if no methods are configured.
    """

    lines_plain, lines_html = _payment_instruction_bullets(
        options, amount_eur=amount_eur
    )
    if not lines_plain:
        return ("", "")

    intro = t.EMAIL_PAYMENT_INSTRUCTIONS_INTRO
    reminder = t.EMAIL_PAYMENT_NAME_REMINDER
    plain = f"{intro}\n" + "\n".join(lines_plain) + f"\n{reminder}"
    html_block = (
        f"<p>{html.escape(intro)}<br>"
        + "<br>".join(lines_html)
        + f"<br>{html.escape(reminder)}</p>"
    )
    return (plain, html_block)


def render_thank_you_payment_instructions(
    *,
    options: PaymentOptions,
    amount_eur: int,
) -> None:
    """Static payment lines on the thank-you page (same bullets as the donor email)."""

    lines_plain, lines_html = _payment_instruction_bullets(
        options, amount_eur=amount_eur
    )
    if not lines_plain:
        st.warning(t.WARN_PAYMENT_METHODS_NOT_CONFIGURED)
        return

    intro = t.THANK_YOU_PAYMENT_INTRO
    st.markdown(
        f"<p style='margin:0 0 0.35rem 0;line-height:1.5;'>{html.escape(intro)}</p>"
        f"<p style='margin:0 0 0.35rem 0;line-height:1.5;'>"
        + "<br>".join(lines_html)
        + "</p>",
        unsafe_allow_html=True,
    )
