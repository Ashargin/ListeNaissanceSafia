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
from pathlib import Path

from playwright.async_api import async_playwright

TIMEOUT_MS = 120_000
WAKE_WAIT_MS = 120_000
RENDER_WAIT_MS = 5_000

WAKE_BUTTON_PATTERN = (
    r"Yes, get this app back up!|"
    r"get this app back up|"
    r"Réveiller.*application|"
    r"relancer.*application"
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_marker() -> str:
    raw = os.getenv("KEEPALIVE_MARKER", "").strip()
    if raw:
        return raw
    site_path = _repo_root() / "data" / "site.json"
    site = json.loads(site_path.read_text(encoding="utf-8"))
    return str(site["hero_title"]).strip()


async def keepalive(url: str, marker: str) -> bool:
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
            await page.wait_for_timeout(RENDER_WAIT_MS)

            wake_btn = page.get_by_role("button", name=re.compile(WAKE_BUTTON_PATTERN, re.I))
            if await wake_btn.count() > 0:
                print("App was sleeping — clicking wake button…")
                await wake_btn.first.click(timeout=30_000)
                await page.wait_for_timeout(WAKE_WAIT_MS)
            else:
                print("No sleep screen detected — page already reachable.")

            locator = page.get_by_text(marker, exact=False).first
            await locator.wait_for(state="visible", timeout=TIMEOUT_MS)
            print(f"App is up (found marker: {marker!r}).")
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

    marker = _load_marker()
    ok = await keepalive(url, marker)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
