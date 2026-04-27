from __future__ import annotations

import streamlit as st

from ui.components import (
    render_empty_state,
    render_fullscreen_bar_chart_button,
    render_fullscreen_dataframe_button,
    render_header,
    render_section_heading,
    require_service,
)
from ui.formatters import department_overview_dataframe, faculty_overview_dataframe, publication_sources_dataframe


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def render() -> None:
    service = require_service()
    render_header(
        "Академічна мережа KSPU",
        subtitle="Оперативний огляд викладачів, публікацій, співавторства та структури університету.",
    )

    counts = service.get_overview_counts()
    profile_coverage = service.get_profile_coverage()
    publication_sources = publication_sources_dataframe(service.get_publication_source_summary())
    faculty_overview_rows = service.get_faculty_overview()
    department_overview_rows = service.get_department_overview()
    faculty_overview = faculty_overview_dataframe(faculty_overview_rows)
    department_overview = department_overview_dataframe(department_overview_rows)

    render_section_heading("Ключові показники")

    primary_columns = st.columns(4, gap="medium")
    primary_columns[0].metric("Викладачі", format_number(counts["teachers"]))
    primary_columns[1].metric("Публікації", format_number(counts["publications"]))
    primary_columns[2].metric("Авторства", format_number(counts["authorship_links"]))
    primary_columns[3].metric("Співавтори", format_number(counts["coauthor_pairs"]))

    secondary_columns = st.columns(2, gap="medium")
    secondary_columns[0].metric("Факультети", format_number(counts["faculties"]))
    secondary_columns[1].metric("Кафедри", format_number(counts["departments"]))

    if faculty_overview.empty and department_overview.empty:
        render_empty_state("Дані відсутні", "Завантажте викладачів KSPU або відкрийте сторінку `Структура`, щоб заповнити базу.")
        return

    if counts["publications"] == 0:
        st.info("Структура вже заведена. Для наповнення бази відкрийте `Структура` і запустіть імпорт викладачів та публікацій.")
    else:
        st.success("База заповнена. Можна переходити до аналітики, графа та модерації записів.")

    overview_columns = st.columns([0.92, 1.08], gap="large")

    with overview_columns[0]:
        header_columns = st.columns([0.72, 0.28], gap="small")
        with header_columns[0]:
            render_section_heading("Факультети")
        with header_columns[1]:
            render_fullscreen_dataframe_button(
                "Факультетний зріз",
                faculty_overview,
                key="dashboard_faculties_fullscreen",
                caption="Повна таблиця факультетів, кафедр, викладачів і публікацій.",
            )
        if faculty_overview.empty:
            render_empty_state("Немає даних", "Факультетний зріз з'явиться після імпорту структури.")
        else:
            st.dataframe(faculty_overview, use_container_width=True, hide_index=True)

    with overview_columns[1]:
        header_columns = st.columns([0.72, 0.28], gap="small")
        with header_columns[0]:
            render_section_heading("Кафедри")
        if department_overview.empty:
            render_empty_state("Немає даних", "Таблиця кафедр з'явиться після імпорту структури.")
        else:
            top_department_rows = sorted(
                department_overview_rows,
                key=lambda row: (
                    -(int(row.get("teachers") or 0)),
                    -(int(row.get("publications") or 0)),
                    str(row.get("name") or ""),
                ),
            )[:12]
            top_departments = department_overview_dataframe(top_department_rows)
            with header_columns[1]:
                render_fullscreen_dataframe_button(
                    "Кафедральний зріз",
                    top_departments,
                    key="dashboard_departments_fullscreen",
                    caption="Поточний топ кафедр за викладачами та публікаціями.",
                )
            st.dataframe(top_departments, use_container_width=True, hide_index=True)

    total_teachers = int(profile_coverage.get("teachers", 0) or 0)
    with st.expander("Покриття профілів і джерел", expanded=False):
        if total_teachers:
            coverage_columns = st.columns(5, gap="medium")
            coverage_columns[0].metric("Будь-який профіль", f"{profile_coverage['with_any_profile']} / {total_teachers}")
            coverage_columns[1].metric("ORCID", f"{profile_coverage['with_orcid']} / {total_teachers}")
            coverage_columns[2].metric("Scholar", f"{profile_coverage['with_scholar']} / {total_teachers}")
            coverage_columns[3].metric("Scopus", f"{profile_coverage['with_scopus']} / {total_teachers}")
            coverage_columns[4].metric("WoS", f"{profile_coverage['with_wos']} / {total_teachers}")

            progress_columns = st.columns(4, gap="medium")
            progress_columns[0].progress(profile_coverage["with_any_profile"] / total_teachers, text="Профілі загалом")
            progress_columns[1].progress(profile_coverage["with_orcid"] / total_teachers, text="ORCID")
            progress_columns[2].progress(profile_coverage["with_scopus"] / total_teachers, text="Scopus")
            progress_columns[3].progress(profile_coverage["with_wos"] / total_teachers, text="Web of Science")

        if not publication_sources.empty:
            header_columns = st.columns([0.68, 0.16, 0.16], gap="small")
            with header_columns[0]:
                render_section_heading("Джерела знайдених публікацій")
            chart_source = publication_sources.set_index("Джерело")
            with header_columns[1]:
                render_fullscreen_bar_chart_button(
                    "Розподіл джерел публікацій",
                    chart_source,
                    key="dashboard_sources_chart_fullscreen",
                )
            with header_columns[2]:
                render_fullscreen_dataframe_button(
                    "Таблиця джерел публікацій",
                    publication_sources,
                    key="dashboard_sources_table_fullscreen",
                )
            source_columns = st.columns([0.95, 1.05], gap="large")
            with source_columns[0]:
                st.bar_chart(chart_source, use_container_width=True, height=250)
            with source_columns[1]:
                st.dataframe(publication_sources, use_container_width=True, hide_index=True)

    with st.expander("Розподіл викладачів і повна структура кафедр", expanded=False):
        if not faculty_overview.empty:
            header_columns = st.columns([0.68, 0.16, 0.16], gap="small")
            with header_columns[0]:
                render_section_heading("Розподіл викладачів за факультетами")
            chart_source = faculty_overview[["Факультет", "Викладачі"]].set_index("Факультет")
            with header_columns[1]:
                render_fullscreen_bar_chart_button(
                    "Розподіл викладачів за факультетами",
                    chart_source,
                    key="dashboard_faculty_chart_fullscreen",
                )
            with header_columns[2]:
                render_fullscreen_dataframe_button(
                    "Повний зріз факультетів",
                    faculty_overview,
                    key="dashboard_faculty_table_secondary_fullscreen",
                )
            st.bar_chart(chart_source, use_container_width=True, height=300)

        if not department_overview.empty:
            header_columns = st.columns([0.72, 0.28], gap="small")
            with header_columns[0]:
                render_section_heading("Уся структура кафедр")
            with header_columns[1]:
                render_fullscreen_dataframe_button(
                    "Повна структура кафедр",
                    department_overview,
                    key="dashboard_full_department_table_fullscreen",
                )
            st.dataframe(department_overview, use_container_width=True, hide_index=True)
