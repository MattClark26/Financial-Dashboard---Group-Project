"""Tests for Financial Stress input diagnostics."""

from __future__ import annotations

import pandas as pd

from panels.financial_stress.data import SERIES_SPECS
from panels.financial_stress.diagnostics import assess_data_quality
from panels.financial_stress.models import FinancialStressDataset, SeriesData, SourceMode


def test_quality_reports_coverage_lag_and_mixed_provenance() -> None:
    cutoff = pd.Timestamp("2024-01-12")
    series = {
        key: SeriesData(
            spec=SERIES_SPECS[key],
            values=pd.Series([1.0], index=[cutoff - pd.Timedelta(days=lag)]),
            retrieved_at=cutoff,
            mode=mode,
        )
        for key, lag, mode in (
            ("ig_oas", 0, SourceMode.LIVE),
            ("hy_oas", 7, SourceMode.CACHE),
        )
    }
    dataset = FinancialStressDataset(as_of=cutoff, series=series)

    quality = assess_data_quality(dataset, expected_series=5)

    assert quality.coverage_percent == 40
    assert quality.maximum_lag_days == 7
    assert quality.source_modes == ("cache", "live")
    assert quality.label == "LIMITED"
