"""The project briefing shown before the analytical workspace."""

from __future__ import annotations

import streamlit as st


def render_intro() -> bool:
    """Render the opening sequence and return whether Continue was pressed."""
    st.html(
        """
        <header class="rr-intro-nav">
          <div class="rr-wordmark">
            <span class="rr-radar-mark" aria-hidden="true">RR</span>
            <span>recession radar</span>
          </div>
          <p class="rr-kicker">UCD / GROUP PROJECT</p>
        </header>
        """
    )
    st.html(
        """
        <section class="rr-intro-copy" aria-labelledby="rr-intro-title">
          <p class="rr-kicker">A FOUR-SIGNAL EARLY WARNING SYSTEM</p>
          <h1 class="rr-intro-title" id="rr-intro-title">
            See what the economy<br>was telling us <em>then.</em>
          </h1>
          <p class="rr-intro-lede">
            Recession Radar brings bond, labour, financial-market and Irish
            exposure signals into one time-aware view—without hiding the
            evidence behind a single score.
          </p>
        </section>
        """
    )
    entered = st.button(
        "Enter the dashboard",
        key="enter_dashboard",
        type="primary",
        use_container_width=False,
    )
    st.html(
        """
        <footer class="rr-intro-foot">
          <span>SCROLL THROUGH HISTORY</span>
          <span>CHANGE THE SIGNAL WEIGHTS</span>
          <span>OPEN ANY PANEL TO GO DEEPER</span>
        </footer>
        """
    )
    return entered
