"""Tests for the Financial Stress panel's transparent score contract."""

from __future__ import annotations

import pandas as pd
import pytest

from panels.financial_stress.analytics import FinancialStressAnalytics, build_stress_features
from panels.financial_stress.scoring import (
    COMPONENT_WEIGHTS,
    score_financial_stress,
    score_history,
)


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


def test_history_exposes_weighted_score_and_alert_breadth(
    synthetic_market_series: dict[str, pd.Series],
) -> None:
    weekly = pd.DataFrame(synthetic_market_series)
    analytics = FinancialStressAnalytics(
        as_of=weekly.index.max(),
        weekly=weekly,
        features=build_stress_features(weekly, window=104, min_history=26),
        z_window=104,
        min_history=26,
    )

    history = score_history(analytics).dropna(subset=["score"])

    assert sum(COMPONENT_WEIGHTS.values()) == 1
    assert history["score"].between(0, 100).all()
    assert history["breadth"].between(0, 5).all()


def test_score_history_supports_auditable_weight_scenarios(
    synthetic_market_series: dict[str, pd.Series],
) -> None:
    weekly = pd.DataFrame(synthetic_market_series)
    analytics = FinancialStressAnalytics(
        as_of=weekly.index.max(),
        weekly=weekly,
        features=build_stress_features(weekly, window=104, min_history=26),
        z_window=104,
        min_history=26,
    )

    credit_only = score_history(
        analytics,
        weights={"ig_oas": 0.4, "hy_oas": 0.6},
    ).dropna(subset=["score"])

    assert credit_only["score"].between(0, 100).all()
    with pytest.raises(ValueError, match="positive weight"):
        score_history(analytics, weights={key: 0 for key in COMPONENT_WEIGHTS})
