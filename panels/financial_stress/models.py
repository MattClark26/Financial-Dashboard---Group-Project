"""Typed data contracts for the Financial Stress panel."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import pandas as pd


class SourceMode(str, Enum):
    """How an observation series reached the panel."""

    LIVE = "live"
    CACHE = "cache"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class SeriesSpec:
    """Stable metadata needed to retrieve and explain one input series."""

    key: str
    label: str
    provider: str
    identifier: str
    frequency: str
    units: str
    source_url: str
    description: str

    def __post_init__(self) -> None:
        if not self.key or not self.key.replace("_", "").isalnum():
            raise ValueError("Series keys must contain only letters, numbers and underscores.")
        if self.provider not in {"fred", "yahoo"}:
            raise ValueError(f"Unsupported provider: {self.provider}.")
        for field_name in (
            "label",
            "identifier",
            "frequency",
            "units",
            "source_url",
            "description",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"Series metadata field '{field_name}' cannot be empty.")


@dataclass(frozen=True)
class SeriesData:
    """Validated observations and provenance for one financial series."""

    spec: SeriesSpec
    values: pd.Series
    retrieved_at: pd.Timestamp
    mode: SourceMode
    cache_path: Path | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.values, pd.Series):
            raise TypeError("SeriesData.values must be a pandas Series.")

        values = self.values.copy()
        try:
            index = pd.DatetimeIndex(pd.to_datetime(values.index))
        except (TypeError, ValueError) as error:
            raise ValueError("Series observations require a datetime-like index.") from error

        if index.tz is not None:
            index = index.tz_convert(None)
        values.index = index
        values = pd.to_numeric(values, errors="coerce").dropna()
        values = values[~values.index.duplicated(keep="last")].sort_index()
        values.name = self.spec.key

        if values.empty:
            raise ValueError(f"Series '{self.spec.key}' contains no numeric observations.")
        if not values.index.is_monotonic_increasing:
            raise ValueError(f"Series '{self.spec.key}' dates must be increasing.")

        retrieved_at = pd.Timestamp(self.retrieved_at)
        if retrieved_at.tz is not None:
            retrieved_at = retrieved_at.tz_convert(None)

        object.__setattr__(self, "values", values.astype("float64"))
        object.__setattr__(self, "retrieved_at", retrieved_at)
        if self.cache_path is not None:
            object.__setattr__(self, "cache_path", Path(self.cache_path))


@dataclass(frozen=True)
class FinancialStressDataset:
    """All validated inputs available at one dashboard date."""

    as_of: pd.Timestamp
    series: Mapping[str, SeriesData]

    def __post_init__(self) -> None:
        as_of = pd.Timestamp(self.as_of).normalize()
        normalized = dict(self.series)
        if not normalized:
            raise ValueError("A FinancialStressDataset needs at least one series.")
        mismatched = [key for key, item in normalized.items() if key != item.spec.key]
        if mismatched:
            raise ValueError(f"Dataset keys do not match their series metadata: {mismatched}.")
        after_cutoff = {
            key: item.values.index.max()
            for key, item in normalized.items()
            if item.values.index.max() > as_of
        }
        if after_cutoff:
            raise ValueError(f"Dataset contains observations after {as_of.date()}: {after_cutoff}.")

        object.__setattr__(self, "as_of", as_of)
        object.__setattr__(self, "series", MappingProxyType(normalized))
