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


@st.cache_data(ttl=3600, show_spinner=False)
def load_fred_series(name: str):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={name}"
    backup = DATA_DIR / f"{name}.csv"

    for source in [url, backup]:
        try:
            frame = pd.read_csv(
                source, index_col=0, parse_dates=True, na_values="."
            )
            if name not in frame.columns:
                continue
            frame.index = pd.to_datetime(frame.index, errors="coerce")
            frame = frame[frame.index.notna()].sort_index()
            frame = frame[~frame.index.duplicated(keep="last")]
            frame[name] = pd.to_numeric(frame[name], errors="coerce")
            if frame[name].notna().any():
                return frame[[name]]
        except Exception:
            continue

    return None


def completed_month(as_of: date) -> pd.Timestamp:
    cutoff = pd.Timestamp(as_of)
    if cutoff != cutoff + pd.offsets.MonthEnd(0):
        cutoff = cutoff - pd.offsets.MonthEnd(1)
    return cutoff


def percentile_rank(values: pd.Series) -> int:
    current_value = values.iloc[-1]
    below = (values < current_value).sum()
    equal = (values == current_value).sum()
    return max(1, min(100, round(100 * (below + 0.5 * equal) / len(values))))


def get_warning_score(as_of: date):
    treasury_frame = load_fred_series("T10Y3M")
    recession_frame = load_fred_series("USREC")
    baa_frame = load_fred_series("BAA10Y")

    if treasury_frame is None or recession_frame is None or baa_frame is None:
        return None

    spread = treasury_frame[["T10Y3M"]].resample("ME").mean()
    recession = recession_frame[["USREC"]].resample("ME").last()
    credit = baa_frame[["BAA10Y"]].resample("ME").mean()

    baseline_training = spread.join(recession).dropna()
    baseline_training["recession_12m"] = baseline_training["USREC"].shift(-12)
    baseline_training = baseline_training.dropna(subset=["recession_12m"])

    credit_training = credit.join(recession).dropna()

    if (len(baseline_training) < 60 or
            baseline_training["recession_12m"].nunique() < 2 or
            len(credit_training) < 60 or credit_training["USREC"].nunique() < 2):
        return None

    try:
        baseline_X = sm.add_constant(baseline_training[["T10Y3M"]], has_constant="add")
        baseline_model = sm.Probit(
            baseline_training["recession_12m"].astype(int), baseline_X
        ).fit(disp=False)

        credit_X = sm.add_constant(credit_training[["BAA10Y"]], has_constant="add")
        credit_model = sm.Probit(
            credit_training["USREC"].astype(int), credit_X
        ).fit(disp=False)
    except Exception:
        return None

    joint = spread.join(credit, how="inner").dropna()
    joint = joint[joint.index <= completed_month(as_of)]
    if len(joint) < 24:
        return None

    joint["yield_probability"] = baseline_model.predict(
        sm.add_constant(joint[["T10Y3M"]], has_constant="add")
    ) * 100
    joint["credit_probability"] = credit_model.predict(
        sm.add_constant(joint[["BAA10Y"]], has_constant="add")
    ) * 100

    yield_rank = percentile_rank(joint["yield_probability"])
    credit_rank = percentile_rank(joint["credit_probability"])
    score = round(0.70 * yield_rank + 0.30 * credit_rank)

    return {
        "score": score,
        "yield_rank": yield_rank,
        "credit_rank": credit_rank,
        "yield_probability": joint["yield_probability"].iloc[-1],
        "credit_probability": joint["credit_probability"].iloc[-1],
        "observation_month": joint.index[-1],
        "comparison_months": len(joint)
    }


def render(as_of: date) -> None:
    st.html('<h2 style="color: #222222; margin: 0;">Bond Market Signal</h2>')
    st.html(
        '<p style="color: #444444; margin: 0 0 10px 0;">'
        'Explore Treasury yield curves, corporate credit spreads and US recession probabilities.'
        '</p>'
    )
    st.html(
        f'<p style="color: #666666; margin: 0 0 12px 0;">'
        f'Time Machine: {as_of:%b %Y}'
        f'</p>'
    )

    warning = get_warning_score(as_of)
    if warning is None:
        st.html(
            '<p style="color: #666666; margin: 0;">'
            'Bond Market and Credit Spread Warning Score: unavailable (check historical BAA10Y data).'
            '</p>'
        )
    else:
        st.html(
            f'<p style="color: #222222; font-size: 22px; margin: 0;">'
            f'Bond Market and Credit Spread Warning Score: <strong>{warning["score"]}/100</strong>'
            f'</p>'
            f'<p style="color: #666666; margin: 0;">'
            f'Historical recession warning index, as of {warning["observation_month"]:%b %Y}; '
            f'not a recession probability.'
            f'</p>'
        )


