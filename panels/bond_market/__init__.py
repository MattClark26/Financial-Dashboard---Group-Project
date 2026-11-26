"""Bond-market charts with a 70/30, sigmoid-smoothed warning index."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from math import exp
from pathlib import Path
from urllib.request import Request, urlopen

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
MODEL_COMPARISON_CACHE = DATA_DIR.parent / "baa_model_comparison_probabilities.csv"


# Live FRED data and offline CSV fallback

@st.cache_data(ttl=1800, show_spinner=False)
def _load_market_series(series_id: str) -> tuple[pd.Series, str]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    source = "LIVE FRED"

    try:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=5) as response:
            frame = pd.read_csv(
                BytesIO(response.read()),
                index_col=0,
                parse_dates=True,
                na_values=".",
            )
        if series_id not in frame.columns or pd.to_numeric(
            frame[series_id], errors="coerce"
        ).dropna().empty:
            raise ValueError(f"FRED returned no usable {series_id} observations")
    except Exception:
        source = "CACHED CSV"
        backup = DATA_DIR / f"{series_id}.csv"
        if not backup.exists():
            return pd.Series(dtype="float64", name=series_id), "UNAVAILABLE"
        frame = pd.read_csv(
            backup, index_col=0, parse_dates=True, na_values="."
        )
        if series_id not in frame.columns:
            return pd.Series(dtype="float64", name=series_id), "UNAVAILABLE"

    frame.index = pd.to_datetime(frame.index, errors="coerce")
    frame = frame.loc[frame.index.notna()]
    values = pd.to_numeric(frame[series_id], errors="coerce").dropna()
    values = values.sort_index()
    values = values[~values.index.duplicated(keep="last")]
    values.name = series_id
    if values.empty:
        return values, "UNAVAILABLE"
    return values, source


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


def _smoothed_warning_score(percentile: float) -> float:
    """Gently squash a 0–100 percentile into about 12–88 with a sigmoid.

    This is a display/index transformation, not a forecast probability.
    It remains monotonic: higher percentiles always produce higher scores.
    """
    return 100.0 / (1.0 + exp(-(percentile - 50.0) / 25.0))


def _completed_month(as_of: object) -> pd.Period:
    """Use fully completed calendar months for comparisons (avoid partial months)."""
    selected = pd.Timestamp(as_of)
    if selected.is_month_end:
        return selected.to_period("M")
    return (selected - pd.offsets.MonthEnd(1)).to_period("M")


def _historical_percentile(values: pd.Series) -> float:
    """Historical midrank of the latest value, on a 0-100 scale.

    Half the tied observations count as below the latest observation.
    This matches the percentile method used in the original 70/30 index.
    """
    latest = float(values.iloc[-1])
    below = int((values < latest).sum())
    tied = int((values == latest).sum())
    return 100.0 * (below + 0.5 * tied) / len(values)


def _no_score(reason: str, probability: float | None = None) -> dict:
    """Keep the shared dashboard API numeric if the 70/30 inputs are missing."""
    return {
        "score": 50.0,
        "status": "WATCH",
        "probability": probability,
        "percentile": None,
        "yield_percentile": None,
        "credit_percentile": None,
        "credit_spread": None,
        "observations": 0,
        "score_month": None,
        "verdict": f"70/30 warning index unavailable ({reason}); neutral placeholder shown.",
    }


def load_bond_market_signal(as_of: object) -> dict:
    """Return the 70% Baseline + 30% Baa percentile index, then sigmoid-smooth it.

    Baseline component: saved 12-month-ahead recession probabilities.
    Baa component: historical percentile of monthly-average BAA10Y credit spread.
    A positive-slope standalone Baa Probit nowcast ranks months in exactly
    the same order as the underlying spread, so its percentile is equivalent.
    Both components use only their *overlapping months* up to the Time Machine
    cutoff. The stored Baseline probabilities are retrospective model outputs.
    """
    selected_date = pd.Timestamp(as_of)
    probabilities = load_recession_probability(selected_date)
    if probabilities.empty:
        return _no_score("Baseline probability CSV missing or empty")

    baseline = pd.Series(
        probabilities.to_numpy(dtype="float64"),
        index=probabilities.index.to_period("M"),
        name="baseline_probability",
    )
    baseline = baseline[~baseline.index.duplicated(keep="last")].sort_index()

    credit_daily, _ = _load_market_series("BAA10Y")
    if credit_daily.empty:
        return _no_score("BAA10Y could not be loaded", float(probabilities.iloc[-1]))
    credit_daily = credit_daily.loc[credit_daily.index <= selected_date]
    if credit_daily.empty:
        return _no_score("no Baa observations before the selected date", float(probabilities.iloc[-1]))

    credit_monthly = credit_daily.resample("ME").mean().dropna()
    credit_monthly.index = credit_monthly.index.to_period("M")
    credit_monthly.name = "baa_credit_spread"

    common = pd.concat([baseline, credit_monthly], axis=1, join="inner").dropna()
    common = common.loc[common.index <= _completed_month(selected_date)].sort_index()
    if len(common) < 24:
        return _no_score("fewer than 24 shared completed months", float(probabilities.iloc[-1]))

    treasury_percentile = _historical_percentile(common["baseline_probability"])
    credit_percentile = _historical_percentile(common["baa_credit_spread"])
    weighted_percentile = 0.70 * treasury_percentile + 0.30 * credit_percentile
    score = _smoothed_warning_score(weighted_percentile)
    status = "ALERT" if score >= 67 else "WATCH" if score >= 34 else "CALM"

    probability = float(common["baseline_probability"].iloc[-1])
    return {
        "score": score,
        "status": status,
        "probability": probability,
        "percentile": weighted_percentile,
        "yield_percentile": treasury_percentile,
        "credit_percentile": credit_percentile,
        "credit_spread": float(common["baa_credit_spread"].iloc[-1]),
        "observations": len(common),
        "score_month": common.index[-1].strftime("%b %Y"),
        "verdict": (
            f"Baseline recession probability: {probability:.1f}%. "
            f"70/30 yield + credit warning score: {score:.0f}/100 "
            "(sigmoid-smoothed, not a probability)."
        ),
    }


def _open_detail() -> None:
    st.session_state["active_panel"] = "bond"


def render(as_of: date, *, signal: dict | None = None) -> dict:
    """Render the compact dashboard card."""
    signal = signal or load_bond_market_signal(as_of)
    _, treasury_source = _load_market_series("T10Y3M")
    st.html(
        f"""
        <div class="rr-panel-body">
          <div class="rr-panel-title-row">
            <div>
              <h2 class="rr-panel-title">Bond Market Signal</h2>
              <p class="rr-panel-summary">Combines historical Treasury
              recession-probability warnings (70%) and Baa credit stress (30%).
              A sigmoid softens the score's extremes.</p>
              <p class="rr-panel-verdict">{signal["verdict"]}</p>
            </div>
            <div class="rr-score"><strong>{signal["score"]:.0f}</strong>
              <span>/100 · {signal["status"]}</span></div>
          </div>
        </div>
        <div class="rr-metric-grid">
          <div class="rr-metric"><span>TIME MACHINE</span><strong>{as_of:%b %Y}</strong></div>
          <div class="rr-metric"><span>SCORE BASIS</span><strong>70/30 + SIGMOID</strong></div>
          <div class="rr-metric"><span>TREASURY DATA</span><strong>{treasury_source}</strong></div>
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
    values, _ = _load_market_series(series_id)
    return values.loc[values.index <= as_of]


