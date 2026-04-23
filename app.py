from __future__ import annotations

import streamlit as st

from ui.components import render_sidebar, require_service, setup_page
from views import analytics, dashboard, graph, publications, teachers


setup_page("Академічна мережа КСПУ / ХДУ")
service = require_service()
render_sidebar(service)

navigation = st.navigation(
    [
        st.Page(dashboard.render, title="Дашборд", url_path="dashboard", default=True),
        st.Page(teachers.render, title="Викладачі", url_path="teachers"),
        st.Page(publications.render, title="Публікації", url_path="publications"),
        st.Page(graph.render, title="Граф", url_path="graph"),
        st.Page(analytics.render, title="Аналітика", url_path="analytics"),
    ],
    position="sidebar",
)
navigation.run()
