"""Tests for the Financial Stress panel's transparent score contract."""

from __future__ import annotations

import pandas as pd

from panels.financial_stress.analytics import FinancialStressAnalytics, build_stress_features
from panels.financial_stress.scoring import score_financial_stress


def test_score_is_bounded_and_exposes_all_components(
    synthetic_market_series: dict[str, pd.Series],
) -> None:
    weekly = pd.DataFrame(synthetic_market_series)
    features = build_stress_features(weekly, window=104, min_history=26)
    analytics = FinancialStressAnalytics(
        as_of=weekly.index.max(),
        weekly=weekly,
        features=features,
        z_window=104,
        min_history=26,
    )

    signal = score_financial_stress(analytics)

    assert 0 <= signal.score <= 100
    assert signal.status in {"CALM", "WATCH", "ALERT"}
    assert set(signal.components) == {
        "ig_oas",
        "hy_oas",
        "vix",
        "stlfsi",
        "drawdown",
    }


def test_score_uses_latest_available_timestamp(
    synthetic_market_series: dict[str, pd.Series],
) -> None:
    weekly = pd.DataFrame(synthetic_market_series)
    features = build_stress_features(weekly, window=104, min_history=26)
    analytics = FinancialStressAnalytics(
        as_of=weekly.index.max(),
        weekly=weekly,
        features=features,
        z_window=104,
        min_history=26,
    )

    signal = score_financial_stress(analytics)

    assert signal.as_of == features.dropna(how="all").index.max()
