"""Transparent conversion from standardised stress features to panel signals."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import pandas as pd

from .analytics import AnalyticsError, FinancialStressAnalytics

COMPONENT_COLUMNS = {
    "ig_oas": "ig_oas_z",
    "hy_oas": "hy_oas_z",
    "vix": "vix_z",
    "stlfsi": "stlfsi_z",
    "drawdown": "drawdown_z",
}


@dataclass(frozen=True)
class StressSignal:
    """One explainable 0–100 panel reading."""

    as_of: pd.Timestamp
    score: float
    status: str
    verdict: str
    components: Mapping[str, float]

    def __post_init__(self) -> None:
        if not 0 <= self.score <= 100:
            raise ValueError("Stress score must be between 0 and 100.")
        if self.status not in {"CALM", "WATCH", "ALERT"}:
            raise ValueError("Stress status must be CALM, WATCH or ALERT.")
        object.__setattr__(self, "components", MappingProxyType(dict(self.components)))


def _score_zvalue(value: float) -> float:
    """Map a z-score to a bounded score while preserving a neutral midpoint."""
    return max(0.0, min(100.0, 50.0 + float(value) * (50.0 / 3.0)))


def score_financial_stress(analytics: FinancialStressAnalytics) -> StressSignal:
    """Score the latest available component values without future information."""
    available = {
        key: column
        for key, column in COMPONENT_COLUMNS.items()
        if column in analytics.features.columns
    }
    if not available:
        raise AnalyticsError("No standardised stress components are available to score.")

    component_frame = analytics.features[list(available.values())].dropna(how="all")
    if component_frame.empty:
        raise AnalyticsError("Stress components need enough prior history to produce a score.")

    latest = component_frame.iloc[-1]
    components = {
        key: _score_zvalue(latest[column])
        for key, column in available.items()
        if pd.notna(latest[column])
    }
    if not components:
        raise AnalyticsError("The latest stress observation has no scoreable components.")

    score = sum(components.values()) / len(components)
    status = "ALERT" if score >= 67 else "WATCH" if score >= 34 else "CALM"
    elevated = sum(value >= 67 for value in components.values())
    if status == "ALERT":
        verdict = (
            f"{elevated} of {len(components)} market channels show acute stress; "
            "the signal is broad enough to warrant an alert."
        )
    elif status == "WATCH":
        verdict = (
            "Financial conditions are mixed or moderately elevated; "
            "monitor whether pressure spreads across markets."
        )
    else:
        verdict = (
            "Credit, volatility and drawdown measures remain contained "
            "relative to their trailing history."
        )
    return StressSignal(
        as_of=component_frame.index[-1],
        score=score,
        status=status,
        verdict=verdict,
        components=components,
    )
