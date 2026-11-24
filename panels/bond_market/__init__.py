
import streamlit as st
import pandas as pd
import plotly.express as px
import statsmodels.api as sm
from datetime import date
from pathlib import Path

TITLE = "Bond market"
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
PROBABILITY_CACHE = DATA_DIR / "us_recession_probability.csv"


def load_recession_probability(selected_date: pd.Timestamp) -> pd.Series:
    if not PROBABILITY_CACHE.exists():
        return pd.Series(dtype="float64", name="Recession Probability (%)")

    frame = pd.read_csv(PROBABILITY_CACHE)
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Recession Probability (%)"] = pd.to_numeric(
        frame["Recession Probability (%)"], errors="coerce"
    )
    frame = frame.dropna(subset=["Date", "Recession Probability (%)"])
    frame = frame[
        (frame["Date"] <= pd.Timestamp(selected_date)) &
        frame["Recession Probability (%)"].between(0, 100)
    ]
    frame = frame.sort_values("Date").drop_duplicates("Date", keep="last")

    return pd.Series(
        frame["Recession Probability (%)"].to_numpy(),
        index=pd.DatetimeIndex(frame["Date"], name="Date"),
        name="Recession Probability (%)"
    )


def render(as_of: date) -> None:
    st.html('<h2 style="color: #222222; margin: 0;">Bond Market Signal</h2>')
    st.html(
        '<p style="color: #444444; margin: 0 0 10px 0;">'
        'Explore Treasury yield curves, inversion signals and US recession probabilities.'
        '</p>'
    )
    st.html(
        f'<p style="color: #666666; margin: 0 0 12px 0;">'
        f'Time Machine: {as_of:%b %Y}'
        f'</p>'
    )


