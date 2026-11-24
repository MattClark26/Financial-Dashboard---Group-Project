"""Panel 4: The Irish Lens"""

from datetime import date
from pathlib import Path

from pyjstat import pyjstat
import plotly.graph_objects as go
import pandas as pd
import streamlit as st    

from panels.bond_market import load_recession_probability

TITLE = "Irish lens"

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

UNEMPLOYMENT_CACHE = "irish_unemployment.csv"
GDP_CACHE = "irish_gdp.csv"
MDD_CACHE = "irish_mdd.csv"
EXPORTS_CACHE = "irish_exports.csv"

IRISH_WARNING_SCORE = 34.0
BACKTEST_HORIZON_MONTHS = 12

CSO_DATASET_URL = (
    "https://ws.cso.ie/public/api.restful/"
    "PxStat.Data.Cube_API.ReadDataset/{table_code}/JSON-stat/2.0/en"
)
def fetch_cso_table(
    table_code: str,
    cache_filename: str,
    data_dir: Path | str = DATA_DIR,
    ) -> pd.DataFrame:
    """Fetch a CSO table and fall back to its local CSV cache."""
    cache_path = Path(data_dir) / cache_filename
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    url = CSO_DATASET_URL.format(table_code=table_code)

    try:
        dataset = pyjstat.Dataset.read(url)
        frame = dataset.write("dataframe")
        frame.to_csv(cache_path, index=False)
        return frame
    except Exception as error:
        if cache_path.exists():
            st.warning(
                f"CSO table {table_code} could not be refreshed. "
                f"Using cached data from {cache_path.name}. Details: {error}"
            )
            return pd.read_csv(cache_path)
        raise RuntimeError(
            f"CSO table {table_code} is unavailable and has no local cache."
        ) from error

def _read_cached_frame(filename: str) -> pd.DataFrame:
    """Read one cached CSO table, or return an empty frame if absent."""
    cache_path = DATA_DIR / filename
    if not cache_path.exists():
        return pd.DataFrame()
    return pd.read_csv(cache_path)

def _load_export_exposure(
    selected_date: pd.Timestamp,
) -> pd.DataFrame:
    """Load US export exposure and calculate its rolling average."""
    frame = _read_cached_frame(EXPORTS_CACHE)

    if frame.empty:
        return pd.DataFrame()

    required_columns = {"Date", "US Exports", "Total Exports"}
    missing_columns = required_columns.difference(frame.columns)

    if missing_columns:
        raise ValueError(
            "Irish exports cache is missing columns: "
            f"{sorted(missing_columns)}"
        )

    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["US Exports"] = pd.to_numeric(
        frame["US Exports"],
        errors="coerce",
    )
    frame["Total Exports"] = pd.to_numeric(
        frame["Total Exports"],
        errors="coerce",
    )

    frame = frame.dropna(
    subset=["Date", "US Exports", "Total Exports"]
    )
    frame = frame[
    (frame["US Exports"] >= 0)
    & (frame["Total Exports"] > 0)
    ]
    frame = frame[frame["Date"] <= selected_date]
    frame = frame.sort_values("Date").drop_duplicates(
    subset=["Date"],
    keep="last",
    )

    if frame.empty:
        return pd.DataFrame()

    frame["US Share (%)"] = (
        frame["US Exports"] / frame["Total Exports"] * 100
    )
    frame["12-month average (%)"] = (
        frame["US Share (%)"]
        .rolling(window=12, min_periods=12)
        .mean()
    )

    return frame

def _find_column(
    columns: pd.Index,
    candidates: tuple[str, ...],
) -> str | None:
    """Find a column without depending on CSO's exact capitalization."""
    columns_by_lowercase = {str(column).lower(): str(column) for column in columns}
    for candidate in candidates:
        if candidate.lower() in columns_by_lowercase:
            return columns_by_lowercase[candidate.lower()]
    return None


