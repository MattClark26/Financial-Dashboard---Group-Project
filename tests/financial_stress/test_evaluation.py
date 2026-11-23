"""Tests for historical Financial Stress evaluation."""

from __future__ import annotations

import pandas as pd

from panels.financial_stress.evaluation import (
    alert_episodes,
    evaluate_alerts,
    recession_episodes,
)


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


def test_alert_episodes_require_a_sustained_breach() -> None:
    index = pd.date_range("2019-01-04", periods=8, freq="W-FRI")
    scores = pd.Series([30, 70, 40, 68, 72, 80, 30, 20], index=index)

    episodes = alert_episodes(scores)

    assert len(episodes) == 1
    assert episodes[0].start == index[3]
    assert episodes[0].peak_score == 80


def test_evaluate_alerts_reports_hits_false_alarms_and_lead_time() -> None:
    index = pd.date_range("2019-01-04", periods=80, freq="W-FRI")
    scores = pd.Series(20.0, index=index)
    scores.iloc[5:8] = 75
    scores.iloc[40:43] = 82
    recession = pd.Series(0, index=index)
    recession.iloc[50:55] = 1

    result = evaluate_alerts(scores, recession, lookahead_weeks=20)

    assert result.hits == 1
    assert result.false_alarms == 1
    assert result.recall == 1
    assert result.precision == 0.5
    assert result.median_lead_weeks == 10


def test_alert_after_recession_onset_cannot_count_as_advance_warning() -> None:
    index = pd.date_range("2019-01-04", periods=20, freq="W-FRI")
    scores = pd.Series(20.0, index=index)
    scores.iloc[12:15] = 80
    recession = pd.Series(0, index=index)
    recession.iloc[10:16] = 1

    result = evaluate_alerts(scores, recession, lookahead_weeks=12)

    assert result.hits == 0
    assert result.false_alarms == 1
    assert result.lead_weeks == ()
