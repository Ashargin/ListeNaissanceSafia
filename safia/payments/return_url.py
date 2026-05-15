"""Parse payment results from return URLs (browser redirect back to this app)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlencode, urlparse, urlunparse


class PaymentOutcome(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class PaymentReturn:
    """Result of a payment provider redirecting the user back to Safia."""

    outcome: PaymentOutcome
    contribution_id: str


_SUCCESS_VALUES = frozenset({"success", "succeeded", "paid", "completed", "ok"})
_FAILED_VALUES = frozenset({"failed", "failure", "cancelled", "canceled", "error", "declined"})


def query_param_first(query_params, name: str) -> str | None:
    return _first(query_params.get(name))


def _first(value: str | list[str] | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        return value[0] if value else None
    return value


def parse_payment_return(query_params) -> PaymentReturn | None:
    """Read ``payment_status`` + ``contribution_id`` from Streamlit query params."""

    raw_status = _first(query_params.get("payment_status"))
    if raw_status is None:
        raw_status = _first(query_params.get("payment_result"))
    contribution_id = _first(query_params.get("contribution_id"))
    if not raw_status or not contribution_id:
        return None

    status = raw_status.strip().lower()
    if status in _SUCCESS_VALUES:
        return PaymentReturn(outcome=PaymentOutcome.SUCCESS, contribution_id=contribution_id)
    if status in _FAILED_VALUES:
        return PaymentReturn(outcome=PaymentOutcome.FAILED, contribution_id=contribution_id)
    return None


def build_return_urls(app_base_url: str, contribution_id: str) -> tuple[str, str]:
    """Build success and failure URLs for the payment provider to redirect to."""

    base = app_base_url.rstrip("/")
    success_qs = urlencode({"payment_status": "success", "contribution_id": contribution_id})
    failed_qs = urlencode({"payment_status": "failed", "contribution_id": contribution_id})
    return (
        f"{base}?{success_qs}",
        f"{base}?{failed_qs}",
    )


def append_return_urls_to_payment_link(
    payment_url: str,
    *,
    app_base_url: str,
    contribution_id: str,
) -> str:
    """
    Append return URL hints as query parameters.

    Providers that support ``success_url`` / ``cancel_url`` (or similar) in the link
  can read these; others must configure return URLs in their dashboard to point at
    the same query-parameter pattern.
    """

    success_url, cancel_url = build_return_urls(app_base_url, contribution_id)
    parsed = urlparse(payment_url)
    extra = urlencode(
        {
            "success_url": success_url,
            "cancel_url": cancel_url,
            "return_url": success_url,
            "contribution_id": contribution_id,
        }
    )
    separator = "&" if parsed.query else "?"
    new_query = f"{parsed.query}{separator}{extra}" if parsed.query else extra
    return urlunparse(parsed._replace(query=new_query))