def _to_time_series(frame: pd.DataFrame) -> pd.Series:
    """Convert a cached CSO frame into a sorted dated numeric series."""
    if frame.empty:
        return pd.Series(dtype="float64")

    time_column = _find_column(
        frame.columns,
        ("time", "date", "period", "quarter", "month"),
    )
    value_column = _find_column(
        frame.columns,
        ("value", "obs_value", "obs value"),
    )
    if time_column is None or value_column is None:
        raise ValueError(
            "Cached CSO data must contain a time column and a value column. "
            f"Found columns: {list(frame.columns)}."
        )
    raw_dates = frame[time_column].astype(str)
    dates = pd.Series(pd.NaT, index=frame.index, dtype="datetime64[ns]")
    regular_mask = ~raw_dates.str.match(r"^\d{4}\s*Q[1-4]$")
    dates.loc[regular_mask] = pd.to_datetime(
        raw_dates.loc[regular_mask],
        errors="coerce",
    ).to_numpy()
    quarter_mask = dates.isna() & raw_dates.str.match(r"^\d{4}\s*Q[1-4]$")
    if quarter_mask.any():
        quarters = raw_dates.loc[quarter_mask].str.replace(" ", "", regex=False)
        dates.loc[quarter_mask] = pd.Series(
            pd.PeriodIndex(quarters, freq="Q")
            .to_timestamp(how="end")
            .normalize(),
            index=quarters.index,
        )

    values = pd.to_numeric(frame[value_column], errors="coerce")
    series = pd.Series(values.to_numpy(), index=dates, name=value_column)
    series = series[~series.index.isna()].dropna().sort_index()
    return series[~series.index.duplicated(keep="last")]

def _slice_to_date(
    series: pd.Series,
    selected_date: pd.Timestamp,
) -> pd.Series:
    """Keep only observations available by the selected dashboard date."""
    if series.empty:
        return series

    cutoff = pd.Timestamp(selected_date)
    return series[series.index <= cutoff]

def compute_sahm_rule(unemployment: pd.Series) -> pd.DataFrame:
    """Calculate the Sahm indicator and its 0.50-point recession trigger."""
    monthly_unemployment = (
        unemployment.sort_index()
        .resample("MS")
        .mean()
    )

    three_month_average = monthly_unemployment.rolling(
        window=3,
        min_periods=3,
    ).mean()

    twelve_month_low = three_month_average.rolling(
        window=12,
        min_periods=12,
    ).min()

    sahm_indicator = three_month_average - twelve_month_low

    return pd.DataFrame(
        {
            "unemployment": monthly_unemployment,
            "sahm_indicator": sahm_indicator,
            "trigger": sahm_indicator >= 0.50,
        }
    )

def _plot_sahm_rule(sahm: pd.DataFrame) -> go.Figure:
    """Create the Irish Sahm Rule chart."""
    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=sahm.index,
            y=sahm["sahm_indicator"],
            mode="lines",
            name="Irish Sahm indicator",
        )
    )

    figure.add_hline(
        y=0.50,
        line_color="#d75f47",
        line_width=3,
        line_dash="dash",
        annotation_text="0.50 trigger",
        annotation_position="bottom right",
    )

    figure.update_layout(
        title="Irish Sahm Rule",
        xaxis_title="Date",
        yaxis_title="Percentage points",
        hovermode="x unified",
    )

    return figure

def _plot_gdp_vs_mdd(
    gdp: pd.Series,
    mdd: pd.Series,
) -> go.Figure:
    """Compare GDP and MDD using 2014 Q4 as the common baseline."""
    baseline_date = pd.Timestamp("2014-12-31")

    gdp_before_baseline = gdp[gdp.index <= baseline_date]
    mdd_before_baseline = mdd[mdd.index <= baseline_date]

    if gdp_before_baseline.empty or mdd_before_baseline.empty:
        raise ValueError(
            "GDP and MDD both need observations through 2014 Q4."
        )

    gdp_index = gdp / gdp_before_baseline.iloc[-1] * 100
    mdd_index = mdd / mdd_before_baseline.iloc[-1] * 100

    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=gdp_index.index,
            y=gdp_index,
            mode="lines",
            name="Headline GDP",
        )
    )

    figure.add_trace(
        go.Scatter(
            x=mdd_index.index,
            y=mdd_index,
            mode="lines",
            name="Modified Domestic Demand",
        )
    )

    figure.update_layout(
        title="Headline GDP vs Modified Domestic Demand",
        xaxis_title="Date",
        yaxis_title="Index, 2014 Q4 = 100",
        hovermode="x unified",
    )

    return figure

