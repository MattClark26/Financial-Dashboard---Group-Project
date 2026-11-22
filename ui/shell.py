"""Shared dashboard chrome and cross-panel status components."""

from __future__ import annotations

from datetime import date

import streamlit as st


def render_topbar(as_of: date) -> None:
    """Render the compact application header."""
    st.html(
        f"""
        <header class="rr-topbar">
          <div class="rr-wordmark">
            <span class="rr-radar-mark" aria-hidden="true">RR</span>
            <span>recession radar</span>
          </div>
          <div class="rr-topbar-centre">
            <span>MACRO EARLY WARNING</span>
            <strong>{as_of:%d %b %Y}</strong>
          </div>
          <span class="rr-topbar-meta">1 OF 4 CONNECTED</span>
        </header>
        """
    )
