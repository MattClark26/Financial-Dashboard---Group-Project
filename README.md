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
Panel 2 – The Labour Market Signal – [Tadhg Findon]
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
| `scripts/check_setup.py` | Fresh-checkout dependency, data and file verifier |
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
dashboard can be deployed with the FRED API key stored in the host's secret manager.

## Running the interface

### Reliable setup from a fresh clone

Use Python 3.11 or newer and run every command from the repository root. The
commands below install every required package, verify that committed data and
interface files are present, and then launch the graded Streamlit application.
The direct package versions in `requirements.txt` are the versions verified by
the clean-checkout procedure below, which prevents installations from changing
unexpectedly between group members.

```sh
git clone https://github.com/MattClark26/Financial-Dashboard---Group-Project.git
cd Financial-Dashboard---Group-Project
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/check_setup.py
python -m streamlit run app.py
```

On Windows PowerShell, activate the environment with
`.venv\Scripts\Activate.ps1`, then run the same `python -m pip`, setup-check and
Streamlit commands. Using `python -m streamlit` ensures Streamlit runs from the
same Python environment where the dependencies were installed.

The dashboard runs from committed cache files without credentials. To refresh
FRED and ALFRED data, open **Data connections & API keys** in the interface and
paste a free FRED key for the current session. The key is masked, held only in
process memory and never written to Git. For local or hosted configuration,
copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and replace
the placeholder; the real file is ignored by Git. Yahoo Finance and the CSO
PxStat API do not require keys.

The app opens with a short project briefing and then enters a full-screen signal
matrix. The Bond Market and Labour Market panels form the top corners, Financial
Stress and the Irish Lens form the bottom corners, and the compact 3D Signal Lab
sits at the centre. Every area explains its purpose and provides a control to
open the complete analysis. A shared time machine controls the historical cutoff
for every panel, while the connected composite explicitly reports how many
panels currently contribute to its reading.

The shared **3D Signal Lab** adds a deeper layer at the centre of the four panels. Its
interactive surface shows the five Financial Stress channels together across
time, with recession weeks coloured separately so broad stress peaks are easy
to distinguish from isolated moves. The strategy view compares buy-and-hold,
a continuously stress-scaled exposure and a CALM/WATCH/ALERT exposure rule.
All strategy decisions use the previous week's signal to avoid look-ahead bias;
the table reports annual return, volatility, a 0%-cash Sharpe ratio, maximum
drawdown and average exposure. A phase view then separates expansion,
pre-recession, recession and recovery observations instead of hiding them in a
single full-sample average. These outputs are historical diagnostics, not
investment advice or forecasts.

### Troubleshooting

- If Python reports `ModuleNotFoundError`, activate `.venv` and rerun
  `python -m pip install -r requirements.txt`.
- If the `streamlit` command is not found, use
  `python -m streamlit run app.py` from the repository root.
- If a chart or cached series is missing, run `git pull origin main` followed by
  `python scripts/check_setup.py`. The checker names the exact missing file.
- If port 8501 is already in use, run
  `python -m streamlit run app.py --server.port 8502`.
- A FRED key is optional for the default offline experience. Add one through
  **Data connections & API keys** only when a live refresh is required.

All four panels are connected to the shared date and composite contract. Panel
2 includes the Sahm rule, claims, payrolls, ALFRED revisions and historical
track record. Panel 4 includes GDP/MDD, Irish Sahm, US export exposure and the
shared US recession probability.

Panel 3 is connected to the Financial Stress analytical pipeline and can expand
into a complete overview, interactive backtest, weighting-sensitivity analysis,
methodology and source-access page. Its default
interface history is deterministically simulated and labelled as such so the
layout remains reproducible offline. A user can request a live refresh from the
expanded panel; public data degrades to runtime cache and then back to the
labelled preview if a provider is unavailable.

The panel aligns observations to completed Friday weeks, calculates causal
156-week z-scores and combines five market channels into a documented weighted
0–100 score. The backtest control lets a user change the alert threshold and
immediately inspect recessions caught, false alarms, precision and median warning
time. The Sources tab reports data coverage and lag, links every public series,
and exports the full dated evidence table as CSV for independent checking.

Panel 4 provides Irish GDP/MDD, unemployment, US-export exposure and US
recession-probability views. Its probability input is linked to Panel 1's
shared calculations, and its track record is evaluated against contractions
in Modified Domestic Demand.

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
| Shared 3D Signal Lab, strategy diagnostics and responsive containment | Rohi Aluede |
| Financial Stress data, transformations, score and views | Rohi Aluede |
| Bond Market analysis | Luke O'Brien Peterson |
| Labour Market analysis | Tadhg Findon |
| Irish Lens analysis | Matthias Clark |

Run the complete automated suite before pushing:

```sh
python scripts/check_setup.py
python -m pytest -q
```

The Financial Stress tests separately cover public-source parsing and fallback,
as-of-date enforcement, causal transformations, bounded scoring, recession and
alert episode detection, false-alarm evaluation, provenance diagnostics and the
offline presentation state. No API key is required for the labelled preview or
for the test suite.

Maintainers can refresh the committed Financial Stress fallback snapshots from
the documented public endpoints with:

```sh
PYTHONPATH=. python scripts/refresh_financial_stress_fallbacks.py
```

Keep changes to the shared shell and dependencies coordinated with the group. Future data integrations must respect release availability at the selected date. Agree the scoring contract before implementing the Recession Thermometer. Store API keys in deployment secrets.
