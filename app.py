from datetime import date
from pathlib import Path

import streamlit as st

from panels import bond_market, financial_stress
from ui.controls import render_time_machine
from ui.cursor import install_cursor, scroll_to_top
from ui.intro import render_intro
from ui.panels import PANEL_IDENTITIES, render_connected_panel, render_placeholder
from ui.shell import render_composite, render_topbar

def render_workspace() -> None:
    """Render the analytical workspace after the project briefing."""
    default_date = st.session_state.get("as_of", date.today())
    stress_view = financial_stress.load_financial_stress_view(default_date)
    if st.session_state.get("active_panel") == "stress":
        scroll_to_top()
        financial_stress.render_detail(default_date, view=stress_view)
        return
    render_topbar(default_date)
    with st.container(key="control_deck"):
        timeline, composite = st.columns([3, 2], gap="large", vertical_alignment="center")
        with timeline:
            as_of = render_time_machine(default_date)
        with composite:
            render_composite({"stress": stress_view.signal.score})
    for offset in (0, 2):
        columns = st.columns(2, gap=None)
        for index, column in enumerate(columns, start=offset):
            with column:
                identity = PANEL_IDENTITIES[index]
                if identity.key == "stress":
                    render_connected_panel(
                        identity,
                        financial_stress,
                        as_of,
                        view=stress_view,
                    )
                elif identity.key == "bond":
                    render_connected_panel(identity, bond_market, as_of)
                else:
                    render_placeholder(identity)


def main() -> None:
    st.set_page_config(page_title="Recession Radar", layout="wide", initial_sidebar_state="collapsed")
    st.html(Path(__file__).parent / "assets" / "dashboard.css")
    install_cursor()

    if not st.session_state.get("dashboard_entered", False):
        if render_intro():
            st.session_state.dashboard_entered = True
            st.rerun()
        return

    render_workspace()


if __name__ == "__main__":
    main()
