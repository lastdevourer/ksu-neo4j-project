from __future__ import annotations

import streamlit as st

from ui.components import render_empty_state, render_header, render_section_heading, require_service
from ui.formatters import department_overview_dataframe, faculty_overview_dataframe, publication_sources_dataframe


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def render() -> None:
    service = require_service()
    render_header("ÐÐ½Ð°Ð»Ñ–Ñ‚Ð¸ÐºÐ° Ð°ÐºÐ°Ð´ÐµÐ¼Ñ–Ñ‡Ð½Ð¾Ñ— Ð¼ÐµÑ€ÐµÐ¶Ñ–")

    counts = service.get_overview_counts()
    profile_coverage = service.get_profile_coverage()
    publication_sources = publication_sources_dataframe(service.get_publication_source_summary())
    faculty_overview = faculty_overview_dataframe(service.get_faculty_overview())
    department_overview = department_overview_dataframe(service.get_department_overview())

    render_section_heading("ÐŸÐ¾ÐºÐ°Ð·Ð½Ð¸ÐºÐ¸")

    primary_columns = st.columns(4, gap="medium")
    primary_columns[0].metric("Ð’Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–", format_number(counts["teachers"]))
    primary_columns[1].metric("ÐŸÑƒÐ±Ð»Ñ–ÐºÐ°Ñ†Ñ–Ñ—", format_number(counts["publications"]))
    primary_columns[2].metric("ÐÐ²Ñ‚Ð¾Ñ€ÑÑ‚Ð²Ð°", format_number(counts["authorship_links"]))
    primary_columns[3].metric("Ð¡Ð¿Ñ–Ð²Ð°Ð²Ñ‚Ð¾Ñ€Ð¸", format_number(counts["coauthor_pairs"]))

    secondary_columns = st.columns(2, gap="medium")
    secondary_columns[0].metric("Ð¤Ð°ÐºÑƒÐ»ÑŒÑ‚ÐµÑ‚Ð¸", format_number(counts["faculties"]))
    secondary_columns[1].metric("ÐšÐ°Ñ„ÐµÐ´Ñ€Ð¸", format_number(counts["departments"]))

    total_teachers = int(profile_coverage.get("teachers", 0) or 0)
    if total_teachers:
        render_section_heading("ÐŸÐ¾ÐºÑ€Ð¸Ñ‚Ñ‚Ñ Ð¿Ñ€Ð¾Ñ„Ñ–Ð»Ñ–Ð²")
        coverage_columns = st.columns(5, gap="medium")
        coverage_columns[0].metric("Ð‘ÑƒÐ´ÑŒ-ÑÐºÐ¸Ð¹ Ð¿Ñ€Ð¾Ñ„Ñ–Ð»ÑŒ", f"{profile_coverage['with_any_profile']} / {total_teachers}")
        coverage_columns[1].metric("ORCID", f"{profile_coverage['with_orcid']} / {total_teachers}")
        coverage_columns[2].metric("Scholar", f"{profile_coverage['with_scholar']} / {total_teachers}")
        coverage_columns[3].metric("Scopus", f"{profile_coverage['with_scopus']} / {total_teachers}")
        coverage_columns[4].metric("WoS", f"{profile_coverage['with_wos']} / {total_teachers}")

        progress_columns = st.columns(4, gap="medium")
        progress_columns[0].progress(profile_coverage["with_any_profile"] / total_teachers, text="ÐŸÑ€Ð¾Ñ„Ñ–Ð»Ñ– Ð·Ð°Ð³Ð°Ð»Ð¾Ð¼")
        progress_columns[1].progress(profile_coverage["with_orcid"] / total_teachers, text="ORCID")
        progress_columns[2].progress(profile_coverage["with_scopus"] / total_teachers, text="Scopus")
        progress_columns[3].progress(profile_coverage["with_wos"] / total_teachers, text="Web of Science")

    if faculty_overview.empty and department_overview.empty:
        render_empty_state("Ð”Ð°Ð½Ñ– Ð²Ñ–Ð´ÑÑƒÑ‚Ð½Ñ–", "Ð—Ð°Ð²Ð°Ð½Ñ‚Ð°Ð¶Ñ‚Ðµ Ð²Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–Ð² KSPU Ñƒ Ð±Ñ–Ñ‡Ð½Ñ–Ð¹ Ð¿Ð°Ð½ÐµÐ»Ñ–.")
        return

    overview_columns = st.columns([0.88, 1.12], gap="large")

    with overview_columns[0]:
        render_section_heading("Ð¤Ð°ÐºÑƒÐ»ÑŒÑ‚ÐµÑ‚Ð¸")
        if faculty_overview.empty:
            render_empty_state("ÐÐµÐ¼Ð°Ñ” Ð´Ð°Ð½Ð¸Ñ…", "Ð¤Ð°ÐºÑƒÐ»ÑŒÑ‚ÐµÑ‚Ð½Ð¸Ð¹ Ð·Ñ€Ñ–Ð· Ð·'ÑÐ²Ð¸Ñ‚ÑŒÑÑ Ð¿Ñ–ÑÐ»Ñ Ñ–Ð¼Ð¿Ð¾Ñ€Ñ‚Ñƒ.")
        else:
            st.dataframe(faculty_overview, use_container_width=True, hide_index=True)

    with overview_columns[1]:
        render_section_heading("ÐšÐ°Ñ„ÐµÐ´Ñ€Ð¸")
        if department_overview.empty:
            render_empty_state("ÐÐµÐ¼Ð°Ñ” Ð´Ð°Ð½Ð¸Ñ…", "Ð¢Ð°Ð±Ð»Ð¸Ñ†Ñ ÐºÐ°Ñ„ÐµÐ´Ñ€ Ð·'ÑÐ²Ð¸Ñ‚ÑŒÑÑ Ð¿Ñ–ÑÐ»Ñ Ñ–Ð¼Ð¿Ð¾Ñ€Ñ‚Ñƒ.")
        else:
            top_departments = department_overview.sort_values(
                by=["Ð’Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–", "ÐŸÑƒÐ±Ð»Ñ–ÐºÐ°Ñ†Ñ–Ñ—", "ÐšÐ°Ñ„ÐµÐ´Ñ€Ð°"],
                ascending=[False, False, True],
            ).head(12)
            st.dataframe(top_departments, use_container_width=True, hide_index=True)

    if not publication_sources.empty:
        render_section_heading("Ð”Ð¶ÐµÑ€ÐµÐ»Ð° Ð·Ð½Ð°Ð¹Ð´ÐµÐ½Ð¸Ñ… Ð¿ÑƒÐ±Ð»Ñ–ÐºÐ°Ñ†Ñ–Ð¹")
        st.bar_chart(publication_sources.set_index("Ð”Ð¶ÐµÑ€ÐµÐ»Ð¾"), use_container_width=True, height=260)
        st.dataframe(publication_sources, use_container_width=True, hide_index=True)

    if not faculty_overview.empty:
        render_section_heading("Ð Ð¾Ð·Ð¿Ð¾Ð´Ñ–Ð» Ð²Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–Ð² Ð·Ð° Ñ„Ð°ÐºÑƒÐ»ÑŒÑ‚ÐµÑ‚Ð°Ð¼Ð¸")
        chart_source = faculty_overview[["Ð¤Ð°ÐºÑƒÐ»ÑŒÑ‚ÐµÑ‚", "Ð’Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–"]].set_index("Ð¤Ð°ÐºÑƒÐ»ÑŒÑ‚ÐµÑ‚")
        st.bar_chart(chart_source, use_container_width=True, height=320)

    if not department_overview.empty:
        render_section_heading("Ð£ÑÑ ÑÑ‚Ñ€ÑƒÐºÑ‚ÑƒÑ€Ð° ÐºÐ°Ñ„ÐµÐ´Ñ€")
        st.dataframe(department_overview, use_container_width=True, hide_index=True)
