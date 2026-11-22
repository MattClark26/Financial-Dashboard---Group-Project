"""Tests for shared dashboard contracts."""

from __future__ import annotations

import pytest

from ui.shell import calculate_composite
from ui.types import PanelIdentity


def test_panel_identity_builds_compact_label() -> None:
    identity = PanelIdentity(3, "stress", "Financial stress", "Markets", "Rohi Aluede")

    assert identity.label == "03 / FINANCIAL STRESS"


def test_composite_uses_only_connected_weighted_scores() -> None:
    score = calculate_composite(
        {"stress": 80, "bond": 20},
        {"stress": 3, "bond": 1},
    )

    assert score == pytest.approx(65)


def test_empty_composite_remains_unavailable() -> None:
    assert calculate_composite({}) is None
