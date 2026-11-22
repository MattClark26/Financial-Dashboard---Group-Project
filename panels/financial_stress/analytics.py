"""Causal transformations for comparable Financial Stress indicators."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .data import PANEL_SERIES_KEYS
from .models import FinancialStressDataset

DEFAULT_Z_WINDOW = 156
DEFAULT_MIN_HISTORY = 52


class AnalyticsError(ValueError):
    """Raised when the requested analytical transformation is not valid."""


@dataclass(frozen=True)
class FinancialStressAnalytics:
    """Weekly raw inputs and causal, comparable stress features."""

    as_of: pd.Timestamp
    weekly: pd.DataFrame
    features: pd.DataFrame
    z_window: int
    min_history: int

    def __post_init__(self) -> None:
        cutoff = pd.Timestamp(self.as_of).normalize()
        if self.weekly.empty or self.features.empty:
            raise AnalyticsError("Financial Stress analytics cannot be empty.")
        for name, frame in (("weekly", self.weekly), ("features", self.features)):
            if not isinstance(frame.index, pd.DatetimeIndex):
                raise AnalyticsError(f"{name} data must use a DatetimeIndex.")
            if frame.index.max() > cutoff:
                raise AnalyticsError(f"{name} data contains observations after {cutoff.date()}.")
            if not frame.index.is_monotonic_increasing:
                raise AnalyticsError(f"{name} data must be sorted chronologically.")
        if self.z_window < 2:
            raise AnalyticsError("The z-score window must contain at least two observations.")
        if not 2 <= self.min_history <= self.z_window:
            raise AnalyticsError("Minimum history must be between 2 and the z-score window.")


def align_weekly(
    dataset: FinancialStressDataset,
    *,
    keys: Iterable[str] = PANEL_SERIES_KEYS,
) -> pd.DataFrame:
    """Align mixed-frequency inputs to completed Friday weeks without backfilling."""
    cutoff = dataset.as_of
    aligned: dict[str, pd.Series] = {}
    for key in keys:
        if key not in dataset.series:
            raise AnalyticsError(f"Required series '{key}' is missing from the dataset.")
        values = dataset.series[key].values.loc[:cutoff]
        weekly = values.resample("W-FRI", closed="right", label="right").last().dropna()
        aligned[key] = weekly[weekly.index <= cutoff]

    frame = pd.concat(aligned, axis=1).sort_index()
    frame = frame.loc[frame.index <= cutoff]
    if frame.empty:
        raise AnalyticsError(f"No complete weekly observations exist by {cutoff.date()}.")
    return frame.astype("float64")


def calculate_drawdown(prices: pd.Series) -> pd.Series:
    """Calculate peak-to-trough drawdown using only peaks known at each date."""
    prices = pd.to_numeric(prices, errors="coerce").astype("float64")
    if (prices.dropna() <= 0).any():
        raise AnalyticsError("Price observations must be positive to calculate drawdown.")
    running_peak = prices.cummax()
    drawdown = (prices / running_peak - 1.0) * 100.0
    drawdown.name = "sp500_drawdown"
    return drawdown


def causal_zscore(
    values: pd.Series,
    *,
    window: int = DEFAULT_Z_WINDOW,
    min_history: int = DEFAULT_MIN_HISTORY,
) -> pd.Series:
    """Standardise each value against prior observations in a trailing window."""
    if window < 2:
        raise AnalyticsError("The z-score window must contain at least two observations.")
    if not 2 <= min_history <= window:
        raise AnalyticsError("Minimum history must be between 2 and the z-score window.")

    numeric = pd.to_numeric(values, errors="coerce").astype("float64")
    history = numeric.shift(1)
    rolling = history.rolling(window=window, min_periods=min_history)
    mean = rolling.mean()
    standard_deviation = rolling.std(ddof=1)
    result = (numeric - mean) / standard_deviation
    result = result.where(standard_deviation > 0)
    result.name = f"{values.name}_z" if values.name else "zscore"
    return result


def build_stress_features(
    weekly: pd.DataFrame,
    *,
    window: int = DEFAULT_Z_WINDOW,
    min_history: int = DEFAULT_MIN_HISTORY,
) -> pd.DataFrame:
    """Create comparable positive-direction stress features from weekly inputs."""
    missing = set(PANEL_SERIES_KEYS).difference(weekly.columns)
    if missing:
        raise AnalyticsError(f"Weekly data is missing required columns: {sorted(missing)}.")

    features = weekly.copy()
    features["sp500_drawdown"] = calculate_drawdown(features["sp500"])
    stress_inputs = {
        "ig_oas": features["ig_oas"],
        "hy_oas": features["hy_oas"],
        "vix": features["vix"],
        "stlfsi": features["stlfsi"],
        "drawdown": -features["sp500_drawdown"],
    }
    for key, values in stress_inputs.items():
        features[f"{key}_z"] = causal_zscore(
            values.rename(key),
            window=window,
            min_history=min_history,
        )
    return features


def prepare_stress_analytics(
    dataset: FinancialStressDataset,
    *,
    window: int = DEFAULT_Z_WINDOW,
    min_history: int = DEFAULT_MIN_HISTORY,
) -> FinancialStressAnalytics:
    """Run the complete causal transformation pipeline for one dashboard date."""
    weekly = align_weekly(dataset)
    features = build_stress_features(
        weekly,
        window=window,
        min_history=min_history,
    )
    return FinancialStressAnalytics(
        as_of=dataset.as_of,
        weekly=weekly,
        features=features,
        z_window=window,
        min_history=min_history,
    )
