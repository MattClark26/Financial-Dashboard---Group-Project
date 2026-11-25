"""End-to-end smoke tests for every dashboard analysis route."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


@pytest.mark.parametrize(
    ("route", "minimum_tabs", "minimum_plots"),
    [
        ("bond", 4, 2),
        ("labour", 6, 4),
        ("stress", 5, 2),
        ("irish", 6, 4),
        ("signal_lab", 0, 2),
    ],
)
def test_analysis_route_renders(route: str, minimum_tabs: int, minimum_plots: int) -> None:
    app = AppTest.from_file(APP_PATH)
    app.session_state["dashboard_entered"] = True
    app.session_state["as_of"] = date(2024, 6, 30)
    app.session_state["active_panel"] = route

    app.run(timeout=60)

    assert not app.exception
    assert not app.error
    assert len(app.tabs) >= minimum_tabs
    assert len(app.get("plotly_chart")) >= minimum_plots
