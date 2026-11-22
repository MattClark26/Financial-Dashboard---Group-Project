"""Deterministic Financial Stress test fixtures."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from panels.financial_stress.models import SeriesSpec


@pytest.fixture
def weekly_index() -> pd.DatetimeIndex:
    return pd.date_range("2018-01-05", periods=180, freq="W-FRI")


@pytest.fixture
def corporate_spread_spec() -> SeriesSpec:
    return SeriesSpec(
        key="ig_oas",
        label="US Corporate Option-Adjusted Spread",
        provider="fred",
        identifier="BAMLC0A0CM",
        frequency="Daily",
        units="Percent",
        source_url="https://fred.stlouisfed.org/series/BAMLC0A0CM",
        description="Investment-grade US corporate bond option-adjusted spread.",
    )


@pytest.fixture
def synthetic_market_series(weekly_index: pd.DatetimeIndex) -> dict[str, pd.Series]:
    count = len(weekly_index)
    phase = np.linspace(0, 8 * np.pi, count)
    shock = np.zeros(count)
    shock[100:108] = np.array([0.2, 0.5, 1.0, 2.4, 1.8, 1.1, 0.5, 0.2])

    returns = np.full(count, 0.002)
    returns[100:108] = np.array([-0.02, -0.04, -0.08, -0.12, 0.04, -0.03, 0.05, 0.06])

    return {
        "ig_oas": pd.Series(1.1 + 0.08 * np.sin(phase) + shock, index=weekly_index),
        "hy_oas": pd.Series(3.6 + 0.25 * np.sin(phase) + 2.2 * shock, index=weekly_index),
        "vix": pd.Series(16 + 1.5 * np.sin(phase) + 12 * shock, index=weekly_index),
        "stlfsi": pd.Series(-0.6 + 0.08 * np.sin(phase) + 0.9 * shock, index=weekly_index),
        "sp500": pd.Series(2400 * np.cumprod(1 + returns), index=weekly_index),
    }
