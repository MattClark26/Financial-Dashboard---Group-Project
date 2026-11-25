"""Shared dashboard chrome and cross-panel status components."""

from __future__ import annotations

from datetime import date
from typing import Mapping

import streamlit as st


def render_topbar(
    as_of: date,
    connected_count: int = 1,
) -> None:
    """Render the compact application header."""
    st.html(
        f"""
        <header class="rr-topbar">
          <div class="rr-wordmark">
            <span class="rr-radar-mark" aria-hidden="true">RR</span>
            <span>recession radar</span>
          </div>
          <div class="rr-topbar-centre">
            <span>MACRO EARLY WARNING</span>
            <strong>{as_of:%d %b %Y}</strong>
          </div>
          <span class="rr-topbar-meta">
            {connected_count} OF 4 CONNECTED
          </span>
        </header>
        """
    )


def calculate_composite(
    scores: Mapping[str, float | None],
    weights: Mapping[str, float] | None = None,
) -> float | None:
    available_scores = {
        key: score
        for key, score in scores.items()
        if score is not None
    }
    if not available_scores:
        return None

    active_weights = weights or {key: 1.0 for key in available_scores}
    denominator = sum(
        max(active_weights.get(key, 0.0), 0.0)
        for key in available_scores
    )
    if denominator == 0:
        return None

    return sum(
        max(0.0, min(100.0, score))
        * max(active_weights.get(key, 0.0), 0.0)
        for key, score in available_scores.items()
    ) / denominator


def render_composite(scores: Mapping[str, float]) -> None:
    """Render the aggregate while clearly stating how many panels contribute."""
    score = calculate_composite(scores)
    if score is None:
        value, status, marker = "Not available", "WAITING", 0.0
    else:
        value = f"{score:.0f}"
        status = "ALERT" if score >= 67 else "WATCH" if score >= 34 else "CALM"
        marker = score
    st.html(
        f"""
        <div class="rr-control-label">
          <span>CONNECTED COMPOSITE</span>
          <strong>{len(scores)} / 4 PANELS</strong>
        </div>
        <div class="rr-composite">
          <div><strong>{value}</strong><small>/100</small></div>
          <span class="rr-composite-status">{status}</span>
          <div class="rr-risk-track" style="--rr-score:{marker:.1f}%"><i></i></div>
        </div>
        """
    )
