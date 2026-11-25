"""Streamlit views for the Financial Stress panel."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.presentation import (
    render_conclusion,
    render_explanation_strip,
    render_quality_grid,
)

from .data import SERIES_SPECS
from .evaluation import BacktestResult, evaluate_alerts
from .presentation import FinancialStressView, load_financial_stress_view
from .scoring import COMPONENT_COLUMNS, COMPONENT_WEIGHTS, StressSignal, score_history


def _enable_live_data() -> None:
    st.session_state["financial_stress_live_enabled"] = True
    st.session_state["data_connection_revision"] = (
        int(st.session_state.get("data_connection_revision", 0)) + 1
    )


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


def _audit_table(view: FinancialStressView) -> pd.DataFrame:
    """Create the dated evidence table offered to users for reproduction."""
    raw = view.analytics.weekly.rename(
        columns={column: f"raw_{column}" for column in view.analytics.weekly.columns}
    )
    standardised = view.analytics.features[list(COMPONENT_COLUMNS.values())]
    scored = view.history[[*COMPONENT_COLUMNS, "score", "breadth", "available"]]
    recession = view.recession_indicator.rename("us_recession")
    return pd.concat([raw, standardised, scored, recession], axis=1).sort_index()


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
              <p class="rr-panel-summary">Combines credit spreads, volatility,
              the Fed stress index and equity drawdown to test whether market
              pressure is broad.</p>
              <p class="rr-panel-verdict">{signal.verdict}</p>
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
        width="stretch",
        theme=None,
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
    if st.button("See full Stress analysis", key="open_stress"):
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
    st.button(
        "Use live public data",
        key="load_live_data",
        on_click=_enable_live_data,
    )
    state = view
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
    render_explanation_strip(
        (
            (
                "CREDIT SPREADS",
                "Investment-grade and high-yield OAS measure the extra yield companies pay above Treasuries. Rising spreads mean funding is becoming more expensive.",
            ),
            (
                "VOLATILITY + BREADTH",
                "VIX captures option-implied uncertainty while STLFSI combines several markets. Agreement across channels matters more than one isolated spike.",
            ),
            (
                "CAUSAL Z-SCORES",
                "Each observation is compared only with the preceding 156 weeks. A +2 reading is two historical standard deviations above its prior baseline.",
            ),
        )
    )
    overview, backtest, sensitivity, method, sources = st.tabs(
        ["Overview", "Backtest", "Sensitivity", "Method", "Sources"]
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
            width="stretch",
            theme=None,
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
        render_conclusion("DATA MODE", state.note)

    with backtest:
        st.html(
            """
            <section class="rr-tab-intro">
              <span>HISTORICAL VALIDATION</span>
              <h2>Did the signal warn before recessions?</h2>
              <p>Move the threshold to test the trade-off between earlier warnings
              and false alarms. An alert must persist for two completed weeks.</p>
            </section>
            """
        )
        with st.container(key="stress_backtest_controls"):
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
        render_quality_grid(
            (
                (f"{result.hits}/{len(result.recessions)}", "Recessions caught"),
                (str(result.false_alarms), "False alarms"),
                (f"{result.precision:.0%}", "Alert precision"),
                (lead, "Median warning"),
            )
        )
        st.plotly_chart(
            _backtest_figure(state, result),
            width="stretch",
            theme=None,
            config={"displayModeBar": False, "responsive": True},
            key="stress_backtest_chart",
        )
        render_conclusion(
            "READ WITH CAUTION",
            "Red bands mark recession episodes. Results are descriptive historical evidence, not a claim that financial stress causes recessions.",
        )

    with sensitivity:
        st.html(
            """
            <section class="rr-tab-intro">
              <span>ROBUSTNESS CHECK</span>
              <h2>Does one weighting choice change the conclusion?</h2>
              <p>Compare the documented baseline with equal and credit-heavy
              alternatives. A robust signal should keep the same broad category.</p>
            </section>
            """
        )
        with st.container(key="stress_sensitivity_controls"):
            preset = st.radio(
                "Weighting scenario",
                ["Baseline", "Equal weights", "Credit-heavy"],
                horizontal=True,
                key="stress_weighting_scenario",
            )
        scenarios = {
            "Baseline": dict(COMPONENT_WEIGHTS),
            "Equal weights": {key: 0.20 for key in COMPONENT_COLUMNS},
            "Credit-heavy": {
                "ig_oas": 0.25,
                "hy_oas": 0.35,
                "vix": 0.15,
                "stlfsi": 0.15,
                "drawdown": 0.10,
            },
        }
        scenario_weights = scenarios[preset]
        scenario_history = score_history(state.analytics, weights=scenario_weights)
        latest_scenario = float(scenario_history["score"].dropna().iloc[-1])
        difference = latest_scenario - signal.score
        render_quality_grid(
            (
                (f"{latest_scenario:.1f}", "Scenario score / 100"),
                (f"{signal.score:.1f}", "Baseline score / 100"),
                (f"{difference:+.1f}", "Difference in points"),
                (signal.status, "Baseline category"),
            )
        )
        weight_rows = "".join(
            (
                '<div class="rr-weight-row">'
                f'<span>{key.replace("_", " ").upper()}</span>'
                f'<b>{value:.0%}</b>'
                '<i><em style="width:'
                f'{value * 100:.0f}%"></em></i></div>'
            )
            for key, value in scenario_weights.items()
        )
        st.html(
            '<section class="rr-weight-panel"><header><span>COMPONENT</span>'
            f'<span>{preset.upper()} WEIGHT</span></header>{weight_rows}</section>'
        )
        render_conclusion(
            "INTERPRETATION",
            "This check changes weights only; it does not refit history. A small score difference supports the conclusion that no single reasonable weighting choice drives the result.",
        )

    with method:
        st.html(
            """
            <section class="rr-tab-intro">
              <span>REPRODUCIBLE PIPELINE</span>
              <h2>From market observations to one stress score</h2>
              <p>Every transformation is dated, causal and documented so another
              analyst can rebuild the same selected-date result.</p>
            </section>
            """
        )
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
        st.html(
            """
            <div class="rr-formula-panel">
              <span>SCORING CONTRACT</span>
              <code>score = weighted_mean(clip(50 + component_z × 50/3, 0, 100))</code>
              <p>A z-score of zero maps to 50. Positive values increase stress;
              negative values reduce it. Every component is bounded before weighting.</p>
            </div>
            """
        )

    with sources:
        st.html(
            """
            <section class="rr-tab-intro">
              <span>PROVENANCE + EXPORT</span>
              <h2>Trace every signal back to its source</h2>
              <p>Identifiers, frequencies and dated evidence remain visible so the
              panel can be audited without relying on the interface alone.</p>
            </section>
            """
        )
        render_quality_grid(
            (
                (state.quality.label, "Data quality"),
                (f"{state.quality.available_series}/6", "Series available"),
                (f"{state.quality.coverage_percent:.0f}%", "Coverage"),
                (f"{state.quality.maximum_lag_days} days", "Maximum lag"),
            )
        )
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
            if key in {"ig_oas", "hy_oas", "vix", "stlfsi", "sp500", "us_recession"}
        ]
        st.dataframe(
            pd.DataFrame(source_rows),
            hide_index=True,
            width="stretch",
            column_config={
                "Source": st.column_config.LinkColumn("Source"),
            },
        )
        render_conclusion(
            "AS-OF DISCIPLINE",
            "Runtime cache files are used when a public endpoint is temporarily unavailable. The selected date is enforced before transformation.",
        )
        audit = _audit_table(state)
        st.download_button(
            "Download dated panel evidence (CSV)",
            data=audit.to_csv(index_label="date"),
            file_name=f"financial-stress-evidence-{signal.as_of:%Y-%m-%d}.csv",
            mime="text/csv",
            key="stress_download_evidence",
        )
        render_conclusion(
            "WHAT THE EXPORT CONTAINS",
            "Raw inputs, causal z-scores, component scores, the composite score, alert breadth and recession reference labels.",
        )
