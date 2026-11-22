from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from panels.financial_stress.analytics import (
    align_weekly,
    build_stress_features,
    calculate_drawdown,
    causal_zscore,
    prepare_stress_analytics,
)
from panels.financial_stress.data import SERIES_SPECS
from panels.financial_stress.models import (
    FinancialStressDataset,
    SeriesData,
    SourceMode,
)


def _dataset(
    series: dict[str, pd.Series],
    as_of: pd.Timestamp | None = None,
) -> FinancialStressDataset:
    cutoff = pd.Timestamp(as_of or max(values.index.max() for values in series.values()))
    loaded = {
        key: SeriesData(
            spec=SERIES_SPECS[key],
            values=values.loc[:cutoff],
            retrieved_at=cutoff + pd.Timedelta(days=1),
            mode=SourceMode.CACHE,
        )
        for key, values in series.items()
    }
    return FinancialStressDataset(as_of=cutoff, series=loaded)


def test_calculate_drawdown_uses_running_historical_peak() -> None:
    prices = pd.Series(
        [100.0, 120.0, 90.0, 108.0, 130.0],
        index=pd.date_range("2020-01-03", periods=5, freq="W-FRI"),
    )

    result = calculate_drawdown(prices)

    assert result.to_numpy() == pytest.approx([0.0, 0.0, -25.0, -10.0, 0.0])


def test_causal_zscore_uses_only_prior_observations() -> None:
    values = pd.Series(
        [1.0, 2.0, 3.0],
        index=pd.date_range("2020-01-03", periods=3, freq="W-FRI"),
        name="test",
    )

    result = causal_zscore(values, window=2, min_history=2)

    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == pytest.approx((3.0 - 1.5) / np.sqrt(0.5))


def test_align_weekly_never_labels_an_incomplete_future_week(
    synthetic_market_series: dict[str, pd.Series],
    weekly_index: pd.DatetimeIndex,
) -> None:
    cutoff = weekly_index[80] + pd.Timedelta(days=3)
    daily_series = {
        key: values.reindex(
            pd.date_range(values.index.min(), values.index.max(), freq="D")
        ).ffill()
        for key, values in synthetic_market_series.items()
    }
    dataset = _dataset(daily_series, cutoff)

    result = align_weekly(dataset)

    assert result.index.max() == weekly_index[80]
    assert result.index.max() <= cutoff


def test_build_features_gives_drawdowns_a_positive_stress_direction(
    synthetic_market_series: dict[str, pd.Series],
) -> None:
    weekly = pd.DataFrame(synthetic_market_series)

    result = build_stress_features(weekly, window=52, min_history=26)

    worst_drawdown_date = result["sp500_drawdown"].idxmin()
    assert result.loc[worst_drawdown_date, "sp500_drawdown"] < 0
    assert result.loc[worst_drawdown_date, "drawdown_z"] > 0
    assert {"ig_oas_z", "hy_oas_z", "vix_z", "stlfsi_z", "drawdown_z"} <= set(
        result.columns
    )


def test_future_outlier_cannot_change_a_historical_stress_result(
    synthetic_market_series: dict[str, pd.Series],
    weekly_index: pd.DatetimeIndex,
) -> None:
    comparison_date = weekly_index[120]
    baseline = prepare_stress_analytics(
        _dataset(synthetic_market_series),
        window=52,
        min_history=26,
    ).features

    modified = {key: values.copy() for key, values in synthetic_market_series.items()}
    for key in ("ig_oas", "hy_oas", "vix", "stlfsi"):
        modified[key].iloc[-1] = 1_000_000.0
    modified["sp500"].iloc[-1] = 1.0
    with_future_outlier = prepare_stress_analytics(
        _dataset(modified),
        window=52,
        min_history=26,
    ).features

    columns = ["ig_oas_z", "hy_oas_z", "vix_z", "stlfsi_z", "drawdown_z"]
    pd.testing.assert_series_equal(
        baseline.loc[comparison_date, columns],
        with_future_outlier.loc[comparison_date, columns],
    )


def test_pipeline_respects_dataset_as_of_date(
    synthetic_market_series: dict[str, pd.Series],
    weekly_index: pd.DatetimeIndex,
) -> None:
    cutoff = weekly_index[120]

    result = prepare_stress_analytics(
        _dataset(synthetic_market_series, cutoff),
        window=52,
        min_history=26,
    )

    assert result.as_of == cutoff
    assert result.weekly.index.max() == cutoff
    assert result.features.index.max() == cutoff
