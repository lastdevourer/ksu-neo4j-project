from __future__ import annotations

import pandas as pd
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


FLASH_KEY = "data_center_flash"
PROBLEM_STATUSES = ["Кандидат", "Потребує перевірки", "Відхилено", "В чорному списку"]
REVIEW_OPTIONS = [
    "Підтверджено",
    "Офіційно підтверджено",
    "Відхилено",
    "В чорному списку",
]


def _show_flash_message() -> None:
    message = st.session_state.pop(FLASH_KEY, "")
    if message:
        st.success(message)


def _teacher_gap_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    renamed = frame.rename(
        columns={
            "id": "ID",
            "full_name": "ПІБ",
            "department_name": "Кафедра",
            "faculty_name": "Факультет",
            "publications": "Публікації",
        }
    )
    columns = ["ID", "ПІБ", "Кафедра", "Факультет", "Публікації"]
    return renamed[columns]


def _problem_publication_option(row: dict[str, object]) -> str:
    year = row.get("year")
    year_label = str(year) if year is not None else "н/д"
    status = str(row.get("status") or "")
    return f"{row.get('title', 'Без назви')} ({year_label}) | {status}"


def _render_review_actions(service, publication_id: str, review_note: str) -> None:
    status_columns = st.columns(2, gap="medium")
    if status_columns[0].button(
        "Підтвердити",
        key=f"review_confirm_{publication_id}",
        use_container_width=True,
    ):
        if service.set_publication_review_status(publication_id, "Підтверджено", review_note=review_note):
            st.session_state[FLASH_KEY] = "Статус публікації оновлено на 'Підтверджено'."
            st.rerun()
    if status_columns[1].button(
        "Офіційно підтвердити",
        key=f"review_official_{publication_id}",
        use_container_width=True,
    ):
        if service.set_publication_review_status(publication_id, "Офіційно підтверджено", review_note=review_note):
            st.session_state[FLASH_KEY] = "Статус публікації оновлено на 'Офіційно підтверджено'."
            st.rerun()

    moderation_columns = st.columns(2, gap="medium")
    if moderation_columns[0].button(
        "Відхилити",
        key=f"review_reject_{publication_id}",
        use_container_width=True,
    ):
        if service.set_publication_review_status(publication_id, "Відхилено", review_note=review_note):
            st.session_state[FLASH_KEY] = "Публікацію відхилено."
            st.rerun()
    if moderation_columns[1].button(
        "В чорний список",
        key=f"review_blacklist_{publication_id}",
        use_container_width=True,
    ):
        if service.set_publication_review_status(publication_id, "В чорному списку", review_note=review_note):
            st.session_state[FLASH_KEY] = "Публікацію додано до чорного списку."
            st.rerun()


