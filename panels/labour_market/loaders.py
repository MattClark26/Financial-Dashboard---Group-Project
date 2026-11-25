"""Streamlit-cached wrappers around data.py, shared by signal.py and panel.py.

Streamlit re-runs the script on every widget change; caching stops it re-downloading.
"""

import streamlit as st

from .data import load_series, load_vintages

# Claims update weekly at most. The TTL also stops a long-running Space serving stale data.
CACHE_TTL = "12h"


@st.cache_data(ttl=CACHE_TTL, show_spinner="Loading labour market data...")
def cached_series(series_id: str):
    return load_series(series_id)


@st.cache_data(ttl=CACHE_TTL, show_spinner="Loading payroll revision history...")
def cached_vintages(series_id: str):
    return load_vintages(series_id)
