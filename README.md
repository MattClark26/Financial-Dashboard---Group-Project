# Financial Dashboard 

| Name | Student Number |
| ---- | -------------- |
| Matthias Clark | 25370033|
| Tadhg Findon| 25316013|
| Rohi Aluede     | 25395156      |
|Luke O'Brien Peterson |25362871|
|    |           |

Overview

Recession Radar is an interactive Python dashboard that tracks the best-known early-warning signals of a US
recession and asks three questions most dashboards skip: is the alarm ringing, has this alarm been right before,
and what would a US downturn mean for Ireland?
Two features run across the whole dashboard:
• Time machine slider. One date control lets the user set the dashboard to any past date (for example,
December 2007 or January 2020). Every panel then shows only data available up to that date.
• Recession Thermometer. Each panel returns a standard output: a score, a green/amber/red status and a
one-sentence verdict. These are combined into a single composite reading at the top of the dashboard, and
the user can adjust how much weight each signal gets.
Each panel also scores its own indicators on how many recessions they caught, how many false alarms they
gave, and how many months of warning they provided.

Panel 1 – The Bond Market Signal (Yield Curve) – [Luke O'Brien Peterson]
Plots the 10-year minus 3-month and 10-year minus 2-year Treasury spreads from FRED, with US recessions
shaded. The code detects inversion episodes and measures the lead time from each inversion to the next
recession. A probit model built with statsmodels estimates the probability of a recession within 12 months. The
user can switch between the two spread definitions to compare their track records.
Panel 2 – The Labour Market Signal – [Student 2]
Calculates the Sahm rule from the US unemployment rate and checks the result against FRED's official series.
Also shows initial jobless claims and monthly payroll changes. Using archived data releases from ALFRED, the
panel compares first-published payroll figures with today's revised figures, showing how much the picture
changed after the fact.
Panel 3 – The Financial Stress Signal – [Rohi Aluede]
Tracks corporate credit spreads, the VIX, the St. Louis Fed Financial Stress Index and S&P 500 drawdowns from
peak. Each series is converted to a z-score so they can be compared on one chart. The panel then tests whether
market stress spikes have preceded recessions or were false alarms.
Panel 4 – The Irish Lens – [Matthias Clark]
Uses the CSO PxStat API to compare Irish GDP with Modified Domestic Demand, and explains why multinational
activity makes headline GDP misleading. Applies the Sahm rule function from Panel 2 to Irish unemployment,
shows the US share of Irish goods exports, and overlays the Panel 1 US recession probability on Irish data.

## Repository structure

The dashboard will have one Streamlit entry point and one Python package per panel. This lets each of us work on our own panel while keeping the date slider, layout and Recession Thermometer in one place.

| Path | What goes there |
| --- | --- |
| `app.py` | Streamlit entry point, dashboard layout, time-machine slider and Recession Thermometer |
| `panels/bond_market/` | Panel 1 · Yield curves and US recession probability |
| `panels/labour_market/` | Panel 2 · Sahm rule, jobless claims and payrolls |
| `panels/financial_stress/` | Panel 3 · Credit spreads, VIX, the Fed stress index and S&P 500 drawdowns |
| `panels/irish_lens/` | Panel 4 · Irish economic indicators and exposure to a US downturn |
| `data/` | Cached CSVs for when an API is unavailable |
| `requirements.txt` | Python dependencies for running and deploying the dashboard |

### Working on a panel

1. Once the scaffold is on `main`, pull the latest changes and create a branch for your panel, for example `panel-3-financial-stress`.
2. Build and test your panel in its own module. Coordinate any changes to `app.py` or shared dependencies with the group.
3. Open a pull request into `main` and include a short note on what changed and how you tested it.

Before building the panels, agree on the score scale and how each module will receive the selected date and return a score, a green/amber/red status and a one-sentence verdict. Keep the recession probability and Sahm rule calculations callable so the Irish Lens can reuse them.

Data Sources

FRED and ALFRED (Federal Reserve Bank of St. Louis), Yahoo Finance via yfinance, and the Central
Statistics Office (CSO) PxStat API. Cached CSV copies of all series will be stored in the repository so the
dashboard still runs if an API is unavailable.

Tools and Deployment
Python with Pandas, NumPy, Matplotlib/Plotly, statsmodels and Streamlit. Code is hosted on GitHub and the
dashboard is deployed on Hugging Face Spaces, with the FRED API key stored as a Space secret.

## Running the interface

Use Python 3.11 or newer:

```sh
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens with a short project briefing and then enters a full-screen
four-quadrant workspace. A shared time machine controls the historical cutoff
for every panel, while the connected composite explicitly reports how many
panels currently contribute to its reading.

Panel 3 is connected to the Financial Stress analytical pipeline and can expand
into a complete overview, methodology and source-access page. Its default
interface history is deterministically simulated and labelled as such so the
layout remains reproducible offline. A user can request a live refresh from the
expanded panel; public data degrades to runtime cache and then back to the
labelled preview if a provider is unavailable.

Panels 1, 2 and 4 intentionally remain presentation placeholders in the shared
workspace. Their existing code is not deleted or represented as Rohi's work;
their owners can connect each module to the same date and signal contract.

### Panel folders

| Pane | Folder |
| --- | --- |
| Top left | `panels/bond_market/` |
| Top right | `panels/labour_market/` |
| Bottom left | `panels/financial_stress/` |
| Bottom right | `panels/irish_lens/` |

Each folder exports `TITLE` and `render(as_of: datetime.date)` from
`__init__.py`. Add Streamlit controls and charts there, and keep supporting
files within the same folder. Prefix widget keys with the panel name to avoid
collisions. Once a panel is ready, connect it in `app.py` and pass its standard
0–100 score into `render_composite`.

### Interface ownership

| Shared or panel area | Current contribution |
| --- | --- |
| Intro, cursor, time machine and four-panel layout | Rohi Aluede |
| Financial Stress data, transformations, score and views | Rohi Aluede |
| Bond Market analysis | Reserved for Luke O'Brien Peterson |
| Labour Market analysis | Reserved for Tadhg Findon |
| Irish Lens analysis | Reserved for Matthias Clark |

Run the complete automated suite before pushing:

```sh
pytest -q
```

Keep changes to the shared shell and dependencies coordinated with the group. Future data integrations must respect release availability at the selected date. Agree the scoring contract before implementing the Recession Thermometer. Store API keys in deployment secrets.
