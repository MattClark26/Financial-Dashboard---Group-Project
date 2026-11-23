
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

    fig.update_layout(
        height=300,
        xaxis_title=None,
        yaxis_title="Percentage points"
    )

    fig.update_xaxes(
        dtick="M60",
        tick0="1980-01-01",
        tickformat="%Y"
    )

    st.plotly_chart(fig, width="stretch")

    st.html(f'<p style="color: #222222;">{signal}</p>')


    # Probit model

    folder = Path(__file__).resolve().parents[2] / "data"

    datasets = {}

    for name in ["T10Y3M", "USREC"]:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={name}"

        try:
            df = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".")
        except Exception:
            df = pd.read_csv(folder / f"{name}.csv",
                             index_col=0, parse_dates=True, na_values=".")

        datasets[name] = df

    spread = datasets["T10Y3M"].resample("ME").mean()
    recession = datasets["USREC"].resample("ME").last()

    model_data = spread.join(recession).dropna()

    model_data["recession_12m"] = model_data["USREC"].shift(-12)

    regression_data = model_data.dropna(subset=["recession_12m"])

    X = regression_data[["T10Y3M"]]
    X = sm.add_constant(X)

    y = regression_data["recession_12m"].astype(int)

    model = sm.Probit(y, X).fit(disp=False)

    correlation = regression_data["T10Y3M"].corr(y)

    cutoff = pd.Timestamp(as_of)

    if cutoff != cutoff + pd.offsets.MonthEnd(0):
        cutoff = cutoff - pd.offsets.MonthEnd(1)

    selected_data = spread[spread.index <= cutoff].dropna().tail(1)

    if selected_data.empty:
        st.warning("No Treasury spread data available for this date.")
        return

    latest_X = sm.add_constant(selected_data, has_constant="add")

    probability = model.predict(latest_X).iloc[0] * 100

    st.html("""
    <style>
    .st-key-panel_bond [data-testid="stExpander"] summary p {
        color: #222222 !important;
    }
    </style>
    """)

    with st.expander("Probit regression"):
        st.html(
            f'<p style="color: #222222;">'
            f'Recession probability (12 months ahead): {probability:.1f}%'
            f'</p>'
        )

        st.html(
            f'<p style="color: #222222;">'
            f'Historical correlation: {correlation:.3f}'
            f'</p>'
        )

        st.html('<p style="color: #222222;">Regression coefficients:</p>')
        st.write(model.params)

    with st.expander("Historical regression table"):

        historical = model_data[model_data.index <= cutoff].copy()

        X_history = sm.add_constant(
            historical[["T10Y3M"]],
            has_constant="add"
        )

        historical["Estimated probability (%)"] = (
            model.predict(X_history) * 100
        ).round(2)

        historical["Actual recession"] = historical["recession_12m"].astype("Int64")

        historical.loc[
            historical.index + pd.DateOffset(months=12) > cutoff,
            "Actual recession"
        ] = pd.NA

        table = historical[
            ["T10Y3M", "Estimated probability (%)", "Actual recession"]
        ].dropna(subset=["Actual recession"]).tail(12)


        table.index = table.index.strftime("%b %Y")
        table.index.name = "Month"

        st.dataframe(table, width="stretch")

    with st.expander("Explore data table"):
        st.dataframe(
            model_data[model_data.index <= cutoff].tail(12),
            width="stretch"
        )
