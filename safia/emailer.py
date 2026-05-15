"""Send transactional email via SMTP (env or Streamlit secrets)."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import streamlit as st

from safia.models import format_eur
from safia.texts import (
    EMAIL_NO_MESSAGE,
    EMAIL_OWNER_BODY,
    EMAIL_OWNER_SUBJECT,
    EMAIL_THANK_YOU_BODY,
    EMAIL_THANK_YOU_SUBJECT,
)


def _smtp_settings() -> dict[str, Any] | None:
    """Build SMTP settings from environment variables, then Streamlit secrets."""

    host = os.getenv("SMTP_HOST")
    if not host:
        try:
            sec = st.secrets["smtp"]
        except (FileNotFoundError, KeyError, TypeError):
            return None
        if not sec or not sec.get("host"):
            return None
        return {
            "host": str(sec["host"]),
            "port": int(sec.get("port", 587)),
            "user": str(sec.get("user", "")),
            "password": str(sec.get("password", "")),
            "from_email": str(sec.get("from_email", sec.get("user", ""))),
            "use_tls": bool(sec.get("use_tls", True)),
        }

    return {
        "host": host,
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_email": os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")),
        "use_tls": os.getenv("SMTP_USE_TLS", "1").strip().lower() in {"1", "true", "yes", "on"},
    }


def _notify_email() -> str | None:
    """Address that receives new-contribution alerts (owner)."""

    addr = os.getenv("SAFIA_NOTIFY_EMAIL", "").strip()
    if addr:
        return addr
    try:
        sec = st.secrets["smtp"]
    except (FileNotFoundError, KeyError, TypeError):
        return None
    if not sec:
        return None
    addr = str(sec.get("notify_email", "")).strip()
    return addr or None


def smtp_configured() -> bool:
    cfg = _smtp_settings()
    return bool(cfg and cfg.get("from_email"))


def owner_notify_email() -> str | None:
    """Configured address for new-contribution alerts."""

    return _notify_email()


def notify_email_configured() -> bool:
    return owner_notify_email() is not None


def _send_email(*, to_email: str, subject: str, body: str) -> None:
    cfg = _smtp_settings()
    if not cfg or not cfg.get("from_email"):
        raise RuntimeError("Email is not configured (set SMTP_* env vars or [smtp] in .streamlit/secrets.toml).")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_email"]
    msg["To"] = to_email
    msg.set_content(body)

    host = cfg["host"]
    port = int(cfg["port"])
    user = cfg["user"]
    password = cfg["password"]
    use_tls = bool(cfg["use_tls"])

    if use_tls and port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            if user:
                server.login(user, password)
            server.send_message(msg)
        return

    with smtplib.SMTP(host, port) as server:
        if use_tls:
            context = ssl.create_default_context()
            server.starttls(context=context)
        if user:
            server.login(user, password)
        server.send_message(msg)


def send_contribution_thank_you(
    *,
    to_email: str,
    donor_name: str,
    item_name: str,
    amount_eur: int,
) -> None:
    """Send thank-you email to the donor. Raises on failure."""

    amount = format_eur(amount_eur)
    body = EMAIL_THANK_YOU_BODY.format(
        donor_name=donor_name,
        amount=amount,
        item_name=item_name,
    )
    _send_email(to_email=to_email, subject=EMAIL_THANK_YOU_SUBJECT, body=body)


def send_contribution_owner_notification(
    *,
    to_email: str,
    donor_name: str,
    donor_email: str,
    item_name: str,
    amount_eur: int,
    donor_message: str,
) -> None:
    """Notify the wishlist owner about a confirmed contribution. Raises on failure."""

    message_text = donor_message.strip() or EMAIL_NO_MESSAGE
    amount = format_eur(amount_eur)
    body = EMAIL_OWNER_BODY.format(
        donor_name=donor_name,
        donor_email=donor_email,
        item_name=item_name,
        amount=amount,
        message=message_text,
    )
    _send_email(
        to_email=to_email,
        subject=EMAIL_OWNER_SUBJECT.format(item_name=item_name, amount=amount),
        body=body,
    )
