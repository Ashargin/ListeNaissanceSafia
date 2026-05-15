"""Load public site copy and catalog from ``data/`` JSON files."""

from __future__ import annotations

import json
from pathlib import Path

from safia.models import SiteContent, WishlistItem


def _read_json(path: Path) -> dict:
    if not path.is_file():
        msg = f"Missing data file: {path}"
        raise FileNotFoundError(msg)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_site_content(data_dir: Path) -> SiteContent:
    raw = _read_json(data_dir / "site.json")
    try:
        return SiteContent(
            page_title=str(raw["page_title"]),
            hero_title=str(raw["hero_title"]),
            cover_image_url=str(raw["cover_image_url"]),
            intro_markdown=str(raw["intro_markdown"]),
        )
    except KeyError as e:
        msg = f"site.json is missing required field: {e.args[0]!r}"
        raise ValueError(msg) from e


def load_wishlist_items(data_dir: Path) -> list[WishlistItem]:
    raw = _read_json(data_dir / "items.json")
    items_raw = raw.get("items")
    if not isinstance(items_raw, list) or not items_raw:
        msg = "items.json must contain a non-empty 'items' array"
        raise ValueError(msg)

    items: list[WishlistItem] = []
    seen: set[str] = set()
    for row in items_raw:
        if not isinstance(row, dict):
            msg = "Each entry in 'items' must be an object"
            raise TypeError(msg)
        raw_price = row["price_eur"]
        if isinstance(raw_price, bool) or not isinstance(raw_price, (int, float)):
            msg = f"Item {row.get('id', '?')!r}: price_eur must be a number"
            raise TypeError(msg)
        free_contribution = bool(row.get("free_contribution", False))
        price_eur = int(raw_price)
        if price_eur < 0:
            msg = f"Item {row.get('id', '?')!r}: price_eur must be zero or positive"
            raise ValueError(msg)
        if free_contribution and price_eur != 0:
            msg = f"Item {row.get('id', '?')!r}: free_contribution items must have price_eur 0"
            raise ValueError(msg)
        item = WishlistItem(
            id=str(row["id"]),
            name=str(row["name"]),
            description=str(row.get("description", "")),
            price_eur=price_eur,
            image_url=str(row["image_url"]),
            payment_url=str(row.get("payment_url", "")),
            free_contribution=free_contribution,
        )
        if item.id in seen:
            msg = f"Duplicate item id in items.json: {item.id!r}"
            raise ValueError(msg)
        seen.add(item.id)
        items.append(item)
    return items
