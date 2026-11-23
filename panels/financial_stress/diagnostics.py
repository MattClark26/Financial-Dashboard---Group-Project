"""Data coverage and provenance diagnostics for the Financial Stress panel."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .models import FinancialStressDataset


@dataclass(frozen=True)
class DataQuality:
    """User-facing summary of input availability at the selected date."""

    expected_series: int
    available_series: int
    latest_observation: pd.Timestamp
    maximum_lag_days: int
    source_modes: tuple[str, ...]

    @property
    def coverage_percent(self) -> float:
        return 100 * self.available_series / self.expected_series

    @property
    def label(self) -> str:
        if self.coverage_percent == 100 and self.maximum_lag_days <= 10:
            return "COMPLETE"
        if self.coverage_percent >= 80:
            return "USABLE"
        return "LIMITED"


def assess_data_quality(
    dataset: FinancialStressDataset,
    *,
    expected_series: int,
) -> DataQuality:
    """Measure coverage, staleness and provenance without hiding missing inputs."""
    if expected_series < 1:
        raise ValueError("expected_series must be positive.")
    latest_dates = [item.values.index.max() for item in dataset.series.values()]
    lags = [(dataset.as_of - date.normalize()).days for date in latest_dates]
    return DataQuality(
        expected_series=expected_series,
        available_series=len(dataset.series),
        latest_observation=max(latest_dates),
        maximum_lag_days=max(lags),
        source_modes=tuple(sorted({item.mode.value for item in dataset.series.values()})),
    )


def demo_data_quality(as_of: pd.Timestamp, *, expected_series: int = 6) -> DataQuality:
    """Describe deterministic preview coverage without implying it is live data."""
    cutoff = pd.Timestamp(as_of).normalize()
    return DataQuality(
        expected_series=expected_series,
        available_series=expected_series,
        latest_observation=cutoff,
        maximum_lag_days=0,
        source_modes=("simulated",),
    )
