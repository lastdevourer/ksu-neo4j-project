from __future__ import annotations

import io
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
    build_diploma_summary,
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


def _safe_sheet_name(name: str) -> str:
    invalid_chars = '[]:*?/\\'
    cleaned = "".join("_" if char in invalid_chars else char for char in str(name or "").strip())
    return (cleaned or "Sheet")[:31]


def _excel_bytes(sections: list[tuple[str, pd.DataFrame]]) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        wrote_sheet = False
        for sheet_name, frame in sections:
            if frame.empty:
                continue
            frame.to_excel(writer, sheet_name=_safe_sheet_name(sheet_name), index=False)
            wrote_sheet = True
        if not wrote_sheet:
            pd.DataFrame([{"Стан": "Немає даних для експорту"}]).to_excel(
                writer,
                sheet_name="Summary",
                index=False,
            )
    buffer.seek(0)
    return buffer.getvalue()


EXPORT_OPTIONS = {
    "Топ викладачів": ("top_teachers.csv", "top_teachers", "csv"),
    "Пари співавторів": ("top_coauthor_pairs.csv", "coauthor_pairs", "csv"),
    "Centrality": ("centrality.csv", "centrality", "csv"),
    "Джерела публікацій": ("publication_sources.csv", "sources", "csv"),
    "Викладачі поточного контуру": ("scoped_teachers.csv", "scoped_teachers", "csv"),
    "Аналітичний пакет XLSX": ("analytics_package.xlsx", "package_xlsx", "xlsx"),
}


@st.cache_data(ttl=300, show_spinner=False)
def _load_analytics_snapshot(_service, scope: str, top_limit: int, year_range: tuple[int, int] | None) -> dict[str, object]:
    year_from = year_range[0] if year_range else None
    year_to = year_range[1] if year_range else None
    return {
        "top_teachers": _service.get_top_teachers_analytics(
            scope=scope,
            year_from=year_from,
            year_to=year_to,
            limit=top_limit,
        ),
        "top_pairs": _service.get_top_coauthor_pairs_analytics(
            scope=scope,
            year_from=year_from,
            year_to=year_to,
            limit=top_limit,
        ),
        "yearly_counts": _service.get_publication_year_dynamics(
            scope=scope,
            year_from=year_from,
            year_to=year_to,
        ),
        "sources": _service.get_publication_source_summary_analytics(
            scope=scope,
            year_from=year_from,
            year_to=year_to,
        ),
    }

def _filter_publications_by_year_range(publications: list[dict], year_range: tuple[int, int] | None) -> list[dict]:
    if not year_range:
        return publications
    year_from, year_to = year_range
    filtered: list[dict] = []
    for row in publications:
        try:
            year = int(row.get("year"))
        except (TypeError, ValueError):
            year = None
        if year is not None and year_from <= year <= year_to:
            filtered.append(row)
    return filtered


def _department_label(row: dict) -> str:
    faculty_name = str(row.get("faculty_name") or "").strip()
    department_name = str(row.get("name") or "").strip()
    return f"{department_name} — {faculty_name}" if faculty_name else department_name


