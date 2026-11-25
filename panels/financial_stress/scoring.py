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

COMPONENT_WEIGHTS: Mapping[str, float] = MappingProxyType(
    {
        "ig_oas": 0.20,
        "hy_oas": 0.25,
        "vix": 0.20,
        "stlfsi": 0.20,
        "drawdown": 0.15,
    }
)


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


def score_history(
    analytics: FinancialStressAnalytics,
    *,
    weights: Mapping[str, float] | None = None,
) -> pd.DataFrame:
    """Build an auditable weekly score, breadth and component contribution table."""
    available = {
        key: column
        for key, column in COMPONENT_COLUMNS.items()
        if column in analytics.features.columns
    }
    if not available:
        raise AnalyticsError("No standardised stress components are available to score.")

    scores = pd.DataFrame(index=analytics.features.index)
    for key, column in available.items():
        scores[key] = analytics.features[column].map(
            lambda value: _score_zvalue(value) if pd.notna(value) else float("nan")
        )

    selected_weights = weights or COMPONENT_WEIGHTS
    unknown = set(selected_weights) - set(COMPONENT_COLUMNS)
    if unknown:
        raise ValueError(f"Unknown stress weight keys: {', '.join(sorted(unknown))}.")
    if any(float(value) < 0 for value in selected_weights.values()):
        raise ValueError("Stress component weights cannot be negative.")
    active_weights = pd.Series(
        {key: float(selected_weights.get(key, 0.0)) for key in available}
    )
    if active_weights.sum() <= 0:
        raise ValueError("At least one available stress component must have a positive weight.")
    valid_weights = scores.notna().mul(active_weights, axis="columns")
    denominator = valid_weights.sum(axis=1).replace(0, float("nan"))
    scores["score"] = scores.mul(active_weights, axis="columns").sum(axis=1) / denominator
    scores["breadth"] = scores[list(available)].ge(67).sum(axis=1)
    scores["available"] = scores[list(available)].notna().sum(axis=1)
    return scores


def score_financial_stress(
    analytics: FinancialStressAnalytics,
    *,
    weights: Mapping[str, float] | None = None,
) -> StressSignal:
    """Score the latest available component values without future information."""
    available = {
        key: column
        for key, column in COMPONENT_COLUMNS.items()
        if column in analytics.features.columns
    }
    if not available:
        raise AnalyticsError("No standardised stress components are available to score.")

    history = score_history(analytics, weights=weights).dropna(subset=["score"])
    if history.empty:
        raise AnalyticsError("Stress components need enough prior history to produce a score.")

    latest = history.iloc[-1]
    components = {
        key: float(latest[key]) for key in available if pd.notna(latest[key])
    }
    if not components:
        raise AnalyticsError("The latest stress observation has no scoreable components.")

    score = float(latest["score"])
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
        as_of=history.index[-1],
        score=score,
        status=status,
        verdict=verdict,
        components=components,
    )
