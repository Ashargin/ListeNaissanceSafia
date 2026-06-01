"""Typed structures for site copy and wishlist items."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SiteContent:
    """Copy and media shown on the main page (loaded from ``data/site.json``)."""

    page_title: str
    hero_title: str
    cover_image_url: str
    intro_markdown: str


@dataclass(frozen=True, slots=True)
class WishlistItem:
    """One wishlist line (loaded from ``data/items.json``)."""

    id: str
    name: str
    description: str
    price_eur: int
    image_url: str
    payment_url: str
    free_contribution: bool = False


@dataclass(frozen=True, slots=True)
class Contribution:
    """A single contribution row stored in SQLite."""

    id: str
    item_id: str
    amount_eur: int
    donor_name: str
    donor_email: str
    donor_message: str
    status: str
    created_at: str


def format_eur(amount: int) -> str:
    """Format an integer euro amount for display (e.g. ``42€``)."""

    return f"{amount}€"