def _faculty_label(row: dict) -> str:
    return str(row.get("name") or "").strip()


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
        st.caption("Публікації без вказаного року не входять у фільтр періоду.")

    year_from = selected_year_range[0] if selected_year_range else None
    year_to = selected_year_range[1] if selected_year_range else None
    all_teachers = service.get_teachers()
    analytics_snapshot = _load_analytics_snapshot(service, scope, top_limit, selected_year_range)
    scoped_teacher_rows = service.get_teachers_analytics(
        scope=scope,
        year_from=year_from,
        year_to=year_to,
    )
    scoped_publications = filter_publications_by_scope(service.get_publications(), scope)
    scoped_publications = _filter_publications_by_year_range(scoped_publications, selected_year_range)
    top_teachers = analytics_snapshot["top_teachers"]
    top_pairs = analytics_snapshot["top_pairs"]
    centrality_rows = calculate_centrality_rows(build_centrality_edges(scoped_publications, all_teachers))[:top_limit]
    profile_coverage = service.get_profile_coverage()
    source_rows = publication_sources_dataframe(analytics_snapshot["sources"])
    scoped_publication_count = len(scoped_publications)
    teachers_with_publications = sum(1 for row in scoped_teacher_rows if int(row.get("publications", 0) or 0) > 0)
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
        pd.DataFrame(analytics_snapshot["yearly_counts"])
        .rename(columns={"year": "Рік", "publications": "Публікації"})
        if analytics_snapshot["yearly_counts"]
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
    scoped_teachers_frame = teachers_dataframe_public(scoped_teacher_rows)

    render_section_heading("Експорт")
    export_choice = st.selectbox("Що завантажити", list(EXPORT_OPTIONS.keys()), key="analytics_export_choice")
    export_file_name, export_key, export_format = EXPORT_OPTIONS[export_choice]
    summary_export = pd.DataFrame(
        [
            {"Показник": "Контур даних", "Значення": scope},
            {"Показник": "Період від", "Значення": year_from if year_from is not None else "Усі роки"},
            {"Показник": "Період до", "Значення": year_to if year_to is not None else "Усі роки"},
            {"Показник": "Публікацій у контурі", "Значення": scoped_publication_count},
            {"Показник": "Викладачів із роботами", "Значення": teachers_with_publications},
            {"Показник": "Середнє навантаження", "Значення": round(average_publications, 2)},
        ]
    )
    export_frames = {
        "top_teachers": top_teachers_export if not top_teachers_export.empty else pd.DataFrame(columns=["Викладач"]),
        "coauthor_pairs": top_pairs_export if not top_pairs_export.empty else pd.DataFrame(columns=["Викладач 1"]),
        "centrality": centrality_export if not centrality_export.empty else pd.DataFrame(columns=["Викладач"]),
        "sources": source_rows if not source_rows.empty else pd.DataFrame(columns=["Джерело"]),
        "scoped_teachers": scoped_teachers_frame if not scoped_teachers_frame.empty else pd.DataFrame(columns=["ПІБ"]),
    }
    package_sections = [
        ("Summary", summary_export),
        ("Top teachers", top_teachers_export),
        ("Coauthor pairs", top_pairs_export),
        ("Centrality", centrality_export),
        ("Sources", source_rows),
        ("Dynamics", yearly_counts),
        ("Scoped teachers", scoped_teachers_frame),
    ]
    if export_format == "xlsx":
        try:
            download_data = _excel_bytes(package_sections)
            st.download_button(
                f"Завантажити: {export_choice}",
                download_data,
                file_name=export_file_name,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="analytics_export_download",
            )
        except ModuleNotFoundError:
            st.warning("Для XLSX-експорту потрібно оновити середовище з бібліотекою openpyxl.")
    else:
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
            scoped_department_teachers = service.get_teachers_analytics(
                scope=scope,
                year_from=year_from,
                year_to=year_to,
                department_code=selected_department_code,
            )
            teacher_report_frame = teachers_dataframe_public(scoped_department_teachers)
            department_overview_rows = service.get_department_overview_analytics(
                scope=scope,
                year_from=year_from,
                year_to=year_to,
                department_code=selected_department_code,
            )
            department_frame = department_overview_dataframe(department_overview_rows)
            department_summary_row = department_overview_rows[0] if department_overview_rows else {}
            teachers_in_scope = int(department_summary_row.get("teachers", len(scoped_department_teachers)) or 0)
            publications_in_scope = int(department_summary_row.get("publications", 0) or 0)
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
            scoped_faculty_teachers = service.get_teachers_analytics(
                scope=scope,
                year_from=year_from,
                year_to=year_to,
                faculty_code=selected_faculty_code,
            )
            faculty_teacher_frame = teachers_dataframe_public(scoped_faculty_teachers)
            faculty_rows = service.get_faculty_overview_analytics(
                scope=scope,
                year_from=year_from,
                year_to=year_to,
                faculty_code=selected_faculty_code,
            )
            faculty_frame = faculty_overview_dataframe(faculty_rows)
            faculty_department_rows = service.get_department_overview_analytics(
                scope=scope,
                year_from=year_from,
                year_to=year_to,
                faculty_code=selected_faculty_code,
            )
            faculty_department_frame = department_overview_dataframe(faculty_department_rows)
            faculty_summary_row = faculty_rows[0] if faculty_rows else {}

            faculty_summary = st.columns(3, gap="medium")
            faculty_summary[0].metric("Кафедри факультету", int(faculty_summary_row.get("departments", len(faculty_department_frame)) or 0))
            faculty_summary[1].metric(
                "Викладачі факультету",
                int(faculty_summary_row.get("teachers", len(scoped_faculty_teachers)) or 0),
            )
            faculty_summary[2].metric(
                "Публікації в контурі",
                int(faculty_summary_row.get("publications", 0) or 0),
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
