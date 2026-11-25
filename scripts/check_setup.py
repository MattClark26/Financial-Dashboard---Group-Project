"""Verify that a fresh Recession Radar checkout is ready to run."""

from __future__ import annotations

import compileall
import csv
import importlib
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_MODULES = {
    "streamlit": "Streamlit",
    "pandas": "pandas",
    "numpy": "NumPy",
    "plotly": "Plotly",
    "matplotlib": "Matplotlib",
    "statsmodels": "statsmodels",
    "pyjstat": "pyjstat",
    "yfinance": "yfinance",
    "fredapi": "fredapi",
    "sklearn": "scikit-learn",
}

REQUIRED_FILES = (
    "app.py",
    "requirements.txt",
    ".streamlit/config.toml",
    "data/ICSA.csv",
    "data/PAYEMS.csv",
    "data/PAYEMS_vintages.csv",
    "data/SAHMREALTIME.csv",
    "data/T10Y2Y.csv",
    "data/T10Y3M.csv",
    "data/UNRATE.csv",
    "data/USREC.csv",
    "data/BAA10Y.csv",
    "data/irish_exports.csv",
    "data/irish_gdp.csv",
    "data/irish_mdd.csv",
    "data/irish_unemployment.csv",
    "data/us_recession_probability.csv",
    "baa_model_comparison_probabilities.csv",
    "compare_baa_website_models.py",
)


def main() -> int:
    errors: list[str] = []

    if sys.version_info < (3, 11):
        errors.append(
            f"Python 3.11 or newer is required; found {sys.version.split()[0]}."
        )

    for module_name, display_name in REQUIRED_MODULES.items():
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - failure is environment-specific
            errors.append(f"Cannot import {display_name}: {exc}")

    for relative_path in REQUIRED_FILES:
        path = ROOT / relative_path
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"Required file is missing or empty: {relative_path}")

    for csv_path in sorted((ROOT / "data").glob("*.csv")):
        try:
            with csv_path.open(newline="", encoding="utf-8-sig") as handle:
                header = next(csv.reader(handle), [])
            if not header:
                errors.append(f"Cached data has no columns: {csv_path.relative_to(ROOT)}")
        except Exception as exc:
            errors.append(f"Cannot read {csv_path.relative_to(ROOT)}: {exc}")

    for package in ("panels", "ui"):
        if not compileall.compile_dir(ROOT / package, quiet=1):
            errors.append(f"Python compilation failed in {package}/")

    if errors:
        print("Setup check failed:\n")
        for error in errors:
            print(f"  - {error}")
        print("\nActivate the project virtual environment and run:")
        print("  python -m pip install -r requirements.txt")
        return 1

    print("Setup check passed.")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Dependencies checked: {len(REQUIRED_MODULES)}")
    print(f"Required project files checked: {len(REQUIRED_FILES)}")
    print("Cached CSV files are readable and the project packages compile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
