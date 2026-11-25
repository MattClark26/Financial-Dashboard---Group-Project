"""Shared panel-grid structure without panel-specific analytics."""

from __future__ import annotations

from html import escape
from types import ModuleType
from typing import Mapping

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
    owner = f"<b>{escape(identity.owner.upper())}</b>"
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
    *,
    signal: object | Mapping[str, object] | None = None,
    **render_kwargs: object,
) -> object:
    """Mount one existing panel module inside the shared quadrant."""
    with st.container(key=f"panel_{identity.key}"):
        view = render_kwargs.get("view")
        resolved_signal = signal or getattr(view, "signal", None)
        if isinstance(resolved_signal, Mapping):
            status = str(resolved_signal.get("status", "CONNECTED"))
        else:
            status = getattr(resolved_signal, "status", "CONNECTED")
        render_panel_header(identity, status=status)
        return panel.render(as_of, **render_kwargs)


def render_placeholder(identity: PanelIdentity) -> None:
    """Reserve a full quadrant without inventing a collaborator's analysis."""
    with st.container(key=f"panel_{identity.key}"):
        render_panel_header(identity)
        st.html(
            f"""
            <div class="rr-panel-body">
              <div class="rr-panel-title-row">
                <div>
                  <h2 class="rr-panel-title">{escape(identity.subtitle)}</h2>
                  <p class="rr-panel-summary">
                    This workspace is reserved for {escape(identity.owner)}'s
                    analysis and will accept the shared historical date.
                  </p>
                </div>
              </div>
              <div class="rr-placeholder">
                <strong>COLLABORATOR PANEL</strong>
                <p>No charts or claims have been added on their behalf.</p>
              </div>
            </div>
            <div class="rr-panel-foot">
              <span>AWAITING PANEL CONTRACT</span>
              <span>WEIGHT: NOT SET</span>
            </div>
            """
        )
