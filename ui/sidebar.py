from __future__ import annotations

import streamlit as st

from services.neo4j_service import Neo4jService


def render_sidebar(service: Neo4jService) -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-kicker">KSPU / KhDU</div>
                <div class="sidebar-brand-title">Академічна мережа</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        coverage = service.get_profile_coverage()
        total_teachers = int(coverage.get("teachers", 0) or 0)
        total_profiles = int(coverage.get("with_any_profile", 0) or 0)
        if total_teachers:
            st.caption(f"Покриття профілів: {total_profiles} / {total_teachers}")

        st.caption("Основні сервісні дії перенесено в сторінки `Структура` та `Центр даних`.")
