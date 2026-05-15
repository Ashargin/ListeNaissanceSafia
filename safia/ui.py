"""Layout helpers: global CSS, hero header, wishlist rows."""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st
import streamlit.components.v1 as components
from streamlit.delta_generator import DeltaGenerator

from safia.models import SiteContent, WishlistItem


def inject_global_css() -> None:
    """Hide the sidebar and tighten default padding for a single-page layout."""

    st.markdown(
        """
        <style>
          [data-testid="stSidebar"],
          [data-testid="stSidebarNav"],
          [data-testid="collapsedControl"] {
            display: none;
          }
          section[data-testid="stMain"] > div {
            padding-top: 0.75rem;
          }
          section[data-testid="stMain"] {
            overflow-x: hidden;
          }
          section[data-testid="stMain"] .block-container {
            padding-top: 0.25rem;
            padding-left: 3em;
            padding-right: 3em;
            max-width: min(1344px, calc(100vw - 6em));
            margin-left: auto;
            margin-right: auto;
            width: 100%;
            box-sizing: border-box;
          }
          @media (max-width: 768px) {
            section[data-testid="stMain"] .block-container {
              padding-left: 1em;
              padding-right: 1em;
              max-width: calc(100vw - 2em);
            }
          }
          /* Wishlist rows: align columns to top; compact contribution panel */
          div[data-testid="stHorizontalBlock"] {
            align-items: flex-start;
          }
          div[data-testid="stForm"] {
            border: none !important;
            padding: 0 !important;
          }
          div[data-testid="stForm"] [data-testid="stVerticalBlock"] {
            gap: 0.35rem;
          }
          @keyframes safiaSpin {
            to { transform: rotate(360deg); }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(site: SiteContent) -> None:
    """Full-width cover image with title overlay (fixed moderate height)."""

    safe_title = html.escape(site.hero_title)
    safe_url = html.escape(site.cover_image_url, quote=True)
    components.html(
        f"""
        <div style="position:relative;width:100%;height:220px;border-radius:12px;overflow:hidden;
                    box-shadow:0 6px 24px rgba(0,0,0,0.12);margin:0 0 1rem 0;">
          <img src="{safe_url}" alt="" style="width:100%;height:220px;object-fit:cover;display:block;"/>
          <div style="position:absolute;inset:0;background:linear-gradient(0deg,rgba(0,0,0,.55),rgba(0,0,0,.15));"></div>
          <h1 style="position:absolute;left:0;right:0;bottom:18px;margin:0;
                     text-align:center;color:#fff;font-family:system-ui,Segoe UI,sans-serif;
                     font-weight:650;letter-spacing:.01em;text-shadow:0 2px 12px rgba(0,0,0,.45);">
            {safe_title}
          </h1>
        </div>
        """,
        height=240,
    )


def render_intro(site: SiteContent) -> None:
    st.markdown(site.intro_markdown)


def _contribution_panel_open(item_id: str) -> bool:
    if st.session_state.get(f"open_form_{item_id}"):
        return True
    return st.session_state.get(f"pending_payment_{item_id}") is not None


def render_item_card(
    parent: DeltaGenerator,
    item: WishlistItem,
    *,
    contributed_eur: float,
    render_contribution_panel: Callable[[DeltaGenerator, DeltaGenerator, bool], None],
) -> None:
    remaining = max(0.0, float(item.price_eur) - float(contributed_eur))
    progress = 0.0 if item.price_eur <= 0 else min(1.0, float(contributed_eur) / float(item.price_eur))
    panel_open = _contribution_panel_open(item.id)

    with parent:
        # Fixed 50/50 split so opening the panel never changes total page width.
        item_col, panel_col = st.columns(2, gap="medium")

        with item_col:
            img_col, detail_col = st.columns([1, 1.4], gap="small")
            with img_col:
                st.image(item.image_url, width="stretch")
            with detail_col:
                st.subheader(item.name)
                if item.description:
                    st.caption(item.description)
                st.progress(
                    progress,
                    text=f"€{contributed_eur:.2f} of €{item.price_eur:.2f} — €{remaining:.2f} left",
                )
                render_contribution_panel(detail_col, panel_col, panel_open)
