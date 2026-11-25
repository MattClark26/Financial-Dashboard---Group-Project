"""Bond-market signal using committed FRED data and model output."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.presentation import (
    INK,
    MUTED,
    RED,
    render_conclusion,
    render_detail_hero,
    render_explanation_strip,
    render_method_grid,
    render_quality_grid,
)


TITLE = "Bond market"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PROBABILITY_CACHE = DATA_DIR / "us_recession_probability.csv"


def load_recession_probability(selected_date: pd.Timestamp) -> pd.Series:
    """Return cached twelve-month recession probabilities through a date."""
    if not PROBABILITY_CACHE.exists():
        return pd.Series(dtype="float64", name="Recession Probability (%)")

    frame = pd.read_csv(PROBABILITY_CACHE)
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Recession Probability (%)"] = pd.to_numeric(
        frame["Recession Probability (%)"], errors="coerce"
    )
    frame = frame.dropna(subset=["Date", "Recession Probability (%)"])
    frame = frame[
        (frame["Date"] <= pd.Timestamp(selected_date))
        & frame["Recession Probability (%)"].between(0, 100)
    ]
    frame = frame.sort_values("Date").drop_duplicates("Date", keep="last")

    return pd.Series(
        frame["Recession Probability (%)"].to_numpy(),
        index=pd.DatetimeIndex(frame["Date"], name="Date"),
        name="Recession Probability (%)",
    )


def load_bond_market_signal(as_of: object) -> dict:
    """Expose the cached recession probability through the shared contract."""
    probability = load_recession_probability(pd.Timestamp(as_of))
    if probability.empty:
        return {
            "score": 50.0,
            "status": "WATCH",
            "verdict": "Bond-market probability is unavailable, so this panel is neutral.",
        }

    score = float(probability.iloc[-1])
    status = "ALERT" if score >= 67 else "WATCH" if score >= 34 else "CALM"
    return {
        "score": score,
        "status": status,
        "verdict": (
            f"The latest cached model assigns a {score:.1f}% US recession probability."
        ),
    }


def _open_detail() -> None:
    st.session_state["active_panel"] = "bond"


def render(as_of: date, *, signal: dict | None = None) -> dict:
    """Render the compact dashboard card."""
    signal = signal or load_bond_market_signal(as_of)
    st.html(
        f"""
        <div class="rr-panel-body">
          <div class="rr-panel-title-row">
            <div>
              <h2 class="rr-panel-title">Bond Market Signal</h2>
              <p class="rr-panel-summary">Shows whether Treasury yield-curve
              inversions are warning that borrowing conditions may precede a
              US recession.</p>
              <p class="rr-panel-verdict">{signal["verdict"]}</p>
            </div>
            <div class="rr-score"><strong>{signal["score"]:.0f}</strong>
              <span>/100 · {signal["status"]}</span></div>
          </div>
        </div>
        <div class="rr-metric-grid">
          <div class="rr-metric"><span>TIME MACHINE</span><strong>{as_of:%b %Y}</strong></div>
          <div class="rr-metric"><span>SPREADS</span><strong>10Y-3M / 10Y-2Y</strong></div>
          <div class="rr-metric"><span>DATA MODE</span><strong>CACHED FRED</strong></div>
        </div>
        """
    )
    st.button(
        "See full Bond analysis",
        key="bond_market_open",
        width="stretch",
        on_click=_open_detail,
    )
    return signal


def _load_spread(series_id: str, as_of: pd.Timestamp) -> pd.Series:
    frame = pd.read_csv(
        DATA_DIR / f"{series_id}.csv",
        index_col=0,
        parse_dates=True,
        na_values=".",
    )
    values = pd.to_numeric(frame[series_id], errors="coerce").dropna()
    values = values[values.index <= as_of].sort_index()
    values.name = series_id
    return values


def _load_recessions(as_of: pd.Timestamp) -> pd.Series:
    frame = pd.read_csv(DATA_DIR / "USREC.csv", index_col=0, parse_dates=True)
    values = pd.to_numeric(frame["USREC"], errors="coerce").dropna()
    return values[values.index <= as_of].sort_index()


def _recession_periods(values: pd.Series) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    monthly = values.resample("ME").max().fillna(0).astype(int)
    starts = monthly.index[(monthly.eq(1)) & (monthly.shift(fill_value=0).eq(0))]
    ends = monthly.index[(monthly.eq(1)) & (monthly.shift(-1, fill_value=0).eq(0))]
    return list(zip(starts, ends, strict=False))


def _spread_figure(
    values: pd.Series,
    recessions: pd.Series,
    title: str,
) -> go.Figure:
    figure = go.Figure()
    figure.add_scatter(
        x=values.index,
        y=values,
        mode="lines",
        line={"color": INK, "width": 2},
        name="Treasury spread",
        hovertemplate="%{x|%d %b %Y}<br>%{y:.2f} percentage points<extra></extra>",
    )
    figure.add_hline(y=0, line_color=RED, line_dash="dash", line_width=2)
    for start, end in _recession_periods(recessions):
        if end < values.index.min() or start > values.index.max():
            continue
        figure.add_vrect(
            x0=start,
            x1=end + pd.offsets.MonthEnd(1),
            fillcolor="rgba(105,100,91,.18)",
            line_width=0,
            layer="below",
        )
    figure.update_layout(
        title=title,
        height=470,
        xaxis_title=None,
        yaxis_title="Percentage points",
        hovermode="x unified",
        showlegend=False,
    )
    return figure


def _baseline_correlation(as_of: pd.Timestamp) -> float | None:
    frame = pd.read_csv(PROBABILITY_CACHE)
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Recession Probability (%)"] = pd.to_numeric(
        frame["Recession Probability (%)"], errors="coerce"
    )
    frame["Actual recession 12 months later"] = pd.to_numeric(
        frame["Actual recession 12 months later"], errors="coerce"
    )
    frame = frame[frame["Date"] <= as_of].dropna()
    if len(frame) < 2:
        return None
    return float(
        frame["Recession Probability (%)"].corr(
            frame["Actual recession 12 months later"]
        )
    )


def render_full(as_of: date) -> None:
    """Render the full Bond page in the shared prototype visual system."""
    selected_date = pd.Timestamp(as_of)
    signal = load_bond_market_signal(selected_date)
    spread_3m = _load_spread("T10Y3M", selected_date)
    spread_2y = _load_spread("T10Y2Y", selected_date)
    recessions = _load_recessions(selected_date)

    current_spread = float(spread_3m.iloc[-1]) if not spread_3m.empty else float("nan")
    inversion_label = "INVERTED" if current_spread < 0 else "NOT INVERTED"

    render_detail_hero(
        kicker="PANEL 01 / TERM STRUCTURE / LUKE O'BRIEN PETERSON",
        title="Bond Market Signal",
        lede=(
            "Treasury yield-curve inversions and estimated US recession "
            "probability twelve months ahead."
        ),
        score=signal["score"],
        status=signal["status"],
    )
    render_explanation_strip(
        (
            (
                "WHY INVERSION MATTERS",
                "Short rates above long rates can signal expected weaker growth and future rate cuts. It is a 6 to 18 month warning, not proof a recession has started.",
            ),
            (
                "DEPTH + PERSISTENCE",
                "A brief shallow inversion differs from a deep one lasting many months. The recent path provides more context than one daily observation.",
            ),
            (
                "HOW TO JUDGE IT",
                "Compare lead time, caught recessions and false alarms. One dramatic probability is less informative than a stable historical track record.",
            ),
        )
    )

    curve_tab, baseline_tab, recent_tab, debt_tab = st.tabs(
        ["Yield curve", "Baseline", "Recent inversion", "Government debt"]
    )

    with curve_tab:
        with st.container(key="bond_detail_curve"):
            spread_choice = st.radio(
                "Choose yield spread",
                ["10Y-3M", "10Y-2Y"],
                horizontal=True,
                key="bond_spread_choice",
            )
            if spread_choice == "10Y-3M":
                values = spread_3m
                title = "10-Year minus 3-Month Treasury Spread"
            else:
                values = spread_2y
                title = "10-Year minus 2-Year Treasury Spread"

            if values.empty:
                st.info("No yield-spread observations are available for this date.")
            else:
                st.plotly_chart(
                    _spread_figure(values, recessions, title),
                    width="stretch",
                    theme=None,
                    config={"displayModeBar": False, "responsive": True},
                )
                latest = float(values.iloc[-1])
                render_conclusion(
                    "YIELD CURVE INVERTED" if latest < 0 else "YIELD CURVE NOT INVERTED",
                    "Grey bands mark US recessions. The red dashed line is the zero-spread inversion threshold.",
                )

    with baseline_tab:
        correlation = _baseline_correlation(selected_date)
        render_quality_grid(
            (
                (f'{signal["score"]:.1f}%', "Estimated probability"),
                (
                    f"{correlation:.3f}" if correlation is not None else "N/A",
                    "Outcome correlation",
                ),
                ("12 months", "Forecast horizon"),
                ("FRED cache", "Data source"),
            )
        )
        st.write(
            "The baseline model uses the 10-year minus 3-month Treasury spread. "
            "Its committed output table pairs each dated probability with the later "
            "recession outcome where that outcome is already observable."
        )
        probability = load_recession_probability(selected_date)
        if not probability.empty:
            probability_figure = go.Figure()
            probability_figure.add_scatter(
                x=probability.index,
                y=probability,
                mode="lines",
                line={"color": INK, "width": 2},
                hovertemplate="%{x|%b %Y}<br>%{y:.1f}%<extra></extra>",
            )
            probability_figure.add_hline(y=34, line_color=MUTED, line_dash="dot")
            probability_figure.add_hline(y=67, line_color=RED, line_dash="dash")
            probability_figure.update_layout(
                title="Estimated US recession probability within twelve months",
                height=430,
                xaxis_title=None,
                yaxis_title="Probability (%)",
                showlegend=False,
            )
            st.plotly_chart(
                probability_figure,
                width="stretch",
                theme=None,
                config={"displayModeBar": False, "responsive": True},
            )

    with recent_tab:
        monthly = spread_3m.resample("ME").mean().dropna()
        recent = monthly.tail(12)
        inverted_months = int(recent.lt(0).sum())
        minimum = float(recent.min()) if not recent.empty else float("nan")
        render_quality_grid(
            (
                (inversion_label, "Current state"),
                (f"{current_spread:.2f}", "Latest spread"),
                (f"{inverted_months} / 12", "Inverted months"),
                (f"{minimum:.2f}", "Twelve-month minimum"),
            )
        )
        render_method_grid(
            (
                ("INPUT 01", "10Y-3M spread", "The selected date's latest available term spread."),
                ("INPUT 02", "Recent persistence", "Counts inverted monthly averages during the preceding year."),
                ("OUTPUT", "Recession probability", "The cached model estimates recession risk twelve months ahead."),
            )
        )

    with debt_tab:
        st.info(
            "The government-debt model is marked as future work. No invented result "
            "is shown until a documented, time-aware debt series is committed."
        )


__all__ = [
    "TITLE",
    "load_bond_market_signal",
    "load_recession_probability",
    "render",
    "render_full",
]
