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
from ui.formatters import audit_events_dataframe, publications_dataframe


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
    top_columns = st.columns(2, gap="medium")
    if top_columns[0].button("Підтвердити", key=f"review_confirm_{publication_id}", use_container_width=True):
        if service.set_publication_review_status(publication_id, "Підтверджено", review_note=review_note):
            st.session_state[FLASH_KEY] = "Статус публікації оновлено на 'Підтверджено'."
            st.rerun()
    if top_columns[1].button(
        "Офіційно підтвердити",
        key=f"review_official_{publication_id}",
        use_container_width=True,
    ):
        if service.set_publication_review_status(publication_id, "Офіційно підтверджено", review_note=review_note):
            st.session_state[FLASH_KEY] = "Статус публікації оновлено на 'Офіційно підтверджено'."
            st.rerun()

    bottom_columns = st.columns(3, gap="medium")
    if bottom_columns[0].button("Відхилити", key=f"review_reject_{publication_id}", use_container_width=True):
        if service.set_publication_review_status(publication_id, "Відхилено", review_note=review_note):
            st.session_state[FLASH_KEY] = "Публікацію відхилено."
            st.rerun()
    if bottom_columns[1].button(
        "В чорний список",
        key=f"review_blacklist_{publication_id}",
        use_container_width=True,
    ):
        if service.set_publication_review_status(publication_id, "В чорному списку", review_note=review_note):
            st.session_state[FLASH_KEY] = "Публікацію додано до чорного списку."
            st.rerun()
    if bottom_columns[2].button(
        "Скинути статус",
        key=f"review_reset_{publication_id}",
        use_container_width=True,
    ):
        if service.clear_publication_review_status(publication_id):
            st.session_state[FLASH_KEY] = "Ручний статус скинуто."
            st.rerun()


def _render_bulk_actions(service, rows: list[dict[str, object]]) -> None:
    render_section_heading("Масові дії", "Швидке очищення та модерація вибраної групи записів.")
    if not rows:
        render_empty_state("Немає вибірки", "Спочатку оберіть проблемні публікації для групової обробки.")
        return

    option_map = {_problem_publication_option(row): row for row in rows}
    selected_labels = st.multiselect(
        "Обрати публікації",
        list(option_map.keys()),
        placeholder="Позначте записи для групової дії",
    )
    selected_rows = [option_map[label] for label in selected_labels]
    selected_ids = [str(row.get("id") or "").strip() for row in selected_rows if row.get("id")]

    bulk_columns = st.columns([1.05, 0.95], gap="large")
    with bulk_columns[0]:
        render_key_value_card(
            "Поточна вибірка",
            [
                ("Позначено записів", str(len(selected_ids))),
                (
                    "Статуси",
                    ", ".join(sorted({str(row.get("status") or "") for row in selected_rows if row.get("status")})) or "—",
                ),
            ],
        )
    with bulk_columns[1]:
        bulk_status = st.selectbox("Масовий статус", REVIEW_OPTIONS, key="bulk_status")
        bulk_note = st.text_area(
            "Єдина нотатка для вибірки",
            key="bulk_note",
            height=92,
            placeholder="Наприклад: перевірено вручну або помилковий матч.",
        )

    action_columns = st.columns(2, gap="medium")
    if action_columns[0].button("Застосувати статус до вибраних", use_container_width=True):
        if not selected_ids:
            st.warning("Спочатку оберіть публікації для масової модерації.")
        else:
            updated = service.bulk_set_publication_review_status(selected_ids, bulk_status, review_note=bulk_note)
            st.session_state[FLASH_KEY] = f"Масово оновлено {updated} публікацій."
            st.rerun()

    delete_confirm = st.checkbox(
        "Підтверджую масове видалення вибраних публікацій",
        key="bulk_delete_confirm",
    )
    if action_columns[1].button("Видалити вибрані з бази", use_container_width=True, type="primary"):
        if not selected_ids:
            st.warning("Немає вибраних записів для видалення.")
        elif not delete_confirm:
            st.warning("Підтвердіть масове видалення перед виконанням дії.")
        else:
            deleted = service.bulk_delete_publications(selected_ids)
            st.session_state[FLASH_KEY] = f"Масово видалено {deleted} публікацій."
            st.rerun()


