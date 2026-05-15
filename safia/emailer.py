"""Send transactional email via SMTP (env or Streamlit secrets)."""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import streamlit as st


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


def send_contribution_thank_you(
    *,
    to_email: str,
    donor_name: str,
    item_name: str,
    amount_eur: float,
) -> None:
    """Send confirmation email. Raises on failure so the caller can surface an error."""

    cfg = _smtp_settings()
    if not cfg or not cfg.get("from_email"):
        raise RuntimeError("Email is not configured (set SMTP_* env vars or [smtp] in .streamlit/secrets.toml).")

    subject = "Thank you for your gift"
    body = (
        f"Hello {donor_name},\n\n"
        f"Thank you so much for your contribution of €{amount_eur:.2f} toward “{item_name}”.\n"
        "We are incredibly grateful.\n\n"
        "With love,\n"
        "Safia’s family\n"
    )

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