def _plot_export_exposure(
    exposure: pd.DataFrame,
    *,
    compact: bool = False,
) -> go.Figure:
    """Create the Irish export exposure chart."""
    figure = go.Figure()

    figure.add_trace(
        go.Scatter(
            x=exposure["Date"],
            y=exposure["US Share (%)"],
            mode="lines",
            name="Monthly US share",
            line={"color": "lightblue"},
        )
    )

    figure.add_trace(
        go.Scatter(
            x=exposure["Date"],
            y=exposure["12-month average (%)"],
            mode="lines",
            name="12-month average",
            line={"color": "darkblue", "width": 3},
        )
    )

    figure.update_layout(
        title={
            "text": "Irish Export Exposure to the United States",
            "x": 0,
            "xanchor": "left",
        },
        template="plotly_dark",
        height=260 if compact else 420,
        margin={"l": 65, "r": 150, "t": 60, "b": 65},
        paper_bgcolor="#080808",
        plot_bgcolor="#080808",
        showlegend=True,
        xaxis_title="Date",
        yaxis_title="US share of Irish exports (%)",
        hovermode="x unified",
        legend={
            "orientation": "v",
            "yanchor": "top",
            "y": 1,
            "xanchor": "left",
            "x": 1.02,
            "font": {"family": "monospace", "size": 11},
        },
    )

    return figure


def _render_export_exposure_chart(
    exposure: pd.DataFrame,
    *,
    key: str,
    compact: bool = False,
) -> None:
    """Render the shared export chart in either dashboard view."""
    st.plotly_chart(
        _plot_export_exposure(exposure, compact=compact),
        width="stretch",
        config={"displayModeBar": False, "responsive": True},
        key=key,
    )

def _render_conclusion(text: str) -> None:
    """Render a readable Panel 4 conclusion beneath a chart."""
    st.html(
        f"""
        <div class="rr-conclusion">
          <strong>CONCLUSION</strong>
          <p>{text}</p>
        </div>
        """
    )

def _bound(value: float) -> float:
    """Keep a component score between 0 and 100."""
    return max(0.0, min(100.0, float(value)))


def score_irish_lens(
    sahm_indicator: float | None,
    export_share: float | None,
    recession_probability: float | None,
    gdp_index: float | None,
    mdd_index: float | None,
) -> dict:
    components = {}
    weights = {
        "us_recession_probability": 0.35,
        "irish_sahm": 0.25,
        "us_export_share": 0.25,
        "gdp_mdd_divergence": 0.15,
    }

    if recession_probability is not None:
        components["us_recession_probability"] = _bound(
            recession_probability
        )

    if sahm_indicator is not None:
        components["irish_sahm"] = _bound(
            sahm_indicator / 0.50 * 67
        )

    if export_share is not None:
        components["us_export_share"] = _bound(
            (export_share - 20) / 20 * 100
        )

    if gdp_index is not None and mdd_index is not None:
        divergence = abs(gdp_index - mdd_index)
        components["gdp_mdd_divergence"] = _bound(
            divergence / 50 * 100
        )

    if not components:
        return {
            "score": 0.0,
            "status": "WATCH",
            "components": {},
        }

    available_weight = sum(weights[key] for key in components)
    score = sum(
        components[key] * weights[key]
        for key in components
    ) / available_weight

    status = (
        "ALERT"
        if score >= 67
        else "WATCH"
        if score >= 34
        else "CALM"
    )

    return {
        "score": round(score, 1),
        "status": status,
        "components": components,
    }

