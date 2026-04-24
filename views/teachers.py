from __future__ import annotations

import streamlit as st

from ui.components import (
    render_empty_state,
    render_header,
    render_key_value_card,
    render_section_heading,
    render_summary_strip,
    require_service,
)
from ui.formatters import coauthors_dataframe, teacher_publications_dataframe, teachers_dataframe


def render() -> None:
    service = require_service()
    render_header("Викладачі", "")

    departments = service.get_departments()
    department_labels = {"Усі кафедри": ""}
    for row in departments:
        department_labels[f"{row['name']} ({row['code']})"] = row["code"]

    filters = st.columns([1.4, 1.1], gap="large")
    search_value = filters[0].text_input("Пошук за ПІБ", placeholder="Введіть прізвище або частину імені")
    selected_department_label = filters[1].selectbox("Фільтр за кафедрою", list(department_labels.keys()))
    selected_department_code = department_labels[selected_department_label]

    teacher_rows = service.get_teachers(search=search_value, department_code=selected_department_code)
    teachers_table = teachers_dataframe(teacher_rows)

    if teachers_table.empty:
        render_empty_state(
            "Викладачів не знайдено",
            "Спробуйте змінити запит або послабити фільтр за кафедрою, щоб побачити доступних викладачів.",
        )
        return

    metrics = st.columns(3, gap="medium")
    teacher_count = len(teacher_rows)
    publication_count = sum(int(row.get("publications", 0) or 0) for row in teacher_rows)
    departments_count = len({row.get("department_code") for row in teacher_rows if row.get("department_code")})

    with metrics[0]:
        render_summary_strip("Викладачі у вибірці", str(teacher_count))
    with metrics[1]:
        render_summary_strip("Публікації у вибірці", str(publication_count))
    with metrics[2]:
        render_summary_strip("Кафедри у вибірці", str(departments_count))

    teacher_labels = {f"{row['full_name']} | {row['department_name']}": row["id"] for row in teacher_rows}
    layout = st.columns([1.18, 0.94], gap="large")

    with layout[0]:
        render_section_heading("Таблиця викладачів")
        st.dataframe(teachers_table, use_container_width=True, hide_index=True)

    with layout[1]:
        render_section_heading("Картка викладача")
        selected_teacher_label = st.selectbox(
            "Обрати викладача",
            list(teacher_labels.keys()),
        )
        selected_teacher_id = teacher_labels[selected_teacher_label]

        profile = service.get_teacher_profile(selected_teacher_id)
        if profile is None:
            render_empty_state(
                "Профіль тимчасово недоступний",
                "Не вдалося знайти детальну картку цього викладача. Спробуйте оновити вибір або перевірити дані у графі.",
            )
            return

        publications = service.get_teacher_publications(selected_teacher_id)
        coauthors = service.get_teacher_coauthors(selected_teacher_id)

        render_key_value_card(
            "Паспорт викладача",
            [
                ("ПІБ", profile["full_name"]),
                ("Кафедра", profile["department_name"]),
                ("Факультет", profile["faculty_name"]),
                ("Посада", profile["position"]),
                ("Науковий ступінь", profile["academic_degree"]),
                ("Вчене звання", profile["academic_title"]),
            ],
        )
        render_key_value_card(
            "Наукові профілі",
            [
                ("ORCID", profile["orcid"]),
                ("Google Scholar", profile["google_scholar"]),
                ("Scopus", profile["scopus"]),
                ("Web of Science", profile["web_of_science"]),
                ("Профіль KSPU", profile["profile_url"]),
                ("Кількість публікацій", str(len(publications))),
                ("Кількість співавторів", str(len(coauthors))),
            ],
        )

    tabs = st.tabs(["Публікації викладача", "Співавтори"])
    with tabs[0]:
        render_section_heading("Публікації викладача")
        publications_table = teacher_publications_dataframe(publications)
        if publications_table.empty:
            render_empty_state(
                "Публікацій не знайдено",
                "Для цього викладача у поточній базі ще немає зафіксованих публікацій.",
            )
        else:
            st.dataframe(publications_table, use_container_width=True, hide_index=True)

    with tabs[1]:
        render_section_heading("Співавтори")
        coauthors_table = coauthors_dataframe(coauthors)
        if coauthors_table.empty:
            render_empty_state(
                "Співавторів не виявлено",
                "У мережі ще не зафіксовано спільних публікацій з іншими викладачами.",
            )
        else:
            st.dataframe(coauthors_table, use_container_width=True, hide_index=True)
