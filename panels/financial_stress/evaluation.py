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


@dataclass(frozen=True)
class AlertEpisode:
    """One sustained period in which the stress score breached its threshold."""

    start: pd.Timestamp
    end: pd.Timestamp
    peak_score: float


@dataclass(frozen=True)
class BacktestResult:
    """Compact track record for sustained alerts against recession onsets."""

    alert_threshold: float
    lookahead_weeks: int
    alerts: tuple[AlertEpisode, ...]
    recessions: tuple[RecessionEpisode, ...]
    hits: int
    false_alarms: int
    lead_weeks: tuple[int, ...]

    @property
    def recall(self) -> float:
        return self.hits / len(self.recessions) if self.recessions else 0.0

    @property
    def precision(self) -> float:
        return self.hits / len(self.alerts) if self.alerts else 0.0

    @property
    def median_lead_weeks(self) -> float | None:
        if not self.lead_weeks:
            return None
        return float(pd.Series(self.lead_weeks).median())


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


def alert_episodes(
    scores: pd.Series,
    *,
    threshold: float = 67,
    minimum_weeks: int = 2,
) -> tuple[AlertEpisode, ...]:
    """Find sustained score breaches, filtering isolated one-week noise."""
    if not isinstance(scores.index, pd.DatetimeIndex):
        raise TypeError("Stress scores require a DatetimeIndex.")
    if not 0 <= threshold <= 100:
        raise ValueError("The alert threshold must be between 0 and 100.")
    if minimum_weeks < 1:
        raise ValueError("minimum_weeks must be at least one.")

    numeric = pd.to_numeric(scores, errors="coerce").dropna().sort_index()
    breached = numeric.ge(threshold)
    groups = breached.ne(breached.shift(fill_value=False)).cumsum()
    episodes: list[AlertEpisode] = []
    for _, values in numeric.groupby(groups):
        if values.iloc[0] >= threshold and len(values) >= minimum_weeks:
            episodes.append(
                AlertEpisode(values.index[0], values.index[-1], float(values.max()))
            )
    return tuple(episodes)


def evaluate_alerts(
    scores: pd.Series,
    recession_indicator: pd.Series,
    *,
    threshold: float = 67,
    minimum_weeks: int = 2,
    lookahead_weeks: int = 52,
) -> BacktestResult:
    """Match each recession onset to the latest eligible preceding alert."""
    alerts = alert_episodes(
        scores,
        threshold=threshold,
        minimum_weeks=minimum_weeks,
    )
    recessions = recession_episodes(recession_indicator)
    matched: set[int] = set()
    lead_weeks: list[int] = []
    window = pd.Timedelta(weeks=lookahead_weeks)
    for recession in recessions:
        eligible = [
            (index, alert)
            for index, alert in enumerate(alerts)
            if index not in matched
            and recession.start - window <= alert.start <= recession.start
        ]
        if eligible:
            index, alert = max(eligible, key=lambda item: item[1].start)
            matched.add(index)
            lead_weeks.append(max(0, int((recession.start - alert.start).days // 7)))

    return BacktestResult(
        alert_threshold=threshold,
        lookahead_weeks=lookahead_weeks,
        alerts=alerts,
        recessions=recessions,
        hits=len(matched),
        false_alarms=len(alerts) - len(matched),
        lead_weeks=tuple(lead_weeks),
    )
