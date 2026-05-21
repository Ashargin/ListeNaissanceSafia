#!/usr/bin/env python3
"""
Wake / keep alive a Streamlit Community Cloud app.

Plain HTTP pings (e.g. UptimeRobot) often return 200 while the app is still
asleep. Streamlit needs a real browser session (JS + WebSocket) to start the
Python process. Opening the app in headless Chromium is enough; we only click
the sleep-page button when it appears.
"""

from __future__ import annotations

import asyncio
import os
import re
import sys

from playwright.async_api import async_playwright

NAV_TIMEOUT_MS = 90_000
WAKE_WAIT_MS = 90_000
DEFAULT_DWELL_MS = 45_000

WAKE_BUTTON_PATTERN = (
    r"Yes, get this app back up!|"
    r"get this app back up|"
    r"Réveiller.*application|"
    r"relancer.*application"
)


def _dwell_ms() -> int:
    raw = os.getenv("KEEPALIVE_DWELL_SEC", "").strip()
    if raw:
        return max(0, int(raw)) * 1000
    return DEFAULT_DWELL_MS


async def keepalive(url: str) -> bool:
    dwell_ms = _dwell_ms()

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
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=NAV_TIMEOUT_MS,
            )
            status = response.status if response else None
            print(f"Opened {url} (HTTP {status}).")

            wake_btn = page.get_by_role(
                "button", name=re.compile(WAKE_BUTTON_PATTERN, re.I)
            )
            if await wake_btn.count() > 0:
                print("Sleep screen detected — clicking wake button…")
                await wake_btn.first.click(timeout=30_000)
                await page.wait_for_timeout(WAKE_WAIT_MS)
            elif dwell_ms > 0:
                print(f"Staying on page {dwell_ms // 1000}s for WebSocket keep-alive…")
                await page.wait_for_timeout(dwell_ms)

            print("Keepalive visit completed.")
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

    ok = await keepalive(url)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
