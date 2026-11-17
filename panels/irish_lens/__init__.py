"""Panel 4: The Irish Lens"""

from datetime import date
from pathlib import Path

from pyjstat import pyjstat
import plotly.graph_objects as go
import pandas as pd
import streamlit as st    

TITLE = "Irish lens"

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

UNEMPLOYMENT_CACHE = "irish_unemployment.csv"
GDP_CACHE = "irish_gdp.csv"
MDD_CACHE = "irish_mdd.csv"

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
        line_dash="dash",
        annotation_text="0.50 trigger",
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
    
def render(as_of: date) -> dict:
    """Render the Irish Lens panel and return Thermometer metrics."""
    selected_date = pd.Timestamp(as_of)
    
    gdp = _slice_to_date(
        _to_time_series(_read_cached_frame(GDP_CACHE)),
        selected_date,
    )
    mdd = _slice_to_date(
        _to_time_series(_read_cached_frame(MDD_CACHE)),
        selected_date,
    )
    if not gdp.empty and not mdd.empty:
        baseline_date = pd.Timestamp("2014-12-31")

        gdp_has_baseline = (gdp.index <= baseline_date).any()
        mdd_has_baseline = (mdd.index <= baseline_date).any()

        if gdp_has_baseline and mdd_has_baseline:
            st.plotly_chart(
                _plot_gdp_vs_mdd(gdp, mdd),
                width="stretch",
            )
            st.caption(
                "Headline Irish GDP surged in 2015 because of multinational "
                "intellectual-property onshoring and aircraft-leasing transfers, "
                "while Modified Domestic Demand better reflects domestic activity."
            )
        else:
            st.info(
                "GDP and MDD need data through 2014 Q4 for the comparison chart."
            )
    else:
        st.info(
            "GDP and MDD data are unavailable for the selected date."
        )
    st.subheader("Panel 4 - The Irish Lens")
    st.caption(f"Selected date: {selected_date:%Y-%m-%d}")

    unemployment = _to_time_series(
        _read_cached_frame(UNEMPLOYMENT_CACHE)
    )
    unemployment = _slice_to_date(unemployment, selected_date)

    if unemployment.empty:
        st.info(
            "Irish unemployment data is not available for the selected date."
        )
    else:
        sahm = compute_sahm_rule(unemployment)
        trigger_count = int(sahm["trigger"].fillna(False).sum())
        st.caption(
            f"Irish Sahm Rule observations: {len(sahm)}; "
            f"triggers: {trigger_count}"
        )
        st.plotly_chart(
            _plot_sahm_rule(sahm),
            width="stretch",
        )
    return { 
        "score": 0.0,
        "status": "green",
        "verdict": "Irish Lens analysis is not available yet.",
        "track_record": {
            "caught": 0,
            "false_alarms": 0,
            "avg_lead_months": 0,
        },
   }
  
   
