# Reproducibility protocol

This document defines the standard the finished dashboard must meet. Commands that depend on files not yet merged are marked as implementation targets until the application scaffold is present.

## Supported setup

- A supported Python version must be stated in the README and enforced by the project configuration.
- Direct and transitive dependencies must be reproducibly installable from a committed environment definition.
- Secrets must never be committed. A safe example configuration must document every optional credential.
- The application must remain demonstrable when a live provider is temporarily unavailable.

## Target clean-run procedure

From a fresh clone:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
python -m streamlit run app.py
```

Before these commands are advertised as working in the main README, they must be executed from a clean clone and recorded in the rubric evidence register.

## Data reproducibility

Every input series must have a registry entry containing:

- provider and human-readable series name;
- stable series identifier and source URL;
- observation frequency, units and expected date range;
- retrieval timestamp and any publication lag;
- transformation applied by the project;
- location and creation method of the fallback snapshot;
- usage or redistribution conditions where applicable.

Live downloads and committed fallback snapshots must pass through the same validation and transformation functions. The interface should visibly distinguish live data from fallback data and show the latest available observation.

Fallback data must be a documented snapshot, not an undocumented substitute. Updating it should be a deliberate, reviewable operation.

## Historical integrity

The selected as-of date is a hard data boundary. Calculations must not use observations, revised values or fitted parameters that would have been unavailable by that date.

At minimum, automated tests must verify:

- observations after the selected date are excluded;
- standardisation uses only the permitted historical window;
- drawdowns use peaks known by the selected date;
- recession-event classification follows a documented rule;
- empty, stale and partially missing series fail clearly or degrade gracefully.

Where vintage data are unavailable, the limitation must be disclosed rather than implying a real-time historical backtest.

## Verification record

Record each clean-run check here or link to its pull request.

| Date | Commit | Environment | Live/fallback mode | Tests | Dashboard start | Verified by |
| --- | --- | --- | --- | --- | --- | --- |
| Not yet run | — | — | — | — | — | — |
