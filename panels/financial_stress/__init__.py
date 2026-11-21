"""Financial Stress panel public interface."""

from datetime import date

from .analytics import FinancialStressAnalytics, prepare_stress_analytics
from .models import FinancialStressDataset, SeriesData, SeriesSpec, SourceMode

TITLE = "Financial stress"

__all__ = [
    "FinancialStressDataset",
    "FinancialStressAnalytics",
    "SeriesData",
    "SeriesSpec",
    "SourceMode",
    "TITLE",
    "prepare_stress_analytics",
    "render",
]


def render(as_of: date) -> None:
    """Render the panel shell while its analytical layers are connected."""
    import streamlit as st

    st.subheader("Financial Stress Signal")
    st.caption(
        f"Selected date: {as_of:%Y-%m-%d}. "
        "Data and analytical foundations are ready for integration."
    )