def _load_recessions(as_of: pd.Timestamp) -> pd.Series:
    values, _ = _load_market_series("USREC")
    return values.loc[values.index <= as_of]


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


def _credit_figure(values: pd.Series, recessions: pd.Series) -> go.Figure:
    figure = go.Figure()
    figure.add_scatter(
        x=values.index,
        y=values,
        mode="lines",
        line={"color": RED, "width": 2},
        name="Baa credit spread",
        hovertemplate="%{x|%d %b %Y}<br>%{y:.2f} percentage points<extra></extra>",
    )
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
        title="Moody's Baa Corporate Bond Spread",
        height=470,
        xaxis_title=None,
        yaxis_title="Percentage points",
        hovermode="x unified",
        showlegend=False,
    )
    return figure


def _load_model_comparison(as_of: pd.Timestamp) -> pd.DataFrame:
    if not MODEL_COMPARISON_CACHE.exists():
        return pd.DataFrame()
    frame = pd.read_csv(MODEL_COMPARISON_CACHE)
    frame["Month"] = pd.to_datetime(frame["Month"], errors="coerce")
    frame = frame.dropna(subset=["Month"]).set_index("Month").sort_index()
    return frame[frame.index <= as_of]


def _baseline_correlation(as_of: pd.Timestamp) -> float | None:
    if not PROBABILITY_CACHE.exists():
        return None
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
    credit_spread = _load_spread("BAA10Y", selected_date)
    recessions = _load_recessions(selected_date)

    current_spread = float(spread_3m.iloc[-1]) if not spread_3m.empty else float("nan")
    inversion_label = "INVERTED" if current_spread < 0 else "NOT INVERTED"

    render_detail_hero(
        kicker="PANEL 01 / TERM STRUCTURE / LUKE O'BRIEN PETERSON",
        title="Bond Market Signal",
        lede=(
            "A 70/30 historical warning index combining Treasury recession risk "
            "and Baa credit stress, gently compressed with a sigmoid."
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

    curve_tab, baseline_tab, recent_tab, credit_tab = st.tabs(
        ["Yield curve", "Baseline", "Recent inversion", "Baa credit spread"]
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
                chart_series = "T10Y3M" if spread_choice == "10Y-3M" else "T10Y2Y"
                _, chart_source = _load_market_series(chart_series)
                st.caption(f"Chart data: {chart_source} · online downloads cached for 30 minutes")
                latest = float(values.iloc[-1])
                render_conclusion(
                    "YIELD CURVE INVERTED" if latest < 0 else "YIELD CURVE NOT INVERTED",
                    "Grey bands mark US recessions. The red dashed line is the zero-spread inversion threshold.",
                )

    with baseline_tab:
        correlation = _baseline_correlation(selected_date)
        baseline_probability = signal.get("probability")
        probability_label = (
            f"{baseline_probability:.1f}%"
            if baseline_probability is not None else "N/A"
        )
        render_quality_grid(
            (
                (probability_label, "Estimated probability"),
                (f'{signal["score"]:.0f}/100', "70/30 smoothed warning score"),
                (
                    f"{correlation:.3f}" if correlation is not None else "N/A",
                    "Outcome correlation",
                ),
                ("12 months", "Forecast horizon"),
            )
        )
        treasury_pct = signal.get("yield_percentile")
        credit_pct = signal.get("credit_percentile")
        combined_pct = signal.get("percentile")
        if combined_pct is None:
            st.info("The 70/30 index needs overlapping Baseline and Baa historical data.")
        else:
            st.write(
                f"Historical Treasury percentile: **{treasury_pct:.1f}/100 (70% weight)**. "
                f"Baa credit-stress percentile: **{credit_pct:.1f}/100 (30% weight)**. "
                f"Combined raw percentile: **{combined_pct:.1f}/100**. "
                f"Observation: **{signal['score_month']}**, compared with "
                f"**{signal['observations']}** shared completed months."
            )
        st.write(
            "The Baseline model uses the 10-year minus 3-month Treasury spread "
            "to estimate recession status exactly 12 months later. "
            "The 70/30 warning index combines (1) the historical percentile of "
            "that saved Baseline probability and (2) the historical percentile "
            "of the monthly Moody's Baa credit spread, compared over the same "
            "available months up to the selected Time Machine date. The Baa "
            "percentile has the same historical ranking as a standalone Baa "
            "same-month Probit nowcast when its fitted slope is positive. "
            "A gentle sigmoid then compresses the combined percentile: "
            "extremes become approximately 12/100 and 88/100, rather than "
            "0 and 100. The 70/30 weights are illustrative, not calibrated. "
            "This is a warning index, not a recession probability. "
            "The saved Baseline probabilities use retrospective, full-history "
            "model estimates, so past Time Machine scores are not genuine "
            "historical real-time forecasts."
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
            probability_figure.update_layout(
                title="Estimated probability of recession exactly twelve months later",
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
                ("INPUT 03", "Baa credit spread", "Its historical percentile supplies 30% of the warning index."),
                ("OUTPUT", "Smoothed warning index", "70% Baseline rank + 30% Baa rank, then sigmoid; not a probability."),
            )
        )

    with credit_tab:
        latest_credit = float(credit_spread.iloc[-1]) if not credit_spread.empty else None
        comparison = _load_model_comparison(selected_date)
        latest_model = (
            float(comparison["Baa credit spreads probability (%)"].dropna().iloc[-1])
            if not comparison.empty
            and comparison["Baa credit spreads probability (%)"].notna().any()
            else None
        )
        render_quality_grid(
            (
                (
                    f"{latest_credit:.2f}" if latest_credit is not None else "N/A",
                    "Latest Baa spread",
                ),
                (
                    f"{latest_model:.1f}%" if latest_model is not None else "N/A",
                    "Saved combined-model probability",
                ),
                ("12 months", "Forecast horizon"),
                ("FRED / CSV backup", "Chart source"),
            )
        )
        st.write(
            "Baa-rated corporate bonds carry more default and liquidity risk than "
            "Treasuries. A widening Baa minus Treasury spread means investors demand "
            "more compensation to lend to riskier firms. This saved comparison "
            "model combines credit-spread evidence with the yield curve and its "
            "recent persistence; it is separate from the warning-score calculation."
        )
        credit_pct = signal.get("credit_percentile")
        if credit_pct is not None:
            st.caption(
                f"Warning-index credit component: {credit_pct:.1f}/100 historical "
                "Baa spread percentile, weighted at 30% before sigmoid smoothing."
            )
        if credit_spread.empty:
            st.info("No Baa credit-spread observations are available for this date.")
        else:
            st.plotly_chart(
                _credit_figure(credit_spread, recessions),
                width="stretch",
                theme=None,
                config={"displayModeBar": False, "responsive": True},
            )
            _, credit_source = _load_market_series("BAA10Y")
            st.caption(f"Chart data: {credit_source} · online downloads cached for 30 minutes")
        if not comparison.empty:
            probability_columns = [
                "Baseline probability (%)",
                "Weighted inversion probability (%)",
                "Baa credit spreads probability (%)",
            ]
            model_figure = go.Figure()
            colors = (MUTED, INK, RED)
            for column, color in zip(probability_columns, colors, strict=True):
                model_figure.add_scatter(
                    x=comparison.index,
                    y=comparison[column],
                    mode="lines",
                    line={"color": color, "width": 2},
                    name=column.replace(" probability (%)", ""),
                    hovertemplate="%{x|%b %Y}<br>%{y:.1f}%<extra></extra>",
                )
            model_figure.update_layout(
                title="Three-model probability comparison",
                height=440,
                xaxis_title=None,
                yaxis_title="Probability (%)",
                hovermode="x unified",
                legend={"orientation": "h", "y": 1.12},
            )
            st.plotly_chart(
                model_figure,
                width="stretch",
                theme=None,
                config={"displayModeBar": False, "responsive": True},
            )
        render_conclusion(
            "CREDIT IS A CONFIRMING SIGNAL",
            "The Baa model should be read beside the Treasury models. Agreement across the three is stronger evidence than any one specification alone.",
        )


__all__ = [
    "TITLE",
    "load_bond_market_signal",
    "load_recession_probability",
    "render",
    "render_full",
]
