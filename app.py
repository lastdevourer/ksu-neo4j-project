from __future__ import annotations

import streamlit as st

from full_app import run as run_full_app
from ui.components import setup_page


setup_page("Академічний портал KSU")

try:
    del st.query_params["mode"]
except Exception:
    pass

run_full_app()
