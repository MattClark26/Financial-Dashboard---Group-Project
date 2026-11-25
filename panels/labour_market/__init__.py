"""Labour-market panel integration for the shared Recession Radar shell."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.presentation import INK, RED

from .data import RELEASE_LAG_DAYS, filter_as_of
from .loaders import cached_series
from .signal import get_signal, labour_reading

TITLE = "Labour market"

_STATUS_LABELS = {
    "green": "CALM",
    "amber": "WATCH",
    "red": "ALERT",
}


def load_labour_market_signal(as_of: object) -> dict:
    """Return Panel 2's score using the dashboard-wide status vocabulary."""
    signal = get_signal(pd.Timestamp(as_of))
    reading = labour_reading(
        pd.Timestamp(as_of),
        cached_series("UNRATE"),
        cached_series("SAHMREALTIME"),
        cached_series("ICSA"),
    )
    return {
        **signal,
        **reading,
        "source_status": signal["status"],
        "status": _STATUS_LABELS.get(signal["status"], "WATCH"),
    }


def _open_detail() -> None:
    st.session_state["active_panel"] = "labour"


def render(as_of: date, *, signal: dict | None = None, **_: object) -> dict:
    """Render the compact dashboard card and return its shared signal."""
    signal = signal or load_labour_market_signal(as_of)
    sahm = signal.get("sahm")
    sahm_label = f"{sahm:.2f}" if sahm is not None else "N/A"
    claims_label = "YES" if signal.get("claims_flagged") else "NO"
    st.html(
        f"""
        <div class="rr-panel-body">
          <div class="rr-panel-title-row">
            <div>
              <h2 class="rr-panel-title">Sahm rule & payrolls</h2>
              <p class="rr-panel-summary">Tests whether unemployment, claims
              and payrolls confirm that economic weakness has reached workers.</p>
              <p class="rr-panel-verdict">{signal["verdict"]}</p>
            </div>
            <div class="rr-score"><strong>{signal["score"]:.0f}</strong>
              <span>/100 · {signal["status"]}</span></div>
          </div>
        </div>
        """
    )

    history = filter_as_of(
        cached_series("SAHMREALTIME"),
        pd.Timestamp(as_of),
        RELEASE_LAG_DAYS["SAHMREALTIME"],
    )
    history = history[history.index >= pd.Timestamp(as_of) - pd.DateOffset(years=10)]
    if not history.empty:
        figure = go.Figure()
        figure.add_scatter(
            x=history.index,
            y=history,
            mode="lines",
            line={"color": INK, "width": 2},
            hovertemplate="%{x|%b %Y}<br>%{y:.2f}<extra></extra>",
        )
        figure.add_hline(y=0.5, line={"color": RED, "dash": "dash"})
        figure.update_layout(
            height=190,
            margin={"l": 36, "r": 12, "t": 12, "b": 28},
            showlegend=False,
            xaxis_title=None,
            yaxis_title=None,
        )
        st.plotly_chart(
            figure,
            width="stretch",
            theme=None,
            config={"displayModeBar": False, "responsive": True},
            key="labour_compact_history",
        )

    st.html(
        f"""
        <div class="rr-metric-grid">
          <div class="rr-metric"><span>SAHM RULE</span><strong>{sahm_label}</strong></div>
          <div class="rr-metric"><span>CLAIMS FLAG</span><strong>{claims_label}</strong></div>
          <div class="rr-metric"><span>DATA MODE</span><strong>CACHED FRED</strong></div>
        </div>
        """
    )

    st.button(
        "See full Labour analysis",
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
