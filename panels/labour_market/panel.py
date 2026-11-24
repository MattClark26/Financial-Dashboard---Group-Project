"""Panel 2 on screen: does the labour market confirm the recession warning?

The main app calls only render_panel(as_of). Sections run: verdict, drivers
(Sahm, claims, payrolls), first-reported vs revised, track record.
"""

import pandas as pd
import streamlit as st

from panel2 import charts
from panel2.claims import claims_indicator
from panel2.data import RELEASE_LAG_DAYS, filter_as_of
from panel2.loaders import cached_series, cached_vintages
from panel2.payrolls import monthly_payroll_change
from panel2.sahm import SAHM_DIFFERENCE_NOTE, sahm_rule
from panel2.scorecard import AUGUST_2024_NOTE, recession_periods, recessions_known_at, track_record
from panel2.signal import labour_reading, signal_from_reading
from panel2.vintages import payroll_revisions, series_as_published

SERIES_NEEDED = ["UNRATE", "SAHMREALTIME", "ICSA", "PAYEMS", "USREC"]

# 25 years usually spans 3-4 recessions without squashing bars into hairlines.
WINDOW_CHOICES = {"Last 10 years": 10, "Last 25 years": 25, "All history": None}
DEFAULT_WINDOW = "Last 25 years"

STATUS_LABELS = {
    "green": "🟢 GREEN: not confirming",
    "amber": "🟠 AMBER: weakening",
    "red": "🔴 RED: confirming a recession",
}


def render_panel(as_of) -> None:
    """Draw the whole of Panel 2 for the time machine date `as_of`."""
    as_of = pd.Timestamp(as_of)
    st.header("Labour market: is the warning being confirmed?")
    st.caption(
        "Recessions are ultimately about jobs. Labour data move later than "
        "markets, but when they turn, a downturn usually follows. This panel "
        "checks whether the job market confirms the bond market's warning."
    )

    data = _load_data()
    if data is None:
        return

    _draw_verdict(as_of, data)

    window = st.radio(
        "Chart period", list(WINDOW_CHOICES), index=list(WINDOW_CHOICES).index(DEFAULT_WINDOW),
        horizontal=True, key="panel2_window",  # prefixed to avoid clashing with other panels
    )
    start = _window_start(as_of, WINDOW_CHOICES[window])
    recessions = _recessions_to_shade(data["USREC"], as_of)

    _draw_sahm_section(as_of, data, start, recessions)
    _draw_claims_section(as_of, data, start, recessions)
    _draw_payrolls_section(as_of, data, start, recessions)
    _draw_revisions_section(as_of, start, recessions)
    _draw_track_record_section(as_of, data)
    _draw_data_note(data)


# --- Sections ---


def _draw_verdict(as_of, data) -> None:
    """Traffic light and verdict.

    Same functions as get_signal, so the panel and main app can't disagree;
    called directly so we can also show which month the verdict uses.
    """
    reading = labour_reading(as_of, data["UNRATE"], data["SAHMREALTIME"], data["ICSA"])
    signal = signal_from_reading(reading)

    score_column, verdict_column = st.columns([1, 3])
    score_column.metric("Labour market score", f"{signal['score']:.0f} / 100")
    verdict_column.subheader(STATUS_LABELS[signal["status"]])
    verdict_column.write(signal["verdict"])
    if reading["sahm_month"] is not None:
        source = "as first published" if reading["sahm_source"] == "real-time" else "revised"
        st.caption(
            f"Based on unemployment data for {reading['sahm_month']:%B %Y} ({source}), "
            "the latest released by this date. Score: 0 at the recent low, 75 at the "
            "Sahm trigger, 100 at 0.8 points or more, plus 10 if jobless claims are flagged."
        )


def _draw_sahm_section(as_of, data, start, recessions) -> None:
    # Compute on full visible history, then cut to the window; cutting first
    # would lose the 12-month look-back and blank the chart's start.
    lag = RELEASE_LAG_DAYS["UNRATE"]
    ours = sahm_rule(filter_as_of(data["UNRATE"], as_of, lag))
    real_time = filter_as_of(data["SAHMREALTIME"], as_of, lag)

    st.subheader("1. The Sahm rule")
    st.plotly_chart(
        charts.sahm_chart(ours[start:], real_time[start:], recessions), width="stretch"
    )
    st.caption(charts.SAHM_CAPTION)
    with st.expander("Why are there two lines?"):
        st.write(SAHM_DIFFERENCE_NOTE)


def _draw_claims_section(as_of, data, start, recessions) -> None:
    # Full history first, as with Sahm (52-week look-back).
    claims = filter_as_of(data["ICSA"], as_of, RELEASE_LAG_DAYS["ICSA"])
    table = claims_indicator(claims)

    st.subheader("2. Jobless claims")
    st.plotly_chart(charts.claims_chart(table[start:], recessions), width="stretch")
    st.caption(charts.CLAIMS_CAPTION)


