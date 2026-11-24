"""Labour-market panel integration for the shared Recession Radar shell."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from .signal import get_signal

TITLE = "Labour market"

_STATUS_LABELS = {
    "green": "CALM",
    "amber": "WATCH",
    "red": "ALERT",
}


def load_labour_market_signal(as_of: object) -> dict:
    """Return Panel 2's score using the dashboard-wide status vocabulary."""
    signal = get_signal(pd.Timestamp(as_of))
    return {
        **signal,
        "source_status": signal["status"],
        "status": _STATUS_LABELS.get(signal["status"], "WATCH"),
    }


def _open_detail() -> None:
    st.session_state["active_panel"] = "labour"


def render(as_of: date, *, signal: dict | None = None, **_: object) -> dict:
    """Render the compact dashboard card and return its shared signal."""
    signal = signal or load_labour_market_signal(as_of)
    st.markdown("## Sahm rule & payrolls")
    st.caption("Does the jobs market confirm the warning from leading indicators?")

    score, state = st.columns([1, 2])
    score.metric("Labour score", f"{signal['score']:.0f} / 100")
    state.markdown(f"### {signal['status']}")
    state.write(signal["verdict"])

    st.button(
        "Explore Labour Market",
        key="labour_market_open",
        width="stretch",
        on_click=_open_detail,
    )
    return signal


def render_detail(as_of: date) -> None:
    """Render Tadhg's complete analytical panel."""
    from .panel import render_panel

    render_panel(as_of)


__all__ = [
    "TITLE",
    "load_labour_market_signal",
    "render",
    "render_detail",
]
