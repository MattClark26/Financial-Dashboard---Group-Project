"""Compare the Bond Market dashboard's three models using the project's actual CSVs.

Put this script in the project root, beside app.py, then run:
    python compare_baa_website_models.py

Required data/: T10Y3M.csv, USREC.csv, BAA10Y.csv
"""
from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import brier_score_loss, roc_auc_score, log_loss

DATA = Path(__file__).resolve().parent / "data"
MODELS = {
    "Baseline": ["T10Y3M"],
    "Weighted inversion": ["T10Y3M", "weighted_inversion"],
    "Baa credit spreads": ["T10Y3M", "weighted_inversion", "credit_spread"],
}


def load(name):
    filename = DATA / f"{name}.csv"
    if not filename.exists():
        raise FileNotFoundError(f"Missing {filename}. Save {name}.csv in the data folder.")
    frame = pd.read_csv(filename, index_col=0, parse_dates=True, na_values=".")
    if name not in frame.columns:
        raise ValueError(f"{filename.name} must contain a column named {name}.")
    frame.index = pd.to_datetime(frame.index)
    frame = frame.sort_index()
    return pd.to_numeric(frame[name], errors="coerce")


def make_data():
    spread = load("T10Y3M").resample("ME").mean()
    recession = load("USREC").resample("ME").last()
    baa = load("BAA10Y").resample("ME").mean()

    # Match the dashboard's data preparation exactly.
    spread.name, recession.name = "T10Y3M", "USREC"
    frame = spread.to_frame().join(recession).dropna()
    frame["recession_12m"] = frame["USREC"].shift(-12)
    weights = list(range(1, 25))
    inversion_depth = -spread.clip(upper=0)
    frame["weighted_inversion"] = inversion_depth.rolling(24, min_periods=24).apply(
        lambda values: sum(values * weights) / sum(weights), raw=True
    )
    frame["credit_spread"] = baa.reindex(spread.index)
    return frame


def fit(train, columns):
    X = sm.add_constant(train[columns].astype(float), has_constant="add")
    return sm.Probit(train["recession_12m"].astype(int), X).fit(disp=False, maxiter=300)


def score(outcomes, probabilities):
    outcomes = outcomes.astype(int)
    p = np.clip(np.asarray(probabilities, dtype=float), 1e-9, 1 - 1e-9)
    return {
        "Brier (lower better)": round(brier_score_loss(outcomes, p), 5),
        "AUC (higher better)": round(roc_auc_score(outcomes, p), 5),
        "Log loss (lower better)": round(log_loss(outcomes, p), 5),
    }


def main():
    frame = make_data()
    common = frame.dropna(subset=["recession_12m"] + MODELS["Baa credit spreads"]).copy()
    if common.empty or common["recession_12m"].nunique() < 2:
        raise ValueError("Not enough overlapping observations containing both outcomes.")
    print(f"Common months: {len(common)}, {common.index.min():%b %Y} to {common.index.max():%b %Y}")
    print(f"Recession-positive months: {int(common['recession_12m'].sum())}")

    # Fit as the website does, then evaluate all three on the same months.
    website_scores = []
    website_probabilities = pd.DataFrame(index=common.index)
    website_probabilities["Actual recession 12 months later"] = common["recession_12m"].astype(int)
    for name, columns in MODELS.items():
        train = frame.dropna(subset=["recession_12m"] + columns)
        model = fit(train, columns)
        X = sm.add_constant(common[columns].astype(float), has_constant="add")
        probabilities = model.predict(X)
        website_probabilities[name + " probability (%)"] = (probabilities * 100).round(2)
        website_scores.append({"Model": name, "Training months": len(train), **score(common["recession_12m"], probabilities)})
        print("\n" + name + " website coefficients:")
        print(model.params.round(4).to_string())
    print("\nWEBSITE-STYLE RESULTS: common evaluation months")
    print(pd.DataFrame(website_scores).to_string(index=False))

    # Fit all three on exactly the same months as a separate fair-fitting comparison.
    same_sample_scores = []
    for name, columns in MODELS.items():
        model = fit(common, columns)
        p = model.predict(sm.add_constant(common[columns].astype(float), has_constant="add"))
        same_sample_scores.append({"Model": name, **score(common["recession_12m"], p)})
    print("\nSAME TRAINING MONTHS (1986 onward, typically)")
    print(pd.DataFrame(same_sample_scores).to_string(index=False))

    # Chronological annual re-fitting: outcomes must be known before each test year.
    backtest = []
    for name, columns in MODELS.items():
        data = frame.dropna(subset=["recession_12m"] + columns)
        predictions = []
        for year in range(2005, 2026):
            start = pd.Timestamp(year, 1, 1)
            train = data.loc[data.index <= start - pd.DateOffset(months=13)]
            test = data.loc[(data.index >= start) & (data.index < start + pd.DateOffset(years=1))]
            if len(train) < 60 or train["recession_12m"].nunique() != 2 or test.empty:
                continue
            try:
                model = fit(train, columns)
                X_test = sm.add_constant(test[columns].astype(float), has_constant="add")
                probabilities = model.predict(X_test)
                predictions.append(pd.DataFrame({"actual": test["recession_12m"], "probability": probabilities}, index=test.index))
            except (ValueError, np.linalg.LinAlgError):
                continue
        if predictions:
            result = pd.concat(predictions)
            if result.actual.nunique() == 2:
                backtest.append({"Model": name, "Test months": len(result), **score(result.actual, result.probability)})
    print("\nANNUALLY REFITTED HISTORICAL BACKTEST")
    print(pd.DataFrame(backtest).to_string(index=False))

    website_probabilities.index.name = "Month"
    out = Path(__file__).resolve().parent / "baa_model_comparison_probabilities.csv"
    website_probabilities.to_csv(out)
    print(f"\nSaved website-style probability comparison to: {out}")
    print("Note: historical fit uses future observations to estimate coefficients; the backtest does not.")


if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=RuntimeWarning)
        main()
