import streamlit as st
import pandas as pd
import plotly.express as px
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor
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

    inversion_depth = -spread["T10Y3M"].clip(upper=0)
    weights = list(range(1, 25))

    weighted_inversion = inversion_depth.rolling(
        24,
        min_periods=24
    ).apply(
        lambda values: sum(values * weights) / sum(weights),
        raw=True
    )

    model_data["weighted_inversion"] = weighted_inversion

    inflation_monthly = pd.Series(index=spread.index, dtype="float64")
    cpi_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"

    try:
        cpi_frame = pd.read_csv(
            cpi_url, index_col=0, parse_dates=True, na_values="."
        )
    except Exception:
        cpi_backup = DATA_DIR / "CPIAUCSL.csv"
        if cpi_backup.exists():
            cpi_frame = pd.read_csv(
                cpi_backup, index_col=0, parse_dates=True, na_values="."
            )
        else:
            cpi_frame = None

    if cpi_frame is not None:
        cpi = pd.to_numeric(cpi_frame["CPIAUCSL"], errors="coerce")
        cpi = cpi.sort_index().resample("ME").last()
        inflation = cpi.pct_change(12, fill_method=None) * 100
        inflation_monthly = inflation.shift(1).reindex(spread.index)

    model_data["inflation_12m"] = inflation_monthly

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
        subset=["recession_12m", "weighted_inversion"]
    )
    X_second = sm.add_constant(
        second_data[["T10Y3M", "weighted_inversion"]].astype(float),
        has_constant="add"
    )
    y_second = second_data["recession_12m"].astype(int)
    second_model = sm.Probit(y_second, X_second).fit(disp=False)

    third_model = None
    third_data = model_data.dropna(
        subset=["recession_12m", "weighted_inversion", "inflation_12m"]
    )

    third_predictors = [
        "T10Y3M", "weighted_inversion", "inflation_12m"
    ]

    if len(third_data) >= 60 and third_data["recession_12m"].nunique() == 2:
        X_third = sm.add_constant(
            third_data[third_predictors].astype(float),
            has_constant="add"
        )
        y_third = third_data["recession_12m"].astype(int)
        try:
            third_model = sm.Probit(y_third, X_third).fit(disp=False)
        except Exception:
            third_model = None

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
    [data-testid="stExpander"] summary {
        background-color: #f2eee6 !important;
    }

    [data-testid="stExpander"] summary p,
    [data-testid="stExpander"] summary span {
        color: #222222 !important;
        opacity: 1 !important;
    }

    [data-testid="stTabs"] button[aria-selected="false"],
    [data-testid="stTabs"] button[aria-selected="false"] p,
    [data-testid="stTabs"] button[aria-selected="false"] span {
        color: #333333 !important;
        opacity: 1 !important;
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
        "Weighted inversion",
        "Inflation"
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
        weighted_value = weighted_inversion.reindex(
            selected_data.index
        ).iloc[0]

        if pd.isna(weighted_value):
            st.warning("Not enough historical data for this model.")
        else:
            second_input = selected_data[["T10Y3M"]].copy()
            second_input["weighted_inversion"] = weighted_value
            second_input = sm.add_constant(
                second_input.astype(float),
                has_constant="add"
            )
            second_probability = second_model.predict(second_input).iloc[0] * 100

            st.html(
                f'<p style="color: #222222;">'
                f'Recession probability (12 months ahead): {second_probability:.1f}%'
                f'</p>'
            )
            st.html(
                f'<p style="color: #222222;">'
                f'Weighted inversion index (24 months): {weighted_value:.3f}'
                f'</p>'
            )
            st.html('<p style="color: #222222;">Regression coefficients:</p>')
            st.write(second_model.params)

        with st.expander("Weighted inversion historical probabilities"):
            weighted_table = spread[["T10Y3M"]].copy()
            weighted_table["weighted_inversion"] = weighted_inversion
            weighted_table = weighted_table.dropna()

            X_weighted = sm.add_constant(
                weighted_table[["T10Y3M", "weighted_inversion"]].astype(float),
                has_constant="add"
            )
            weighted_table["Estimated probability (%)"] = (
                second_model.predict(X_weighted) * 100
            ).round(2)
            weighted_table["Actual recession 12 months later"] = (
                model_data["recession_12m"].astype("Int64")
            )
            weighted_table["Actual recession 12 months later"] = (
                weighted_table["Actual recession 12 months later"]
                .astype("string").fillna("N/A")
            )
            weighted_table = weighted_table.sort_index(ascending=False)

            selected_period = weighted_table[
                weighted_table.index <= cutoff
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

            if st.checkbox("Show full historical series", key="weighted_full_history"):
                full_table = weighted_table.copy()
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
                    full_table, width="stretch", height=400,
                    key="bond_weighted_full_history"
                )

    with tab3:
        if third_model is None:
            st.warning(
                "Inflation data or sufficient recession history is unavailable. "
                "Download CPIAUCSL.csv from FRED into the data folder if needed."
            )
        else:
            selected_inflation = inflation_monthly.reindex(selected_data.index).iloc[0]
            selected_weighted = weighted_inversion.reindex(selected_data.index).iloc[0]

            if any(pd.isna(value) for value in [
                selected_inflation, selected_weighted
            ]):
                st.warning("Not enough historical data for the inflation model at this date.")
            else:
                third_input = selected_data[["T10Y3M"]].copy()
                third_input["weighted_inversion"] = selected_weighted
                third_input["inflation_12m"] = selected_inflation
                third_input = sm.add_constant(
                    third_input.astype(float), has_constant="add"
                )
                third_probability = third_model.predict(third_input).iloc[0] * 100

                st.html(
                    f'<p style="color: #222222;">'
                    f'Recession probability (12 months ahead): {third_probability:.1f}%'
                    f'</p>'
                )
                st.html(
                    f'<p style="color: #222222;">'
                    f'Weighted inversion index (24 months): {selected_weighted:.3f}'
                    f'</p>'
                )
                st.html(
                    f'<p style="color: #222222;">'
                    f'Annual CPI inflation: {selected_inflation:.1f}%'
                    f'</p>'
                )
                st.html(
                    '<p style="color: #444444;">'
                    'Annual inflation is the CPI change over the previous 12 months, '
                    'used with a one-month reporting lag.'
                    '</p>'
                )
                st.html('<p style="color: #222222;">Regression coefficients:</p>')
                st.write(third_model.params)

            with st.expander("Inflation historical probabilities"):
                inflation_table = spread[["T10Y3M"]].copy()
                inflation_table["weighted_inversion"] = weighted_inversion
                inflation_table["inflation_12m"] = inflation_monthly
                inflation_table = inflation_table.dropna()

                X_inflation_history = sm.add_constant(
                    inflation_table[third_predictors].astype(float),
                    has_constant="add"
                )
                inflation_table["Estimated probability (%)"] = (
                    third_model.predict(X_inflation_history) * 100
                ).round(2)
                inflation_table["Actual recession 12 months later"] = (
                    model_data["recession_12m"].astype("Int64")
                )
                inflation_table["Actual recession 12 months later"] = (
                    inflation_table["Actual recession 12 months later"]
                    .astype("string").fillna("N/A")
                )
                inflation_table = inflation_table.rename(columns={
                    "weighted_inversion": "Weighted Inversion Index",
                    "inflation_12m": "Annual CPI Inflation (%)"
                }).sort_index(ascending=False)

                selected_period = inflation_table[
                    inflation_table.index <= cutoff
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

                if st.checkbox("Show full historical series", key="inflation_full_history"):
                    full_table = inflation_table.copy()
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
                        full_table, width="stretch", height=400,
                        key="bond_inflation_full_history"
                    )

            with st.expander("Inflation model diagnostics"):
                correlation_table = third_data[third_predictors].corr().round(2)
                st.html('<p style="color: #222222;">Predictor correlations</p>')
                st.dataframe(correlation_table, width="stretch")

                vif_values = [
                    variance_inflation_factor(X_third.to_numpy(), column)
                    for column in range(1, len(X_third.columns))
                ]
                vif_table = pd.DataFrame({
                    "Variable": third_predictors,
                    "VIF": [round(value, 2) for value in vif_values]
                })
                st.html('<p style="color: #222222;">Variance inflation factors (VIF)</p>')
                st.dataframe(vif_table, hide_index=True, width="stretch")

    with st.expander("Explore data table"):
        display_data = model_data[model_data.index <= cutoff].tail(12).copy()
        display_data = display_data.rename(columns={
            "T10Y3M": "10Y–3M Treasury Spread",
            "USREC": "US Recession",
            "recession_12m": "Recession 12 Months Later",
            "weighted_inversion": "Weighted Inversion Index",
            "inflation_12m": "Annual CPI Inflation (%)"
        })
        display_data.index.name = "Observation Date"
        st.dataframe(display_data, width="stretch")
