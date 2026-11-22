from datetime import date
from html import escape
from pathlib import Path
from types import ModuleType

import streamlit as st

from panels import bond_market, financial_stress, irish_lens, labour_market
from ui.intro import render_intro

PANELS = (bond_market, labour_market, financial_stress, irish_lens)


def render_panel(panel: ModuleType, number: int, as_of: date) -> None:
    with st.container(border=True, height=350, key=f"pane_{number}"):
        st.html(
            f'<div class="pane-heading"><span>{number:02d} &nbsp; {escape(panel.TITLE)}</span>'
            '<span class="pane-state">UNCONNECTED</span></div>'
        )
        panel.render(as_of)


def render_workspace() -> None:
    """Render the analytical workspace after the project briefing."""
    st.html('<div class="terminal-bar"><strong>RECESSION RADAR</strong><span>US / IRELAND</span><span class="layout-label">2 × 2</span></div>')
    label, control = st.columns([5, 2], vertical_alignment="center")
    with label:
        st.html('<div class="workspace-label">WORKSPACE 01 <span> / FOUR PANEL VIEW</span></div>')
    with control:
        as_of = st.date_input("AS OF", value=date.today(), min_value=date(2006, 1, 1), max_value=date.today(), format="DD/MM/YYYY", key="as_of")
    for offset in (0, 2):
        columns = st.columns(2, gap="small")
        for index, column in enumerate(columns, start=offset):
            with column:
                render_panel(PANELS[index], index + 1, as_of)
    st.html('<div class="terminal-footer"><span>LAYOUT READY</span><span>DATA CONNECTIONS: 0 / 4</span></div>')


def main() -> None:
    st.set_page_config(page_title="Recession Radar", layout="wide", initial_sidebar_state="collapsed")
    st.html(Path(__file__).parent / "assets" / "dashboard.css")

    if not st.session_state.get("dashboard_entered", False):
        if render_intro():
            st.session_state.dashboard_entered = True
            st.rerun()
        return

    render_workspace()


if __name__ == "__main__":
    main()
