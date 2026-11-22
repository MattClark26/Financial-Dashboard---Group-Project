"""Resilient view state for the Financial Stress Streamlit presentation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .analytics import (
    AnalyticsError,
    FinancialStressAnalytics,
    build_stress_features,
    prepare_stress_analytics,
)
from .data import DataAccessError, load_financial_stress_data
from .scoring import StressSignal, score_financial_stress


@dataclass(frozen=True)
class FinancialStressView:
    """Everything the UI needs, including an honest provenance label."""

    analytics: FinancialStressAnalytics
    signal: StressSignal
    mode: str
    note: str

    @property
    def is_live(self) -> bool:
        return self.mode == "LIVE PUBLIC DATA"


def _gaussian(values: np.ndarray, centre: float, width: float) -> np.ndarray:
    return np.exp(-np.square(values - centre) / (2 * width * width))


def build_demo_analytics(as_of: pd.Timestamp) -> FinancialStressAnalytics:
    """Build deterministic illustrative history for offline interface previews."""
    cutoff = pd.Timestamp(as_of).normalize()
    start = min(pd.Timestamp("2002-01-04"), cutoff - pd.Timedelta(weeks=320))
    index = pd.date_range(start, cutoff, freq="W-FRI")
    if len(index) < 210:
        index = pd.date_range(end=cutoff, periods=210, freq="W-FRI")
    years = index.year.to_numpy() + (index.dayofyear.to_numpy() - 1) / 365.25
    cycle = np.sin(np.arange(len(index)) / 17.0)
    shock = (
        2.7 * _gaussian(years, 2008.75, .28)
        + 1.2 * _gaussian(years, 2011.7, .18)
        + 3.2 * _gaussian(years, 2020.22, .10)
        + 1.0 * _gaussian(years, 2022.55, .35)
    )
    returns = np.clip(.002 + .0015 * cycle - .025 * shock, -.14, .025)
    weekly = pd.DataFrame(
        {
            "ig_oas": 1.05 + .06 * cycle + .65 * shock,
            "hy_oas": 3.45 + .18 * cycle + 2.1 * shock,
            "vix": 15.5 + 1.1 * cycle + 10.5 * shock,
            "stlfsi": -.55 + .05 * cycle + .72 * shock,
            "sp500": 1100 * np.cumprod(1 + returns),
        },
        index=index,
    )
    features = build_stress_features(weekly, window=156, min_history=52)
    return FinancialStressAnalytics(
        as_of=cutoff,
        weekly=weekly,
        features=features,
        z_window=156,
        min_history=52,
    )


def load_financial_stress_view(
    as_of: pd.Timestamp,
    *,
    prefer_live: bool = False,
) -> FinancialStressView:
    """Load public data on request and otherwise degrade to labelled demo data."""
    cutoff = pd.Timestamp(as_of).normalize()
    if prefer_live:
        try:
            dataset = load_financial_stress_data(cutoff, allow_live=True)
            analytics = prepare_stress_analytics(dataset)
            signal = score_financial_stress(analytics)
            return FinancialStressView(
                analytics=analytics,
                signal=signal,
                mode="LIVE PUBLIC DATA",
                note="Public FRED and market series, cut off at the selected date.",
            )
        except (DataAccessError, AnalyticsError, OSError, ValueError) as error:
            fallback_note = (
                "Live refresh was unavailable, so the interface is showing "
                f"deterministic illustrative history. Details: {error}"
            )
    else:
        fallback_note = (
            "Deterministic illustrative history. Open the panel and request "
            "a live refresh to use public source data."
        )

    analytics = build_demo_analytics(cutoff)
    return FinancialStressView(
        analytics=analytics,
        signal=score_financial_stress(analytics),
        mode="SIMULATED PREVIEW",
        note=fallback_note,
    )
