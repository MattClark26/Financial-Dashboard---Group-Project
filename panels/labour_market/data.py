"""Panel 2 data layer: fetch FRED series, keep a CSV backup, and apply the time machine.

Every download is saved to data/panel2/<series>.csv (committed to Git), so the
panel still draws if FRED is down or the key is missing. No Streamlit import:
caching lives in panel.py so this module works in plain Python and pytest.
"""

import logging
import os
from pathlib import Path

import pandas as pd

# Optional: locally, .env supplies FRED_API_KEY; on Hugging Face it's a Space secret.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# Anchored to this file, not the working directory, which differs per launcher.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = PROJECT_ROOT / "data"

# Days between an observation's date stamp and its release. Monthly series are
# dated the 1st but published early next month; weekly claims 5 days after the
# week ends. USREC is excluded: NBER dates are handled in the scorecard.
RELEASE_LAG_DAYS = {
    "UNRATE": 38,
    "SAHMREALTIME": 38,
    "PAYEMS": 38,
    "ICSA": 5,
}

# FRED silently truncates at 100k rows, so vintages are fetched in 5-year chunks.
FRED_MAX_ROWS = 100_000
VINTAGE_CHUNK_YEARS = 5

# Jobs reports are 4-5 weeks apart, so a cache whose newest vintage is under
# 28 days old can't be stale. Based on the data, not file timestamps (reset on deploy).
VINTAGE_REFRESH_DAYS = 28


def load_series(series_id: str) -> pd.Series:
    """Return a FRED series (sorted DatetimeIndex), falling back to the CSV on any failure.

    attrs["source"] is "api" or "cache". Raises FileNotFoundError only if the
    API fails and no CSV exists.
    """
    try:
        series = _standardise(_download_from_fred(series_id), series_id)
    except Exception as error:  # deliberately broad: every failure means "use the cache"
        logger.warning(
            "FRED download for %s failed (%s). Falling back to the cached CSV.",
            series_id,
            _hide_api_key(error),
        )
        series = _read_cache(series_id)
        series.attrs["source"] = "cache"
        return series

    # A failed backup write shouldn't throw away good data.
    try:
        _write_cache(series, series_id)
    except OSError as error:
        logger.warning("Could not write cache for %s: %s", series_id, error)

    series.attrs["source"] = "api"
    return series


def filter_as_of(series: pd.Series, as_of, release_lag_days: int = 0) -> pd.Series:
    """Keep only observations published by `as_of` (dated on or before as_of - lag).

    The core of the time machine. Pass RELEASE_LAG_DAYS[series_id] as the lag.
    """
    cutoff = pd.Timestamp(as_of) - pd.Timedelta(days=release_lag_days)
    return series[series.index <= cutoff]


def load_vintages(series_id: str) -> pd.DataFrame:
    """Every published version of a series from ALFRED: realtime_start, date, value.

    Checks the cache first (see VINTAGE_REFRESH_DAYS); falls back to it if the API fails.
    """
    cache_path = CACHE_DIR / f"{series_id}_vintages.csv"

    if cache_path.exists():
        cached = _read_vintage_cache(cache_path)
        newest_release = cached["realtime_start"].max()
        if pd.Timestamp.today() - newest_release < pd.Timedelta(days=VINTAGE_REFRESH_DAYS):
            cached.attrs["source"] = "cache"
            return cached

    try:
        vintages = _download_vintages(series_id)
    except Exception as error:
        logger.warning(
            "ALFRED download for %s failed (%s). Falling back to the cached CSV.",
            series_id,
            _hide_api_key(error),
        )
        if not cache_path.exists():
            raise FileNotFoundError(
                f"The ALFRED download failed and there is no cached file at {cache_path}."
            ) from error
        cached = _read_vintage_cache(cache_path)
        cached.attrs["source"] = "cache"
        return cached

    try:
        _write_csv_safely(vintages, cache_path, include_index=False)
    except OSError as error:
        logger.warning("Could not write vintage cache for %s: %s", series_id, error)

    vintages.attrs["source"] = "api"
    return vintages


# --- Private helpers ---


