from __future__ import annotations

import streamlit as st

from ui.components import render_empty_state, render_header, render_section_heading, require_service
from ui.formatters import department_overview_dataframe, faculty_overview_dataframe, publication_sources_dataframe


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def render() -> None:
    service = require_service()
    render_header("Аналітика академічної мережі")

    counts = service.get_overview_counts()
    profile_coverage = service.get_profile_coverage()
    publication_sources = publication_sources_dataframe(service.get_publication_source_summary())
    faculty_overview = faculty_overview_dataframe(service.get_faculty_overview())
    department_overview = department_overview_dataframe(service.get_department_overview())

    render_section_heading("Показники")

    primary_columns = st.columns(4, gap="medium")
    primary_columns[0].metric("Викладачі", format_number(counts["teachers"]))
    primary_columns[1].metric("Публікації", format_number(counts["publications"]))
    primary_columns[2].metric("Авторства", format_number(counts["authorship_links"]))
    primary_columns[3].metric("Співавтори", format_number(counts["coauthor_pairs"]))

    secondary_columns = st.columns(2, gap="medium")
    secondary_columns[0].metric("Факультети", format_number(counts["faculties"]))
    secondary_columns[1].metric("Кафедри", format_number(counts["departments"]))

    total_teachers = int(profile_coverage.get("teachers", 0) or 0)
    if total_teachers:
        render_section_heading("Покриття профілів")
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

    if faculty_overview.empty and department_overview.empty:
        render_empty_state("Дані відсутні", "Завантажте викладачів KSPU або відкрийте сторінку `Структура` для керування базою.")
        return

    overview_columns = st.columns([0.88, 1.12], gap="large")

    with overview_columns[0]:
        render_section_heading("Факультети")
        if faculty_overview.empty:
            render_empty_state("Немає даних", "Факультетний зріз з'явиться після імпорту структури.")
        else:
            st.dataframe(faculty_overview, use_container_width=True, hide_index=True)

    with overview_columns[1]:
        render_section_heading("Кафедри")
        if department_overview.empty:
            render_empty_state("Немає даних", "Таблиця кафедр з'явиться після імпорту структури.")
        else:
            top_departments = department_overview.sort_values(
                by=["Викладачі", "Публікації", "Кафедра"],
                ascending=[False, False, True],
            ).head(12)
            st.dataframe(top_departments, use_container_width=True, hide_index=True)

    if not publication_sources.empty:
        render_section_heading("Джерела знайдених публікацій")
        st.bar_chart(publication_sources.set_index("Джерело"), use_container_width=True, height=260)
        st.dataframe(publication_sources, use_container_width=True, hide_index=True)

    if not faculty_overview.empty:
        render_section_heading("Розподіл викладачів за факультетами")
        chart_source = faculty_overview[["Факультет", "Викладачі"]].set_index("Факультет")
        st.bar_chart(chart_source, use_container_width=True, height=320)

    if not department_overview.empty:
        render_section_heading("Уся структура кафедр")
        st.dataframe(department_overview, use_container_width=True, hide_index=True)