def render() -> None:
    service = require_service()
    render_header("Центр даних")
    _show_flash_message()

    all_teachers = service.get_teachers()
    all_publications = service.get_publications()

    problematic_publications = [row for row in all_publications if row.get("status") in PROBLEM_STATUSES]
    teachers_without_profiles = [
        row
        for row in all_teachers
        if not any(str(row.get(key) or "").strip() for key in ("orcid", "google_scholar", "scopus", "web_of_science"))
    ]
    teachers_without_publications = [row for row in all_teachers if int(row.get("publications", 0) or 0) == 0]

    summary = st.columns(4, gap="medium")
    with summary[0]:
        render_summary_strip("Проблемні роботи", str(len(problematic_publications)))
    with summary[1]:
        render_summary_strip("Без зовнішніх профілів", str(len(teachers_without_profiles)))
    with summary[2]:
        render_summary_strip("Без публікацій", str(len(teachers_without_publications)))
    with summary[3]:
        render_summary_strip("Усього записів", str(len(all_publications)))

    render_section_heading("Керування проблемними публікаціями")
    publication_filters = st.columns([1.2, 0.8], gap="large")
    search_value = publication_filters[0].text_input(
        "Пошук за назвою або DOI",
        placeholder="Введіть фрагмент назви, DOI або джерело",
    ).strip().lower()
    status_filter = publication_filters[1].selectbox(
        "Показати статус",
        ["Усі проблемні", "Кандидат", "Потребує перевірки", "Відхилено", "В чорному списку"],
    )

    filtered_problematic = problematic_publications
    if status_filter != "Усі проблемні":
        filtered_problematic = [row for row in filtered_problematic if row.get("status") == status_filter]
    if search_value:
        filtered_problematic = [
            row
            for row in filtered_problematic
            if search_value in str(row.get("title") or "").lower()
            or search_value in str(row.get("doi") or "").lower()
            or search_value in str(row.get("source") or "").lower()
        ]

    problem_layout = st.columns([1.15, 0.85], gap="large")
    with problem_layout[0]:
        if filtered_problematic:
            st.dataframe(publications_dataframe(filtered_problematic), use_container_width=True, hide_index=True)
        else:
            render_empty_state(
                "Проблемних публікацій не знайдено",
                "Після фільтрації немає записів, які потребують ручної уваги.",
            )

    with problem_layout[1]:
        if filtered_problematic:
            publication_map = {_problem_publication_option(row): row for row in filtered_problematic}
            selected_label = st.selectbox("Обрати запис", list(publication_map.keys()))
            selected_publication = publication_map[selected_label]
            publication_id = str(selected_publication.get("id") or "").strip()
            details = service.get_publication_management_details(publication_id) or {}
            confidence = float(selected_publication.get("confidence") or 0.0)

            render_key_value_card(
                "Швидка перевірка",
                [
                    ("Статус", str(selected_publication.get("status") or "")),
                    ("Рівень довіри", f"{confidence:.2f}"),
                    ("Джерело", str(selected_publication.get("source") or "Невідомо")),
                    ("Пов'язані викладачі", str(details.get("linked_teachers_count") or 0)),
                ],
            )
            render_key_value_card(
                "Пов'язаний контур",
                [
                    ("Назва", str(details.get("title") or selected_publication.get("title") or "")),
                    ("Рік", str(details.get("year") or selected_publication.get("year") or "н/д")),
                    (
                        "Викладачі",
                        ", ".join(str(item) for item in details.get("linked_teachers", []) if item) or "Немає",
                    ),
                ],
            )

            review_note = st.text_area(
                "Нотатка модератора",
                value=str(details.get("review_note") or ""),
                height=100,
                key=f"data_center_review_note_{publication_id}",
            )
            _render_review_actions(service, publication_id, review_note)

            with st.expander("Редагування запису", expanded=False):
                edited_title = st.text_input(
                    "Назва",
                    value=str(details.get("title") or selected_publication.get("title") or ""),
                    key=f"data_center_title_{publication_id}",
                )
                edit_columns = st.columns(2, gap="medium")
                edited_year_raw = edit_columns[0].text_input(
                    "Рік",
                    value="" if details.get("year") is None else str(details.get("year")),
                    key=f"data_center_year_{publication_id}",
                )
                edited_confidence = edit_columns[1].slider(
                    "Рівень довіри",
                    min_value=0.0,
                    max_value=1.0,
                    value=float(details.get("confidence") or selected_publication.get("confidence") or 0.0),
                    step=0.01,
                    key=f"data_center_confidence_{publication_id}",
                )
                edited_doi = st.text_input(
                    "DOI",
                    value=str(details.get("doi") or selected_publication.get("doi") or ""),
                    key=f"data_center_doi_{publication_id}",
                )
                edited_pub_type = st.text_input(
                    "Тип",
                    value=str(details.get("pub_type") or selected_publication.get("pub_type") or ""),
                    key=f"data_center_type_{publication_id}",
                )
                edited_source = st.text_input(
                    "Джерело",
                    value=str(details.get("source") or selected_publication.get("source") or ""),
                    key=f"data_center_source_{publication_id}",
                )
                edited_status = st.selectbox(
                    "Ручний статус",
                    ["Автостатус"] + REVIEW_OPTIONS,
                    index=(
                        ["Автостатус"] + REVIEW_OPTIONS
                    ).index(str(details.get("review_status") or "Автостатус"))
                    if str(details.get("review_status") or "Автостатус") in (["Автостатус"] + REVIEW_OPTIONS)
                    else 0,
                    key=f"data_center_status_{publication_id}",
                )

                if st.button(
                    "Зберегти зміни",
                    key=f"data_center_save_{publication_id}",
                    use_container_width=True,
                ):
                    edited_year = int(edited_year_raw) if edited_year_raw.strip().isdigit() else None
                    saved = service.update_publication_metadata(
                        publication_id,
                        title=edited_title,
                        year=edited_year,
                        doi=edited_doi,
                        pub_type=edited_pub_type,
                        source=edited_source,
                        confidence=edited_confidence,
                        review_note=review_note,
                    )
                    if edited_status == "Автостатус":
                        service.clear_publication_review_status(publication_id)
                    else:
                        service.set_publication_review_status(publication_id, edited_status, review_note=review_note)

                    if saved:
                        st.session_state[FLASH_KEY] = "Публікацію оновлено."
                        st.rerun()
                    st.error("Не вдалося зберегти зміни.")

                if st.button(
                    "Скинути ручний статус",
                    key=f"data_center_reset_status_{publication_id}",
                    use_container_width=True,
                ):
                    if service.clear_publication_review_status(publication_id):
                        st.session_state[FLASH_KEY] = "Ручний статус скинуто, знову діє автооцінка."
                        st.rerun()

            delete_confirm = st.checkbox(
                "Підтверджую повне видалення вибраної публікації",
                key=f"data_center_delete_{publication_id}",
            )
            if st.button(
                "Видалити проблемну публікацію",
                key=f"data_center_delete_button_{publication_id}",
                use_container_width=True,
                type="primary",
            ):
                if not delete_confirm:
                    st.warning("Спочатку підтвердіть видалення запису.")
                elif service.delete_publication(publication_id):
                    st.session_state[FLASH_KEY] = "Проблемну публікацію видалено з бази."
                    st.rerun()
                else:
                    st.error("Не вдалося видалити запис. Спробуйте ще раз.")
        else:
            render_empty_state(
                "Немає запису для дії",
                "Обраний фільтр не повернув проблемних публікацій.",
            )

    teacher_sections = st.columns(2, gap="large")
    with teacher_sections[0]:
        render_section_heading("Викладачі без зовнішніх профілів")
        without_profiles_frame = _teacher_gap_frame(teachers_without_profiles)
        if without_profiles_frame.empty:
            render_empty_state(
                "Усі мають профілі",
                "Зараз кожен викладач має хоча б один зовнішній ідентифікатор.",
            )
        else:
            st.dataframe(without_profiles_frame, use_container_width=True, hide_index=True)

    with teacher_sections[1]:
        render_section_heading("Викладачі без знайдених публікацій")
        without_publications_frame = _teacher_gap_frame(teachers_without_publications)
        if without_publications_frame.empty:
            render_empty_state(
                "Усі мають знайдені роботи",
                "Зараз у вибірці немає викладачів без жодної публікації.",
            )
        else:
            st.dataframe(without_publications_frame, use_container_width=True, hide_index=True)
