
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from pathlib import Path

TITLE = "Bond market"

def render(as_of: date) -> None:
    st.html('<h2 style="color: #222222; margin: 0;">Bond Market Signal</h2>')

    st.html('<p style="color: #444444; margin: 0;">Choose yield spread</p>')

    series = st.selectbox(
        "Choose yield spread",
        ["T10Y3M", "T10Y2Y"],
        label_visibility="collapsed"
    )

    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

    backup = Path(__file__).resolve().parents[2] / "data" / f"{series}.csv"

    try:
        data = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".")

    except Exception:
        data = pd.read_csv(backup, index_col=0, parse_dates=True, na_values=".")
        st.info("Using saved FRED data.")

    data = data[data.index <= pd.Timestamp(as_of)]

    if series == "T10Y3M":
        title = "10-Year minus 3-Month Treasury Spread"
    else:
        title = "10-Year minus 2-Year Treasury Spread"

    fig = px.line(data, x=data.index, y=series, title=title)

    fig.add_hline(y=0, line_color="red", line_dash="dash")

    fig.update_traces(
        hovertemplate="Date: %{x|%d %B %Y}<br>Spread: %{y:.2f}<extra></extra>"
    )

    fig.update_layout(height=300, xaxis_title=None, yaxis_title="Percentage points")

    st.plotly_chart(fig, width="stretch")