def _render_manual_add(service, teachers: list[dict[str, object]], departments: list[dict[str, object]]) -> None:
    render_section_heading(
        "Ручне додавання публікації",
        "Додавайте перевірені записи вручну, якщо автоматичний імпорт нічого не знайшов або потребує корекції.",
    )

    department_options = {"Усі кафедри": ""}
    for row in departments:
        code = str(row.get("code") or "").strip()
        label = str(row.get("name") or code or "Без назви")
        if code:
            department_options[label] = code

    selected_department_label = st.selectbox("Фільтр викладачів за кафедрою", list(department_options.keys()))
    selected_department_code = department_options[selected_department_label]
    filtered_teachers = [
        row
        for row in teachers
        if not selected_department_code or str(row.get("department_code") or "").strip() == selected_department_code
    ]
    teacher_labels = {
        (
            f"{row.get('full_name', 'Без ПІБ')} | "
            f"{row.get('department_name', 'Без кафедри')} | "
            f"{row.get('id', '')}"
        ): str(row.get("id") or "").strip()
        for row in filtered_teachers
        if row.get("id")
    }

    with st.form("manual_publication_form", clear_on_submit=False):
        title = st.text_input("Назва публікації", placeholder="Введіть повну назву")
        top_columns = st.columns(3, gap="medium")
        year_raw = top_columns[0].text_input("Рік", placeholder="2024")
        doi = top_columns[1].text_input("DOI", placeholder="10.xxxx/xxxxx")
        pub_type = top_columns[2].text_input("Тип", value="article")

        source_columns = st.columns(3, gap="medium")
        source = source_columns[0].text_input("Джерело", value="Ручне додавання")
        confidence = source_columns[1].slider("Рівень довіри", 0.0, 1.0, 1.0, 0.01)
        review_status = source_columns[2].selectbox("Статус", REVIEW_OPTIONS, index=0)

        teacher_selection = st.multiselect(
            "Прив'язати до викладачів",
            list(teacher_labels.keys()),
            placeholder="Оберіть одного або кількох викладачів",
        )
        extra_authors = st.text_area(
            "Додаткові автори",
            placeholder="Через кому, якщо потрібно додати співавторів поза базою.",
            height=80,
        )
        review_note = st.text_area(
            "Нотатка модератора",
            placeholder="Короткий коментар про походження або перевірку запису.",
            height=80,
        )

        submitted = st.form_submit_button("Додати публікацію", use_container_width=True, type="primary")

    if submitted:
        year = int(year_raw) if year_raw.strip().isdigit() else None
        teacher_ids = [teacher_labels[label] for label in teacher_selection if label in teacher_labels]
        authors_snapshot = [item.strip() for item in extra_authors.split(",") if item.strip()]
        result = service.create_manual_publication(
            title=title,
            year=year,
            doi=doi,
            pub_type=pub_type,
            source=source,
            teacher_ids=teacher_ids,
            authors_snapshot=authors_snapshot,
            confidence=confidence,
            review_status=review_status,
            review_note=review_note,
        )
        if result.get("created"):
            if result.get("matched_existing"):
                st.session_state[FLASH_KEY] = "Знайдено наявну публікацію та додано нові зв'язки з викладачами."
            else:
                st.session_state[FLASH_KEY] = "Публікацію успішно додано вручну."
            st.rerun()
        st.error("Не вдалося додати публікацію. Перевірте назву та список викладачів.")


def _render_audit_tab(service) -> None:
    render_section_heading("Журнал аудиту", "Усі ключові зміни по публікаціях та модерації зберігаються для контролю.")
    events = service.get_audit_events(limit=120)
    if not events:
        render_empty_state("Журнал поки порожній", "Після змін у базі тут з'явиться історія дій.")
        return

    audit_frame = audit_events_dataframe(events)
    if audit_frame.empty:
        render_empty_state("Журнал поки порожній", "Ще не зафіксовано змін для показу.")
        return

    top = st.columns([1.2, 0.8], gap="large")
    with top[0]:
        st.dataframe(audit_frame, use_container_width=True, hide_index=True)
    with top[1]:
        last_event = events[0]
        render_key_value_card(
            "Остання дія",
            [
                ("Час", str(last_event.get("created_at") or "")),
                ("Дія", str(last_event.get("action") or "")),
                ("Сутність", str(last_event.get("entity_type") or "")),
                ("ID", str(last_event.get("entity_id") or "")),
                ("Ініціатор", str(last_event.get("actor") or "")),
            ],
        )


