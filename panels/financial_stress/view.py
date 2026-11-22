"""Streamlit views for the Financial Stress panel."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .presentation import FinancialStressView, load_financial_stress_view
from .scoring import COMPONENT_COLUMNS, StressSignal


def _history_figure(view: FinancialStressView, weeks: int = 104) -> go.Figure:
    components = view.analytics.features[list(COMPONENT_COLUMNS.values())]
    history = (50 + components.mean(axis=1) * (50 / 3)).clip(0, 100).dropna().tail(weeks)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=history.index,
            y=history,
            mode="lines",
            line={"color": "#15130f", "width": 2},
            fill="tozeroy",
            fillcolor="rgba(245,189,62,.20)",
            hovertemplate="%{x|%d %b %Y}<br>Stress %{y:.0f}/100<extra></extra>",
        )
    )
    figure.add_hline(y=67, line_color="#aaa194", line_dash="dot")
    figure.add_hline(y=34, line_color="#cbc3b6", line_dash="dot")
    figure.update_layout(
        height=150,
        margin={"l": 0, "r": 0, "t": 4, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False, "range": [0, 100]},
        hoverlabel={"bgcolor": "#15130f", "font_color": "#f2eee6"},
    )
    return figure


def render_overview(
    as_of: date,
    *,
    view: FinancialStressView | None = None,
) -> StressSignal:
    """Render the compact quadrant and return its standard signal."""
    state = view or load_financial_stress_view(pd.Timestamp(as_of))
    signal = state.signal
    st.html(
        f"""
        <div class="rr-panel-body">
          <div class="rr-panel-title-row">
            <div>
              <h2 class="rr-panel-title">Markets under pressure</h2>
              <p class="rr-panel-summary">{signal.verdict}</p>
            </div>
            <div class="rr-score">
              <strong>{signal.score:.0f}</strong><span>/100</span>
            </div>
          </div>
        </div>
        """
    )
    st.plotly_chart(
        _history_figure(state),
        use_container_width=True,
        config={"displayModeBar": False, "responsive": True},
        key="stress_overview_chart",
    )
    latest = state.analytics.features.iloc[-1]
    st.html(
        f"""
        <div class="rr-metric-grid">
          <div class="rr-metric"><span>HY OAS Z</span><strong>{latest['hy_oas_z']:.2f}</strong></div>
          <div class="rr-metric"><span>VIX Z</span><strong>{latest['vix_z']:.2f}</strong></div>
          <div class="rr-metric"><span>DATA MODE</span><strong>{state.mode}</strong></div>
        </div>
        """
    )
    if st.button("Explore panel", key="open_stress"):
        st.session_state.active_panel = "stress"
        st.rerun()
    return signal
