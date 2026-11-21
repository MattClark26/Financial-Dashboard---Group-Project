from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from panels.financial_stress.data import (
    DataAccessError,
    SERIES_SPECS,
    fetch_fred_series,
    fetch_yahoo_series,
    load_financial_stress_data,
    load_series,
)
from panels.financial_stress.models import SeriesSpec, SourceMode


def test_registry_documents_all_panel_inputs() -> None:
    assert {"ig_oas", "hy_oas", "vix", "stlfsi", "sp500", "us_recession"} <= set(
        SERIES_SPECS
    )
    assert all(spec.source_url.startswith("https://") for spec in SERIES_SPECS.values())


def test_fetch_fred_series_parses_missing_values_and_cutoff(
    corporate_spread_spec: SeriesSpec,
) -> None:
    payload = (
        b"observation_date,BAMLC0A0CM\n"
        b"2020-01-01,1.10\n"
        b"2020-01-02,.\n"
        b"2020-01-03,1.25\n"
    )

    result = fetch_fred_series(
        corporate_spread_spec,
        pd.Timestamp("2020-01-02"),
        http_get=lambda _url, _timeout: payload,
    )

    assert result.to_dict() == {pd.Timestamp("2020-01-01"): 1.10}


def test_fetch_yahoo_series_handles_multi_index_columns() -> None:
    spec = SERIES_SPECS["sp500"]
    index = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    frame = pd.DataFrame(
        [[3200.0], [3230.0], [3250.0]],
        index=index,
        columns=pd.MultiIndex.from_tuples([("Close", "^GSPC")]),
    )

    result = fetch_yahoo_series(
        spec,
        pd.Timestamp("2020-01-03"),
        downloader=lambda *args, **kwargs: frame,
    )

    assert result.to_dict() == {
        pd.Timestamp("2020-01-02"): 3200.0,
        pd.Timestamp("2020-01-03"): 3230.0,
    }


def test_load_series_writes_live_cache_and_applies_cutoff(
    tmp_path: Path,
    corporate_spread_spec: SeriesSpec,
) -> None:
    values = pd.Series(
        [1.0, 1.1, 1.2],
        index=pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
    )

    result = load_series(
        corporate_spread_spec,
        pd.Timestamp("2020-01-02"),
        cache_dir=tmp_path / "cache",
        fallback_dir=tmp_path / "fallback",
        fetchers={"fred": lambda _spec, _as_of: values},
    )

    assert result.mode is SourceMode.LIVE
    assert result.values.index.max() == pd.Timestamp("2020-01-02")
    assert (tmp_path / "cache" / "ig_oas.csv").exists()


def test_load_series_uses_cache_after_live_failure(
    tmp_path: Path,
    corporate_spread_spec: SeriesSpec,
) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    pd.DataFrame(
        {"date": ["2020-01-01", "2020-01-03"], "value": [1.0, 1.3]}
    ).to_csv(cache_dir / "ig_oas.csv", index=False)

    def fail(_spec: SeriesSpec, _as_of: pd.Timestamp) -> pd.Series:
        raise TimeoutError("provider timeout")

    result = load_series(
        corporate_spread_spec,
        pd.Timestamp("2020-01-02"),
        cache_dir=cache_dir,
        fallback_dir=tmp_path / "fallback",
        fetchers={"fred": fail},
    )

    assert result.mode is SourceMode.CACHE
    assert result.values.to_dict() == {pd.Timestamp("2020-01-01"): 1.0}


def test_load_series_reports_missing_live_and_local_data(
    tmp_path: Path,
    corporate_spread_spec: SeriesSpec,
) -> None:
    with pytest.raises(DataAccessError, match="Unable to load ig_oas"):
        load_series(
            corporate_spread_spec,
            pd.Timestamp("2020-01-02"),
            cache_dir=tmp_path / "cache",
            fallback_dir=tmp_path / "fallback",
            allow_live=False,
        )


def test_load_dataset_uses_one_as_of_boundary(tmp_path: Path) -> None:
    index = pd.to_datetime(["2020-01-01", "2020-01-10"])
    values = pd.Series([1.0, 2.0], index=index)
    fetchers = {
        "fred": lambda _spec, _as_of: values,
        "yahoo": lambda _spec, _as_of: values,
    }

    result = load_financial_stress_data(
        pd.Timestamp("2020-01-05"),
        keys=("ig_oas", "sp500"),
        cache_dir=tmp_path / "cache",
        fallback_dir=tmp_path / "fallback",
        fetchers=fetchers,
    )

    assert result.as_of == pd.Timestamp("2020-01-05")
    assert all(item.values.index.max() <= result.as_of for item in result.series.values())
