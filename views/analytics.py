from __future__ import annotations

import streamlit as st

from ui.components import render_header, render_info_card, require_service
from ui.formatters import centrality_dataframe, top_coauthor_pairs_dataframe, top_teachers_dataframe
from utils.analytics import build_diploma_summary, calculate_centrality_rows


def render() -> None:
    service = require_service()
    render_header(
        "Аналітика",
        "Порівняння наукової активності викладачів, аналіз сталих пар співавторів та мережеві метрики "
        "для опису структури академічної взаємодії.",
    )

    top_limit = st.slider("Кількість записів у топах", min_value=5, max_value=20, value=10, step=1)

    top_teachers = service.get_top_teachers_by_publications(limit=top_limit)
    top_pairs = service.get_top_coauthor_pairs(limit=top_limit)
    centrality_rows = calculate_centrality_rows(service.get_coauthor_edges())[:top_limit]

    render_info_card(
        "Пояснення результатів для дипломної роботи",
        build_diploma_summary(top_teachers, top_pairs, centrality_rows),
    )

    top_columns = st.columns(2, gap="large")
    with top_columns[0]:
        st.markdown("### Топ викладачів за кількістю публікацій")
        top_teachers_table = top_teachers_dataframe(top_teachers)
        if top_teachers_table.empty:
            st.info("Публікаційні дані відсутні.")
        else:
            st.dataframe(top_teachers_table, use_container_width=True, hide_index=True)

    with top_columns[1]:
        st.markdown("### Топ пар співавторів")
        top_pairs_table = top_coauthor_pairs_dataframe(top_pairs)
        if top_pairs_table.empty:
            st.info("Пари співавторів поки не виявлено.")
        else:
            st.dataframe(top_pairs_table, use_container_width=True, hide_index=True)

    st.markdown("### Centrality показники")
    centrality_table = centrality_dataframe(centrality_rows)
    if centrality_table.empty:
        st.info("Для розрахунку degree centrality та betweenness centrality потрібні зв'язки співавторства.")
    else:
        st.dataframe(centrality_table, use_container_width=True, hide_index=True)
