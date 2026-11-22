
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date
from pathlib import Path

TITLE = "Bond market"

def render(as_of: date) -> None:
    st.subheader("Bond Market Signal")

    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y3M"

    backup = Path(__file__).resolve().parents[2] / "data" / "T10Y3M.csv"

    try:
        data = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".")

    except Exception:
        data = pd.read_csv(backup, index_col=0, parse_dates=True, na_values=".")
        st.info("Using saved FRED data.")

    data = data[data.index <= pd.Timestamp(as_of)]

    fig = plt.figure(figsize=(9, 2.8))

    plt.plot(data.index, data["T10Y3M"])

    plt.axhline(0, color="red", linestyle="--")

    plt.title("10-Year minus 3-Month Treasury Spread")
    plt.ylabel("Percentage points")

    st.pyplot(fig, width="stretch")
    plt.close(fig)
