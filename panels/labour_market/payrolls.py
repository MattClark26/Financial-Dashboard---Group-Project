"""Nonfarm payrolls (PAYEMS, thousands): jobs added or lost each month.

The level just grows with population; the monthly change shows the cycle.
Sustained negative months have only happened around recessions.
"""

import pandas as pd


def level_to_monthly_change(level: pd.Series) -> pd.Series:
    """Month-on-month change in thousands of jobs.

    vintages.py must use this same rule for first-reported vs revised to be
    fair; change both together. resample("MS") makes a missing month NaN
    instead of letting diff() silently span two months.
    """
    monthly = level.dropna().resample("MS").mean()
    change = monthly.diff()
    change.name = "monthly_change"
    return change


def monthly_payroll_change(payems: pd.Series) -> pd.DataFrame:
    """monthly_change and three_month_avg (thousands) for the payrolls chart.

    The 3-month average smooths survey noise (about +/-130k a month).
    """
    change = level_to_monthly_change(payems)
    return pd.DataFrame(
        {
            "monthly_change": change,
            "three_month_avg": change.rolling(3).mean(),
        }
    )