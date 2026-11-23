"""Streamlit views for the Financial Stress panel."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from .data import SERIES_SPECS
from .evaluation import BacktestResult, evaluate_alerts
from .presentation import FinancialStressView, load_financial_stress_view
from .scoring import COMPONENT_COLUMNS, StressSignal


def _history_figure(view: FinancialStressView, weeks: int = 104) -> go.Figure:
    history = view.history["score"].dropna().tail(weeks)
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
    component_bars = "".join(
        (
            f'<span><b>{key.replace("_", " ").upper()}</b>'
            f'<i style="--rr-level:{value:.1f}%"></i></span>'
        )
        for key, value in signal.components.items()
    )
    st.html(f'<div class="rr-component-bars">{component_bars}</div>')
    st.plotly_chart(
        _history_figure(state),
        use_container_width=True,
        config={"displayModeBar": False, "responsive": True},
        key="stress_overview_history",
    )
    latest = state.analytics.features.iloc[-1]
    latest_history = state.history.dropna(subset=["score"]).iloc[-1]
    st.html(
        f"""
        <div class="rr-metric-grid">
          <div class="rr-metric"><span>HY OAS Z</span><strong>{latest['hy_oas_z']:.2f}</strong></div>
          <div class="rr-metric"><span>VIX Z</span><strong>{latest['vix_z']:.2f}</strong></div>
          <div class="rr-metric"><span>ALERT BREADTH</span><strong>{int(latest_history['breadth'])}/5</strong></div>
          <div class="rr-metric"><span>DATA MODE</span><strong>{state.mode}</strong></div>
        </div>
        """
    )
    if st.button("Explore panel", key="open_stress"):
        st.session_state.active_panel = "stress"
        st.rerun()
    return signal


def _component_figure(view: FinancialStressView) -> go.Figure:
    colours = {
        "ig_oas": "#69645b",
        "hy_oas": "#d75f47",
        "vix": "#15130f",
        "stlfsi": "#3c7555",
        "drawdown": "#b27b16",
    }
    figure = go.Figure()
    history = view.analytics.features.tail(156)
    for key, column in COMPONENT_COLUMNS.items():
        figure.add_trace(
            go.Scatter(
                x=history.index,
                y=history[column],
                name=key.replace("_", " ").upper(),
                mode="lines",
                line={"width": 1.8, "color": colours[key]},
                hovertemplate="%{x|%d %b %Y}<br>%{y:.2f}σ<extra>%{fullData.name}</extra>",
            )
        )
    figure.add_hline(y=0, line_color="#aaa194", line_dash="dot")
    figure.update_layout(
        height=430,
        margin={"l": 0, "r": 0, "t": 10, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
            "font": {"family": "monospace", "size": 11, "color": "#15130f"},
        },
        font={"color": "#15130f"},
        xaxis={"gridcolor": "#cbc3b6", "zeroline": False, "tickfont": {"color": "#69645b"}},
        yaxis={
            "gridcolor": "#cbc3b6",
            "zeroline": False,
            "title": "Rolling z-score",
            "tickfont": {"color": "#69645b"},
        },
    )
    return figure


def _backtest_figure(view: FinancialStressView, result: BacktestResult) -> go.Figure:
    history = view.history["score"].dropna()
    figure = go.Figure(
        go.Scatter(
            x=history.index,
            y=history,
            mode="lines",
            name="Stress score",
            line={"color": "#15130f", "width": 2},
            hovertemplate="%{x|%d %b %Y}<br>Stress %{y:.0f}/100<extra></extra>",
        )
    )
    for recession in result.recessions:
        figure.add_vrect(
            x0=recession.start,
            x1=recession.end,
            fillcolor="#d75f47",
            opacity=0.14,
            line_width=0,
        )
    figure.add_hline(
        y=result.alert_threshold,
        line_color="#d75f47",
        line_dash="dash",
        annotation_text=f"Alert {result.alert_threshold:.0f}",
    )
    figure.update_layout(
        height=420,
        margin={"l": 0, "r": 0, "t": 10, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis={"gridcolor": "#cbc3b6"},
        yaxis={"gridcolor": "#cbc3b6", "range": [0, 100], "title": "Stress score"},
    )
    return figure


def render_detail(as_of: date, *, view: FinancialStressView) -> None:
    """Render Rohi Aluede's full-page analysis with method and provenance."""
    actions = st.columns([1, 1, 4], vertical_alignment="center")
    with actions[0]:
        if st.button("Back to all signals", key="back_to_dashboard"):
            st.session_state.active_panel = None
            st.rerun()
    with actions[1]:
        refresh = st.button("Load live public data", key="load_live_data")
    state = load_financial_stress_view(pd.Timestamp(as_of), prefer_live=True) if refresh else view
    signal = state.signal

    st.html(
        f"""
        <section class="rr-detail-hero">
          <div>
            <p class="rr-kicker">PANEL 03 / FINANCIAL STRESS / ROHI ALUEDE</p>
            <h1 class="rr-detail-title">Markets under pressure</h1>
            <p class="rr-detail-lede">
              A multi-market test of whether financial conditions are
              tightening fast enough to threaten real economic activity.
            </p>
          </div>
          <div class="rr-detail-score">
            <strong>{signal.score:.0f}</strong><span>/100 · {signal.status}</span>
          </div>
        </section>
        """
    )
    overview, backtest, method, sources = st.tabs(
        ["Overview", "Backtest", "Method", "Sources"]
    )
    with overview:
        st.html(
            f"""
            <div class="rr-section-head">
              <span>156-WEEK COMPONENT HISTORY</span>
              <strong>{state.mode} · AS OF {signal.as_of:%d %b %Y}</strong>
            </div>
            """
        )
        st.plotly_chart(
            _component_figure(state),
            use_container_width=True,
            config={"displayModeBar": False, "responsive": True},
            key="stress_detail_chart",
        )
        component_items = "".join(
            (
                '<div class="rr-metric"><span>'
                + key.replace("_", " ").upper()
                + f"</span><strong>{value:.0f}/100</strong></div>"
            )
            for key, value in signal.components.items()
        )
        st.html(f'<div class="rr-metric-grid">{component_items}</div>')
        st.info(state.note)

    with backtest:
        threshold = st.slider(
            "Alert threshold",
            min_value=50,
            max_value=90,
            value=67,
            help="An alert must remain above this level for two consecutive weeks.",
            key="stress_backtest_threshold",
        )
        result = evaluate_alerts(
            state.history["score"],
            state.recession_indicator,
            threshold=threshold,
        )
        lead = (
            f"{result.median_lead_weeks:.0f} weeks"
            if result.median_lead_weeks is not None
            else "No matched alert"
        )
        metrics = st.columns(4)
        metrics[0].metric("Recessions caught", f"{result.hits}/{len(result.recessions)}")
        metrics[1].metric("False alarms", result.false_alarms)
        metrics[2].metric("Alert precision", f"{result.precision:.0%}")
        metrics[3].metric("Median warning", lead)
        st.plotly_chart(
            _backtest_figure(state, result),
            use_container_width=True,
            config={"displayModeBar": False, "responsive": True},
            key="stress_backtest_chart",
        )
        st.caption(
            "Red bands mark recession episodes. Results are descriptive historical "
            "evidence, not a claim that financial stress causes recessions."
        )

    with method:
        st.html(
            """
            <div class="rr-method-grid">
              <article class="rr-method-card">
                <span>01 / ALIGN</span>
                <strong>Completed weeks</strong>
                <p>Mixed-frequency inputs are aligned to Friday observations
                without backfilling unavailable values.</p>
              </article>
              <article class="rr-method-card">
                <span>02 / STANDARDISE</span>
                <strong>Causal z-scores</strong>
                <p>Every value is compared only with the preceding 156 weeks;
                the current observation never enters its own baseline.</p>
              </article>
              <article class="rr-method-card">
                <span>03 / SCORE</span>
                <strong>Transparent 0–100</strong>
                <p>Five equally directed components are bounded and weighted,
                then mapped to calm, watch and alert zones.</p>
              </article>
            </div>
            """
        )
        st.code(
            "score = mean(clip(50 + component_z × 50/3, 0, 100))",
            language="python",
        )

    with sources:
        source_rows = [
            {
                "Measure": spec.label,
                "Provider": spec.provider.upper(),
                "Identifier": spec.identifier,
                "Frequency": spec.frequency,
                "Units": spec.units,
                "Source": spec.source_url,
            }
            for key, spec in SERIES_SPECS.items()
            if key in {"ig_oas", "hy_oas", "vix", "stlfsi", "sp500"}
        ]
        st.dataframe(
            pd.DataFrame(source_rows),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Source": st.column_config.LinkColumn("Source"),
            },
        )
        st.caption(
            "Runtime cache files are used when a public endpoint is temporarily "
            "unavailable. The selected date is enforced before transformation."
        )