def _fred_client():
    """A FRED client using FRED_API_KEY from the environment."""
    from fredapi import Fred

    api_key = os.environ.get("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY environment variable is not set")
    return Fred(api_key=api_key)


def _download_from_fred(series_id: str) -> pd.Series:
    """Fetch one series. Empty results raise, so they can't overwrite a good CSV."""
    series = _fred_client().get_series(series_id)
    if series.dropna().empty:
        raise ValueError(f"FRED returned no data for {series_id}")
    return series


def _standardise(series: pd.Series, series_id: str) -> pd.Series:
    """Sorted DatetimeIndex named "date", float values, no NaNs, named series_id."""
    series = series.dropna().astype(float).sort_index()
    series.index = pd.to_datetime(series.index)
    series.index.name = "date"
    series.name = series_id
    return series


def _cache_path(series_id: str) -> Path:
    return CACHE_DIR / f"{series_id}.csv"


def _write_cache(series: pd.Series, series_id: str) -> None:
    _write_csv_safely(series, _cache_path(series_id), include_index=True)


def _write_csv_safely(table, final_path: Path, include_index: bool) -> None:
    """Write to a temp file then rename, so a crash never leaves a half-written CSV."""
    final_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = final_path.with_name(final_path.name + ".tmp")
    table.to_csv(temp_path, index=include_index, header=True)
    temp_path.replace(final_path)


def _read_cache(series_id: str) -> pd.Series:
    path = _cache_path(series_id)
    if not path.exists():
        raise FileNotFoundError(
            f"The FRED API failed and there is no cached file at {path}. "
            "Run once with FRED_API_KEY set to create the cache."
        )
    table = pd.read_csv(path, index_col="date", parse_dates=["date"])
    return _standardise(table[series_id], series_id)


def _download_vintages(series_id: str) -> pd.DataFrame:
    """Download full revision history in release-date chunks.

    Raises if a chunk hits FRED_MAX_ROWS (possibly truncated) rather than cache
    incomplete data. Values repeated at a window's start are deduplicated.
    """
    fred = _fred_client()

    chunks = []
    for window_start, window_end in _release_windows():
        chunk = fred.get_series_all_releases(
            series_id, realtime_start=window_start, realtime_end=window_end
        )
        if len(chunk) >= FRED_MAX_ROWS:
            raise ValueError(
                f"ALFRED chunk {window_start} to {window_end} hit the "
                f"{FRED_MAX_ROWS:,}-row limit and may be incomplete"
            )
        chunks.append(chunk)

    vintages = _standardise_vintages(pd.concat(chunks, ignore_index=True))
    if vintages.empty:
        raise ValueError(f"ALFRED returned no vintages for {series_id}")
    return vintages


def _release_windows() -> list:
    """(start, end) text dates: FRED's earliest date to 1964, then 5-year steps to 9999."""
    windows = []
    start = "1776-07-04"
    for year in range(1965, pd.Timestamp.today().year + 1, VINTAGE_CHUNK_YEARS):
        end = f"{year - 1}-12-31"
        windows.append((start, end))
        start = f"{year}-01-01"
    windows.append((start, "9999-12-31"))
    return windows


def _standardise_vintages(table: pd.DataFrame) -> pd.DataFrame:
    """Datetime/float columns, no NaNs or duplicates, sorted by date then release."""
    table = table[["realtime_start", "date", "value"]].copy()
    table["realtime_start"] = pd.to_datetime(table["realtime_start"])
    table["date"] = pd.to_datetime(table["date"])
    table["value"] = pd.to_numeric(table["value"], errors="coerce")
    table = table.dropna().drop_duplicates(subset=["realtime_start", "date"])
    return table.sort_values(["date", "realtime_start"]).reset_index(drop=True)


def _read_vintage_cache(path: Path) -> pd.DataFrame:
    return _standardise_vintages(pd.read_csv(path))


def _hide_api_key(error: Exception) -> str:
    """Blank out the API key in error messages (Hugging Face logs are public)."""
    message = str(error)
    api_key = os.environ.get("FRED_API_KEY")
    if api_key:
        message = message.replace(api_key, "***")
    return message
