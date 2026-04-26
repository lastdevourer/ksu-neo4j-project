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
from ui.formatters import (
    centrality_dataframe,
    publication_sources_dataframe,
    top_coauthor_pairs_dataframe,
    top_teachers_dataframe,
)
from utils.analytics import (
    build_centrality_edges,
    build_coauthor_pair_rankings,
    build_diploma_summary,
    build_publication_source_rows,
    build_teacher_publication_rankings,
    calculate_centrality_rows,
    filter_publications_by_scope,
)


def render() -> None:
    service = require_service()
    render_header("Аналітика", "")

    controls = st.columns(2, gap="large")
    top_limit = controls[0].slider("Кількість записів у топах", min_value=5, max_value=20, value=10, step=1)
    scope = controls[1].selectbox("Контур даних", ["Усі записи", "Підтверджені", "Офіційні"])

    all_teachers = service.get_teachers()
    scoped_publications = filter_publications_by_scope(service.get_publications(), scope)
    top_teachers = build_teacher_publication_rankings(scoped_publications, all_teachers, top_limit)
    top_pairs = build_coauthor_pair_rankings(scoped_publications, all_teachers, top_limit)
    centrality_rows = calculate_centrality_rows(build_centrality_edges(scoped_publications, all_teachers))[:top_limit]
    profile_coverage = service.get_profile_coverage()
    source_rows = publication_sources_dataframe(build_publication_source_rows(scoped_publications))
    scoped_publication_count = len(scoped_publications)

    highlights = st.columns(3, gap="medium")
    with highlights[0]:
        render_summary_strip(
            "Лідер публікацій",
            top_teachers[0]["teacher"] if top_teachers else "—",
            scope,
        )
    with highlights[1]:
        render_summary_strip(
            "Найсильніша пара",
            f"{top_pairs[0]['teacher_a']} / {top_pairs[0]['teacher_b']}" if top_pairs else "—",
            scope,
        )
    with highlights[2]:
        render_summary_strip(
            "Центральний вузол",
            centrality_rows[0]["teacher"] if centrality_rows else "—",
            f"Публікацій у контурі: {scoped_publication_count}",
        )

    render_section_heading("Пояснення для диплома")
    render_info_card(
        "Короткий висновок",
        build_diploma_summary(top_teachers, top_pairs, centrality_rows),
    )

    if profile_coverage.get("teachers", 0):
        render_section_heading("Готовність профілів до автоматичного імпорту")
        total_teachers = max(int(profile_coverage["teachers"] or 0), 1)
        readiness_columns = st.columns(4, gap="medium")
        readiness_columns[0].metric("ORCID", f"{profile_coverage['with_orcid']} / {total_teachers}")
        readiness_columns[1].metric("Scholar", f"{profile_coverage['with_scholar']} / {total_teachers}")
        readiness_columns[2].metric("Scopus", f"{profile_coverage['with_scopus']} / {total_teachers}")
        readiness_columns[3].metric("WoS", f"{profile_coverage['with_wos']} / {total_teachers}")

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

    render_section_heading("Структура джерел")
    if source_rows.empty:
        render_empty_state(
            "Джерела ще не накопичені",
            "Після завантаження робіт тут буде видно, які сервіси реально дають найбільше покриття.",
        )
    else:
        source_columns = st.columns([1.05, 0.95], gap="large")
        with source_columns[0]:
            st.bar_chart(source_rows.set_index("Джерело"), use_container_width=True, height=280)
        with source_columns[1]:
            st.dataframe(source_rows, use_container_width=True, hide_index=True)
