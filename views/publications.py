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
    "Відхилено",
    "В чорному списку",
]

PUBLICATION_FLASH_KEY = "publication_management_flash"


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


def _show_flash_message() -> None:
    message = st.session_state.pop(PUBLICATION_FLASH_KEY, "")
    if message:
        st.success(message)


def _publication_option(row: dict[str, object]) -> str:
    year = row.get("year")
    year_label = str(year) if year is not None else "н/д"
    return f"{row.get('title', 'Без назви')} ({year_label})"


def _teacher_option(row: dict[str, object]) -> str:
    return f"{row.get('full_name', 'Без ПІБ')} | {row.get('department_name', 'Без кафедри')} | {row.get('id', '')}"


def _render_review_shortcuts(service, publication_id: str, review_note: str) -> None:
    top = st.columns(2, gap="medium")
    if top[0].button("Підтвердити", key=f"pub_confirm_{publication_id}", use_container_width=True):
        if service.set_publication_review_status(publication_id, "Підтверджено", review_note=review_note):
            st.session_state[PUBLICATION_FLASH_KEY] = "Статус публікації оновлено."
            st.rerun()
    if top[1].button("Відхилити", key=f"pub_reject_{publication_id}", use_container_width=True):
        if service.set_publication_review_status(publication_id, "Відхилено", review_note=review_note):
            st.session_state[PUBLICATION_FLASH_KEY] = "Публікацію відхилено."
            st.rerun()

    bottom = st.columns(2, gap="medium")
    if bottom[0].button("В чорний список", key=f"pub_blacklist_{publication_id}", use_container_width=True):
        if service.set_publication_review_status(publication_id, "В чорному списку", review_note=review_note):
            st.session_state[PUBLICATION_FLASH_KEY] = "Публікацію додано до чорного списку."
            st.rerun()
    if bottom[1].button("Скинути ручний статус", key=f"pub_reset_{publication_id}", use_container_width=True):
        if service.clear_publication_review_status(publication_id):
            st.session_state[PUBLICATION_FLASH_KEY] = "Ручний статус скинуто."
            st.rerun()


