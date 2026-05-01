from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import (
    render_empty_state,
    render_fullscreen_bar_chart_heading,
    render_fullscreen_dataframe_heading,
    render_header,
    render_info_card,
    render_section_heading,
    render_summary_strip,
    require_service,
)
from ui.formatters import (
    centrality_dataframe,
    department_overview_dataframe,
    faculty_overview_dataframe,
    publication_sources_dataframe,
    top_coauthor_pairs_dataframe,
    top_teachers_dataframe,
    teachers_dataframe_public,
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


EXPORT_OPTIONS = {
    "Топ викладачів": ("top_teachers.csv", "top_teachers"),
    "Пари співавторів": ("top_coauthor_pairs.csv", "coauthor_pairs"),
    "Centrality": ("centrality.csv", "centrality"),
    "Джерела публікацій": ("publication_sources.csv", "sources"),
    "Викладачі поточного контуру": ("scoped_teachers.csv", "scoped_teachers"),
    "Аналітичний пакет": ("analytics_package.csv", "package"),
}


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def _teacher_names(rows: list[dict]) -> set[str]:
    return {str(row.get("full_name") or "").strip() for row in rows if str(row.get("full_name") or "").strip()}


def _filter_publications_for_teachers(publications: list[dict], teachers: list[dict]) -> list[dict]:
    scoped_names = _teacher_names(teachers)
    if not scoped_names:
        return []
    filtered_rows: list[dict] = []
    for publication in publications:
        authors = {str(author).strip() for author in (publication.get("authors") or []) if str(author).strip()}
        if authors & scoped_names:
            filtered_rows.append(publication)
    return filtered_rows


def _filter_publications_by_year_range(publications: list[dict], year_range: tuple[int, int] | None) -> list[dict]:
    if not year_range:
        return publications
    year_from, year_to = year_range
    return [
        row
        for row in publications
        if row.get("year") is not None and year_from <= int(row.get("year") or 0) <= year_to
    ]


def _department_label(row: dict) -> str:
    faculty_name = str(row.get("faculty_name") or "").strip()
    department_name = str(row.get("name") or "").strip()
    return f"{department_name} — {faculty_name}" if faculty_name else department_name


def _faculty_label(row: dict) -> str:
    return str(row.get("name") or "").strip()


def _scoped_teacher_rows(teachers: list[dict], publications: list[dict]) -> list[dict]:
    publication_counts = {row["teacher"]: row["publications"] for row in build_teacher_publication_rankings(publications, teachers, 10_000)}
    rows: list[dict] = []
    for teacher in teachers:
        row = dict(teacher)
        row["publications"] = int(publication_counts.get(str(teacher.get("full_name") or "").strip(), 0))
        rows.append(row)
    return rows


def _report_package_frame(sections: list[tuple[str, pd.DataFrame]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for section_name, frame in sections:
        if frame.empty:
            continue
        section_frame = frame.copy()
        section_frame.insert(0, "Розділ", section_name)
        frames.append(section_frame)
    if not frames:
        return pd.DataFrame(columns=["Розділ"])
    return pd.concat(frames, ignore_index=True, sort=False)


def render() -> None:
    service = require_service()
    render_header("Аналітика", "")

    controls = st.columns(2, gap="large")
    top_limit = controls[0].slider("Кількість записів у топах", min_value=5, max_value=20, value=10, step=1)
    scope = controls[1].selectbox("Контур даних", ["Усі записи", "Підтверджені", "Офіційні"])
    available_years = service.get_publication_years()
    selected_year_range: tuple[int, int] | None = None
    if available_years:
        year_min = min(available_years)
        year_max = max(available_years)
        selected_year_range = st.slider(
            "Період публікацій",
            min_value=year_min,
            max_value=year_max,
            value=(year_min, year_max),
            step=1,
        )

    all_teachers = service.get_teachers()
    scoped_publications = filter_publications_by_scope(service.get_publications(), scope)
    scoped_publications = _filter_publications_by_year_range(scoped_publications, selected_year_range)
    top_teachers = build_teacher_publication_rankings(scoped_publications, all_teachers, top_limit)
    top_pairs = build_coauthor_pair_rankings(scoped_publications, all_teachers, top_limit)
    centrality_rows = calculate_centrality_rows(build_centrality_edges(scoped_publications, all_teachers))[:top_limit]
    profile_coverage = service.get_profile_coverage()
    source_rows = publication_sources_dataframe(build_publication_source_rows(scoped_publications))
    scoped_publication_count = len(scoped_publications)
    teachers_with_publications = sum(1 for row in _scoped_teacher_rows(all_teachers, scoped_publications) if int(row.get("publications", 0) or 0) > 0)
    average_publications = (scoped_publication_count / teachers_with_publications) if teachers_with_publications else 0.0

    highlights = st.columns(4, gap="medium")
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
    with highlights[3]:
        render_summary_strip(
            "Середнє навантаження",
            f"{average_publications:.1f}",
            f"викладачів з роботами: {teachers_with_publications}",
        )

    render_info_card(
        "Аналітичний висновок",
        build_diploma_summary(top_teachers, top_pairs, centrality_rows),
    )

    yearly_counts = (
        pd.DataFrame(scoped_publications)
        .dropna(subset=["year"])
        .groupby("year")
        .size()
        .reset_index(name="Публікації")
        .rename(columns={"year": "Рік"})
        .sort_values("Рік")
        if scoped_publications
        else pd.DataFrame(columns=["Рік", "Публікації"])
    )
    if not yearly_counts.empty:
        render_section_heading("Динаміка публікацій")
        trend_columns = st.columns([1.05, 0.95], gap="large")
        with trend_columns[0]:
            chart_frame = yearly_counts.set_index("Рік")
            render_fullscreen_bar_chart_heading(
                "Публікації за роками",
                chart_frame,
                key="analytics_yearly_chart_fullscreen",
            )
            st.bar_chart(chart_frame, use_container_width=True, height=260)
        with trend_columns[1]:
            render_fullscreen_dataframe_heading(
                "Таблиця динаміки",
                yearly_counts,
                key="analytics_yearly_table_fullscreen",
            )
            st.dataframe(yearly_counts, use_container_width=True, hide_index=True)

    top_teachers_export = top_teachers_dataframe(top_teachers)
    top_pairs_export = top_coauthor_pairs_dataframe(top_pairs)
    centrality_export = centrality_dataframe(centrality_rows)

    package_frame = _report_package_frame(
        [
            ("Топ викладачів", top_teachers_export),
            ("Пари співавторів", top_pairs_export),
            ("Centrality", centrality_export),
            ("Джерела публікацій", source_rows),
        ]
    )
    scoped_teachers_frame = teachers_dataframe_public(_scoped_teacher_rows(all_teachers, scoped_publications))

    render_section_heading("Експорт")
    export_choice = st.selectbox("Що завантажити", list(EXPORT_OPTIONS.keys()), key="analytics_export_choice")
    export_file_name, export_key = EXPORT_OPTIONS[export_choice]
    export_frames = {
        "top_teachers": top_teachers_export if not top_teachers_export.empty else pd.DataFrame(columns=["Викладач"]),
        "coauthor_pairs": top_pairs_export if not top_pairs_export.empty else pd.DataFrame(columns=["Викладач 1"]),
        "centrality": centrality_export if not centrality_export.empty else pd.DataFrame(columns=["Викладач"]),
        "sources": source_rows if not source_rows.empty else pd.DataFrame(columns=["Джерело"]),
        "scoped_teachers": scoped_teachers_frame if not scoped_teachers_frame.empty else pd.DataFrame(columns=["ПІБ"]),
        "package": package_frame if not package_frame.empty else pd.DataFrame(columns=["Розділ"]),
    }
    st.download_button(
        f"Завантажити: {export_choice}",
        _csv_bytes(export_frames[export_key]),
        file_name=export_file_name,
        mime="text/csv",
        use_container_width=True,
        key="analytics_export_download",
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
        top_teachers_table = top_teachers_dataframe(top_teachers)
        if top_teachers_table.empty:
            render_section_heading("Топ викладачів за кількістю публікацій")
            render_empty_state(
                "Публікаційні дані відсутні",
                "Коли у базі з'являться публікації, тут буде сформовано рейтинг викладачів.",
            )
        else:
            render_fullscreen_dataframe_heading(
                "Топ викладачів за кількістю публікацій",
                top_teachers_table,
                key="analytics_top_teachers_fullscreen",
                caption="Топ викладачів",
            )
            st.dataframe(top_teachers_table, use_container_width=True, hide_index=True)

    with top_columns[1]:
        top_pairs_table = top_coauthor_pairs_dataframe(top_pairs)
        if top_pairs_table.empty:
            render_section_heading("Топ пар співавторів")
            render_empty_state(
                "Пари співавторів поки не виявлено",
                "Після появи спільних публікацій тут буде показано стійкі пари колаборантів.",
            )
        else:
            render_fullscreen_dataframe_heading(
                "Топ пар співавторів",
                top_pairs_table,
                key="analytics_top_pairs_fullscreen",
            )
            st.dataframe(top_pairs_table, use_container_width=True, hide_index=True)

    centrality_table = centrality_dataframe(centrality_rows)
    if centrality_table.empty:
        render_section_heading("Мережеві показники")
        render_empty_state(
            "Недостатньо даних для centrality",
            "Для розрахунку degree centrality та betweenness centrality потрібні зв'язки співавторства між викладачами.",
        )
    else:
        render_fullscreen_dataframe_heading(
            "Мережеві показники",
            centrality_table,
            key="analytics_centrality_fullscreen",
        )
        st.dataframe(centrality_table, use_container_width=True, hide_index=True)

    if source_rows.empty:
        render_section_heading("Структура джерел")
        render_empty_state(
            "Джерела ще не накопичені",
            "Після завантаження робіт тут буде видно, які сервіси реально дають найбільше покриття.",
        )
    else:
        chart_source = source_rows.set_index("Джерело")
        source_columns = st.columns([1.05, 0.95], gap="large")
        with source_columns[0]:
            render_fullscreen_bar_chart_heading(
                "Структура джерел",
                chart_source,
                key="analytics_sources_chart_fullscreen",
            )
            st.bar_chart(chart_source, use_container_width=True, height=280)
        with source_columns[1]:
            render_fullscreen_dataframe_heading(
                "Таблиця джерел",
                source_rows,
                key="analytics_sources_table_fullscreen",
            )
            st.dataframe(source_rows, use_container_width=True, hide_index=True)

    render_section_heading("Звіти", "Локальні зрізи для кафедри, факультету або окремого підрозділу.")
    departments = service.get_departments()
    faculties = service.get_faculty_overview()
    report_department_tab, report_faculty_tab = st.tabs(["Звіт кафедри", "Звіт факультету"])

    with report_department_tab:
        department_map = {_department_label(row): row for row in departments}
        department_labels = {label: str(row.get("code") or "") for label, row in department_map.items()}
        if not department_labels:
            render_empty_state("Кафедри недоступні", "Спочатку потрібно заповнити довідник факультетів і кафедр.")
        else:
            selected_department_label = st.selectbox("Оберіть кафедру для звіту", list(department_labels.keys()))
            selected_department_code = department_labels[selected_department_label]
            raw_department_teachers = [
                row for row in all_teachers if str(row.get("department_code") or "") == selected_department_code
            ]
            scoped_department_publications = _filter_publications_for_teachers(scoped_publications, raw_department_teachers)
            scoped_department_teachers = _scoped_teacher_rows(raw_department_teachers, scoped_department_publications)
            teacher_report_frame = teachers_dataframe_public(scoped_department_teachers)
            department_overview_rows = [row for row in service.get_department_overview() if row.get("code") == selected_department_code]
            department_frame = department_overview_dataframe(department_overview_rows)
            teachers_in_scope = len(scoped_department_teachers)
            publications_in_scope = len(scoped_department_publications)
            profiles_ready = sum(
                1
                for row in scoped_department_teachers
                if any(str(row.get(key) or "").strip() for key in ("orcid", "google_scholar", "scopus", "web_of_science"))
            )

            report_summary = st.columns(3, gap="medium")
            report_summary[0].metric("Викладачі кафедри", teachers_in_scope)
            report_summary[1].metric("Публікації в контурі", publications_in_scope)
            report_summary[2].metric("Профілі готові", profiles_ready)

            report_columns = st.columns([1.15, 0.85], gap="large")
            with report_columns[0]:
                if teacher_report_frame.empty:
                    render_section_heading("Звіт кафедри: викладачі")
                    render_empty_state(
                        "Дані кафедри порожні",
                        "За поточним контуром даних у вибраної кафедри немає записів для звіту.",
                    )
                else:
                    render_fullscreen_dataframe_heading(
                        "Звіт кафедри: викладачі",
                        teacher_report_frame,
                        key="analytics_department_teachers_fullscreen",
                    )
                    st.dataframe(teacher_report_frame, use_container_width=True, hide_index=True)
            with report_columns[1]:
                if not department_frame.empty:
                    render_fullscreen_dataframe_heading(
                        "Звіт кафедри: огляд",
                        department_frame,
                        key="analytics_department_overview_fullscreen",
                    )
                    st.dataframe(department_frame, use_container_width=True, hide_index=True)
                report_csv = _report_package_frame(
                    [
                        ("Огляд кафедри", department_frame),
                        ("Викладачі кафедри", teacher_report_frame),
                    ]
                )
                st.download_button(
                    "Завантажити звіт кафедри CSV",
                    _csv_bytes(report_csv),
                    file_name=f"department_report_{selected_department_code}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    with report_faculty_tab:
        faculty_map = {_faculty_label(row): row for row in faculties if row.get("code")}
        faculty_labels = {label: str(row.get("code") or "") for label, row in faculty_map.items()}
        if not faculty_labels:
            render_empty_state("Факультети недоступні", "Спочатку потрібно заповнити структуру університету.")
        else:
            selected_faculty_label = st.selectbox("Оберіть факультет для звіту", list(faculty_labels.keys()))
            selected_faculty_code = faculty_labels[selected_faculty_label]
            raw_faculty_teachers = [row for row in all_teachers if str(row.get("faculty_code") or "") == selected_faculty_code]
            scoped_faculty_publications = _filter_publications_for_teachers(scoped_publications, raw_faculty_teachers)
            scoped_faculty_teachers = _scoped_teacher_rows(raw_faculty_teachers, scoped_faculty_publications)
            faculty_teacher_frame = teachers_dataframe_public(scoped_faculty_teachers)
            faculty_frame = faculty_overview_dataframe([row for row in faculties if row.get("code") == selected_faculty_code])
            faculty_department_frame = department_overview_dataframe(
                [row for row in service.get_department_overview() if row.get("faculty_code") == selected_faculty_code]
            )

            faculty_summary = st.columns(3, gap="medium")
            faculty_summary[0].metric("Кафедри факультету", len(faculty_department_frame))
            faculty_summary[1].metric(
                "Викладачі факультету",
                len(scoped_faculty_teachers),
            )
            faculty_summary[2].metric(
                "Публікації в контурі",
                len(scoped_faculty_publications),
            )

            faculty_columns = st.columns([1.12, 0.88], gap="large")
            with faculty_columns[0]:
                if faculty_teacher_frame.empty:
                    render_section_heading("Звіт факультету: викладачі")
                    render_empty_state(
                        "Дані факультету порожні",
                        "За поточним контуром даних у вибраного факультету немає записів для звіту.",
                    )
                else:
                    render_fullscreen_dataframe_heading(
                        "Звіт факультету: викладачі",
                        faculty_teacher_frame,
                        key="analytics_faculty_teachers_fullscreen",
                    )
                    st.dataframe(faculty_teacher_frame, use_container_width=True, hide_index=True)
            with faculty_columns[1]:
                if not faculty_frame.empty:
                    render_fullscreen_dataframe_heading(
                        "Звіт факультету: огляд",
                        faculty_frame,
                        key="analytics_faculty_overview_fullscreen",
                    )
                    st.dataframe(faculty_frame, use_container_width=True, hide_index=True)
                if not faculty_department_frame.empty:
                    render_fullscreen_dataframe_heading(
                        "Звіт факультету: кафедри",
                        faculty_department_frame,
                        key="analytics_faculty_departments_fullscreen",
                    )
                    st.dataframe(faculty_department_frame, use_container_width=True, hide_index=True)
                faculty_report_csv = _report_package_frame(
                    [
                        ("Огляд факультету", faculty_frame),
                        ("Кафедри факультету", faculty_department_frame),
                        ("Викладачі факультету", faculty_teacher_frame),
                    ]
                )
                st.download_button(
                    "Завантажити звіт факультету CSV",
                    _csv_bytes(faculty_report_csv),
                    file_name=f"faculty_report_{selected_faculty_code}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
