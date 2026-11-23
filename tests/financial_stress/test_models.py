from __future__ import annotations

import pandas as pd
import pytest

from panels.financial_stress.models import (
    FinancialStressDataset,
    SeriesData,
    SeriesSpec,
    SourceMode,
)


def test_series_data_normalizes_dates_values_and_duplicates(
    corporate_spread_spec: SeriesSpec,
) -> None:
    values = pd.Series(
        ["1.20", "bad", "1.10", "1.05"],
        index=["2020-01-03", "2020-01-02", "2020-01-03", "2020-01-01"],
    )

    result = SeriesData(
        spec=corporate_spread_spec,
        values=values,
        retrieved_at=pd.Timestamp("2020-01-04", tz="UTC"),
        mode=SourceMode.LIVE,
    )

    assert result.values.to_dict() == {
        pd.Timestamp("2020-01-01"): 1.05,
        pd.Timestamp("2020-01-03"): 1.10,
    }
    assert result.values.name == "ig_oas"
    assert result.retrieved_at.tz is None


def test_series_spec_rejects_unsupported_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported provider"):
        SeriesSpec(
            key="bad",
            label="Bad source",
            provider="unknown",
            identifier="BAD",
            frequency="Daily",
            units="Index",
            source_url="https://example.com",
            description="Unsupported test source.",
        )


def test_dataset_rejects_observations_after_as_of(
    corporate_spread_spec: SeriesSpec,
) -> None:
    series = SeriesData(
        spec=corporate_spread_spec,
        values=pd.Series([1.0, 1.1], index=pd.to_datetime(["2020-01-03", "2020-01-10"])),
        retrieved_at=pd.Timestamp("2020-01-11"),
        mode=SourceMode.CACHE,
    )

    with pytest.raises(ValueError, match="observations after"):
        FinancialStressDataset(as_of=pd.Timestamp("2020-01-05"), series={"ig_oas": series})


def test_dataset_exposes_an_immutable_mapping(
    corporate_spread_spec: SeriesSpec,
) -> None:
    series = SeriesData(
        spec=corporate_spread_spec,
        values=pd.Series([1.0], index=pd.to_datetime(["2020-01-03"])),
        retrieved_at=pd.Timestamp("2020-01-04"),
        mode=SourceMode.CACHE,
    )
    dataset = FinancialStressDataset(
        as_of=pd.Timestamp("2020-01-03"),
        series={"ig_oas": series},
    )

    with pytest.raises(TypeError):
        dataset.series["other"] = series  # type: ignore[index]
