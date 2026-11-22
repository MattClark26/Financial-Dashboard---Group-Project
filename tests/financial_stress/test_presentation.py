"""Tests for deterministic offline presentation state."""

from __future__ import annotations

import pandas as pd

from panels.financial_stress.presentation import build_demo_analytics, load_financial_stress_view


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
