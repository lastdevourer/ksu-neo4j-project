from __future__ import annotations

import streamlit as st

from services.neo4j_service import Neo4jService


def render_sidebar(
    service: Neo4jService,
    *,
    current_page: str,
    pages: dict[str, dict[str, object]],
) -> str:
    selected_page = current_page
    counts = service.get_overview_counts()
    coverage = service.get_profile_coverage()
    section_order = ["Огляд", "Каталог", "Адміністрування"]

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-kicker">KSPU</div>
                <div class="sidebar-brand-title">Академічна мережа</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for section_name in section_order:
            section_pages = [
                (page_key, page_meta)
                for page_key, page_meta in pages.items()
                if page_meta.get("section") == section_name
            ]
            if not section_pages:
                continue

            with st.expander(section_name, expanded=False):
                for page_key, page_meta in section_pages:
                    button_type = "primary" if page_key == current_page else "secondary"
                    if st.button(
                        str(page_meta["title"]),
                        key=f"sidebar_nav_{page_key}",
                        use_container_width=True,
                        type=button_type,
                    ):
                        selected_page = page_key

        with st.expander("Стан бази", expanded=False):
            status_columns = st.columns(2, gap="small")
            status_columns[0].metric("Факультети", counts["faculties"])
            status_columns[1].metric("Кафедри", counts["departments"])
            status_columns[0].metric("Викладачі", counts["teachers"])
            status_columns[1].metric("Публікації", counts["publications"])
            st.caption(
                f"Профілі для імпорту: {coverage['with_any_profile']} / {coverage['teachers']}. "
                "Операційні дії зібрано на сторінках `Структура` та `Центр даних`."
            )

    return selected_page
