"""Plotly chart builders for Panel 2. Inputs are already cut by the time machine.

Colours: blue/red for good/bad (colour-blind safe), orange = as first published,
blue = today's revised data, grey bands = recessions.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from panel2.claims import CLAIMS_THRESHOLD_PCT
from panel2.sahm import SAHM_THRESHOLD

GAIN_COLOUR = "#2a78d6"
LOSS_COLOUR = "#e34948"
TREND_COLOUR = "#7a7974"
REVISED_COLOUR = "#2a78d6"
FIRST_REPORTED_COLOUR = "#eb6834"
RECESSION_FILL = "rgba(128, 128, 128, 0.18)"  # works on light and dark themes

# Axis caps, so one extreme episode (spring 2020) doesn't flatten everything else.
PAYROLL_AXIS_LIMIT = 1_000  # thousands of jobs; 99% of months since 1939 within +/-900k
SAHM_AXIS_LIMIT = 4  # points; every pre-2020 recession peaked below 4
CLAIMS_AXIS_LIMIT = 1_000  # thousands; 2009 peak was ~660k

SAHM_CAPTION = (
    "How far unemployment (3-month average) has risen above its low of the "
    "previous year. When the line crosses the dashed 0.5 line, the Sahm rule "
    "has triggered; grey bands are official recessions."
)
CLAIMS_CAPTION = (
    "New claims for unemployment benefit each week (4-week average): a "
    "near-live count of layoffs. The warning flag goes up when the blue line "
    "climbs above the dashed line, 20% above its lowest point of the past year."
)
PAYROLL_CAPTION = (
    "Each bar is the number of jobs added (blue) or lost (red) that month; "
    "the grey line is the 3-month average. Look for a run of red bars and "
    "the line falling below zero, which has happened only around recessions."
)
REVISIONS_CAPTION = (
    "Orange is the jobs number as announced on the day; blue is the same month "
    "after later revisions. Bars below show the gap: below zero means the first "
    "report was too optimistic. Look at recessions, where first reports were "
    "consistently too rosy, so things were worse than they looked at the time."
)


def sahm_chart(ours, real_time, recessions) -> go.Figure:
    """Our Sahm rule vs FRED's real-time version (the overlap is the validation)."""
    figure = go.Figure()
    figure.add_scatter(
        x=real_time.index,
        y=real_time,
        mode="lines",
        line={"color": FIRST_REPORTED_COLOUR, "width": 2},
        name="FRED real-time (data as first published)",
        hovertemplate="%{x|%b %Y} real-time: %{y:.2f}<extra></extra>",
    )
    figure.add_scatter(
        x=ours.index,
        y=ours,
        mode="lines",
        line={"color": REVISED_COLOUR, "width": 2},
        name="Our calculation (today's revised data)",
        hovertemplate="%{x|%b %Y} ours: %{y:.2f}<extra></extra>",
    )
    figure.add_hline(
        y=SAHM_THRESHOLD,
        line={"color": TREND_COLOUR, "dash": "dash", "width": 1.5},
        annotation_text=f"Sahm trigger ({SAHM_THRESHOLD})",
        annotation_position="top left",
    )
    add_recession_shading(figure, recessions)
    _cap_axis_if_needed(
        figure, ours.combine_first(real_time), SAHM_AXIS_LIMIT, decimals=2, signed=False
    )
    figure.update_layout(
        title="Sahm rule: rise in unemployment above its recent low",
        xaxis_title="Month",
        yaxis_title="Percentage points",
        legend={"orientation": "h", "y": -0.2},
        hovermode="x unified",
    )
    return figure


def claims_chart(table, recessions) -> go.Figure:
    """Claims (4-week avg, thousands) vs the flag level, drawn in the same units."""
    average = table["four_week_avg"] / 1000
    flag_level = table["low_52_weeks"] * (1 + CLAIMS_THRESHOLD_PCT / 100) / 1000

    figure = go.Figure()
    figure.add_scatter(
        x=table.index,
        y=average,
        mode="lines",
        line={"color": REVISED_COLOUR, "width": 2},
        name="Claims, 4-week average",
        hovertemplate="Week of %{x|%d %b %Y}: %{y:,.0f}k<extra></extra>",
    )
    figure.add_scatter(
        x=table.index,
        y=flag_level,
        mode="lines",
        line={"color": TREND_COLOUR, "dash": "dash", "width": 1.5},
        name=f"Flag level ({CLAIMS_THRESHOLD_PCT}% above 52-week low)",
        hovertemplate="Flag level: %{y:,.0f}k<extra></extra>",
    )
    add_recession_shading(figure, recessions)
    _cap_axis_if_needed(figure, average.dropna(), CLAIMS_AXIS_LIMIT, unit="k", signed=False)
    figure.update_layout(
        title="Initial jobless claims: new layoffs each week",
        xaxis_title="Week",
        yaxis_title="Claims per week (thousands)",
        legend={"orientation": "h", "y": -0.2},
        hovermode="x unified",
    )
    return figure


