"""Initial jobless claims (FRED: ICSA): weekly early warning ahead of the Sahm rule."""

import pandas as pd

CLAIMS_THRESHOLD_PCT = 20
SMOOTHING_WEEKS = 4
LOOKBACK_WEEKS = 52


def claims_indicator(claims: pd.Series) -> pd.DataFrame:
    """Flag when the 4-week average is 20%+ above its prior 52-week low.

    Pass claims cut with filter_as_of(..., RELEASE_LAG_DAYS["ICSA"]).
    """
    four_week_avg = claims.rolling(SMOOTHING_WEEKS).mean()
    # Low of the smoothed series (so one quiet week can't set the bar),
    # excluding the current week, like the Sahm rule.
    low_52_weeks = four_week_avg.shift(1).rolling(LOOKBACK_WEEKS).min()
    pct_above_low = (four_week_avg / low_52_weeks - 1) * 100

    return pd.DataFrame({
        "claims": claims,
        "four_week_avg": four_week_avg,
        "low_52_weeks": low_52_weeks,
        "pct_above_low": pct_above_low.round(1),
        "flagged": pct_above_low >= CLAIMS_THRESHOLD_PCT,
    })