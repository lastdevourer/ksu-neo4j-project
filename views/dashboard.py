from __future__ import annotations

import streamlit as st

from data.seed_data import SYSTEM_DESCRIPTION
from ui.components import render_header, render_info_card, require_service
from ui.formatters import department_overview_dataframe


def format_number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def render() -> None:
    service = require_service()
    render_header(
        "Програмний модуль обліку наукових публікацій викладачів",
        "MVP сервіс для аналізу академічної мережі КСПУ/ХДУ: факультети, кафедри, викладачі, "
        "публікації, співавторство та базова мережева аналітика на Neo4j Aura.",
    )

    counts = service.get_overview_counts()

    primary_columns = st.columns(4)
    primary_columns[0].metric("Викладачі", format_number(counts["teachers"]))
    primary_columns[1].metric("Публікації", format_number(counts["publications"]))
    primary_columns[2].metric("Зв'язки авторства", format_number(counts["authorship_links"]))
    primary_columns[3].metric("Пари співавторів", format_number(counts["coauthor_pairs"]))

    secondary_columns = st.columns(2)
    secondary_columns[0].metric("Факультети", format_number(counts["faculties"]))
    secondary_columns[1].metric("Кафедри", format_number(counts["departments"]))

    if counts["teachers"] == 0 and counts["publications"] == 0:
        st.info(
            "База ще не містить викладачів або публікацій. Для швидкого старту можна створити схему та "
            "заповнити довідник факультетів і кафедр у лівій панелі."
        )

    left, right = st.columns([1.05, 1.25], gap="large")

    with left:
        render_info_card("Коротко про систему", SYSTEM_DESCRIPTION)
        render_info_card(
            "Що показує MVP",
            "Сервіс дозволяє шукати викладачів, переглядати їхні публікації та співавторів, аналізувати "
            "публікаційний потік за роками, будувати граф авторства та отримувати базові мережеві метрики "
            "для дипломної роботи.",
        )

    with right:
        st.markdown("### Структура факультетів і кафедр")
        department_overview = department_overview_dataframe(service.get_department_overview())
        if department_overview.empty:
            st.info("Дані про факультети та кафедри поки що відсутні.")
        else:
            st.dataframe(department_overview, use_container_width=True, hide_index=True)