def render() -> None:
    service = require_service()
    render_header("Публікації")
    _show_flash_message()

    years = service.get_publication_years()
    year_options = ["Усі роки"] + [str(year) for year in years]

    filters = st.columns(3, gap="large")
    selected_year = filters[0].selectbox("Фільтр за роком", year_options)
    year_value = None if selected_year == "Усі роки" else int(selected_year)

    publication_rows = service.get_publications(year=year_value)
    all_teachers = service.get_teachers()
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
        filtered_rows = [
            row
            for row in filtered_rows
            if (str(row.get("source") or "").strip() or "Невідомо") == selected_source
        ]

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

    publication_map = {_publication_option(row): row for row in filtered_rows}

    layout = st.columns([1.16, 0.94], gap="large")
    with layout[0]:
        render_section_heading("Таблиця публікацій")
        st.dataframe(publications_table, use_container_width=True, hide_index=True)

    with layout[1]:
        render_section_heading("Деталі публікації")
        selected_publication_label = st.selectbox("Обрати публікацію", list(publication_map.keys()))
        selected_publication = publication_map[selected_publication_label]
        publication_id = str(selected_publication.get("id") or "").strip()
        details = service.get_publication_management_details(publication_id) or {}

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
            "Вплив на базу",
            [
                ("Пов'язані викладачі", str(details.get("linked_teachers_count") or 0)),
                (
                    "Список викладачів",
                    ", ".join(str(item) for item in details.get("linked_teachers", []) if item) or "Немає",
                ),
            ],
        )
        linked_teacher_ids = {
            str(item).strip() for item in details.get("linked_teacher_ids", []) if str(item or "").strip()
        }
        review_note = st.text_area(
            "Нотатка модератора",
            value=str(details.get("review_note") or selected_publication.get("review_note") or ""),
            height=100,
            key=f"publication_review_note_{publication_id}",
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

        with st.expander("Модерація", expanded=False):
            _render_review_shortcuts(service, publication_id, review_note)
            edit_columns = st.columns(2, gap="medium")
            edited_year_raw = edit_columns[0].text_input(
                "Рік",
                value="" if details.get("year") is None else str(details.get("year")),
                key=f"publication_year_{publication_id}",
            )
            edited_confidence = edit_columns[1].slider(
                "Рівень довіри",
                min_value=0.0,
                max_value=1.0,
                value=float(details.get("confidence") or selected_publication.get("confidence") or 0.0),
                step=0.01,
                key=f"publication_confidence_{publication_id}",
            )
            edited_title = st.text_input(
                "Назва",
                value=str(details.get("title") or selected_publication.get("title") or ""),
                key=f"publication_title_{publication_id}",
            )
            edited_doi = st.text_input(
                "DOI",
                value=str(details.get("doi") or selected_publication.get("doi") or ""),
                key=f"publication_doi_{publication_id}",
            )
            edited_pub_type = st.text_input(
                "Тип",
                value=str(details.get("pub_type") or selected_publication.get("pub_type") or ""),
                key=f"publication_type_{publication_id}",
            )
            edited_source = st.text_input(
                "Джерело",
                value=str(details.get("source") or selected_publication.get("source") or ""),
                key=f"publication_source_{publication_id}",
            )
            if st.button(
                "Зберегти редагування",
                key=f"publication_save_{publication_id}",
                use_container_width=True,
            ):
                edited_year = int(edited_year_raw) if edited_year_raw.strip().isdigit() else None
                if service.update_publication_metadata(
                    publication_id,
                    title=edited_title,
                    year=edited_year,
                    doi=edited_doi,
                    pub_type=edited_pub_type,
                    source=edited_source,
                    confidence=edited_confidence,
                    review_note=review_note,
                ):
                    st.session_state[PUBLICATION_FLASH_KEY] = "Зміни по публікації збережено."
                    st.rerun()
                st.error("Не вдалося зберегти редагування.")

        with st.expander("Керування авторством", expanded=False):
            teacher_search = st.text_input(
                "Знайти викладача для прив'язування",
                placeholder="Введіть ПІБ або кафедру",
                key=f"publication_teacher_search_{publication_id}",
            ).strip().lower()
            available_teachers = [
                row
                for row in all_teachers
                if str(row.get("id") or "").strip() not in linked_teacher_ids
                and (
                    not teacher_search
                    or teacher_search in str(row.get("full_name") or "").lower()
                    or teacher_search in str(row.get("department_name") or "").lower()
                )
            ]
            teacher_map = {_teacher_option(row): row for row in available_teachers[:120]}
            link_columns = st.columns([1.2, 0.8], gap="medium")
            if teacher_map:
                selected_teacher_label = link_columns[0].selectbox(
                    "Додати викладача до публікації",
                    list(teacher_map.keys()),
                    key=f"publication_link_teacher_{publication_id}",
                )
                selected_teacher = teacher_map[selected_teacher_label]
                if link_columns[1].button(
                    "Прив'язати викладача",
                    key=f"publication_link_button_{publication_id}",
                    use_container_width=True,
                ):
                    teacher_id = str(selected_teacher.get("id") or "").strip()
                    if service.create_teacher_publication_link(teacher_id, publication_id):
                        st.session_state[PUBLICATION_FLASH_KEY] = "Викладача прив'язано до публікації."
                        st.rerun()
                    st.error("Не вдалося прив'язати викладача.")
            else:
                st.caption("Немає доступних викладачів для прив'язування за поточним фільтром.")

            linked_rows = [
                row for row in all_teachers if str(row.get("id") or "").strip() in linked_teacher_ids
            ]
            linked_map = {_teacher_option(row): row for row in linked_rows}
            if linked_map:
                unlink_columns = st.columns([1.2, 0.8], gap="medium")
                selected_linked_label = unlink_columns[0].selectbox(
                    "Відв'язати викладача",
                    list(linked_map.keys()),
                    key=f"publication_unlink_teacher_{publication_id}",
                )
                unlink_confirm = st.checkbox(
                    "Підтверджую видалення зв'язку автора з цією публікацією",
                    key=f"publication_unlink_confirm_{publication_id}",
                )
                if unlink_columns[1].button(
                    "Видалити зв'язок",
                    key=f"publication_unlink_button_{publication_id}",
                    use_container_width=True,
                ):
                    if not unlink_confirm:
                        st.warning("Спочатку підтвердіть видалення зв'язку.")
                    else:
                        linked_teacher = linked_map[selected_linked_label]
                        teacher_id = str(linked_teacher.get("id") or "").strip()
                        if service.delete_teacher_publication_link(teacher_id, publication_id):
                            st.session_state[PUBLICATION_FLASH_KEY] = "Зв'язок автора з публікацією видалено."
                            st.rerun()
                        st.error("Не вдалося видалити зв'язок.")

        with st.expander("Керування записом", expanded=False):
            delete_confirm = st.checkbox(
                "Підтверджую повне видалення цієї публікації з бази",
                key=f"publication_delete_confirm_{publication_id}",
            )
            if st.button(
                "Видалити публікацію з бази",
                key=f"publication_delete_button_{publication_id}",
                use_container_width=True,
                type="primary",
            ):
                if not delete_confirm:
                    st.warning("Спочатку підтвердіть видалення запису.")
                elif service.delete_publication(publication_id):
                    st.session_state[PUBLICATION_FLASH_KEY] = "Публікацію видалено з бази."
                    st.rerun()
                else:
                    st.error("Не вдалося видалити публікацію. Спробуйте ще раз.")