def render_full(as_of: date) -> None:
    from ui.controls import render_time_machine
    as_of = render_time_machine(as_of)

    # Yield and corporate credit spread charts

    st.html('<h2 style="color: #222222; margin: 0;">Bond Market Signal</h2>')
    st.html('<p style="color: #444444; margin: 0;">Choose yield or credit spread</p>')

    titles = {
        "T10Y3M": "10-Year minus 3-Month Treasury Spread",
        "T10Y2Y": "10-Year minus 2-Year Treasury Spread",
        "BAA10Y": "Moody's Baa Corporate Credit Spread"
    }
    series = st.selectbox(
        "Choose yield or credit spread",
        list(titles),
        format_func=lambda name: titles[name],
        label_visibility="collapsed"
    )

    treasury_frame = load_fred_series("T10Y3M")
    recession_frame = load_fred_series("USREC")
    baa_frame = load_fred_series("BAA10Y")

    if treasury_frame is None or recession_frame is None:
        st.error(
            "Treasury or US recession data is missing. "
            "Check T10Y3M.csv and USREC.csv in the data folder."
        )
        return

    chart_data = {
        "T10Y3M": treasury_frame,
        "T10Y2Y": load_fred_series("T10Y2Y") if series == "T10Y2Y" else None,
        "BAA10Y": baa_frame
    }[series]

    if chart_data is None:
        st.warning(
            f"{titles[series]} data is unavailable. "
            f"Download {series}.csv from FRED into your data folder."
        )
    else:
        chart_data = chart_data.loc[
            chart_data.index <= pd.Timestamp(as_of), [series]
        ].dropna()

        if chart_data.empty:
            st.warning("No chart data available for this Time Machine date.")
        else:
            latest_value = chart_data[series].iloc[-1]
            fig = px.line(
                chart_data, x=chart_data.index, y=series, title=titles[series]
            )

            if series in ("T10Y3M", "T10Y2Y"):
                fig.add_hline(y=0, line_color="red", line_dash="dash")
                signal = (
                    "Yield curve inverted" if latest_value < 0
                    else "Yield curve not inverted"
                )
            else:
                signal = (
                    f"Moody's Baa credit spread: {latest_value:.2f} "
                    "percentage points"
                )

            chart_recessions = recession_frame.loc[
                (recession_frame.index >= chart_data.index.min()) &
                (recession_frame.index <= pd.Timestamp(as_of))
            ]
            for month in chart_recessions.index[chart_recessions["USREC"] == 1]:
                fig.add_vrect(
                    x0=month,
                    x1=month + pd.DateOffset(months=1),
                    fillcolor="gray",
                    opacity=0.2,
                    line_width=0,
                    layer="below"
                )

            fig.update_traces(
                hovertemplate=(
                    "Date: %{x|%d %B %Y}<br>Spread: %{y:.2f} "
                    "percentage points<extra></extra>"
                )
            )
            fig.update_layout(
                height=300, xaxis_title=None,
                yaxis_title="Percentage points"
            )
            fig.update_xaxes(dtick="M60", tick0="1980-01-01", tickformat="%Y")
            st.plotly_chart(fig, width="stretch")
            st.html(f'<p style="color: #222222;">{signal}</p>')

    # Prepare regression data

    spread = treasury_frame[["T10Y3M"]].resample("ME").mean()
    recession = recession_frame[["USREC"]].resample("ME").last()

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

    credit_monthly = pd.Series(index=spread.index, dtype="float64")
    if baa_frame is not None:
        credit_monthly = (
            baa_frame["BAA10Y"].resample("ME").mean().reindex(spread.index)
        )
    model_data["credit_spread"] = credit_monthly

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
    third_data = model_data.dropna(subset=["credit_spread", "USREC"])
    if len(third_data) >= 60 and third_data["USREC"].nunique() == 2:
        X_third = sm.add_constant(
            third_data[["credit_spread"]].astype(float), has_constant="add"
        )
        y_third = third_data["USREC"].astype(int)
        try:
            third_model = sm.Probit(y_third, X_third).fit(disp=False)
        except Exception:
            third_model = None

    # Time Machine

    cutoff = completed_month(as_of)

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

    # Bond market warning score

    warning = get_warning_score(as_of)
    st.html('<h3 style="color: #222222; margin-bottom: 4px;">Bond Market and Credit Spread Warning Score</h3>')
    if warning is None:
        st.warning(
            "Warning score unavailable for this Time Machine date. "
            "It requires historical Treasury, recession and BAA10Y data."
        )
    else:
        st.metric("Historical recession warning index", f'{warning["score"]}/100')
        st.progress(warning["score"])
        st.html(
            f'<p style="color: #222222;">'
            f'Yield curve percentile: <strong>{warning["yield_rank"]}/100</strong> '
            f'(70% weight) &nbsp;|&nbsp; '
            f'Credit stress percentile: <strong>{warning["credit_rank"]}/100</strong> '
            f'(30% weight)'
            f'</p>'
        )
        st.caption(
            f'Observation: {warning["observation_month"]:%b %Y}. '
            f'Ranked against {warning["comparison_months"]} months available '
            'up to this Time Machine date, beginning in the Baa data period. '
            'A score of 80 is not an 80% chance of recession.'
        )
        with st.expander("How the warning score is calculated"):
            st.write(
                "The Baseline estimates the probability of being in recession "
                "exactly 12 months later. The Baa model estimates whether "
                "the economy is in recession in the current month. "
                "Each model's probability is ranked against its own historical "
                "probabilities observed through the selected month. "
                "The warning score is 70% of the yield percentile plus "
                "30% of the credit percentile, rounded to a whole number. "
                "Weights are illustrative, not statistically optimized. "
                "The Probit coefficients use the full available historical dataset, "
                "so past Time Machine scores are retrospective estimates, "
                "not genuine forecasts made at that time."
            )

    tab1, tab2, tab3 = st.tabs([
        "Baseline",
        "Weighted inversion",
        "Baa credit spreads (current)"
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
                "Baa recession nowcast unavailable. "
                "Check that data/BAA10Y.csv contains enough historical observations."
            )
        else:
            credit_available = credit_monthly[credit_monthly.index <= cutoff].dropna()
            if credit_available.empty:
                st.warning("No Baa credit spread data available for this date.")
            else:
                selected_credit = credit_available.iloc[-1]
                selected_credit_month = credit_available.index[-1]
                third_input = pd.DataFrame(
                    {"credit_spread": [selected_credit]}, index=[selected_credit_month]
                )
                third_input = sm.add_constant(third_input, has_constant="add")
                third_probability = third_model.predict(third_input).iloc[0] * 100
                credit_correlation = third_data["credit_spread"].corr(third_data["USREC"])

                st.html(
                    f'<p style="color: #222222;">'
                    f'Estimated probability of recession now: {third_probability:.1f}%'
                    f'</p>'
                )
                st.html(
                    f'<p style="color: #222222;">'
                    f"Moody's Baa credit spread ({selected_credit_month:%b %Y}): "
                    f'{selected_credit:.2f} percentage points'
                    f'</p>'
                )
                st.html(
                    f'<p style="color: #222222;">'
                    f'Historical correlation with same-month recession: '
                    f'{credit_correlation:.3f}'
                    f'</p>'
                )
                st.caption(
                    "This is a same-month recession nowcast based on credit spreads, "
                    "not a 12-month-ahead forecast or an official recession determination."
                )
                st.html('<p style="color: #222222;">Regression coefficients:</p>')
                st.write(third_model.params)

            with st.expander("Baa current-recession historical probabilities"):
                credit_table = credit_monthly.dropna().to_frame("credit_spread")
                X_credit = sm.add_constant(
                    credit_table[["credit_spread"]], has_constant="add"
                )
                credit_table["Estimated probability of recession now (%)"] = (
                    third_model.predict(X_credit) * 100
                ).round(2)
                credit_table["Actual recession this month"] = (
                    recession["USREC"].astype("Int64")
                )
                credit_table["Actual recession this month"] = (
                    credit_table["Actual recession this month"]
                    .astype("string").fillna("N/A")
                )
                credit_table = credit_table.rename(columns={
                    "credit_spread": "Baa Credit Spread (percentage points)"
                }).sort_index(ascending=False)

                selected_period = credit_table[
                    credit_table.index <= cutoff
                ].head(13).copy()
                if selected_period.empty:
                    st.info("No credit-spread probabilities available for this date.")
                else:
                    selected_month = selected_period.index.max()
                    st.html(
                        f'<p style="color: #222222;">'
                        f'Selected period: {selected_month:%b %Y} '
                        f'and the previous 12 months'
                        f'</p>'
                    )
                    selected_period.index = selected_period.index.strftime("%b %Y")
                    selected_period.index.name = "Month"
                    st.dataframe(selected_period, width="stretch", height=500)

                if st.checkbox("Show full historical series", key="baa_now_full_history"):
                    full_table = credit_table.copy()
                    first_month = full_table.index.min()
                    last_month = full_table.index.max()
                    st.html(
                        f'<p style="color: #222222;">'
                        f'Full historical data: {first_month:%b %Y} '
                        f'to {last_month:%b %Y}'
                        f'</p>'
                    )
                    full_table.index = full_table.index.strftime("%b %Y")
                    full_table.index.name = "Month"
                    st.dataframe(
                        full_table, width="stretch", height=400,
                        key="bond_baa_now_full_history"
                    )

    with st.expander("Explore data table"):
        display_data = model_data[model_data.index <= cutoff].tail(12).copy()
        display_data = display_data.rename(columns={
            "T10Y3M": "10Y–3M Treasury Spread",
            "USREC": "US Recession",
            "recession_12m": "Recession 12 Months Later",
            "weighted_inversion": "Weighted Inversion Index",
            "credit_spread": "Baa Credit Spread (percentage points)"
        })
        display_data.index.name = "Observation Date"
        st.dataframe(display_data, width="stretch")
