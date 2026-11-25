"""Shared visual primitives for the connected analytical pages."""

from __future__ import annotations

from html import escape
from typing import Iterable

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st


PAPER = "#f2eee6"
PAPER_DEEP = "#e7e0d4"
INK = "#15130f"
MUTED = "#69645b"
LINE = "#cbc3b6"
YELLOW = "#f5bd3e"
RED = "#d75f47"
GREEN = "#3c7555"
BLUE = "#5ca9d6"


def configure_plotly_theme() -> None:
    """Make every unopinionated Plotly chart match the Recession Radar shell."""
    pio.templates["recession_radar"] = go.layout.Template(
        layout={
            "paper_bgcolor": PAPER,
            "plot_bgcolor": PAPER,
            "font": {
                "family": "IBM Plex Mono, Liberation Mono, monospace",
                "color": INK,
                "size": 12,
            },
            "title": {
                "font": {
                    "family": "Helvetica Neue, Nimbus Sans L, sans-serif",
                    "color": INK,
                    "size": 22,
                },
                "x": 0,
                "xanchor": "left",
            },
            "colorway": [INK, RED, GREEN, BLUE, YELLOW, MUTED],
            "hoverlabel": {
                "bgcolor": INK,
                "font": {"color": PAPER},
                "bordercolor": INK,
            },
            "legend": {
                "bgcolor": "rgba(0,0,0,0)",
                "font": {"color": INK},
            },
            "xaxis": {
                "gridcolor": LINE,
                "linecolor": INK,
                "tickcolor": INK,
                "zerolinecolor": MUTED,
                "showline": True,
                "mirror": False,
            },
            "yaxis": {
                "gridcolor": LINE,
                "linecolor": INK,
                "tickcolor": INK,
                "zerolinecolor": MUTED,
                "showline": True,
                "mirror": False,
            },
            "margin": {"l": 55, "r": 24, "t": 70, "b": 55},
        }
    )
    pio.templates.default = "recession_radar"


def render_detail_hero(
    *,
    kicker: str,
    title: str,
    lede: str,
    score: float,
    status: str,
) -> None:
    """Render the shared full-page panel introduction."""
    st.html(
        f"""
        <section class="rr-detail-hero">
          <div>
            <p class="rr-kicker">{escape(kicker)}</p>
            <h1 class="rr-detail-title">{escape(title)}</h1>
            <p class="rr-detail-lede">{escape(lede)}</p>
          </div>
          <div class="rr-detail-score">
            <strong>{score:.0f}</strong>
            <span>/100 · {escape(status)}</span>
          </div>
        </section>
        """
    )


def render_explanation_strip(
    items: Iterable[tuple[str, str]],
) -> None:
    """Render three concise reading instructions under a detail hero."""
    cards = "".join(
        f"<article><strong>{escape(title)}</strong><p>{escape(copy)}</p></article>"
        for title, copy in items
    )
    st.html(f'<section class="rr-explanation-strip">{cards}</section>')


def render_quality_grid(items: Iterable[tuple[str, str]]) -> None:
    """Render a compact row of labelled evidence metrics."""
    cards = "".join(
        f"<div><strong>{escape(value)}</strong><span>{escape(label)}</span></div>"
        for value, label in items
    )
    st.html(f'<section class="rr-quality-grid">{cards}</section>')


def render_method_grid(
    items: Iterable[tuple[str, str, str]],
) -> None:
    """Render numbered or named method cards."""
    cards = "".join(
        "<article>"
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(title)}</strong>"
        f"<p>{escape(copy)}</p>"
        "</article>"
        for label, title, copy in items
    )
    st.html(f'<section class="rr-method-grid">{cards}</section>')


def render_conclusion(title: str, copy: str) -> None:
    """Render a consistent interpretation beneath a chart."""
    st.html(
        f'<div class="rr-conclusion"><strong>{escape(title)}</strong>'
        f'<p>{escape(copy)}</p></div>'
    )
