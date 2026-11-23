
import streamlit as st
import pandas as pd
import plotly.express as px
import statsmodels.api as sm
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

    latest_spread = data[series].dropna().iloc[-1]

    if latest_spread < 0:
        signal = "Yield curve inverted"
    else:
        signal = "Yield curve not inverted"

    if series == "T10Y3M":
        title = "10-Year minus 3-Month Treasury Spread"
    else:
        title = "10-Year minus 2-Year Treasury Spread"

    fig = px.line(data, x=data.index, y=series, title=title)

    fig.add_hline(y=0, line_color="red", line_dash="dash")

    recession_file = Path(__file__).resolve().parents[2] / "data" / "USREC.csv"

    recession = pd.read_csv(recession_file, index_col=0, parse_dates=True)

    recession = recession[
        (recession.index >= data.index.min()) &
        (recession.index <= pd.Timestamp(as_of))
    ]

    for month in recession.index[recession["USREC"] == 1]:
        fig.add_vrect(
            x0=month,
            x1=month + pd.DateOffset(months=1),
            fillcolor="gray",
            opacity=0.2,
            line_width=0,
            layer="below"
        )

    fig.update_traces(
        hovertemplate="Date: %{x|%d %B %Y}<br>Spread: %{y:.2f}<extra></extra>"
    )

    fig.update_layout(height=300, xaxis_title=None, yaxis_title="Percentage points")

    fig.update_xaxes(dtick="M60", tick0="1980-01-01", tickformat="%Y")

    st.plotly_chart(fig, width="stretch")

    st.html(f'<p style="color: #222222;">{signal}</p>')

    # Probit model

    folder = Path(__file__).resolve().parents[2] / "data"

    series_names = ["T10Y3M", "T10Y2Y", "USREC"]
    datasets = []

    for name in series_names:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={name}"

        try:
            df = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".")
        except Exception:
            df = pd.read_csv(folder / f"{name}.csv", index_col=0, parse_dates=True, na_values=".")

        datasets.append(df)

    spread_3m, spread_2y, recessions = datasets

    spread_3m = spread_3m.resample("ME").last()
    spread_2y = spread_2y.resample("ME").last()
    recessions = recessions.resample("ME").last()

    model_data = spread_3m.join(spread_2y).join(recessions)

    model_data = model_data.dropna()
    model_data = model_data[model_data.index <= pd.Timestamp(as_of)]

    recession_start = (model_data["USREC"] == 1) & (model_data["USREC"].shift(1) == 0)

    model_data["recession_next_12m"] = False

    for month in range(1, 13):
        model_data["recession_next_12m"] |= recession_start.shift(-month, fill_value=False)

    model_data["recession_next_12m"] = model_data["recession_next_12m"].astype("Int64")
    model_data.loc[model_data.index[-12:], "recession_next_12m"] = pd.NA

    training_data = model_data.dropna(subset=["recession_next_12m"])

    X = training_data[["T10Y3M", "T10Y2Y"]]

    X = sm.add_constant(X)

    y = training_data["recession_next_12m"].astype(int)

    probit_model = sm.Probit(y, X).fit(disp=False)

    latest_data = model_data[["T10Y3M", "T10Y2Y"]].tail(1)

    latest_data = sm.add_constant(latest_data, has_constant="add")

    probability = probit_model.predict(latest_data).iloc[0] * 100

    with st.expander("Baseline Probit model"):
        st.write(f"Estimated recession probability: {probability:.1f}%")
        st.write("Regression coefficients:")
        st.write(probit_model.params)

    with st.expander("Explore data table"):
        st.dataframe(model_data.tail(12), width="stretch")
