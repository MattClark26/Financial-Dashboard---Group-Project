import pandas as pd

from panels.financial_stress.presentation import load_financial_stress_view
from ui.signal_lab import build_strategy_lab, classify_recession_phases


def test_recession_phase_classification_marks_flanks() -> None:
    index = pd.date_range("2020-01-03", periods=60, freq="W-FRI")
    recession = pd.Series(0.0, index=index)
    recession.iloc[30:35] = 1.0

    phases = classify_recession_phases(recession, flank_weeks=4)

    assert phases.iloc[29] == "Pre-recession"
    assert phases.iloc[30] == "Recession"
    assert phases.iloc[35] == "Recovery"
    assert phases.iloc[10] == "Expansion"


def test_strategy_lab_returns_bounded_exposures_and_metrics() -> None:
    view = load_financial_stress_view(pd.Timestamp("2026-11-24"))

    result = build_strategy_lab(view)

    assert list(result.returns) == ["Buy & hold", "Stress-scaled", "Alert reducer"]
    assert result.exposures.min().min() >= 0.20
    assert result.exposures.max().max() <= 1.0
    assert result.cumulative.iloc[-1].gt(0).all()
    assert set(result.metrics.columns) == {
        "Annual return",
        "Annual volatility",
        "Sharpe (0% cash)",
        "Maximum drawdown",
        "Average exposure",
    }
