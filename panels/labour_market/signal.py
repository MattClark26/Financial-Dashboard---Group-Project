"""Panel 2's contribution to the Recession Thermometer.

get_signal(as_of) -> {"score": 0-100, "status": "green"|"amber"|"red", "verdict": str}

Score: linear from 0 (unemployment at its recent low) to 75 at the 0.5 Sahm
trigger and 100 at 0.8, plus 10 if claims are flagged. Red >= 75, amber >= 40.
- Sahm drives it: best track record (every post-war recession, 2 false alarms).
- The trigger lands exactly on red, so red means "Sahm has triggered".
- Capped at 0.8: every past episode beyond that was a recession.
- Claims are only a +10 bump: noisier (6 false alarms since 1967) and tuned
  on the same history, so they can tip a boundary but never alarm alone.
"""

import logging

import numpy as np
import pandas as pd

from panel2.claims import claims_indicator
from panel2.data import RELEASE_LAG_DAYS, filter_as_of
from panel2.sahm import SAHM_THRESHOLD, sahm_rule

logger = logging.getLogger(__name__)

SAHM_POINTS = [0.0, SAHM_THRESHOLD, 0.8]
SCORE_POINTS = [0.0, 75.0, 100.0]
CLAIMS_BUMP = 10.0

# 75 = the Sahm trigger. 40 = a Sahm reading of ~0.27, clearly beyond survey noise.
RED_FROM = 75.0
AMBER_FROM = 40.0

# Neutral amber 50 neither reassures nor alarms. (Agree with the group: it
# affects the composite thermometer.)
UNAVAILABLE_SIGNAL = {
    "score": 50.0,
    "status": "amber",
    "verdict": "Labour market data are not available for this date, so this panel gives a neutral reading.",
}


def get_signal(as_of) -> dict:
    """Panel 2's signal at as_of. Never raises: one panel must not break the thermometer."""
    # Imported here so the pure functions and their tests don't need Streamlit.
    from panel2.loaders import cached_series

    try:
        unemployment = cached_series("UNRATE")
        real_time_sahm = _try_to_load(cached_series, "SAHMREALTIME")
        claims = _try_to_load(cached_series, "ICSA")
        reading = labour_reading(as_of, unemployment, real_time_sahm, claims)
        return signal_from_reading(reading)
    except Exception as error:
        logger.warning("Panel 2 signal unavailable for %s: %s", as_of, error)
        return dict(UNAVAILABLE_SIGNAL)


def labour_reading(as_of, unemployment, real_time_sahm=None, claims=None) -> dict:
    """The latest Sahm and claims numbers visible at as_of.

    Prefers FRED's real-time Sahm (what was actually known then); our own
    calculation on revised UNRATE is the fallback. Claims use today's revised
    ICSA, a known limitation (revisions are small; weekly vintages are huge).
    Values are None where no data exist yet.
    """
    sahm, sahm_month, sahm_source = _latest_sahm(as_of, unemployment, real_time_sahm)

    claims_flagged = claims_pct = claims_week = None
    if claims is not None:
        visible_claims = filter_as_of(claims, as_of, RELEASE_LAG_DAYS["ICSA"])
        table = claims_indicator(visible_claims).dropna()
        if not table.empty:
            latest = table.iloc[-1]
            claims_flagged = bool(latest["flagged"])
            claims_pct = float(latest["pct_above_low"])
            claims_week = table.index[-1]

    return {
        "sahm": sahm,
        "sahm_month": sahm_month,
        "sahm_source": sahm_source,
        "claims_flagged": claims_flagged,
        "claims_pct_above_low": claims_pct,
        "claims_week": claims_week,
    }


def signal_from_reading(reading: dict) -> dict:
    if reading["sahm"] is None:
        return dict(UNAVAILABLE_SIGNAL)
    score = compute_score(reading["sahm"], bool(reading["claims_flagged"]))
    status = score_to_status(score)
    return {
        "score": score,
        "status": status,
        "verdict": make_verdict(reading, status),
    }


def compute_score(sahm: float, claims_flagged: bool) -> float:
    # np.interp holds the end values outside the points, giving the 0-100 clamp.
    score = float(np.interp(sahm, SAHM_POINTS, SCORE_POINTS))
    if claims_flagged:
        score = min(score + CLAIMS_BUMP, 100.0)
    return round(score, 1)


def score_to_status(score: float) -> str:
    if score >= RED_FROM:
        return "red"
    if score >= AMBER_FROM:
        return "amber"
    return "green"


def make_verdict(reading: dict, status: str) -> str:
    """One sentence: what unemployment did, what it means, what claims say."""
    sahm = reading["sahm"]
    triggered = sahm >= SAHM_THRESHOLD

    if sahm <= 0:
        what_happened = "Unemployment is at or below its recent low"
    else:
        what_happened = f"Unemployment is {sahm:.2f} points above its recent low"

    if status == "red" and triggered:
        meaning = "past the 0.5 Sahm trigger, so the labour market is confirming a recession"
    elif status == "red":
        meaning = (
            "just short of the 0.5 Sahm trigger, and with jobless claims also rising "
            "the labour market is close to confirming a recession"
        )
    elif status == "amber":
        meaning = (
            "below the 0.5 Sahm trigger but rising, so the labour market is "
            "weakening without yet confirming a recession"
        )
    else:
        meaning = "well below the 0.5 Sahm trigger, so the labour market is not confirming a recession"

    claims_pct = reading["claims_pct_above_low"]
    if claims_pct is None:
        claims_part = ""
    elif reading["claims_flagged"]:
        claims_part = f"; jobless claims are up {claims_pct:.0f}% from their 52-week low"
    elif claims_pct < 1:
        claims_part = "; jobless claims are at their 52-week low"
    else:
        claims_part = f"; jobless claims are only {max(claims_pct, 0):.0f}% above their 52-week low"

    return f"{what_happened}, {meaning}{claims_part}."


def _latest_sahm(as_of, unemployment, real_time_sahm):
    """(value, month, "real-time" | "revised") of the latest visible reading, or Nones."""
    lag = RELEASE_LAG_DAYS["UNRATE"]

    if real_time_sahm is not None:
        visible = filter_as_of(real_time_sahm, as_of, lag).dropna()
        if not visible.empty:
            return float(visible.iloc[-1]), visible.index[-1], "real-time"

    if unemployment is not None:
        ours = sahm_rule(filter_as_of(unemployment, as_of, lag)).dropna()
        if not ours.empty:
            return float(ours.iloc[-1]), ours.index[-1], "revised"

    return None, None, None


def _try_to_load(loader, series_id):
    """Load an optional series, or None (with a warning) if it fails."""
    try:
        return loader(series_id)
    except Exception as error:
        logger.warning("Optional series %s unavailable: %s", series_id, error)
        return None