def load_irish_lens_signal(
    selected_date: pd.Timestamp,
) -> dict:
    gdp = _slice_to_date(
        _to_time_series(_read_cached_frame(GDP_CACHE)),
        selected_date,
    )
    mdd = _slice_to_date(
        _to_time_series(_read_cached_frame(MDD_CACHE)),
        selected_date,
    )
    unemployment = _slice_to_date(
        _to_time_series(_read_cached_frame(UNEMPLOYMENT_CACHE)),
        selected_date,
    )
    export_exposure = _load_export_exposure(selected_date)
    recession_probability = load_recession_probability(selected_date)

    sahm_indicator = None
    if not unemployment.empty:
        sahm = compute_sahm_rule(unemployment)
        valid_sahm = sahm["sahm_indicator"].dropna()
        if not valid_sahm.empty:
            sahm_indicator = float(valid_sahm.iloc[-1])

    export_share = None
    if not export_exposure.empty:
        valid_average = export_exposure[
            "12-month average (%)"
        ].dropna()
        if not valid_average.empty:
            export_share = float(valid_average.iloc[-1])

    us_probability = None
    if not recession_probability.empty:
        us_probability = float(recession_probability.iloc[-1])

    gdp_index = None
    mdd_index = None
    if not gdp.empty and not mdd.empty:
        baseline_date = pd.Timestamp("2014-12-31")
        gdp_baseline = gdp[gdp.index <= baseline_date]
        mdd_baseline = mdd[mdd.index <= baseline_date]
        if not gdp_baseline.empty and not mdd_baseline.empty:
            gdp_index = float(gdp.iloc[-1] / gdp_baseline.iloc[-1] * 100)
            mdd_index = float(mdd.iloc[-1] / mdd_baseline.iloc[-1] * 100)

    return score_irish_lens(
        sahm_indicator=sahm_indicator,
        export_share=export_share,
        recession_probability=us_probability,
        gdp_index=gdp_index,
        mdd_index=mdd_index,
    )

def _mdd_recession_starts(mdd: pd.Series) -> pd.DatetimeIndex:
    """Return quarter-end dates confirming two consecutive MDD declines."""
    declines = mdd.sort_index().pct_change().lt(0)
    two_consecutive_declines = declines & declines.shift(
        1,
        fill_value=False,
    )
    episode_starts = two_consecutive_declines & ~two_consecutive_declines.shift(
        1,
        fill_value=False,
    )
    return pd.DatetimeIndex(episode_starts.index[episode_starts])


@st.cache_data(ttl=3600, max_entries=100)
def _compute_irish_track_record(
    as_of: pd.Timestamp,
) -> dict[str, int | float | None]:
    """Backtest warnings against two-quarter MDD contractions."""
    mdd = _slice_to_date(
        _to_time_series(_read_cached_frame(MDD_CACHE)),
        as_of,
    )
    exports = _load_export_exposure(as_of)

    empty_result = {
        "caught": None,
        "false_alarms": None,
        "avg_lead_months": None,
    }
    if mdd.empty or exports.empty:
        return empty_result

    valid_export_dates = exports.loc[
        exports["12-month average (%)"].notna(),
        "Date",
    ]
    if valid_export_dates.empty:
        return empty_result

    first_score_date = max(
        mdd.index.min(),
        pd.Timestamp(valid_export_dates.min()),
    )
    last_outcome_date = mdd.index.max()
    score_dates = pd.date_range(
        start=first_score_date,
        end=last_outcome_date,
        freq=pd.offsets.MonthEnd(),
    )
    if score_dates.empty:
        return empty_result

    scores = pd.Series(
        [
            load_irish_lens_signal(score_date)["score"]
            for score_date in score_dates
        ],
        index=score_dates,
        dtype="float64",
    )

    warning = scores >= IRISH_WARNING_SCORE
    warning_starts = scores.index[
        warning & ~warning.shift(1, fill_value=False)
    ]

    recession_starts = _mdd_recession_starts(mdd)
    horizon = pd.DateOffset(months=BACKTEST_HORIZON_MONTHS)

    lead_months = []
    for recession_start in recession_starts:
        window_start = recession_start - horizon
        if window_start < scores.index.min():
            continue

        prior_warnings = warning_starts[
            (warning_starts >= window_start)
            & (warning_starts < recession_start)
        ]
        if not prior_warnings.empty:
            days_to_recession = (
                recession_start - prior_warnings[0]
            ).days
            lead_months.append(days_to_recession / 30.4375)

    complete_warnings = warning_starts[
        warning_starts + horizon <= last_outcome_date
    ]
    false_alarms = sum(
        not (
            (recession_starts > warning_start)
            & (recession_starts <= warning_start + horizon)
        ).any()
        for warning_start in complete_warnings
    )

    return {
        "caught": len(lead_months),
        "false_alarms": int(false_alarms),
        "avg_lead_months": (
            round(sum(lead_months) / len(lead_months), 1)
            if lead_months
            else None
        ),
    }
    
