from __future__ import annotations

import streamlit as st

from ui.components import (
    render_empty_state,
    render_header,
    render_info_card,
    render_section_heading,
    render_summary_strip,
    require_service,
)
from ui.formatters import centrality_dataframe, top_coauthor_pairs_dataframe, top_teachers_dataframe
from utils.analytics import build_diploma_summary, calculate_centrality_rows


def render() -> None:
    service = require_service()
    render_header("Аналітика", "")

    top_limit = st.slider("Кількість записів у топах", min_value=5, max_value=20, value=10, step=1)

    top_teachers = service.get_top_teachers_by_publications(limit=top_limit)
    top_pairs = service.get_top_coauthor_pairs(limit=top_limit)
    centrality_rows = calculate_centrality_rows(service.get_coauthor_edges())[:top_limit]

    highlights = st.columns(3, gap="medium")
    with highlights[0]:
        render_summary_strip(
            "Лідер публікацій",
            top_teachers[0]["teacher"] if top_teachers else "—",
        )
    with highlights[1]:
        render_summary_strip(
            "Найсильніша пара",
            f"{top_pairs[0]['teacher_a']} / {top_pairs[0]['teacher_b']}" if top_pairs else "—",
        )
    with highlights[2]:
        render_summary_strip(
            "Центральний вузол",
            centrality_rows[0]["teacher"] if centrality_rows else "—",
        )

    render_section_heading("Пояснення для диплома")
    render_info_card(
        "Короткий висновок",
        build_diploma_summary(top_teachers, top_pairs, centrality_rows),
    )

    top_columns = st.columns(2, gap="large")
    with top_columns[0]:
        render_section_heading("Топ викладачів за кількістю публікацій")
        top_teachers_table = top_teachers_dataframe(top_teachers)
        if top_teachers_table.empty:
            render_empty_state(
                "Публікаційні дані відсутні",
                "Коли у базі з'являться публікації, тут буде сформовано рейтинг викладачів.",
            )
        else:
            st.dataframe(top_teachers_table, use_container_width=True, hide_index=True)

    with top_columns[1]:
        render_section_heading("Топ пар співавторів")
        top_pairs_table = top_coauthor_pairs_dataframe(top_pairs)
        if top_pairs_table.empty:
            render_empty_state(
                "Пари співавторів поки не виявлено",
                "Після появи спільних публікацій тут буде показано стійкі пари колаборантів.",
            )
        else:
            st.dataframe(top_pairs_table, use_container_width=True, hide_index=True)

    render_section_heading("Мережеві показники")
    centrality_table = centrality_dataframe(centrality_rows)
    if centrality_table.empty:
        render_empty_state(
            "Недостатньо даних для centrality",
            "Для розрахунку degree centrality та betweenness centrality потрібні зв'язки співавторства між викладачами.",
        )
    else:
        st.dataframe(centrality_table, use_container_width=True, hide_index=True)
