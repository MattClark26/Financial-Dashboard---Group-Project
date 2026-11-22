"""Install the eROdo-inspired targeting cursor in Streamlit's parent page."""

from __future__ import annotations

from pathlib import Path

import streamlit.components.v1 as components


CURSOR_SCRIPT = Path(__file__).resolve().parents[1] / "assets" / "cursor.js"


def install_cursor() -> None:
    """Run a guarded parent-document cursor installer in a zero-height frame."""
    script = CURSOR_SCRIPT.read_text(encoding="utf-8")
    components.html(f"<script>{script}</script>", height=0, width=0)
