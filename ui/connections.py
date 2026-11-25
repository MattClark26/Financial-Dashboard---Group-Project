"""Session-only data connection settings and connection status."""

from __future__ import annotations

import os

import streamlit as st


def _configured_secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "")).strip()
    except (FileNotFoundError, AttributeError):
        return ""


def activate_session_credentials() -> None:
    """Expose configured credentials to data clients without writing them to disk."""
    fred_key = str(st.session_state.get("fred_api_key", "")).strip()
    fred_key = fred_key or _configured_secret("FRED_API_KEY")
    if fred_key:
        os.environ["FRED_API_KEY"] = fred_key


def _save_fred_key() -> None:
    key = str(st.session_state.get("fred_api_key_input", "")).strip()
    if key:
        st.session_state["fred_api_key"] = key
        st.session_state["financial_stress_live_enabled"] = True
        st.session_state["data_connection_revision"] = (
            int(st.session_state.get("data_connection_revision", 0)) + 1
        )
        os.environ["FRED_API_KEY"] = key


def _clear_fred_key() -> None:
    st.session_state.pop("fred_api_key", None)
    st.session_state["financial_stress_live_enabled"] = False
    st.session_state["data_connection_revision"] = (
        int(st.session_state.get("data_connection_revision", 0)) + 1
    )
    os.environ.pop("FRED_API_KEY", None)


def render_connections() -> None:
    """Render a safe place to configure optional live-data credentials."""
    activate_session_credentials()
    configured = bool(os.environ.get("FRED_API_KEY"))

    st.markdown("# Data connections")
    st.write(
        "Add optional credentials for live refreshes. Keys entered here remain in "
        "this running browser session and are never written to the repository."
    )

    with st.container(border=True):
        left, right = st.columns([3, 1], vertical_alignment="center")
        with left:
            st.markdown("### FRED + ALFRED")
            st.write(
                "Used by Labour Market for current releases and historical vintages. "
                "Saving a key also switches Financial Stress into live-refresh mode; "
                "its FRED and Yahoo feeds still retain local fallbacks."
            )
        right.metric("Status", "CONNECTED" if configured else "CACHED")

        with st.form("fred_connection_form", clear_on_submit=True):
            st.text_input(
                "FRED API key",
                type="password",
                key="fred_api_key_input",
                placeholder="Paste a key from fred.stlouisfed.org",
            )
            st.form_submit_button("Use key for this session", on_click=_save_fred_key)

        if configured:
            st.button("Clear session key", on_click=_clear_fred_key)
        st.link_button("Get a free FRED API key", "https://fred.stlouisfed.org/docs/api/api_key.html")

    with st.container(border=True):
        st.markdown("### Yahoo Finance")
        st.write("No key required. Used for VIX, high-yield spreads and equity-market history.")
        st.success("Public connection: no credentials required")

    with st.container(border=True):
        st.markdown("### Central Statistics Office Ireland")
        st.write("No key required. The Irish Lens uses the CSO public PxStat API and local fallbacks.")
        st.success("Public connection: no credentials required")

    st.info(
        "For a deployed app, add FRED_API_KEY in the host's secret manager. "
        "For local development, copy .streamlit/secrets.toml.example to "
        ".streamlit/secrets.toml; the real file is ignored by Git."
    )
