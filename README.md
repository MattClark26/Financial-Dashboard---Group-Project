# Financial Dashboard

## Start here: reproduce the project from a fresh clone

These instructions run the same graded Streamlit application on Windows,
macOS and Linux. The app is designed to start without API keys because the
required fallback datasets are committed to the repository.

### Before you begin

Install both of the following:

- [Git](https://git-scm.com/downloads)
- A 64-bit version of [Python](https://www.python.org/downloads/) from 3.11 to
  3.13. Python 3.13 is the recommended fresh installation.

Do not install the project packages globally. Create the `.venv` environment
shown below and run every command from the repository root. The final launch
command deliberately uses `python -m streamlit`, which guarantees that
Streamlit comes from the same environment as `pyjstat`, pandas and the other
project dependencies.

### Windows 10 or 11 using PowerShell

```powershell
git clone https://github.com/MattClark26/Financial-Dashboard---Group-Project.git
cd Financial-Dashboard---Group-Project
py -3.13 --version
py -3.13 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/check_setup.py
python -m streamlit run app.py
```

If Python 3.12 or 3.11 is already installed instead, replace `-3.13` in the
first two Python commands with `-3.12` or `-3.11`.

### macOS using Terminal

```bash
git clone https://github.com/MattClark26/Financial-Dashboard---Group-Project.git
cd Financial-Dashboard---Group-Project
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/check_setup.py
python -m streamlit run app.py
```

### Linux using a terminal

```bash
git clone https://github.com/MattClark26/Financial-Dashboard---Group-Project.git
cd Financial-Dashboard---Group-Project
python3 --version
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python scripts/check_setup.py
python -m streamlit run app.py
```

When setup succeeds, the checker prints `Setup check passed.` and Streamlit
prints a local address, normally `http://localhost:8501`. Open that address and
select **Enter the dashboard**. Keep the terminal open while using the app.
Stop it with `Ctrl+C`.

### Optional live-data setup

No key is needed to reproduce the interface, explore every panel or run the
tests. The default Financial Stress history is therefore clearly labelled
**SIMULATED PREVIEW**, while the other panels can use their committed cache
files if a provider is unavailable.

To refresh Financial Stress from FRED and the public market feed, obtain a free
[FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html), open
**Data connections & API keys** in the dashboard, and enter it for the current
session. Then open Financial Stress and select **Refresh live data**. The panel
changes to **LIVE PUBLIC DATA** only after a successful load. Yahoo Finance and
the CSO PxStat API do not need keys.

For a reusable local key, create the ignored secrets file after activating the
environment:

```powershell
# Windows PowerShell
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
```

```bash
# macOS or Linux
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Replace the placeholder in `.streamlit/secrets.toml` with the real key. Never
commit that file.

### If setup does not pass

| Problem | Exact fix |
| --- | --- |
| `ModuleNotFoundError`, including `No module named 'pyjstat'` | Activate `.venv`, run `python -m pip install -r requirements.txt`, then rerun `python scripts/check_setup.py`. |
| PowerShell says script execution is disabled | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate `.venv` again. This applies only to the current PowerShell window. |
| Linux says `ensurepip` or `venv` is unavailable | On Ubuntu or Debian run `sudo apt update && sudo apt install python3-venv`, then recreate `.venv`. |
| `python` or `py` is not recognised | Install Python 3.11 to 3.13 and enable **Add Python to PATH** on Windows, then open a new terminal. |
| `streamlit` is not recognised | Use the documented `python -m streamlit run app.py` command, not `streamlit run app.py`. |
| Port 8501 is already in use | Run `python -m streamlit run app.py --server.port 8502` and open `http://localhost:8502`. |
| A required CSV or interface file is missing | Run `git pull origin main`, then `python scripts/check_setup.py`. The checker identifies the missing file. |

To verify the complete codebase after setup, run:

```bash
python scripts/check_setup.py
python -m pytest -q
```

The setup checker validates the Python version, imports every direct runtime
dependency, checks the committed data and configuration files, reads every
cached CSV header and compiles the project packages before the dashboard is
launched.

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

Follow the operating-system instructions at the beginning of this README for a
fresh installation. The dependency versions in `requirements.txt` are pinned
for consistent marking and the dashboard runs from committed cache files when
live providers are unavailable.

The app opens with a short project briefing and then enters a full-screen 2 by 2
signal matrix. The Bond Market and Labour Market panels form the top row, while
Financial Stress and the Irish Lens form the bottom row. The Financial Stress
preview uses the interactive 3D Signal Lab terrain, and its full analysis places
the complete terrain and strategy diagnostics in a dedicated tab. Every panel
explains its purpose and provides a control to open the complete analysis. A
shared time machine controls the historical cutoff for every panel, while the
connected composite explicitly reports how many panels currently contribute to
its reading.

The **3D Signal Lab** belongs to the Financial Stress panel. Its
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
| Financial Stress signal, financial stress, market volatility, backtesting, dashboard design, time machine | Rohi Aluede |
| Bond Market analysis: yield curve, bond spreads, recession probability, credit spreads | Luke O'Brien Peterson |
| Labour Market analysis: Sahm rule, jobless claims, payrolls, data revisions, track record | Tadhg Findon |
| Irish Lens analysis: Irish economy, GDP vs domestic demand, Irish unemployment, US trade exposure | Matthias Clark |

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