def render(as_of: date) -> dict:
    """Render the compact Irish Lens quadrant."""
    selected_date = pd.Timestamp(as_of)

    gdp = _slice_to_date(
        _to_time_series(_read_cached_frame(GDP_CACHE)),
        selected_date,
    )
    mdd = _slice_to_date(
        _to_time_series(_read_cached_frame(MDD_CACHE)),
        selected_date,
    )
    unemployment = _slice_to_date(
        _to_time_series(_read_cached_frame(UNEMPLOYMENT_CACHE)),
        selected_date,
    )
    export_exposure = _load_export_exposure(selected_date)
    recession_probability = load_recession_probability(selected_date)

    sahm_indicator = None
    if not unemployment.empty:
        sahm = compute_sahm_rule(unemployment)
        if not sahm["sahm_indicator"].dropna().empty:
            sahm_indicator = float(
                sahm["sahm_indicator"].dropna().iloc[-1]
            )

    latest_export_share = None
    if not export_exposure.empty:
        rolling_average = export_exposure[
            "12-month average (%)"
        ].dropna()
        if not rolling_average.empty:
            latest_export_share = float(rolling_average.iloc[-1])

    latest_recession_probability = None
    if not recession_probability.empty:
        latest_recession_probability = float(
            recession_probability.iloc[-1]
        )

    gdp_index = None
    mdd_index = None
    if not gdp.empty and not mdd.empty:
        baseline_date = pd.Timestamp("2014-12-31")
        gdp_baseline = gdp[gdp.index <= baseline_date]
        mdd_baseline = mdd[mdd.index <= baseline_date]
        if not gdp_baseline.empty and not mdd_baseline.empty:
            gdp_index = float(gdp.iloc[-1] / gdp_baseline.iloc[-1] * 100)
            mdd_index = float(mdd.iloc[-1] / mdd_baseline.iloc[-1] * 100)

    panel_signal = score_irish_lens(
        sahm_indicator=sahm_indicator,
        export_share=latest_export_share,
        recession_probability=latest_recession_probability,
        gdp_index=gdp_index,
        mdd_index=mdd_index,
    )

    trigger_count = 0
    if not unemployment.empty:
        sahm = compute_sahm_rule(unemployment)
        trigger_count = int(sahm["trigger"].fillna(False).sum())

    latest_export_share = None
    if not export_exposure.empty:
        latest_export_share = float(
            export_exposure["US Share (%)"].iloc[-1]
        )

    score = panel_signal["score"]
    status = panel_signal["status"]

    if status == "ALERT":
        verdict = (
        "Multiple Irish Lens indicators indicate acute recession risk; "
        "the evidence is broad but does not prove a recession."
        )
    elif status == "WATCH":
        verdict = (
        "Irish Lens indicators are mixed or moderately elevated; "
        "monitor US transmission and domestic warning signals."
        )
    else:
        verdict = (
        "Irish Lens indicators remain contained relative to the "
        "current scoring thresholds."
        )

    st.html(
        f"""
        <div class="rr-panel-body">
          <div class="rr-panel-title-row">
            <div>
              <h2 class="rr-panel-title">Exposure & domestic demand</h2>
              <p class="rr-panel-summary">{verdict}</p>
            </div>
            <div class="rr-score">
              <strong>{panel_signal["score"]:.0f}</strong><span>/100· {panel_signal["status"]}</span>
            </div>
          </div>
        </div>
        """
    )

    export_value = (
        f"{latest_export_share:.1f}%"
        if latest_export_share is not None
        else "—"
    )
    gdp_available = "YES" if not gdp.empty else "NO"
    mdd_available = "YES" if not mdd.empty else "NO"

    st.html(
        f"""
        <div class="rr-metric-grid">
          <div class="rr-metric">
            <span>US EXPORT SHARE</span>
            <strong>{export_value}</strong>
          </div>
          <div class="rr-metric">
            <span>SAHM TRIGGERS</span>
            <strong>{trigger_count}</strong>
          </div>
          <div class="rr-metric">
            <span>GDP / MDD</span>
            <strong>{gdp_available} / {mdd_available}</strong>
          </div>
        </div>
        """
    )

    if export_exposure.empty:
        st.info(
            "Irish export exposure data is not available "
            "for the selected date."
        )
    else:
        _render_export_exposure_chart(
            export_exposure,
            compact=True,
            key="irish_export_overview",
        )

    if st.button("Explore panel", key="open_irish"):
        st.session_state.active_panel = "irish"
        st.rerun()

    return {
        "score": panel_signal["score"],
        "status": panel_signal["status"],
        "verdict": verdict,
        "components": panel_signal["components"],
        "track_record": _compute_irish_track_record(selected_date),
    }