def payroll_change_chart(table, recessions=None) -> go.Figure:
    """Monthly payroll change bars with a 3-month average line."""
    change = table["monthly_change"].dropna()
    colours = [GAIN_COLOUR if value >= 0 else LOSS_COLOUR for value in change]

    figure = go.Figure()
    figure.add_bar(
        x=change.index,
        y=change.values,
        marker_color=colours,
        name="Monthly change",
        showlegend=False,  # a one-colour swatch would mislead; the caption explains
        hovertemplate="%{x|%b %Y}: %{y:+,.0f}k jobs<extra></extra>",
    )
    figure.add_scatter(
        x=table.index,
        y=table["three_month_avg"],
        mode="lines",
        line={"color": TREND_COLOUR, "width": 2},
        name="3-month average",
        hovertemplate="%{x|%b %Y} 3-month avg: %{y:+,.0f}k<extra></extra>",
    )
    add_recession_shading(figure, recessions)
    _cap_axis_if_needed(figure, change, PAYROLL_AXIS_LIMIT, unit="k")
    figure.update_layout(
        title="Jobs added or lost each month (US nonfarm payrolls)",
        xaxis_title="Month",
        yaxis_title="Change in jobs (thousands)",
        legend={"orientation": "h", "y": -0.2},
        bargap=0.1,
        hovermode="x unified",
    )
    return figure


def revisions_chart(revisions, recessions=None) -> go.Figure:
    """First-reported vs revised payrolls, with the gap in a stacked chart below.

    Stacked rather than twin y-axes: two scales on one chart are easy to misread.
    """
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.08,
    )
    figure.add_scatter(
        x=revisions.index,
        y=revisions["first_reported"],
        mode="lines",
        line={"color": FIRST_REPORTED_COLOUR, "width": 2},
        name="First reported",
        hovertemplate="%{x|%b %Y} first reported: %{y:+,.0f}k<extra></extra>",
        row=1,
        col=1,
    )
    figure.add_scatter(
        x=revisions.index,
        y=revisions["revised"],
        mode="lines",
        line={"color": REVISED_COLOUR, "width": 2},
        name="Revised (latest)",
        hovertemplate="%{x|%b %Y} revised: %{y:+,.0f}k<extra></extra>",
        row=1,
        col=1,
    )
    figure.add_bar(
        x=revisions.index,
        y=revisions["revision"],
        marker_color=TREND_COLOUR,
        name="Revision (revised minus first)",
        hovertemplate="%{x|%b %Y} revision: %{y:+,.0f}k<extra></extra>",
        row=2,
        col=1,
    )
    add_recession_shading(figure, recessions)
    both_lines = revisions["revised"].combine_first(revisions["first_reported"])
    _cap_axis_if_needed(figure, both_lines, PAYROLL_AXIS_LIMIT, row=1, unit="k")

    # Short titles: a long one on the lower chart runs into the upper one.
    figure.update_yaxes(title_text="Jobs added (k)", row=1, col=1)
    figure.update_yaxes(title_text="Gap (k)", row=2, col=1)
    figure.update_xaxes(title_text="Month", row=2, col=1)
    figure.update_layout(
        title="Jobs numbers as first announced vs after revision",
        height=550,
        legend={"orientation": "h", "y": -0.2},
        hovermode="x unified",
    )
    return figure


def add_recession_shading(figure: go.Figure, recessions) -> None:
    """Grey band per recession (from scorecard.recessions_known_at, so time-machine safe).

    yref="paper" spans the whole figure, covering both stacked charts.
    """
    if recessions is None:
        return

    # Plotly widens the x-axis to fit every shape, so pin it to the data first
    # and skip bands outside it.
    first_date, last_date = _x_data_range(figure)
    if first_date is None:
        return
    figure.update_xaxes(range=[first_date, last_date])

    for row in recessions.itertuples():
        if row.end < first_date or row.start > last_date:
            continue
        figure.add_shape(
            type="rect",
            xref="x",
            yref="paper",
            x0=row.start,
            x1=row.end + pd.DateOffset(months=1),  # to the end of the last month
            y0=0,
            y1=1,
            fillcolor=RECESSION_FILL,
            line_width=0,
            layer="below",
        )


def _x_data_range(figure: go.Figure):
    """Earliest and latest date across all traces."""
    dates = [pd.Timestamp(x) for trace in figure.data if trace.x is not None for x in trace.x]
    if not dates:
        return None, None
    return min(dates), max(dates)


def _cap_axis_if_needed(
    figure, values, limit, row=None, decimals=0, unit="", signed=True
) -> None:
    """Cap the y-axis at +/-limit if needed and label the most extreme cut-off value.

    Each end is capped separately. One label per direction, since off-scale
    months cluster and labels would overlap. `signed` adds "+" to positive labels.
    """
    values = values.dropna()
    if values.empty or values.abs().max() <= limit:
        return

    low = max(values.min(), -limit)
    high = min(values.max(), limit)
    padding = 0.08 * (high - low)
    col = None if row is None else 1
    figure.update_yaxes(range=[low - padding, high + padding], row=row, col=col)

    # Labels in the right half point leftwards so they stay on the chart.
    first_date, last_date = _x_data_range(figure)
    midpoint = first_date + (last_date - first_date) / 2
    sign = "+" if signed else ""

    for extreme_date in [values.idxmax(), values.idxmin()]:
        value = values[extreme_date]
        if abs(value) <= limit:
            continue
        in_right_half = extreme_date > midpoint
        figure.add_annotation(
            x=extreme_date,
            y=high if value > 0 else low,
            text=f"{extreme_date:%b %Y}: {value:{sign},.{decimals}f}{unit} (cut off)",
            showarrow=False,
            xanchor="right" if in_right_half else "left",
            xshift=-8 if in_right_half else 8,
            font={"size": 11},
            row=row,
            col=col,
        )
