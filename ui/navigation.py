"""Shared navigation actions for full-screen panel views."""

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
