"""Tests for historical Financial Stress evaluation."""

from __future__ import annotations

import pandas as pd

from panels.financial_stress.evaluation import recession_episodes


def test_recession_episodes_find_contiguous_windows() -> None:
    index = pd.date_range("2019-01-04", periods=8, freq="W-FRI")
    indicator = pd.Series([0, 1, 1, 0, 0, 1, 1, 0], index=index)

    episodes = recession_episodes(indicator)

    assert [(episode.start, episode.end) for episode in episodes] == [
        (index[1], index[2]),
        (index[5], index[6]),
    ]


def test_recession_episodes_return_empty_for_no_recession() -> None:
    indicator = pd.Series(
        [0, 0, 0],
        index=pd.date_range("2023-01-06", periods=3, freq="W-FRI"),
    )

    assert recession_episodes(indicator) == ()
