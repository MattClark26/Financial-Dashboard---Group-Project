"""Track record: how well has the Sahm rule caught past US recessions (USREC/NBER)?

Scores caught recessions, lag (it's a confirmation signal, so expect a few
months after the start) and false alarms. Works on any Sahm series, so the
panel can compare real-time vs revised data.
"""

import pandas as pd

from .sahm import sahm_triggers

# Months either side of a recession's start for a trigger to count. The same
# window defines false alarms, so every trigger is exactly one or the other.
MATCH_WINDOW_MONTHS = 12

# Post-war era; unemployment data begin in 1948, plus a year of history.
SCORECARD_START = "1950-01-01"

# Time machine: when the NBER announced each recession's start, so a June 2008
# view doesn't "know" about January 2008. Keys are the first USREC month.
# Source: https://www.nber.org/research/business-cycle-dating
NBER_START_ANNOUNCED = {
    "1980-02-01": "1980-06-03",
    "1981-08-01": "1982-01-06",
    "1990-08-01": "1991-04-25",
    "2001-04-01": "2001-11-26",
    "2008-01-01": "2008-12-01",
    "2020-03-01": "2020-06-08",
}

# No NBER announcements before 1978: assume known 12 months after the end
# (cautious, so a recession is never revealed too early).
PRE_1980_KNOWN_AFTER_MONTHS = 12

AUGUST_2024_NOTE = (
    "In August 2024 the Sahm rule triggered (July unemployment, published 2 August, "
    "pushed the reading to 0.53), yet no recession followed. Unemployment had risen "
    "mainly because more people were joining the labour force, largely through "
    "immigration, while layoffs stayed low: jobless claims were about 17% above "
    "their low, under our 20% flag. Claudia Sahm herself said the rule was likely "
    "overstating the risk. The lesson: the rule assumes unemployment rises because "
    "people lose jobs, and that is worth checking against claims before trusting it."
)


def recession_periods(usrec: pd.Series) -> pd.DataFrame:
    """The 0/1 USREC series as a start/end table of recessions since SCORECARD_START."""
    usrec = usrec[usrec.index >= SCORECARD_START]
    in_recession = usrec == 1
    starts = usrec.index[in_recession & ~in_recession.shift(1, fill_value=False)]
    ends = usrec.index[in_recession & ~in_recession.shift(-1, fill_value=False)]
    return pd.DataFrame({"start": starts, "end": ends})


def recessions_known_at(periods: pd.DataFrame, as_of) -> pd.DataFrame:
    """Only the recessions officially announced by as_of."""
    as_of = pd.Timestamp(as_of)
    known_dates = [_date_recession_became_known(row.start, row.end) for row in periods.itertuples()]
    return periods[[known <= as_of for known in known_dates]].reset_index(drop=True)


def track_record(sahm: pd.Series, usrec: pd.Series, as_of=None) -> dict:
    """Score a Sahm series (already cut to as_of; default today) against recessions.

    Returns "recessions" (with first_trigger and lag_months, negative = early),
    "false_alarms", "pending" (too recent to judge) and "summary".

    Takes the full series, not just triggers, so recessions before its first
    reading can be excluded: the rule had no chance to catch them.
    """
    as_of = pd.Timestamp.today().normalize() if as_of is None else pd.Timestamp(as_of)
    window = pd.DateOffset(months=MATCH_WINDOW_MONTHS)

    triggers = [
        t for t in sahm_triggers(sahm) if pd.Timestamp(SCORECARD_START) <= t <= as_of
    ]
    recessions = recessions_known_at(recession_periods(usrec), as_of)
    first_reading = sahm.first_valid_index()
    recessions = recessions[recessions["start"] >= first_reading].reset_index(drop=True)

    # Match each recession to its earliest nearby trigger.
    first_triggers, lags = [], []
    for start in recessions["start"]:
        nearby = [t for t in triggers if start - window <= t <= start + window]
        first = min(nearby) if nearby else pd.NaT
        first_triggers.append(first)
        lags.append(_months_between(start, first) if nearby else None)
    recessions["first_trigger"] = first_triggers
    recessions["lag_months"] = pd.array(lags, dtype="Int64")

    false_alarms, pending = [], []
    for trigger in triggers:
        near_a_recession = any(
            start - window <= trigger <= start + window for start in recessions["start"]
        )
        if near_a_recession:
            continue
        if trigger + window > as_of:
            pending.append(trigger)
        else:
            false_alarms.append(trigger)

    return {
        "recessions": recessions,
        "false_alarms": false_alarms,
        "pending": pending,
        "summary": _summary_table(recessions, false_alarms, pending),
    }


def _summary_table(recessions: pd.DataFrame, false_alarms: list, pending: list) -> pd.DataFrame:
    """Headline numbers. Median lag, since one outlier skews a mean of ~10 recessions."""
    caught = recessions["first_trigger"].notna().sum()
    median_lag = recessions["lag_months"].median()
    rows = {
        "Recessions caught": f"{caught} of {len(recessions)}",
        "Recessions missed": str(len(recessions) - caught),
        "False alarms": str(len(false_alarms)),
        "Median lag (months)": "n/a" if pd.isna(median_lag) else f"{median_lag:+.0f}",
    }
    if pending:
        rows["Too recent to judge"] = ", ".join(f"{t:%b %Y}" for t in pending)
    return pd.DataFrame({"Measure": list(rows), "Result": list(rows.values())})


def _date_recession_became_known(start: pd.Timestamp, end: pd.Timestamp) -> pd.Timestamp:
    announced = NBER_START_ANNOUNCED.get(start.strftime("%Y-%m-%d"))
    if announced is not None:
        return pd.Timestamp(announced)
    return end + pd.DateOffset(months=PRE_1980_KNOWN_AFTER_MONTHS)


def _months_between(earlier: pd.Timestamp, later: pd.Timestamp) -> int:
    """Whole calendar months from earlier to later (negative if before)."""
    return (later.year - earlier.year) * 12 + (later.month - earlier.month)