def render_full(as_of: date) -> None:
    from ui.controls import render_time_machine
    as_of = render_time_machine(as_of)

    # Yield curve chart

    st.html('<h2 style="color: #222222; margin: 0;">Bond Market Signal</h2>')
    st.html('<p style="color: #444444; margin: 0;">Choose yield spread</p>')

    series = st.selectbox(
        "Choose yield spread",
        ["T10Y3M", "T10Y2Y"],
        label_visibility="collapsed"
    )

    folder = Path(__file__).resolve().parents[2] / "data"
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"

    try:
        data = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".")
    except Exception:
        data = pd.read_csv(
            folder / f"{series}.csv",
            index_col=0,
            parse_dates=True,
            na_values="."
        )
        st.info("Using saved FRED data.")

    data = data[data.index <= pd.Timestamp(as_of)]

    if data[series].dropna().empty:
        st.warning("No yield spread data available for this date.")
        return

    latest_spread = data[series].dropna().iloc[-1]
    signal = "Yield curve inverted" if latest_spread < 0 else "Yield curve not inverted"

    if series == "T10Y3M":
        title = "10-Year minus 3-Month Treasury Spread"
    else:
        title = "10-Year minus 2-Year Treasury Spread"

    fig = px.line(data, x=data.index, y=series, title=title)
    fig.add_hline(y=0, line_color="red", line_dash="dash")

    recession = pd.read_csv(
        folder / "USREC.csv",
        index_col=0,
        parse_dates=True
    )
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

    # Prepare regression data

    datasets = {}

    for name in ["T10Y3M", "USREC"]:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={name}"

        try:
            df = pd.read_csv(url, index_col=0, parse_dates=True, na_values=".")
        except Exception:
            df = pd.read_csv(
                folder / f"{name}.csv",
                index_col=0,
                parse_dates=True,
                na_values="."
            )

        datasets[name] = df

    spread = datasets["T10Y3M"].resample("ME").mean()
    recession = datasets["USREC"].resample("ME").last()

    model_data = spread.join(recession).dropna()
    model_data["recession_12m"] = model_data["USREC"].shift(-12)

    rolling_min = spread["T10Y3M"].rolling(12, min_periods=12).min()
    model_data["recent_inversion"] = (
        (rolling_min < 0).where(rolling_min.notna())
    )

    # Fit regression models

    regression_data = model_data.dropna(subset=["recession_12m"])
    X = sm.add_constant(regression_data[["T10Y3M"]], has_constant="add")
    y = regression_data["recession_12m"].astype(int)
    model = sm.Probit(y, X).fit(disp=False)

    correlation = regression_data["T10Y3M"].corr(y)

    all_X = sm.add_constant(
        spread[["T10Y3M"]].dropna(),
        has_constant="add"
    )
    all_probabilities = model.predict(all_X) * 100

    second_data = model_data.dropna(
        subset=["recession_12m", "recent_inversion"]
    )
    X_second = sm.add_constant(
        second_data[["T10Y3M", "recent_inversion"]].astype(float),
        has_constant="add"
    )
    y_second = second_data["recession_12m"].astype(int)
    second_model = sm.Probit(y_second, X_second).fit(disp=False)

    # Time Machine

    cutoff = pd.Timestamp(as_of)

    if cutoff != cutoff + pd.offsets.MonthEnd(0):
        cutoff = cutoff - pd.offsets.MonthEnd(1)

    selected_data = spread[spread.index <= cutoff].dropna().tail(1)

    if selected_data.empty:
        st.warning("No Treasury spread data available for this date.")
        return

    latest_X = sm.add_constant(selected_data, has_constant="add")
    probability = model.predict(latest_X).iloc[0] * 100

    # Website display

    st.html("""
    <style>
    [data-testid="stExpander"] summary p {
        color: #222222 !important;
    }

    div[data-testid="stTabs"] button[data-baseweb="tab"],
    div[data-testid="stTabs"] button[data-baseweb="tab"] p {
        color: #333333 !important;
        opacity: 1 !important;
    }

    div[data-testid="stTabs"] button[aria-selected="true"],
    div[data-testid="stTabs"] button[aria-selected="true"] p {
        color: #e87e00 !important;
    }
    </style>
    """)

    historical = model_data[
        (model_data.index + pd.DateOffset(months=12) <= cutoff) &
        model_data["recession_12m"].notna()
    ].copy()

    tab1, tab2, tab3 = st.tabs([
        "Baseline",
        "Recent inversion",
        "Government debt"
    ])

    with tab1:
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

        if st.button("Create / update shared CSV", key="bond_export_probabilities"):
            export_table = all_probabilities[
                all_probabilities.index <= pd.Timestamp(date.today())
            ].to_frame(name="Recession Probability (%)")
            export_table["Actual recession 12 months later"] = (
                model_data["recession_12m"].astype("Int64")
            )
            export_table["Actual recession 12 months later"] = (
                export_table["Actual recession 12 months later"]
                .astype("string")
                .fillna("N/A")
            )
            export_table = export_table.rename_axis("Date").reset_index()
            export_table["Date"] = export_table["Date"].dt.strftime("%Y-%m-%d")

            try:
                export_table.to_csv(PROBABILITY_CACHE, index=False)
                st.success("Saved data/us_recession_probability.csv for your group.")
            except OSError as error:
                st.error(f"Could not save CSV: {error}")

        with st.expander("Baseline historical recession probabilities"):
            probability_table = all_probabilities.to_frame(
                name="Estimated probability (%)"
            )
            probability_table["T10Y3M"] = spread["T10Y3M"]
            probability_table["Actual recession 12 months later"] = (
                model_data["recession_12m"].astype("Int64")
            )

            probability_table["Estimated probability (%)"] = (
                probability_table["Estimated probability (%)"].round(2)
            )
            probability_table["Actual recession 12 months later"] = (
                probability_table["Actual recession 12 months later"]
                .astype("string")
                .fillna("N/A")
            )
            probability_table = probability_table[
                [
                    "T10Y3M",
                    "Estimated probability (%)",
                    "Actual recession 12 months later"
                ]
            ].sort_index(ascending=False)

            selected_period = probability_table[
                probability_table.index <= cutoff
            ].head(13).copy()

            if selected_period.empty:
                st.info("No historical probabilities available for this date.")
            else:
                selected_month = selected_period.index.max()
                st.html(
                    f'<p style="color: #222222;">'
                    f'Selected period: {selected_month:%b %Y} and the previous 12 months'
                    f'</p>'
                )

                selected_period.index = selected_period.index.strftime("%b %Y")
                selected_period.index.name = "Month"
                st.dataframe(selected_period, width="stretch", height=500)

            if st.checkbox("Show full historical series", key="baseline_full_history"):
                full_table = probability_table.copy()
                first_month = full_table.index.min()
                last_month = full_table.index.max()

                st.html(
                    f'<p style="color: #222222;">'
                    f'Full historical data: {first_month:%b %Y} to {last_month:%b %Y}'
                    f'</p>'
                )

                full_table.index = full_table.index.strftime("%b %Y")
                full_table.index.name = "Month"
                st.dataframe(
                    full_table,
                    width="stretch",
                    height=400,
                    key="bond_baseline_full_history"
                )

    with tab2:
        selected_min = rolling_min.loc[selected_data.index].iloc[0]

        if pd.isna(selected_min):
            st.warning("Not enough historical data for this model.")
        else:
            recent_inversion = int(selected_min < 0)
            second_input = selected_data[["T10Y3M"]].copy()
            second_input["recent_inversion"] = recent_inversion
            second_input = sm.add_constant(
                second_input.astype(float),
                has_constant="add"
            )
            second_probability = second_model.predict(second_input).iloc[0] * 100
            inversion_text = "Yes" if recent_inversion == 1 else "No"

            st.html(
                f'<p style="color: #222222;">'
                f'Recession probability (12 months ahead): {second_probability:.1f}%'
                f'</p>'
            )
            st.html(
                f'<p style="color: #222222;">'
                f'Yield curve inverted in the past 12 months: {inversion_text}'
                f'</p>'
            )
            st.html('<p style="color: #222222;">Regression coefficients:</p>')
            st.write(second_model.params)

        with st.expander("Historical regression table"):
            second_historical = historical.dropna(
                subset=["recent_inversion"]
            ).copy()

            if second_historical.empty:
                st.info("No completed 12-month recession outcomes available.")
            else:
                second_table = second_historical[
                    ["T10Y3M", "recent_inversion"]
                ].copy()
                X_history_second = sm.add_constant(
                    second_table[["T10Y3M", "recent_inversion"]].astype(float),
                    has_constant="add"
                )
                second_table["Estimated probability (%)"] = (
                    second_model.predict(X_history_second) * 100
                ).round(2)
                second_table["Actual recession"] = (
                    second_historical["recession_12m"].astype(int)
                )
                second_table = second_table.tail(12)
                second_table.index = second_table.index.strftime("%b %Y")
                second_table.index.name = "Month"
                st.dataframe(second_table, width="stretch")

    with tab3:
        st.html(
            '<p style="color: #222222;">'
            'Government debt model coming later.'
            '</p>'
        )

    with st.expander("Explore data table"):
        st.dataframe(
            model_data[model_data.index <= cutoff].tail(12),
            width="stretch"
        )