def _render_publication_detail(service, selected_publication: dict[str, object]) -> None:
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
        review_status_options = ["Автостатус"] + REVIEW_OPTIONS
        current_review_status = str(details.get("review_status") or "Автостатус")
        edited_status = st.selectbox(
            "Ручний статус",
            review_status_options,
            index=review_status_options.index(current_review_status) if current_review_status in review_status_options else 0,
            key=f"data_center_status_{publication_id}",
        )

        if st.button("Зберегти зміни", key=f"data_center_save_{publication_id}", use_container_width=True):
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

    delete_confirm = st.checkbox(
        "Підтверджую повне видалення вибраної публікації",
        key=f"data_center_delete_{publication_id}",
    )
    if st.button(
        "Видалити публікацію з бази",
        key=f"data_center_delete_button_{publication_id}",
        use_container_width=True,
        type="primary",
    ):
        if not delete_confirm:
            st.warning("Спочатку підтвердіть видалення запису.")
        elif service.delete_publication(publication_id):
            st.session_state[FLASH_KEY] = "Публікацію видалено з бази."
            st.rerun()
        else:
            st.error("Не вдалося видалити запис. Спробуйте ще раз.")


def render() -> None:
    service = require_service()
    render_header("Центр даних", subtitle="Модерація, ручне додавання та контроль змін у єдиному просторі.")
    _show_flash_message()

    all_teachers = service.get_teachers()
    all_publications = service.get_publications()
    departments = service.get_departments()

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
        render_summary_strip("Усього публікацій", str(len(all_publications)))

    moderation_tab, manual_tab, audit_tab = st.tabs(["Модерація", "Ручне додавання", "Аудит"])

    with moderation_tab:
        render_section_heading("Проблемні записи", "Працюйте з кандидатами, сумнівними матчами та відхиленими роботами.")
        filter_columns = st.columns([1.2, 0.8], gap="large")
        search_value = filter_columns[0].text_input(
            "Пошук за назвою, DOI або джерелом",
            placeholder="Введіть фрагмент назви, DOI або джерело",
        ).strip().lower()
        status_filter = filter_columns[1].selectbox(
            "Статус вибірки",
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

        moderation_layout = st.columns([1.1, 0.9], gap="large")
        with moderation_layout[0]:
            if filtered_problematic:
                st.dataframe(publications_dataframe(filtered_problematic), use_container_width=True, hide_index=True)
                _render_bulk_actions(service, filtered_problematic)
            else:
                render_empty_state(
                    "Проблемних публікацій не знайдено",
                    "Після поточної фільтрації не залишилося записів, які потребують ручної уваги.",
                )

        with moderation_layout[1]:
            if filtered_problematic:
                publication_map = {_problem_publication_option(row): row for row in filtered_problematic}
                selected_label = st.selectbox("Обрати запис", list(publication_map.keys()))
                _render_publication_detail(service, publication_map[selected_label])
            else:
                render_empty_state("Немає запису для дії", "Оберіть інший фільтр або дочекайтеся нових результатів імпорту.")

        teacher_sections = st.columns(2, gap="large")
        with teacher_sections[0]:
            render_section_heading("Викладачі без зовнішніх профілів")
            without_profiles_frame = _teacher_gap_frame(teachers_without_profiles)
            if without_profiles_frame.empty:
                render_empty_state("Усі мають профілі", "Зараз у кожного викладача є хоча б один зовнішній ідентифікатор.")
            else:
                st.dataframe(without_profiles_frame, use_container_width=True, hide_index=True)

        with teacher_sections[1]:
            render_section_heading("Викладачі без знайдених публікацій")
            without_publications_frame = _teacher_gap_frame(teachers_without_publications)
            if without_publications_frame.empty:
                render_empty_state("Усі мають знайдені роботи", "Зараз у вибірці немає викладачів без жодної публікації.")
            else:
                st.dataframe(without_publications_frame, use_container_width=True, hide_index=True)

    with manual_tab:
        _render_manual_add(service, all_teachers, departments)

    with audit_tab:
        _render_audit_tab(service)
