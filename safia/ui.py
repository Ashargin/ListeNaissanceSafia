"""Layout helpers: global CSS, hero header, wishlist rows."""

from __future__ import annotations

import html
from collections.abc import Callable

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

from safia.models import SiteContent, WishlistItem
from safia.texts import progress_label


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
          /* Item photos: a bit taller than default stretch height so the bottom aligns
             closer to the text block (object-fit keeps cropping natural). */
          section[data-testid="stMain"] [data-testid="stImageContainer"] img,
          section[data-testid="stMain"] a[data-testid="stImageLink"] img {
            min-height: 12.5rem;
            object-fit: cover;
            object-position: center;
            width: 100%;
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
          /* Clear Streamlit header overlap (outcome screens + hero cover) */
          .safia-outcome-top-spacer,
          .safia-hero-top-spacer {
            display: block;
            height: 3.25rem;
            margin: 0;
            padding: 0;
          }
          section[data-testid="stMain"] [data-testid="stIframe"] {
            overflow: visible !important;
          }
          section[data-testid="stMain"] [data-testid="stIframe"] iframe {
            border: none;
            display: block;
          }
          div[data-testid="stMarkdown"]:has(.safia-success-banner),
          div[data-testid="stMarkdownContainer"]:has(.safia-success-banner) {
            overflow: visible !important;
          }
          div.element-container:has(.safia-success-banner) {
            width: 100% !important;
            max-width: 100% !important;
          }
          .safia-success-banner {
            width: 100%;
            max-width: 100%;
            box-sizing: border-box;
          }
          /* Checkout handoff: same readable width as intro, avoid header clipping */
          div[data-testid="stMarkdown"]:has(.safia-checkout-handoff),
          div[data-testid="stMarkdownContainer"]:has(.safia-checkout-handoff) {
            overflow: visible !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_hero(site: SiteContent) -> None:
    """Full-width cover image with title overlay (fixed moderate height)."""

    st.markdown(
        '<div class="safia-hero-top-spacer" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )
    safe_title = html.escape(site.hero_title)
    safe_url = html.escape(site.cover_image_url, quote=True)
    st.iframe(
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


def render_outcome_top_spacer() -> None:
    """Push outcome content below the Streamlit header (avoids white bar covering text)."""

    st.markdown(
        '<div class="safia-outcome-top-spacer" aria-hidden="true"></div>',
        unsafe_allow_html=True,
    )


def render_success_message(message: str) -> None:
    """Green success block; ``\\n\\n`` separates paragraphs inside one banner."""

    paragraphs = [p.strip() for p in message.strip().split("\n\n") if p.strip()]
    parts: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        margin = "0" if index == len(paragraphs) - 1 else "0 0 0.65em 0"
        parts.append(
            f"<p style='margin:{margin};line-height:1.5;'>{html.escape(paragraph)}</p>"
        )
    body = "".join(parts)

    st.markdown(
        f"""
        <div class="safia-success-banner" role="alert" style="
          padding: 1rem 1.25rem;
          margin: 0 0 0.35rem 0;
          border-radius: 0.5rem;
          border: 1px solid rgb(195, 230, 203);
          background-color: rgb(212, 237, 218);
          color: rgb(21, 87, 36);
          font-size: 1rem;
          overflow: visible;
        ">{body}</div>
        """,
        unsafe_allow_html=True,
    )


def _contribution_panel_open(item_id: str) -> bool:
    if st.session_state.get(f"open_form_{item_id}"):
        return True
    return st.session_state.get(f"pending_payment_{item_id}") is not None


def render_item_card(
    parent: DeltaGenerator,
    item: WishlistItem,
    *,
    contributed_eur: int,
    render_contribution_panel: Callable[[DeltaGenerator, DeltaGenerator, bool], None],
) -> None:
    panel_open = _contribution_panel_open(item.id)
    remaining = max(0, item.price_eur - contributed_eur)

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
                if not item.free_contribution:
                    progress = (
                        0.0
                        if item.price_eur <= 0
                        else min(1.0, contributed_eur / item.price_eur)
                    )
                    st.progress(
                        progress,
                        text=progress_label(
                            contributed=contributed_eur,
                            price=item.price_eur,
                            remaining=remaining,
                        ),
                    )
                render_contribution_panel(detail_col, panel_col, panel_open)
