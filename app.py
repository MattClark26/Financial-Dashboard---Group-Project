from datetime import date
from pathlib import Path

import streamlit as st
import pandas as pd

from panels import bond_market, financial_stress, irish_lens, labour_market
from ui.controls import render_time_machine
from ui.connections import activate_session_credentials, render_connections
from ui.cursor import install_cursor, scroll_to_top
from ui.intro import render_intro
from ui.navigation import render_back_to_signals
from ui.panels import PANEL_IDENTITIES, render_connected_panel
from ui.presentation import configure_plotly_theme
from ui.shell import render_composite, render_topbar


def open_connections() -> None:
    st.session_state["active_panel"] = "connections"


@st.cache_resource(ttl=900, show_spinner="Refreshing financial-market data...")
def load_workspace_stress_view(
    as_of: date,
    prefer_live: bool,
    connection_revision: int,
):
    """Reuse one stress-data refresh across panel navigation for fifteen minutes."""
    del connection_revision  # Included only to invalidate the cache after key changes.
    return financial_stress.load_financial_stress_view(
        as_of,
        prefer_live=prefer_live,
    )


def render_workspace() -> None:
    activate_session_credentials()
    default_date = st.session_state.get("as_of", date.today())
    active_panel = st.session_state.get("active_panel")

    if active_panel == "connections":
        scroll_to_top()
        render_back_to_signals(key="connections_back")
        render_connections()
        return

    if active_panel == "bond":
        scroll_to_top()
        render_back_to_signals(key="bond_market_back")
        bond_market.render_full(default_date)
        return

    if active_panel == "labour":
        scroll_to_top()
        render_back_to_signals(key="labour_market_back")
        labour_market.render_detail(default_date)
        return

    stress_view = load_workspace_stress_view(
        default_date,
        prefer_live=bool(st.session_state.get("financial_stress_live_enabled", False)),
        connection_revision=int(st.session_state.get("data_connection_revision", 0)),
    )

    if active_panel == "irish":
        scroll_to_top()
        render_back_to_signals(key="irish_lens_back")
        irish_lens.render_detail(default_date)
        return

    if active_panel in {"stress", "signal_lab"}:
        scroll_to_top()
        render_back_to_signals(key="financial_stress_back")
        financial_stress.render_detail(
            default_date,
            view=stress_view,
        )
        return

    with st.container(key="control_deck"):
        timeline, composite = st.columns(
            [3, 2],
            gap="large",
            vertical_alignment="center",
        )

        with timeline:
            as_of = render_time_machine(default_date)
        irish_signal = irish_lens.load_irish_lens_signal(
            pd.Timestamp(as_of)
        )
        labour_signal = labour_market.load_labour_market_signal(as_of)
        bond_signal = bond_market.load_bond_market_signal(as_of)
        with composite:
            render_composite({
                "bond": bond_signal["score"],
                "labour": labour_signal["score"],
                "stress": stress_view.signal.score,
                "irish": irish_signal["score"],
            })

    render_topbar(
        as_of,
        connected_count=4,
    )
    connection_action, _ = st.columns([1, 4])
    connection_action.button(
        "Data connections & API keys",
        key="open_data_connections",
        on_click=open_connections,
        width="stretch",
    )

    with st.container(key="signal_matrix"):
        bond_column, labour_column = st.columns(
            2,
            gap=None,
            vertical_alignment="top",
        )
        with bond_column:
            render_connected_panel(
                PANEL_IDENTITIES[0],
                bond_market,
                as_of,
                signal=bond_signal,
            )
        with labour_column:
            render_connected_panel(
                PANEL_IDENTITIES[1],
                labour_market,
                as_of,
                signal=labour_signal,
            )
        stress_column, irish_column = st.columns(
            2,
            gap=None,
            vertical_alignment="top",
        )
        with stress_column:
            render_connected_panel(
                PANEL_IDENTITIES[2],
                financial_stress,
                as_of,
                view=stress_view,
            )
        with irish_column:
            render_connected_panel(
                PANEL_IDENTITIES[3],
                irish_lens,
                as_of,
                signal=irish_signal,
            )


def main() -> None:
    st.set_page_config(
        page_title="Recession Radar",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    configure_plotly_theme()

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
