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


def _terrain_figure(view: FinancialStressView) -> go.Figure:
    labels = ["IG OAS", "HY OAS", "VIX", "STLFSI", "Drawdown"]
    keys = ["ig_oas", "hy_oas", "vix", "stlfsi", "drawdown"]
    history = view.history[keys].dropna(how="all").tail(260)
    recession = (
        view.recession_indicator.reindex(history.index, method="ffill")
        .fillna(0)
        .ge(0.5)
        .astype(int)
    )
    colours = np.tile(recession.to_numpy(), (len(keys), 1))
    figure = go.Figure(
        go.Surface(
            x=history.index,
            y=labels,
            z=history[keys].T.to_numpy(),
            surfacecolor=colours,
            colorscale=[[0, "#f5bd3e"], [0.49, "#f5bd3e"], [0.5, "#d75f47"], [1, "#d75f47"]],
            cmin=0,
            cmax=1,
            showscale=False,
            contours={"z": {"show": True, "usecolormap": False, "color": "#15130f", "width": 1}},
            hovertemplate="%{x|%d %b %Y}<br>%{y}<br>Stress %{z:.1f}/100<extra></extra>",
        )
    )
    figure.update_layout(
        height=650,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)",
        scene={
            "xaxis_title": "Historical week",
            "yaxis_title": "Market channel",
            "zaxis_title": "Stress score (0–100)",
            "zaxis": {"range": [0, 100]},
            "camera": {"eye": {"x": 1.55, "y": 1.55, "z": 0.85}},
            "bgcolor": "rgba(0,0,0,0)",
        },
    )
    return figure


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
    """Render the shared analytical lab."""
    result = build_strategy_lab(view)
    st.caption("SHARED SIGNAL LAB / FOUR-PANEL RECESSION RADAR")
    st.title("Signal terrain & strategy diagnostics")
    st.write(
        "This lab turns the dashboard's market-stress history into a deeper visual "
        "diagnostic. It asks how the component z-scores behaved before, during and "
        "after recessions, and how simple exposure rules would have changed historical "
        "return and risk. It is an explanatory backtest, not investment advice."
    )

    terrain, strategies, phases, glossary = st.tabs(
        ["3D signal terrain", "Strategy comparison", "Recession phases", "Definitions"]
    )
    with terrain:
        st.subheader("Five-dimensional stress surface")
        st.write(
            "Height is the 0–100 stress score for each market channel. Yellow surface "
            "sections are non-recession weeks and red sections coincide with NBER "
            "recession labels. Rotate, zoom and hover to inspect individual weeks."
        )
        st.plotly_chart(
            _terrain_figure(view),
            width="stretch",
            config={"displayModeBar": True, "responsive": True},
            key="signal_lab_terrain",
        )

    with strategies:
        st.subheader("Three transparent exposure rules")
        st.write(
            "Buy & hold remains fully invested. Stress-scaled exposure falls gradually "
            "as the composite rises. Alert reducer uses 100% exposure in CALM, 65% in "
            "WATCH and 25% in ALERT. Every rule uses the previous week's score to avoid "
            "look-ahead bias; cash is modelled at 0% and costs are omitted."
        )
        st.plotly_chart(
            _wealth_figure(result),
            width="stretch",
            config={"displayModeBar": False, "responsive": True},
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

    with phases:
        st.subheader("Performance around recession episodes")
        st.write(
            "Pre-recession and recovery each cover 26 weeks around the NBER-labelled "
            "episode. The table separates what happened in each regime instead of "
            "allowing a strong expansion to hide weak recession performance."
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

    with glossary:
        st.markdown(
            """
            ### Z-score
            The number of historical standard deviations an observation sits above or
            below its trailing baseline. Positive stress z-scores mean conditions are
            tighter than normal; they do not directly mean a recession is certain.

            ### Sharpe ratio
            Annualised average strategy return divided by annualised volatility. This
            implementation uses a 0% cash benchmark so the comparison stays transparent.
            A higher historical Sharpe ratio is not a promise of future performance.

            ### Maximum drawdown
            The largest peak-to-trough loss in the historical strategy path. It measures
            severity, while volatility measures the typical variation in weekly returns.

            ### Recession phases
            **Pre-recession** is the 26 weeks before an NBER episode, **recession** is the
            labelled episode, and **recovery** is the following 26 weeks. All other weeks
            are classified as expansion.
            """
        )
