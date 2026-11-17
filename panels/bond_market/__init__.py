import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date

TITLE = "Bond market"

def render(as_of: date) -> None:
    st.subheader("Bond Market Signal")

    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=T10Y3M"

    data = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".")

    data = data[data.index <= pd.Timestamp(as_of)]

    fig = plt.figure(figsize=(9, 2.8))

    plt.plot(data.index, data["T10Y3M"])

    plt.axhline(0, color="red", linestyle="--")

    plt.title("10-Year minus 3-Month Treasury Spread")
    plt.ylabel("Percentage points")

    st.pyplot(fig, width="stretch")
    plt.close(fig)
