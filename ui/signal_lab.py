"""Cross-panel 3D diagnostics and historical strategy comparisons."""

from __future__ import annotations

from collections.abc import Callable
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
            "xaxis_title": "Historical week",
            "yaxis_title": "Market channel",
            "zaxis_title": "Stress score (0–100)",
            "zaxis": {"range": [0, 100]},
            "camera": {"eye": {"x": 1.55, "y": 1.55, "z": 0.85}},
            "bgcolor": "rgba(0,0,0,0)",
        },
    )
    return figure


def render_signal_lab_preview(
    view: FinancialStressView,
    *,
    on_open: Callable[[], None],
) -> None:
    """Render a compact central terrain with a route to the full lab."""
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

    st.caption("CENTRE / INTERACTIVE 3D SIGNAL LAB")
    st.subheader("See stress spread across markets")
    st.write(
        "The surface puts credit spreads, VIX, STLFSI and equity drawdown on "
        "one 0 to 100 scale. A broad ridge across several rows is more meaningful "
        "than one isolated spike. Red begins at 55 as an early visual warning; "
        "the formal ALERT classification still begins at 67."
    )
    st.plotly_chart(
        _terrain_figure(view, height=460),
        width="stretch",
        theme=None,
        config={"displayModeBar": False, "responsive": True},
        key="signal_lab_terrain_preview",
    )
    st.markdown(
        f"**Current reading:** {signal.score:.0f}/100, **{signal.status}**. "
        f"{breadth} of {len(signal.components)} channels are in ALERT. "
        f"The strongest channel is {names.get(strongest_key, strongest_key)} "
        f"at {strongest_value:.0f}/100."
    )
    st.button(
        "See the full Signal Lab",
        key="open_signal_lab_centre",
        on_click=on_open,
        width="stretch",
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

    st.subheader("Five-dimensional stress surface")
    st.write(
        "Start here. The surface puts every Financial Stress channel on the same "
        "0 to 100 scale, making it possible to see whether pressure is isolated or "
        "spreading across credit, volatility, the Fed stress index and equity drawdown."
    )
    st.plotly_chart(
        _terrain_figure(view),
        width="stretch",
        theme=None,
        config={"displayModeBar": True, "responsive": True},
        key="signal_lab_terrain",
    )

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
    st.markdown(
        f"""
        ### How to read what you are seeing

        **Left to right is time.** Each slice is one completed historical week. The five
        rows are IG OAS, HY OAS, VIX, STLFSI and S&P 500 drawdown.

        **Height is stress, not return.** A height near 50 is close to the trailing
        historical baseline. Values above 67 enter the ALERT band. Values below 34 are
        comparatively calm. The score is derived from causal 156-week z-scores, so the
        current week never enters its own baseline.

        **Colour shows warning intensity.** Green is comparatively calm, yellow is
        elevated, and red starts at 55/100 so emerging pressure is visible before the
        formal 67/100 ALERT threshold. Colour is an early visual cue, not a recession
        prediction by itself.

        **Shape shows breadth.** One tall row is an isolated warning. A ridge across
        several rows means credit, volatility and market losses are agreeing, which is a
        stronger stress signal.

        **Current selected-date reading:** {signal.score:.0f}/100, **{signal.status}**,
        with {breadth} of {len(signal.components)} channels in ALERT. The strongest
        channel is {component_names.get(strongest_key, strongest_key)} at
        {strongest_value:.0f}/100. {signal.verdict}
        """
    )

    st.divider()
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
        theme=None,
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

    st.divider()
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

    st.divider()
    st.markdown(
        """
        ## Definitions

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
