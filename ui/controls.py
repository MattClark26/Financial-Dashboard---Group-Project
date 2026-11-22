"""Cross-panel controls shared by every analytical view."""

from __future__ import annotations

from datetime import date

import streamlit as st


EARLIEST_DATE = date(2007, 1, 1)


def render_time_machine(default: date) -> date:
    """Render the historical cutoff slider and return the selected date."""
    st.html(
        f"""
        <div class="rr-control-label">
          <span>TIME MACHINE</span>
          <strong>{default:%B %Y}</strong>
        </div>
        """
    )
    return st.slider(
        "Historical dashboard date",
        min_value=EARLIEST_DATE,
        max_value=date.today(),
        value=default,
        format="MMM YYYY",
        key="as_of",
        label_visibility="collapsed",
    )
