"""Real-time vs revised payrolls: how different did the picture look at the time?

First estimates are revised for months, and at turning points they tend to be
too optimistic, so revised data make past signals look cleaner than they were.
ALFRED lets us rebuild each release ("vintage") and compare first vs latest.
"""

import pandas as pd

# Longest genuine first-release delay is 80 days (Sep 2025, shutdown). The
# 3 Nov 1961 release backfilled history to 1939, decades late; this excludes it.
MAX_FIRST_RELEASE_DELAY_DAYS = 120


def build_vintage_table(vintages: pd.DataFrame, as_of=None) -> pd.DataFrame:
    """Grid of release date (rows) x month (columns): each row is the full series as published that day.

    ALFRED lists only new or changed values, so ffill carries each forward until revised.
    realtime_start is the exact publication date, so no release lag is needed.
    """
    if as_of is not None:
        vintages = vintages[vintages["realtime_start"] <= pd.Timestamp(as_of)]

    table = vintages.pivot(index="realtime_start", columns="date", values="value")
    return table.ffill()


def series_as_published(vintages: pd.DataFrame, as_of) -> pd.Series:
    """The series exactly as downloadable on as_of (empty if nothing released yet)."""
    table = build_vintage_table(vintages, as_of)
    if table.empty:
        return pd.Series(dtype=float)
    return table.iloc[-1].dropna()


def payroll_revisions(vintages: pd.DataFrame, as_of=None) -> pd.DataFrame:
    """Each month's first-reported vs latest change (thousands), plus revision and first_release_date.

    Never mix vintages: both levels in a change come from the same release,
    enforced by diffing along each row. Must match payrolls.level_to_monthly_change
    (regular calendar, then diff); done vectorised because calling it per release
    took ~5s per slider move.

    Excludes months in the archive's first release and months first published
    over MAX_FIRST_RELEASE_DELAY_DAYS late: neither was a real first report.
    """
    table = build_vintage_table(vintages, as_of)

    # Regular calendar, so neighbouring columns are neighbouring months.
    all_months = pd.date_range(table.columns.min(), table.columns.max(), freq="MS")
    table = table.reindex(columns=all_months)

    changes_by_release = table.diff(axis=1)

    # First release = where the LEVEL first appears, not where a change first
    # becomes computable (which could be later if the prior month was missing).
    months_ever_published = table.columns[table.notna().any()]
    first_release_date = table[months_ever_published].apply(pd.Series.first_valid_index)

    # NaN if that release lacked the prior month; dropped at the end.
    first_reported = pd.Series(
        [changes_by_release.at[release, month] for month, release in first_release_date.items()],
        index=first_release_date.index,
    )
    revised = changes_by_release.iloc[-1]  # last row = latest vintage (forward-filled)

    result = pd.DataFrame(
        {
            "first_reported": first_reported,
            "revised": revised,
            "revision": revised - first_reported,
            "first_release_date": first_release_date,
        }
    )
    result.index.name = "date"

    in_first_archive_release = result["first_release_date"] == table.index[0]
    delay = result["first_release_date"] - result.index.to_series()
    added_as_history = delay > pd.Timedelta(days=MAX_FIRST_RELEASE_DELAY_DAYS)
    return result[~in_first_archive_release & ~added_as_history].dropna()