def _draw_payrolls_section(as_of, data, start, recessions) -> None:
    """Payrolls as published on as_of if vintages exist, else today's revised data (noted)."""
    payems = _payems_as_published(as_of)
    note = "Data as published on this date."
    if payems is None or payems.empty:
        payems = filter_as_of(data["PAYEMS"], as_of, RELEASE_LAG_DAYS["PAYEMS"])
        note = "Revision history unavailable, so this uses today's revised figures."

    st.subheader("3. Jobs added each month")
    table = monthly_payroll_change(payems)
    st.plotly_chart(charts.payroll_change_chart(table[start:], recessions), width="stretch")
    st.caption(f"{charts.PAYROLL_CAPTION} {note}")


def _draw_revisions_section(as_of, start, recessions) -> None:
    """First-reported vs revised payrolls. Explains itself if ALFRED data is missing."""
    st.subheader("4. First reported vs revised: did it look different at the time?")
    revisions = _revisions_at(as_of)
    if revisions is None or revisions.empty:
        st.info(
            "No payroll revision history (ALFRED) is available for this date. Either "
            "the date is before ALFRED's archive begins, or the history has not been "
            "downloaded yet (run the app once with FRED_API_KEY set to cache it)."
        )
        return

    st.plotly_chart(charts.revisions_chart(revisions[start:], recessions), width="stretch")
    st.caption(charts.REVISIONS_CAPTION)

    # Skip the last ~3 months: they've barely been revised yet.
    settled = revisions[revisions["first_release_date"] <= as_of - pd.DateOffset(months=3)]
    recent = settled.tail(12)
    if not recent.empty:
        average = recent["revision"].mean()
        direction = "raised" if average > 0 else "lowered"
        st.write(
            f"Over {recent.index[0]:%b %Y} to {recent.index[-1]:%b %Y}, later revisions "
            f"{direction} the first-reported jobs numbers by an average of "
            f"**{abs(average):,.0f}k per month**."
        )


def _draw_track_record_section(as_of, data) -> None:
    """Sahm rule scored on real-time data (the honest test) and revised data (hindsight)."""
    lag = RELEASE_LAG_DAYS["UNRATE"]
    real_time = track_record(filter_as_of(data["SAHMREALTIME"], as_of, lag), data["USREC"], as_of)
    revised = track_record(sahm_rule(filter_as_of(data["UNRATE"], as_of, lag)), data["USREC"], as_of)

    st.subheader("5. Track record: can we trust the Sahm rule?")
    left, right = st.columns(2)
    left.markdown("**As published at the time** (FRED real-time, from 1960)")
    left.dataframe(real_time["summary"], hide_index=True, width="stretch")
    right.markdown("**With today's revised data** (hindsight)")
    right.dataframe(revised["summary"], hide_index=True, width="stretch")
    st.caption(
        "A recession counts as caught if the rule triggered within 12 months of its "
        "start; any other trigger is a false alarm. Lag = months from the start of the "
        "recession to the trigger (the figure is published about a month later). Only "
        "recessions officially announced by this date are counted."
    )

    with st.expander("Recession-by-recession detail"):
        st.dataframe(_recession_detail(real_time["recessions"]), hide_index=True, width="stretch")

    if as_of >= pd.Timestamp("2024-08-08"):
        st.markdown("**The August 2024 false alarm**")
        st.write(AUGUST_2024_NOTE)


def _draw_data_note(data) -> None:
    from_cache = [name for name, series in data.items() if series.attrs.get("source") == "cache"]
    note = "Source: FRED and ALFRED, Federal Reserve Bank of St. Louis."
    if from_cache:
        note += f" Live download unavailable, so showing saved copies of: {', '.join(from_cache)}."
    st.caption(note)


# --- Helpers ---


def _load_data():
    """All series the panel needs, or one clear error message and None."""
    try:
        return {series_id: cached_series(series_id) for series_id in SERIES_NEEDED}
    except Exception as error:
        st.error(f"Labour market data could not be loaded: {error}")
        return None


@st.cache_data(ttl="12h", show_spinner=False)
def _revisions_at(as_of):
    try:
        return payroll_revisions(cached_vintages("PAYEMS"), as_of)
    except Exception:
        return None


@st.cache_data(ttl="12h", show_spinner=False)
def _payems_as_published(as_of):
    try:
        return series_as_published(cached_vintages("PAYEMS"), as_of)
    except Exception:
        return None


def _window_start(as_of, years):
    if years is None:
        return None  # [None:] keeps everything
    return as_of - pd.DateOffset(years=years)


def _recessions_to_shade(usrec, as_of) -> pd.DataFrame:
    """Recessions announced by as_of, with any ongoing one shaded only up to as_of."""
    known = recessions_known_at(recession_periods(usrec), as_of)
    known["end"] = known["end"].clip(upper=as_of)
    return known


def _recession_detail(recessions) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Recession began": recessions["start"].dt.strftime("%b %Y"),
            "Sahm rule triggered": recessions["first_trigger"].dt.strftime("%b %Y").fillna("No"),
            "Months after start": recessions["lag_months"].astype("string").fillna("-"),
        }
    )
