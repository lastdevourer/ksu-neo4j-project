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
from ui.formatters import publications_dataframe


STATUS_ORDER = [
    "Офіційно підтверджено",
    "Підтверджено",
    "Кандидат",
    "Потребує перевірки",
]


def _status_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_ORDER}
    for row in rows:
        status = str(row.get("status") or "").strip()
        if status in counts:
            counts[status] += 1
    return counts


def _source_counts(rows: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        source = str(row.get("source") or "").strip() or "Невідомо"
        counts[source] = counts.get(source, 0) + 1
    return counts


def render() -> None:
    service = require_service()
    render_header("Публікації")

    years = service.get_publication_years()
    year_options = ["Усі роки"] + [str(year) for year in years]

    filters = st.columns(3, gap="large")
    selected_year = filters[0].selectbox("Фільтр за роком", year_options)
    year_value = None if selected_year == "Усі роки" else int(selected_year)

    publication_rows = service.get_publications(year=year_value)
    status_counts = _status_counts(publication_rows)
    available_statuses = [status for status in STATUS_ORDER if status_counts[status] > 0]
    selected_status = filters[1].selectbox("Статус робіт", ["Усі статуси"] + available_statuses)

    source_counts = _source_counts(publication_rows)
    source_options = ["Усі джерела"] + sorted(source_counts.keys())
    selected_source = filters[2].selectbox("Джерело", source_options)

    filtered_rows = publication_rows
    if selected_status != "Усі статуси":
        filtered_rows = [row for row in filtered_rows if row.get("status") == selected_status]
    if selected_source != "Усі джерела":
        filtered_rows = [row for row in filtered_rows if (str(row.get("source") or "").strip() or "Невідомо") == selected_source]

    publications_table = publications_dataframe(filtered_rows)

    if publications_table.empty:
        render_empty_state(
            "Публікацій не знайдено",
            "Змініть рік, статус або джерело, щоб переглянути доступні роботи.",
        )
        return

    filtered_status_counts = _status_counts(filtered_rows)
    publications_count = len(filtered_rows)
    authorship_links = sum(int(row.get("authors_count", 0) or 0) for row in filtered_rows)
    covered_years = len({row.get("year") for row in filtered_rows if row.get("year") is not None})

    metrics = st.columns(4, gap="medium")
    with metrics[0]:
        render_summary_strip("Публікації", str(publications_count))
    with metrics[1]:
        render_summary_strip(
            "Підтверджені",
            str(filtered_status_counts["Офіційно підтверджено"] + filtered_status_counts["Підтверджено"]),
        )
    with metrics[2]:
        render_summary_strip("Потребують перевірки", str(filtered_status_counts["Потребує перевірки"]))
    with metrics[3]:
        render_summary_strip("Охоплені роки", str(covered_years))

    secondary = st.columns(3, gap="medium")
    secondary[0].metric("Авторські входження", authorship_links)
    secondary[1].metric("Кандидати", filtered_status_counts["Кандидат"])
    secondary[2].metric("Офіційно підтверджено", filtered_status_counts["Офіційно підтверджено"])

    publication_map = {
        f"{row['title']} ({row['year'] if row['year'] is not None else 'н/д'})": row
        for row in filtered_rows
    }

    layout = st.columns([1.16, 0.94], gap="large")
    with layout[0]:
        render_section_heading("Таблиця публікацій")
        st.dataframe(publications_table, use_container_width=True, hide_index=True)

    with layout[1]:
        render_section_heading("Деталі публікації")
        selected_publication_label = st.selectbox("Обрати публікацію", list(publication_map.keys()))
        selected_publication = publication_map[selected_publication_label]

        confidence = float(selected_publication.get("confidence") or 0.0)
        confidence_label = f"{confidence:.2f}"

        render_key_value_card(
            "Статус і верифікація",
            [
                ("Статус", str(selected_publication.get("status") or "")),
                ("Рівень довіри", confidence_label),
                ("Джерело", str(selected_publication.get("source") or "Невідомо")),
                ("Тип", str(selected_publication.get("pub_type") or "Невідомо")),
            ],
        )
        render_key_value_card(
            "Коротка інформація",
            [
                ("Назва", str(selected_publication.get("title") or "")),
                ("Рік", str(selected_publication.get("year") or "н/д")),
                ("DOI", str(selected_publication.get("doi") or "Немає")),
                ("Кількість авторів", str(selected_publication.get("authors_count") or 0)),
            ],
        )
        render_key_value_card(
            "Авторський склад",
            [
                (
                    "Автори",
                    ", ".join(selected_publication["authors"]) if selected_publication.get("authors") else "Немає даних",
                ),
            ],
        )
