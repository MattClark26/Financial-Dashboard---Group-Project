"""Tests for deterministic offline presentation state."""

from __future__ import annotations

import pandas as pd

from panels.financial_stress.presentation import (
    build_demo_analytics,
    build_demo_recession_indicator,
    load_financial_stress_view,
)


def test_demo_history_respects_selected_date() -> None:
    cutoff = pd.Timestamp("2020-03-31")

    analytics = build_demo_analytics(cutoff)

    assert analytics.as_of == cutoff
    assert analytics.weekly.index.max() <= cutoff
    assert analytics.features.index.max() <= cutoff


def test_default_view_is_clearly_labelled_simulated() -> None:
    view = load_financial_stress_view(pd.Timestamp("2022-10-31"))

    assert view.mode == "SIMULATED PREVIEW"
    assert not view.is_live
    assert 0 <= view.signal.score <= 100
    assert not view.history.empty
    assert view.quality.coverage_percent == 100
    assert len(view.backtest.recessions) == 2


def test_demo_recession_labels_cover_known_episodes() -> None:
    index = pd.date_range("2007-01-05", "2020-12-25", freq="W-FRI")

    indicator = build_demo_recession_indicator(index)

    assert indicator.loc["2008-01-01":"2009-05-31"].eq(1).all()
    assert indicator.loc["2020-03-01":"2020-04-30"].eq(1).all()
    assert indicator.loc["2015"].eq(0).all()
