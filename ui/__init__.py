"""Shared presentation components for the Recession Radar dashboard.

Panel-specific analytics stay inside the panels package. This package owns
only the cross-panel experience: navigation, controls, layout and style.
"""

from .types import PanelIdentity

__all__ = ["PanelIdentity"]
