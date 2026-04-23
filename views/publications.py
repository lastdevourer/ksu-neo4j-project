from __future__ import annotations

import streamlit as st

from ui.components import render_header, render_key_value_card, require_service
from ui.formatters import publications_dataframe


def render() -> None:
    service = require_service()
    render_header(
        "Публікації",
        "Огляд публікаційної бази з фільтрацією за роком та швидким переглядом складу авторів.",
    )

    years = service.get_publication_years()
    year_options = ["Усі роки"] + [str(year) for year in years]
    selected_year = st.selectbox("Фільтр за роком", year_options)
    year_value = None if selected_year == "Усі роки" else int(selected_year)

    publication_rows = service.get_publications(year=year_value)
    publications_table = publications_dataframe(publication_rows)

    st.markdown("### Таблиця публікацій")
    if publications_table.empty:
        st.info("Публікацій за вибраним роком не знайдено.")
        return

    st.dataframe(publications_table, use_container_width=True, hide_index=True)

    publication_map = {
        f"{row['title']} ({row['year'] if row['year'] is not None else 'н/д'})": row
        for row in publication_rows
    }
    selected_publication_label = st.selectbox(
        "Склад авторів публікації",
        list(publication_map.keys()),
        help="Оберіть публікацію, щоб переглянути її авторів і короткі метадані.",
    )
    selected_publication = publication_map[selected_publication_label]

    render_key_value_card(
        "Коротка інформація про публікацію",
        [
            ("Назва", selected_publication["title"]),
            ("Рік", str(selected_publication["year"] or "н/д")),
            ("Тип", selected_publication["pub_type"]),
            ("Джерело", selected_publication["source"]),
            ("DOI", selected_publication["doi"]),
            ("Автори", ", ".join(selected_publication["authors"]) if selected_publication["authors"] else "—"),
        ],
    )
