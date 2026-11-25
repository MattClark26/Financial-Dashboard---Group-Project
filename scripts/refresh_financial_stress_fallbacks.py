"""Refresh committed Financial Stress fallbacks from the documented public sources."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from panels.financial_stress.data import (
    DEFAULT_FALLBACK_DIR,
    SERIES_SPECS,
    _write_cache,
    fetch_fred_series,
    fetch_yahoo_series,
)


def main() -> None:
    cutoff = pd.Timestamp.today().normalize()
    output = Path(DEFAULT_FALLBACK_DIR)
    output.mkdir(parents=True, exist_ok=True)

    failures = []
    for key in ("ig_oas", "hy_oas", "vix", "stlfsi", "sp500", "us_recession"):
        spec = SERIES_SPECS[key]
        try:
            if spec.provider == "fred":
                values = fetch_fred_series(spec, cutoff, timeout=180)
            else:
                values = fetch_yahoo_series(spec, cutoff)
        except Exception as error:
            failures.append(f"{key}: {error}")
            print(f"{key}: FAILED ({error})")
            continue
        path = output / f"{key}.csv"
        _write_cache(values, path)
        print(f"{key}: {len(values):,} observations -> {path}")

    if failures:
        raise SystemExit("Fallback refresh incomplete:\n" + "\n".join(failures))


if __name__ == "__main__":
    main()
