from __future__ import annotations

import streamlit as st

from ui.components import render_header, render_key_value_card, require_service
from ui.formatters import coauthors_dataframe, teacher_publications_dataframe, teachers_dataframe


def render() -> None:
    service = require_service()
    render_header(
        "Викладачі",
        "Пошук, фільтрація та детальні картки викладачів із прив'язкою до кафедр, публікацій і співавторів.",
    )

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

    st.markdown("### Таблиця викладачів")
    if teachers_table.empty:
        st.info("За вибраними параметрами викладачів не знайдено.")
        return

    st.dataframe(teachers_table, use_container_width=True, hide_index=True)

    teacher_labels = {f"{row['full_name']} | {row['department_name']}": row["id"] for row in teacher_rows}
    selected_teacher_label = st.selectbox(
        "Картка викладача",
        list(teacher_labels.keys()),
        help="Оберіть викладача для детального перегляду публікацій і співавторства.",
    )
    selected_teacher_id = teacher_labels[selected_teacher_label]

    profile = service.get_teacher_profile(selected_teacher_id)
    publications = service.get_teacher_publications(selected_teacher_id)
    coauthors = service.get_teacher_coauthors(selected_teacher_id)

    profile_columns = st.columns([1.05, 1.25], gap="large")
    with profile_columns[0]:
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

    with profile_columns[1]:
        render_key_value_card(
            "Наукові профілі",
            [
                ("ORCID", profile["orcid"]),
                ("Google Scholar", profile["google_scholar"]),
                ("Scopus", profile["scopus"]),
                ("Кількість публікацій", str(len(publications))),
                ("Кількість співавторів", str(len(coauthors))),
            ],
        )

    bottom_columns = st.columns(2, gap="large")
    with bottom_columns[0]:
        st.markdown("### Публікації викладача")
        publications_table = teacher_publications_dataframe(publications)
        if publications_table.empty:
            st.info("Для цього викладача публікацій поки не знайдено.")
        else:
            st.dataframe(publications_table, use_container_width=True, hide_index=True)

    with bottom_columns[1]:
        st.markdown("### Співавтори")
        coauthors_table = coauthors_dataframe(coauthors)
        if coauthors_table.empty:
            st.info("Співавторів поки не виявлено.")
        else:
            st.dataframe(coauthors_table, use_container_width=True, hide_index=True)
