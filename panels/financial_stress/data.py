"""Resilient source access for the Financial Stress panel."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from io import BytesIO
import os
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

from .models import FinancialStressDataset, SeriesData, SeriesSpec, SourceMode

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / "data" / "cache" / "financial_stress"
DEFAULT_FALLBACK_DIR = PROJECT_ROOT / "data" / "fallback" / "financial_stress"
FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={identifier}"


class DataAccessError(RuntimeError):
    """Raised when a series is unavailable live and from local storage."""


SERIES_SPECS: Mapping[str, SeriesSpec] = {
    "ig_oas": SeriesSpec(
        key="ig_oas",
        label="US Corporate Option-Adjusted Spread",
        provider="fred",
        identifier="BAMLC0A0CM",
        frequency="Daily",
        units="Percent",
        source_url="https://fred.stlouisfed.org/series/BAMLC0A0CM",
        description="Investment-grade US corporate bond option-adjusted spread.",
    ),
    "hy_oas": SeriesSpec(
        key="hy_oas",
        label="US High Yield Option-Adjusted Spread",
        provider="fred",
        identifier="BAMLH0A0HYM2",
        frequency="Daily",
        units="Percent",
        source_url="https://fred.stlouisfed.org/series/BAMLH0A0HYM2",
        description="US high-yield corporate bond option-adjusted spread.",
    ),
    "vix": SeriesSpec(
        key="vix",
        label="CBOE Volatility Index",
        provider="fred",
        identifier="VIXCLS",
        frequency="Daily",
        units="Index",
        source_url="https://fred.stlouisfed.org/series/VIXCLS",
        description="Expected near-term US equity-market volatility.",
    ),
    "stlfsi": SeriesSpec(
        key="stlfsi",
        label="St. Louis Fed Financial Stress Index",
        provider="fred",
        identifier="STLFSI4",
        frequency="Weekly",
        units="Standard deviations",
        source_url="https://fred.stlouisfed.org/series/STLFSI4",
        description="Composite weekly measure of US financial-market stress.",
    ),
    "sp500": SeriesSpec(
        key="sp500",
        label="S&P 500",
        provider="yahoo",
        identifier="^GSPC",
        frequency="Daily",
        units="Index",
        source_url="https://finance.yahoo.com/quote/%5EGSPC/history/",
        description="Adjusted S&P 500 closing level used to calculate drawdowns.",
    ),
    "us_recession": SeriesSpec(
        key="us_recession",
        label="NBER-based US Recession Indicator",
        provider="fred",
        identifier="USREC",
        frequency="Monthly",
        units="Binary indicator",
        source_url="https://fred.stlouisfed.org/series/USREC",
        description="Monthly NBER recession indicator distributed by FRED.",
    ),
}

PANEL_SERIES_KEYS = ("ig_oas", "hy_oas", "vix", "stlfsi", "sp500")


def _download_bytes(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "RecessionRadar/1.0"})
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def _cut_off(values: pd.Series, as_of: pd.Timestamp) -> pd.Series:
    cutoff = pd.Timestamp(as_of).normalize()
    index = pd.DatetimeIndex(pd.to_datetime(values.index))
    if index.tz is not None:
        index = index.tz_convert(None)
    values = values.copy()
    values.index = index
    return values[values.index <= cutoff]


def fetch_fred_series(
    spec: SeriesSpec,
    as_of: pd.Timestamp,
    *,
    timeout: float = 45,
    http_get: Callable[[str, float], bytes] = _download_bytes,
) -> pd.Series:
    """Download one public FRED CSV series without requiring an API key."""
    if spec.provider != "fred":
        raise ValueError(f"{spec.key} is not a FRED series.")

    api_key = os.environ.get("FRED_API_KEY", "").strip()
    api_failure: Exception | None = None
    if api_key and http_get is _download_bytes:
        try:
            from fredapi import Fred

            client = Fred(api_key=api_key)
            api_values = client.get_series(
                spec.identifier,
                observation_end=pd.Timestamp(as_of).date().isoformat(),
            )
            api_values = pd.to_numeric(api_values, errors="coerce").dropna()
            api_values.name = spec.key
            api_values = _cut_off(api_values, pd.Timestamp(as_of))
            if not api_values.empty:
                return api_values
        except Exception as error:
            api_failure = error

    url = FRED_CSV_URL.format(identifier=spec.identifier)
    try:
        payload = http_get(url, timeout)
        frame = pd.read_csv(BytesIO(payload), na_values=".")
    except Exception as error:
        api_detail = f"; keyed API failed: {api_failure}" if api_failure else ""
        raise DataAccessError(
            f"FRED download failed for {spec.identifier}: {error}{api_detail}"
        ) from error

    if frame.shape[1] < 2:
        raise DataAccessError(f"FRED returned no value column for {spec.identifier}.")
    date_column = frame.columns[0]
    value_column = spec.identifier if spec.identifier in frame.columns else frame.columns[1]
    dates = pd.to_datetime(frame[date_column], errors="coerce")
    values = pd.to_numeric(frame[value_column], errors="coerce")
    series = pd.Series(values.to_numpy(), index=dates, name=spec.key).dropna()
    series = series[~series.index.isna()]
    series = _cut_off(series, pd.Timestamp(as_of))
    if series.empty:
        raise DataAccessError(f"FRED returned no {spec.identifier} observations by {as_of}.")
    return series


def _select_yahoo_close(frame: pd.DataFrame, identifier: str) -> pd.Series:
    if frame.empty:
        raise DataAccessError(f"Yahoo Finance returned no observations for {identifier}.")

    if isinstance(frame.columns, pd.MultiIndex):
        for field in ("Close", "Adj Close"):
            candidate = (field, identifier)
            if candidate in frame.columns:
                return frame[candidate]
        for field in ("Close", "Adj Close"):
            matches = [column for column in frame.columns if column[0] == field]
            if len(matches) == 1:
                return frame[matches[0]]
    else:
        for field in ("Close", "Adj Close"):
            if field in frame.columns:
                return frame[field]
    raise DataAccessError(f"Yahoo Finance returned no close column for {identifier}.")


def fetch_yahoo_series(
    spec: SeriesSpec,
    as_of: pd.Timestamp,
    *,
    downloader: Callable[..., pd.DataFrame] | None = None,
) -> pd.Series:
    """Download adjusted market history through yfinance."""
    if spec.provider != "yahoo":
        raise ValueError(f"{spec.key} is not a Yahoo Finance series.")
    if downloader is None:
        try:
            import yfinance as yf
        except ImportError as error:
            raise DataAccessError("yfinance is required for Yahoo market data.") from error
        downloader = yf.download

    cutoff = pd.Timestamp(as_of).normalize()
    try:
        frame = downloader(
            spec.identifier,
            start="1990-01-01",
            end=(cutoff + pd.Timedelta(days=1)).date().isoformat(),
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as error:
        raise DataAccessError(f"Yahoo download failed for {spec.identifier}: {error}") from error

    values = pd.to_numeric(_select_yahoo_close(frame, spec.identifier), errors="coerce")
    values.name = spec.key
    values = _cut_off(values.dropna(), cutoff)
    if values.empty:
        raise DataAccessError(f"Yahoo returned no {spec.identifier} observations by {as_of}.")
    return values


def _cache_path(directory: Path, spec: SeriesSpec) -> Path:
    return Path(directory) / f"{spec.key}.csv"


def _write_cache(values: pd.Series, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    values.rename("value").to_frame().rename_axis("date").to_csv(temporary)
    temporary.replace(path)


def _read_cache(path: Path) -> pd.Series:
    frame = pd.read_csv(path)
    if not {"date", "value"}.issubset(frame.columns):
        raise DataAccessError(f"Cache {path} must contain date and value columns.")
    dates = pd.to_datetime(frame["date"], errors="coerce")
    values = pd.to_numeric(frame["value"], errors="coerce")
    return pd.Series(values.to_numpy(), index=dates).dropna()


def _default_fetchers() -> Mapping[str, Callable[[SeriesSpec, pd.Timestamp], pd.Series]]:
    return {"fred": fetch_fred_series, "yahoo": fetch_yahoo_series}


def load_series(
    spec: SeriesSpec,
    as_of: pd.Timestamp,
    *,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    fallback_dir: Path = DEFAULT_FALLBACK_DIR,
    allow_live: bool = True,
    fetchers: Mapping[str, Callable[[SeriesSpec, pd.Timestamp], pd.Series]] | None = None,
) -> SeriesData:
    """Load a series live, then degrade to runtime cache and committed fallback."""
    cutoff = pd.Timestamp(as_of).normalize()
    cache_path = _cache_path(Path(cache_dir), spec)
    failures: list[str] = []

    if allow_live:
        loader = (fetchers or _default_fetchers()).get(spec.provider)
        if loader is None:
            failures.append(f"no loader registered for {spec.provider}")
        else:
            try:
                values = _cut_off(loader(spec, cutoff), cutoff)
                result = SeriesData(
                    spec=spec,
                    values=values,
                    retrieved_at=pd.Timestamp.now(tz="UTC"),
                    mode=SourceMode.LIVE,
                    cache_path=cache_path,
                )
                _write_cache(result.values, cache_path)
                return result
            except Exception as error:
                failures.append(f"live: {error}")

    local_candidates = (
        (SourceMode.CACHE, cache_path),
        (SourceMode.FALLBACK, _cache_path(Path(fallback_dir), spec)),
    )
    for mode, path in local_candidates:
        if not path.exists():
            continue
        try:
            values = _cut_off(_read_cache(path), cutoff)
            retrieved_at = pd.Timestamp.fromtimestamp(path.stat().st_mtime, tz="UTC")
            return SeriesData(
                spec=spec,
                values=values,
                retrieved_at=retrieved_at,
                mode=mode,
                cache_path=path,
            )
        except Exception as error:
            failures.append(f"{mode.value}: {error}")

    detail = "; ".join(failures) if failures else "no local file exists"
    raise DataAccessError(f"Unable to load {spec.key} by {cutoff.date()}: {detail}.")


def load_financial_stress_data(
    as_of: pd.Timestamp,
    *,
    keys: Iterable[str] = PANEL_SERIES_KEYS,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    fallback_dir: Path = DEFAULT_FALLBACK_DIR,
    allow_live: bool = True,
    fetchers: Mapping[str, Callable[[SeriesSpec, pd.Timestamp], pd.Series]] | None = None,
) -> FinancialStressDataset:
    """Load the requested panel inputs with one consistent as-of boundary."""
    cutoff = pd.Timestamp(as_of).normalize()
    loaded: dict[str, SeriesData] = {}
    for key in keys:
        try:
            spec = SERIES_SPECS[key]
        except KeyError as error:
            raise KeyError(f"Unknown Financial Stress series: {key}.") from error
        loaded[key] = load_series(
            spec,
            cutoff,
            cache_dir=cache_dir,
            fallback_dir=fallback_dir,
            allow_live=allow_live,
            fetchers=fetchers,
        )
    return FinancialStressDataset(as_of=cutoff, series=loaded)
