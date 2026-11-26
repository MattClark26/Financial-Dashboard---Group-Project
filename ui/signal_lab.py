"""Cross-panel 3D diagnostics and historical strategy comparisons."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from panels.financial_stress.presentation import FinancialStressView


@dataclass(frozen=True)
class StrategyLabResult:
    returns: pd.DataFrame
    cumulative: pd.DataFrame
    exposures: pd.DataFrame
    scores: pd.Series
    phases: pd.Series
    metrics: pd.DataFrame


def classify_recession_phases(
    recession: pd.Series,
    *,
    flank_weeks: int = 26,
) -> pd.Series:
    """Classify expansion, pre-recession, recession and recovery weeks."""
    indicator = recession.fillna(0).astype(float).ge(0.5)
    phases = pd.Series("Expansion", index=indicator.index, dtype="object")
    phases.loc[indicator] = "Recession"

    starts = indicator & ~indicator.shift(1, fill_value=False)
    ends = indicator & ~indicator.shift(-1, fill_value=False)
    for start in indicator.index[starts]:
        before = (phases.index < start) & (phases.index >= start - pd.Timedelta(weeks=flank_weeks))
        phases.loc[before & phases.eq("Expansion")] = "Pre-recession"
    for end in indicator.index[ends]:
        after = (phases.index > end) & (phases.index <= end + pd.Timedelta(weeks=flank_weeks))
        phases.loc[after & phases.eq("Expansion")] = "Recovery"
    return phases


def build_strategy_lab(view: FinancialStressView) -> StrategyLabResult:
    """Compare transparent exposure rules using one-week-lagged signals."""
    prices = pd.to_numeric(view.analytics.weekly["sp500"], errors="coerce").dropna()
    market_returns = prices.pct_change().dropna().rename("Market return")
    scores = view.history["score"].reindex(market_returns.index).ffill().bfill()

    exposures = pd.DataFrame(index=market_returns.index)
    exposures["Buy & hold"] = 1.0
    exposures["Stress-scaled"] = ((100.0 - scores) / 100.0).clip(0.20, 1.0)
    exposures["Alert reducer"] = np.select(
        [scores.ge(67), scores.ge(34)],
        [0.25, 0.65],
        default=1.0,
    )

    # Lagging exposure prevents the strategy from trading on a score not yet known.
    strategy_returns = exposures.shift(1).fillna(1.0).mul(market_returns, axis="index")
    cumulative = (1.0 + strategy_returns).cumprod()
    recession = (
        view.recession_indicator.reindex(market_returns.index, method="ffill")
        .fillna(0)
        .astype(float)
    )
    phases = classify_recession_phases(recession)

    rows = []
    for name in strategy_returns:
        values = strategy_returns[name].dropna()
        annual_return = (1.0 + values).prod() ** (52.0 / len(values)) - 1.0
        annual_volatility = values.std(ddof=1) * np.sqrt(52.0)
        sharpe = (
            values.mean() / values.std(ddof=1) * np.sqrt(52.0)
            if values.std(ddof=1) > 0
            else np.nan
        )
        wealth = (1.0 + values).cumprod()
        drawdown = wealth / wealth.cummax() - 1.0
        rows.append(
            {
                "Strategy": name,
                "Annual return": annual_return,
                "Annual volatility": annual_volatility,
                "Sharpe (0% cash)": sharpe,
                "Maximum drawdown": drawdown.min(),
                "Average exposure": exposures.loc[values.index, name].mean(),
            }
        )
    metrics = pd.DataFrame(rows).set_index("Strategy")
    return StrategyLabResult(
        returns=strategy_returns,
        cumulative=cumulative,
        exposures=exposures,
        scores=scores,
        phases=phases,
        metrics=metrics,
    )


def _terrain_figure(
    view: FinancialStressView,
    *,
    height: int = 650,
    compact: bool = False,
) -> go.Figure:
    labels = ["IG OAS", "HY OAS", "VIX", "STLFSI", "Drawdown"]
    keys = ["ig_oas", "hy_oas", "vix", "stlfsi", "drawdown"]
    history = view.history[keys].dropna(how="all").tail(260)
    colours = history[keys].T.to_numpy()
    figure = go.Figure(
        go.Surface(
            x=history.index,
            y=labels,
            z=history[keys].T.to_numpy(),
            surfacecolor=colours,
            colorscale=[
                [0.00, "#3c7555"],
                [0.33, "#3c7555"],
                [0.34, "#f5bd3e"],
                [0.54, "#f5bd3e"],
                [0.55, "#d75f47"],
                [1.00, "#d75f47"],
            ],
            cmin=0,
            cmax=100,
            opacity=0.5,
            showscale=False,
            contours={"z": {"show": True, "usecolormap": False, "color": "#15130f", "width": 1}},
            hovertemplate="%{x|%d %b %Y}<br>%{y}<br>Stress %{z:.1f}/100<extra></extra>",
        )
    )
    figure.update_layout(
        height=height,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        scene={
            "xaxis_title": "" if compact else "Historical week",
            "yaxis_title": "" if compact else "Market channel",
            "zaxis_title": "" if compact else "Stress score (0–100)",
            "zaxis": {"range": [0, 100]},
            "camera": {
                "eye": {"x": 1.35, "y": 1.35, "z": 0.8}
                if compact
                else {"x": 1.55, "y": 1.55, "z": 0.85}
            },
            "aspectmode": "manual",
            "aspectratio": (
                {"x": 1.55, "y": 1.0, "z": 0.8}
                if compact
                else {"x": 2.15, "y": 1.05, "z": 0.9}
            ),
            "bgcolor": "rgba(0,0,0,0)",
        },
    )
    return figure


def render_signal_lab_preview(
    view: FinancialStressView,
) -> None:
    """Render the Financial Stress terrain inside its four-panel preview."""
    signal = view.signal
    strongest_key, strongest_value = max(
        signal.components.items(),
        key=lambda item: item[1],
    )
    names = {
        "ig_oas": "IG credit",
        "hy_oas": "high-yield credit",
        "vix": "VIX",
        "stlfsi": "STLFSI",
        "drawdown": "equity drawdown",
    }
    breadth = sum(value >= 67 for value in signal.components.values())

    st.plotly_chart(
        _terrain_figure(view, height=300, compact=True),
        width="stretch",
        theme=None,
        config={"displayModeBar": False, "responsive": True, "scrollZoom": False},
        key="signal_lab_terrain_preview",
    )
    st.caption(
        f"3D SIGNAL LAB · {signal.score:.0f}/100 · {signal.status}. "
        f"{breadth} of {len(signal.components)} channels are in ALERT. "
        f"The strongest channel is {names.get(strongest_key, strongest_key)} "
        f"at {strongest_value:.0f}/100."
    )


def _wealth_figure(result: StrategyLabResult) -> go.Figure:
    colours = ["#15130f", "#d75f47", "#3c7555"]
    figure = go.Figure()
    for colour, name in zip(colours, result.cumulative.columns, strict=True):
        figure.add_trace(
            go.Scatter(
                x=result.cumulative.index,
                y=result.cumulative[name],
                mode="lines",
                name=name,
                line={"color": colour, "width": 2.3},
                hovertemplate="%{x|%d %b %Y}<br>Growth of 1: %{y:.2f}<extra>%{fullData.name}</extra>",
            )
        )
    figure.update_layout(
        height=430,
        margin={"l": 0, "r": 0, "t": 20, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.08},
        xaxis={"gridcolor": "#cbc3b6"},
        yaxis={"title": "Growth of €1 (illustrative)", "gridcolor": "#cbc3b6"},
    )
    return figure


def _phase_table(result: StrategyLabResult) -> pd.DataFrame:
    rows = []
    for phase in ("Expansion", "Pre-recession", "Recession", "Recovery"):
        mask = result.phases.eq(phase)
        if not mask.any():
            continue
        for strategy in result.returns:
            values = result.returns.loc[mask, strategy]
            rows.append(
                {
                    "Phase": phase,
                    "Strategy": strategy,
                    "Average annualised return": values.mean() * 52,
                    "Weekly volatility": values.std(ddof=1),
                    "Average stress z-score": ((result.scores.loc[mask] - 50) / (50 / 3)).mean(),
                    "Observations": int(values.count()),
                }
            )
    return pd.DataFrame(rows)


def render_signal_lab(view: FinancialStressView) -> None:
    """Render the Financial Stress terrain and strategy diagnostics."""
    result = build_strategy_lab(view)
    signal = view.signal
    strongest_key, strongest_value = max(
        signal.components.items(),
        key=lambda item: item[1],
    )
    breadth = sum(value >= 67 for value in signal.components.values())
    component_names = {
        "ig_oas": "investment-grade credit",
        "hy_oas": "high-yield credit",
        "vix": "equity volatility",
        "stlfsi": "the St. Louis Fed stress index",
        "drawdown": "equity drawdown",
    }
    st.html(
        """
        <section class="rr-lab-hero">
          <p class="rr-kicker">PANEL 03 / FINANCIAL STRESS / 3D SIGNAL LAB</p>
          <h2>Signal terrain and strategy diagnostics</h2>
          <p>This lab turns market-stress history into a deeper visual diagnostic.
          It compares five causal stress channels across time, then tests how simple
          exposure rules behaved before, during and after recessions.</p>
          <div class="rr-lab-tags"><span>156-WEEK BASELINE</span><span>5 CHANNELS</span>
          <span>NO LOOK-AHEAD</span><span>EXPLANATORY BACKTEST</span></div>
        </section>
        """
    )
    with st.container(key="signal_lab_surface_section"):
        st.html(
            """
            <div class="rr-lab-section-head"><span>01 / STRESS TERRAIN</span>
            <div><h3>Five-dimensional stress surface</h3>
            <p>Rotate or drag the surface to inspect it. Scroll-wheel zoom is disabled
            so the page remains easy to read.</p></div></div>
            """
        )
        st.plotly_chart(
            _terrain_figure(view, height=720),
            width="stretch",
            theme=None,
            config={"displayModeBar": True, "responsive": True, "scrollZoom": False},
            key="signal_lab_terrain",
        )
        st.html(
            f"""
            <div class="rr-lab-reading-grid">
              <article><span>TIME</span><strong>Left to right</strong><p>Each slice is one
              completed historical week.</p></article>
              <article><span>HEIGHT</span><strong>Stress, not return</strong><p>Values above
              67 enter ALERT. Values below 34 are comparatively calm.</p></article>
              <article><span>COLOUR</span><strong>Early warning</strong><p>Red begins at
              55/100 to reveal pressure before the formal alert threshold.</p></article>
              <article><span>SHAPE</span><strong>Signal breadth</strong><p>A ridge across
              rows means several markets are warning together.</p></article>
            </div>
            <div class="rr-lab-current"><span>CURRENT SELECTED-DATE READING</span>
            <strong>{signal.score:.0f}/100 · {signal.status}</strong>
            <p>{breadth} of {len(signal.components)} channels are in ALERT. The strongest
            channel is {component_names.get(strongest_key, strongest_key)} at
            {strongest_value:.0f}/100. {signal.verdict}</p></div>
            """
        )

    with st.container(key="signal_lab_strategy_section"):
        st.html(
            """
            <div class="rr-lab-section-head"><span>02 / STRATEGY TEST</span>
            <div><h3>Three transparent exposure rules</h3>
            <p>Buy and hold remains fully invested. Stress-scaled exposure falls
            gradually as stress rises. Alert reducer moves from 100% to 65% and then
            25% exposure. Every rule uses the previous week's score.</p></div></div>
            """
        )
        st.plotly_chart(
            _wealth_figure(result),
            width="stretch",
            theme=None,
            config={"displayModeBar": False, "responsive": True, "scrollZoom": False},
            key="signal_lab_wealth",
        )
        formatted = result.metrics.reset_index()
        st.dataframe(
            formatted,
            hide_index=True,
            width="stretch",
            column_config={
                "Annual return": st.column_config.NumberColumn(format="percent"),
                "Annual volatility": st.column_config.NumberColumn(format="percent"),
                "Sharpe (0% cash)": st.column_config.NumberColumn(format="%.2f"),
                "Maximum drawdown": st.column_config.NumberColumn(format="percent"),
                "Average exposure": st.column_config.NumberColumn(format="percent"),
            },
        )

        st.html(
            """
            <div class="rr-lab-section-head rr-lab-section-head--nested">
            <span>03 / RECESSION PHASES</span><div><h3>Performance around recession episodes</h3>
            <p>Pre-recession and recovery each cover 26 weeks around the NBER-labelled
            episode. Separating regimes prevents a strong expansion from hiding weak
            recession performance.</p></div></div>
            """
        )
        st.dataframe(
            _phase_table(result),
            hide_index=True,
            width="stretch",
            column_config={
                "Average annualised return": st.column_config.NumberColumn(format="percent"),
                "Weekly volatility": st.column_config.NumberColumn(format="percent"),
                "Average stress z-score": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    st.html(
        """
        <section class="rr-lab-definitions"><header><span>04 / DEFINITIONS</span>
        <h3>Read the diagnostics correctly</h3></header><div>
        <article><strong>Z-score</strong><p>Historical standard deviations above or below
        the trailing baseline. A positive stress z-score does not guarantee recession.</p></article>
        <article><strong>Sharpe ratio</strong><p>Annualised average return divided by
        annualised volatility, using a 0% cash benchmark here.</p></article>
        <article><strong>Maximum drawdown</strong><p>The largest peak-to-trough loss in the
        historical strategy path.</p></article>
        <article><strong>Recession phases</strong><p>The 26 weeks before an NBER episode,
        the episode itself, the following 26 weeks, and all other expansion weeks.</p></article>
        </div></section>
        """
    )
