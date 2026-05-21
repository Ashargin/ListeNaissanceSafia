#!/usr/bin/env python3
"""
Wake / keep alive a Streamlit Community Cloud app.

Plain HTTP pings (e.g. UptimeRobot) often return 200 while the app is still
asleep. Streamlit needs a real browser session (JS + WebSocket) to start the
Python process. This script opens the app in headless Chromium and clicks the
sleep-page button when present.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

from playwright.async_api import Frame, Page, async_playwright

TIMEOUT_MS = 180_000
WAKE_WAIT_MS = 120_000
POLL_MS = 2_000

WAKE_BUTTON_PATTERN = (
    r"Yes, get this app back up!|"
    r"get this app back up|"
    r"Réveiller.*application|"
    r"relancer.*application"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_markers() -> list[str]:
    """Text snippets that appear when the real app UI has loaded."""

    raw = os.getenv("KEEPALIVE_MARKER", "").strip()
    if raw:
        return [raw]

    site_path = _repo_root() / "data" / "site.json"
    site = json.loads(site_path.read_text(encoding="utf-8"))

    markers: list[str] = []
    intro = str(site.get("intro_markdown", "")).strip()
    for line in intro.splitlines():
        line = line.strip()
        if len(line) >= 12:
            markers.append(line)
            break

    if intro and "Loïc" in intro:
        markers.append("Loïc")

    hero = str(site.get("hero_title", "")).strip()
    if hero:
        markers.append(hero)

    page_title = str(site.get("page_title", "")).strip()
    if page_title and page_title not in markers:
        markers.append(page_title)

    # Wishlist rows use this button label (French UI).
    markers.append("Contribuer")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for marker in markers:
        if marker not in seen:
            seen.add(marker)
            unique.append(marker)
    return unique


async def _text_visible(target: Page | Frame, marker: str) -> bool:
    try:
        return await target.get_by_text(marker, exact=False).count() > 0
    except Exception:
        return False


async def _marker_visible(page: Page, marker: str) -> bool:
    if await _text_visible(page, marker):
        return True
    for frame in page.frames:
        if frame is page.main_frame:
            continue
        if await _text_visible(frame, marker):
            return True
    return False


async def _wait_for_app_ready(page: Page, markers: list[str]) -> str:
    await page.wait_for_selector(
        '[data-testid="stApp"], [data-testid="stMain"]',
        state="attached",
        timeout=TIMEOUT_MS,
    )

    deadline = time.monotonic() + TIMEOUT_MS / 1000
    while time.monotonic() < deadline:
        for marker in markers:
            if await _marker_visible(page, marker):
                return marker
        await page.wait_for_timeout(POLL_MS)

    msg = f"None of the markers became visible: {markers!r}"
    raise TimeoutError(msg)


async def keepalive(url: str, markers: list[str]) -> bool:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

            wake_btn = page.get_by_role("button", name=re.compile(WAKE_BUTTON_PATTERN, re.I))
            if await wake_btn.count() > 0:
                print("App was sleeping — clicking wake button…")
                await wake_btn.first.click(timeout=30_000)
                await page.wait_for_timeout(WAKE_WAIT_MS)
            else:
                print("No sleep screen detected — loading app UI…")

            found = await _wait_for_app_ready(page, markers)
            print(f"App is up (found marker: {found!r}).")
            return True
        except Exception as exc:
            print(f"Keepalive failed: {exc}", file=sys.stderr)
            return False
        finally:
            await browser.close()


async def main() -> int:
    url = os.getenv("SAFIA_APP_URL", "").strip().rstrip("/")
    if not url:
        print("Set SAFIA_APP_URL to your public Streamlit app URL.", file=sys.stderr)
        return 1

    markers = _load_markers()
    print(f"Looking for any of: {markers!r}")
    ok = await keepalive(url, markers)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
