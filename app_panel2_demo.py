"""
Stand-alone test page for Panel 2. This is NOT the main app.

It mimics what the main app will do: a time machine slider, then calls to
get_signal(as_of) and render_panel(as_of) and nothing else. That lets
Panel 2 be developed and demonstrated before the other panels are ready,
and proves the panel only depends on the agreed interface.

Run with:  streamlit run app_panel2_demo.py
"""

import datetime

import streamlit as st

from panel2.panel import render_panel
from panel2.signal import get_signal

st.set_page_config(page_title="Recession Radar: Panel 2 test", layout="wide")

as_of = st.slider(
    "Time machine: show the world as it looked on",
    min_value=datetime.date(1970, 1, 1),
    max_value=datetime.date.today(),
    value=datetime.date.today(),
    format="DD MMM YYYY",
)

with st.sidebar:
    st.subheader("What the main app receives")
    st.json(get_signal(as_of))

render_panel(as_of)
