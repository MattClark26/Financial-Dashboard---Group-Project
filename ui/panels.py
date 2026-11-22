"""Shared panel-grid structure without panel-specific analytics."""

from __future__ import annotations

from html import escape
from types import ModuleType

import streamlit as st

from .types import PanelIdentity


PANEL_IDENTITIES = (
    PanelIdentity(1, "bond", "Bond market", "Yield curve", "Luke O'Brien Peterson"),
    PanelIdentity(2, "labour", "Labour market", "Sahm rule & payrolls", "Tadhg Findon"),
    PanelIdentity(3, "stress", "Financial stress", "Markets under pressure", "Rohi Aluede"),
    PanelIdentity(4, "irish", "Irish lens", "Exposure & domestic demand", "Matthias Clark"),
)


def render_panel_header(
    identity: PanelIdentity,
    *,
    status: str = "UNCONNECTED",
) -> None:
    """Render consistent panel identity and ownership."""
    status_class = status.lower() if status in {"CALM", "WATCH", "ALERT"} else ""
    owner = (
        f"<b>{escape(identity.owner.upper())}</b>"
        if identity.key == "stress"
        else ""
    )
    st.html(
        f"""
        <div class="rr-panel-topline">
          <span>{identity.label} {owner}</span>
          <span class="rr-status rr-status--{status_class}">{escape(status)}</span>
        </div>
        """
    )


def render_connected_panel(
    identity: PanelIdentity,
    panel: ModuleType,
    as_of: object,
) -> None:
    """Mount one existing panel module inside the shared quadrant."""
    with st.container(key=f"panel_{identity.key}"):
        render_panel_header(identity)
        panel.render(as_of)
