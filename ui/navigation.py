"""Shared navigation actions for full-screen panel views."""

from collections.abc import Callable
from html import escape

import streamlit as st


def _show_signal_grid() -> None:
    st.session_state["active_panel"] = None


def render_back_to_signals(*, key: str) -> None:
    """Render the same escape route on every panel and settings view."""
    st.button(
        "Back to all signals",
        key=key,
        on_click=_show_signal_grid,
        width="content",
    )


def render_detail_topbar(
    *,
    key: str,
    panel_label: str,
    owner: str,
    status: str = "ANALYSIS VIEW",
    action_label: str | None = None,
    action_note: str | None = None,
    action_callback: Callable[[], None] | None = None,
) -> None:
    """Render one consistent navigation bar for every detailed workspace."""
    with st.container(key=f"detail_nav_{key}"):
        back, context, action = st.columns(
            [1.15, 3.2, 1.45],
            gap="medium",
            vertical_alignment="center",
        )
        back.button(
            "Back to all signals",
            key=key,
            on_click=_show_signal_grid,
            width="stretch",
        )
        context.html(
            f"""
            <div class="rr-detail-nav-context">
              <span>{escape(panel_label.upper())}</span>
              <strong>{escape(owner)}</strong>
              <small>{escape(status)}</small>
            </div>
            """
        )
        if action_label:
            action.button(
                action_label,
                key=f"{key}_action",
                on_click=action_callback,
                width="stretch",
            )
            if action_note:
                action.caption(action_note)