def render_detail(as_of: date) -> None:
    """Render the full Irish Lens individual-panel view."""
    selected_date = pd.Timestamp(as_of)
    panel_signal = load_irish_lens_signal(selected_date)
    st.html(
        f"""
        <section class="rr-detail-hero">
          <div>
            <p class="rr-kicker">
              PANEL 04 / IRISH LENS / MATTHIAS CLARK
            </p>
            <h1 class="rr-detail-title">Exposure & domestic demand</h1>
            <p class="rr-detail-lede">
              Irish economic activity, labour-market pressure and exposure
              to the United States, assessed within one historical-date view.
            </p>
          </div>
          <div class="rr-detail-score">
            <strong>{panel_signal["score"]:.0f}</strong>
            <span>/100 · {panel_signal["status"]}</span>
          </div>
        </section>
        """
    )
    gdp_tab, sahm_tab, exports_tab, probability_tab, method, sources = st.tabs(
        [
            "GDP & MDD",
            "Irish Sahm Rule",
            "US Export Exposure",
            "US Recession Probability",
            "Method",
            "Sources",
        ]
    )

    gdp = _slice_to_date(
        _to_time_series(_read_cached_frame(GDP_CACHE)),
        selected_date,
    )
    mdd = _slice_to_date(
        _to_time_series(_read_cached_frame(MDD_CACHE)),
        selected_date,
    )
    unemployment = _slice_to_date(
        _to_time_series(_read_cached_frame(UNEMPLOYMENT_CACHE)),
        selected_date,
    )
    export_exposure = _load_export_exposure(selected_date)
    recession_probability = load_recession_probability(selected_date)

    with gdp_tab:
        if gdp.empty or mdd.empty:
            st.info("GDP and MDD data are unavailable for this date.")
        else:
            st.plotly_chart(
               _plot_gdp_vs_mdd(gdp, mdd),
               width="stretch",
               config={"displayModeBar": False, "responsive": True},
               key="irish_gdp_mdd_tab",
            )
            _render_conclusion(
                "Headline GDP has risen sharply compared with 2014 Q4, "
                "while Modified Domestic Demand provides a steadier view "
                "of domestic activity. GDP can include multinational "
                "distortions."
            )
            
    with sahm_tab:
        if unemployment.empty:
            st.info("Irish unemployment data is unavailable for this date.")
        else:
            sahm = compute_sahm_rule(unemployment)
            trigger_count = int(sahm["trigger"].fillna(False).sum())

            st.plotly_chart(
                _plot_sahm_rule(sahm),
                width="stretch",
                config={"displayModeBar": False, "responsive": True},
                key="irish_sahm_tab",
            )

            if trigger_count == 0:
                _render_conclusion(
                    "The Irish Sahm indicator has not reached its "
                    "0.50-point trigger."
                )
            else:
                _render_conclusion(
                    f"The Irish Sahm indicator has crossed the "
                    f"0.50-point trigger {trigger_count} time(s). "
                    "This is a warning indicator, not proof of recession."
                )
    with exports_tab:
        if export_exposure.empty:
            st.info(
                "Irish export exposure data is unavailable for this date."
            )
        else:
            _render_export_exposure_chart(
                export_exposure,
                key="irish_export_tab",
            )
            latest_share = float(
                export_exposure["US Share (%)"].iloc[-1]
            )
            rolling_average = export_exposure[
                "12-month average (%)"
            ].dropna()

            if rolling_average.empty:
                _render_conclusion(
                    f"The latest US share of Irish exports is "
                    f"{latest_share:.1f}%. "
                    "This indicates exposure, not proof that a US "
                    "downturn will cause an Irish recession."
                )
            else:
                latest_average = float(rolling_average.iloc[-1])
                _render_conclusion(
                    f"The latest US share of Irish exports is "
                    f"{latest_share:.1f}%, with a 12-month average of "
                    f"{latest_average:.1f}%. "
                    "This indicates exposure, not proof that a US "
                    "downturn will cause an Irish recession."
                )

    with probability_tab:
        st.html(
            f"""
            <div class="rr-section-head">
              <span>US RECESSION PROBABILITY</span>
              <strong>12-Month Baseline Probit · AS OF {selected_date:%d %b %Y}</strong>
            </div>
            """
        )

        if recession_probability.empty:
            st.info(
                "US recession probability is unavailable for this date."
            )
        else:
            probability_figure = go.Figure()

            probability_figure.add_trace(
                go.Scatter(
                    x=recession_probability.index,
                    y=recession_probability,
                    mode="lines",
                    name="Recession probability",
                    line={"color": "#d75f47", "width": 2},
                )
            )

            probability_figure.update_layout(
                title="Estimated US Recession Probability",
                xaxis_title="Date",
                yaxis_title="Probability (%)",
                yaxis_range=[0, 100],
                hovermode="x unified",
            )

            st.plotly_chart(
                probability_figure,
                width="stretch",
                config={
                    "displayModeBar": False,
                    "responsive": True,
                },
                key="irish_us_recession_probability",
            )

            latest_probability = float(recession_probability.iloc[-1])

            _render_conclusion(
                f"The latest estimated probability of a US recession "
                f"within the next 12 months is "
                f"{latest_probability:.1f}%. "
                "This is a model estimate, not a certainty."
            )
    with method:
        st.html(
            """
            <div class="rr-section-head">
              <span>METHOD</span>
              <strong>CACHE-FIRST CALCULATION</strong>
            </div>
            """
        )
        st.info(
            "US export share is calculated as US exports divided by total "
            "Irish exports, multiplied by 100. The result is accompanied "
            "by a 12-month rolling average."
        )
        st.write(
            """
            GDP and MDD are indexed using 2014 Q4 as the common baseline.
            The Irish Sahm indicator compares the three-month unemployment
            average with its twelve-month minimum. The 0.50-point threshold
            is shown as a recession warning.
            Current weights are 35% US recession probability, 25% Irish Sahm,
            25% US export share, and 15% GDP/MDD divergence. Component scores
            are bounded from 0 to 100; missing components are omitted and the
            remaining weights are renormalized. The status bands are CALM
            below 34, WATCH from 34 through 66, and ALERT at 67 or above.
            """
        )



    with sources:
        st.html(
            """
            <div class="rr-section-head">
              <span>SOURCES</span>
              <strong>CSO CACHE-FIRST</strong>
            </div>
            """
        )
        st.write(
            """
            - Central Statistics Office TSM10: country-level Irish exports
            - Central Statistics Office TSM01: total Irish exports
            - Central Statistics Office NAQ01: headline GDP
            - Central Statistics Office NAQ05: modified domestic demand
            - Central Statistics Office MUM01: monthly unemployment
            """
        )
        st.info(
            "Local CSV caches are used to keep the dashboard functional "
            "offline. Cached observations are filtered by the selected date."
        )
   
