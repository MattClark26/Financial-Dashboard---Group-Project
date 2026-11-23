"""Financial Stress panel public interface."""

from datetime import date

from .analytics import FinancialStressAnalytics, prepare_stress_analytics
from .models import FinancialStressDataset, SeriesData, SeriesSpec, SourceMode
from .presentation import FinancialStressView, load_financial_stress_view
from .scoring import StressSignal, score_financial_stress

TITLE = "Financial stress"

__all__ = [
    "FinancialStressDataset",
    "FinancialStressView",
    "FinancialStressAnalytics",
    "SeriesData",
    "SeriesSpec",
    "SourceMode",
    "StressSignal",
    "TITLE",
    "prepare_stress_analytics",
    "load_financial_stress_view",
    "score_financial_stress",
    "render",
    "render_detail",
]


def render(as_of: date, **kwargs: object) -> StressSignal:
    """Render the compact panel and return its standard signal."""
    from .view import render_overview

    return render_overview(as_of, **kwargs)


def render_detail(as_of: date, **kwargs: object) -> None:
    """Render the full-page financial stress analysis."""
    from .view import render_detail as render_detail_view

    render_detail_view(as_of, **kwargs)
