"""The Sahm rule: a recession signal from the unemployment rate alone.

Generic on purpose (no FRED/US specifics), so Panel 4 can reuse it on Irish data.
Backward-looking only, so input cut by filter_as_of can't leak the future.
"""

import pandas as pd

SAHM_THRESHOLD = 0.5  # Sahm (2019), in percentage points

SAHM_DIFFERENCE_NOTE = (
    "The two lines differ slightly because FRED's real-time series uses each "
    "month's unemployment rate as it was first published, while ours uses "
    "today's revised figures. Revisions are small (usually 0.1 points or less), "
    "but near the 0.5 line they can decide whether the rule triggers at all."
)


def sahm_rule(unemployment: pd.Series) -> pd.Series:
    """3-month average unemployment minus its lowest value in the previous 12 months.

    - resample("MS") makes missing months explicit (e.g. Oct 2025, never collected),
      so windows don't silently span extra months; also accepts end-of-month dates.
    - min_periods=2 keeps the average going across a single missing month.
    - Rounded to 2dp like FRED, which also stops 0.4999999 failing a >= 0.5 test.
    """
    monthly = unemployment.dropna().resample("MS").mean()
    three_month_avg = monthly.rolling(3, min_periods=2).mean()
    # shift(1): the window covers t-12 to t-1, matching FRED's definition.
    previous_low = three_month_avg.shift(1).rolling(12).min()

    indicator = (three_month_avg - previous_low).round(2)
    indicator.name = "sahm"
    return indicator


def sahm_triggers(sahm: pd.Series, threshold: float = SAHM_THRESHOLD) -> list:
    """Dates where the indicator first crosses the threshold (below, then at/above).

    One date per episode. A series that starts above the line, or a month
    next to a gap, isn't a trigger: we never saw it cross.
    """
    last_month = sahm.shift(1)
    first_crossing = (sahm >= threshold) & (last_month < threshold)
    return list(sahm.index[first_crossing])


def compare_with_fred(my_sahm: pd.Series, fred_sahm: pd.Series) -> pd.DataFrame:
    """Validation: ours vs FRED real-time on shared months, with the difference.

    A small, patternless gap means only data revisions differ, not the formula.
    """
    table = pd.concat(
        {"ours": my_sahm, "fred_real_time": fred_sahm}, axis=1, join="inner"
    ).dropna()
    table["difference"] = (table["ours"] - table["fred_real_time"]).round(2)
    return table