"""Stripe Checkout Session creation and return verification."""

from __future__ import annotations

import os
from typing import Any

import streamlit as st
import stripe

from safia.payments.return_url import PaymentOutcome, build_return_urls


def stripe_secret_key() -> str | None:
    """Load Stripe secret key from env or Streamlit secrets."""

    key = os.getenv("STRIPE_SECRET_KEY", "").strip()
    if key:
        return key
    try:
        sec = st.secrets["stripe"]
        key = str(sec.get("secret_key", "")).strip()
        return key or None
    except (FileNotFoundError, KeyError, TypeError, AttributeError):
        return None


def stripe_configured() -> bool:
    return stripe_secret_key() is not None


def create_checkout_session(
    *,
    contribution_id: str,
    item_id: str,
    item_name: str,
    amount_eur: float,
    donor_email: str,
    app_base_url: str,
) -> str:
    """
    Create a Stripe Checkout Session and return its URL (open in a new browser tab).

    Raises ``stripe.StripeError`` or ``ValueError`` on failure.
    """

    secret = stripe_secret_key()
    if not secret:
        msg = "Stripe is not configured (set STRIPE_SECRET_KEY or [stripe] in secrets)."
        raise RuntimeError(msg)

    amount_cents = int(round(float(amount_eur) * 100))
    if amount_cents < 50:
        msg = "Amount must be at least €0.50 for card payments."
        raise ValueError(msg)

    success_url, cancel_url = build_return_urls(app_base_url, contribution_id)
    success_url = f"{success_url}&session_id={{CHECKOUT_SESSION_ID}}"

    stripe.api_key = secret
    session = stripe.checkout.Session.create(
        mode="payment",
        customer_email=donor_email,
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": amount_cents,
                    "product_data": {"name": item_name},
                },
                "quantity": 1,
            }
        ],
        metadata={
            "contribution_id": contribution_id,
            "item_id": item_id,
        },
        success_url=success_url,
        cancel_url=cancel_url,
    )

    if not session.url:
        msg = "Stripe did not return a checkout URL."
        raise RuntimeError(msg)
    return str(session.url)


def verify_checkout_return(session_id: str, contribution_id: str) -> PaymentOutcome | None:
    """
    Confirm a return from Stripe Checkout using ``session_id`` from the success URL.

    Returns ``None`` if the session cannot be verified for this contribution.
    """

    secret = stripe_secret_key()
    if not secret:
        return None

    stripe.api_key = secret
    session: Any = stripe.checkout.Session.retrieve(session_id)

    if str(session.metadata.get("contribution_id", "")) != contribution_id:
        return None

    if session.payment_status == "paid":
        return PaymentOutcome.SUCCESS

    if session.status in {"expired", "complete"} and session.payment_status != "paid":
        return PaymentOutcome.FAILED

    return None
