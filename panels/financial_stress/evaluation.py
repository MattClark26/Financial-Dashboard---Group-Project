"""Historical evaluation helpers for the Financial Stress signal."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class RecessionEpisode:
    """One contiguous recession window in a binary reference series."""

    start: pd.Timestamp
    end: pd.Timestamp

    def __post_init__(self) -> None:
        start = pd.Timestamp(self.start)
        end = pd.Timestamp(self.end)
        if end < start:
            raise ValueError("A recession episode cannot end before it starts.")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


def recession_episodes(indicator: pd.Series) -> tuple[RecessionEpisode, ...]:
    """Convert a dated 0/1 recession indicator into contiguous episodes."""
    if not isinstance(indicator.index, pd.DatetimeIndex):
        raise TypeError("Recession indicators require a DatetimeIndex.")
    active = pd.to_numeric(indicator, errors="coerce").fillna(0).gt(0)
    active = active[~active.index.duplicated(keep="last")].sort_index()
    if active.empty:
        return ()

    groups = active.ne(active.shift(fill_value=False)).cumsum()
    episodes: list[RecessionEpisode] = []
    for _, values in active.groupby(groups):
        if bool(values.iloc[0]):
            episodes.append(RecessionEpisode(values.index[0], values.index[-1]))
    return tuple(episodes)
