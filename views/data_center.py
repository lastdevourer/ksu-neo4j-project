from __future__ import annotations

import pandas as pd
import streamlit as st

from ui.components import (
    render_empty_state,
    render_fullscreen_dataframe_heading,
    render_header,
    render_key_value_card,
    render_section_heading,
    render_summary_strip,
    require_service,
)
from ui.formatters import audit_events_dataframe, duplicate_candidates_dataframe, publications_dataframe


FLASH_KEY = "data_center_flash"
PROBLEM_STATUSES = ["Кандидат", "Потребує перевірки", "Відхилено", "В чорному списку"]
REVIEW_OPTIONS = [
    "Підтверджено",
    "Офіційно підтверджено",
    "Відхилено",
    "В чорному списку",
]
SELFTEST_KEY = "data_center_selftest_results"
DATA_CENTER_EXPORT_OPTIONS = {
    "Проблемні записи": ("problematic_publications.csv", "problematic"),
    "Викладачі без профілів": ("teachers_without_profiles.csv", "without_profiles"),
    "Викладачі без публікацій": ("teachers_without_publications.csv", "without_publications"),
    "Журнал аудиту": ("audit_log.csv", "audit"),
    "Самоперевірка": ("selftest_results.csv", "selftest"),
}


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def _show_flash_message() -> None:
    message = st.session_state.pop(FLASH_KEY, "")
    if message:
        st.success(message)


def _run_selftest(service) -> list[dict[str, object]]:
    checks: list[tuple[str, str, callable]] = [
        ("overview", "Огляд бази", service.get_overview_counts),
        ("faculties", "Факультети", service.get_faculty_overview),
        ("departments", "Кафедри", service.get_department_overview),
        ("teachers", "Викладачі", service.get_teachers),
        ("publications", "Публікації", service.get_publications),
        ("sources", "Джерела публікацій", service.get_publication_source_summary),
        ("duplicates", "Пошук дублів", service.get_duplicate_publication_candidates),
        ("audit", "Журнал аудиту", lambda: service.get_audit_events(limit=10)),
    ]
    results: list[dict[str, object]] = []
    for code, label, callback in checks:
        try:
            payload = callback()
            if isinstance(payload, dict):
                size = len(payload.keys())
                summary = ", ".join(f"{key}: {value}" for key, value in list(payload.items())[:4])
            elif isinstance(payload, list):
                size = len(payload)
                summary = f"рядків: {size}"
            else:
                size = 1
                summary = str(payload)
            results.append(
                {
                    "code": code,
                    "label": label,
                    "status": "OK",
                    "size": size,
                    "summary": summary,
                    "error": "",
                }
            )
        except Exception as exc:  # pragma: no cover - UI smoke helper
            results.append(
                {
                    "code": code,
                    "label": label,
                    "status": "FAIL",
                    "size": 0,
                    "summary": "",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return results


def _selftest_frame(results: list[dict[str, object]]) -> pd.DataFrame:
    if not results:
        return pd.DataFrame()
    frame = pd.DataFrame(results)
    return frame.rename(
        columns={
            "label": "Перевірка",
            "status": "Статус",
            "size": "Результат",
            "summary": "Коротко",
            "error": "Помилка",
        }
    )[["Перевірка", "Статус", "Результат", "Коротко", "Помилка"]]


def _render_selftest_tab(service) -> None:
    render_section_heading(
        "Самоперевірка сценаріїв",
        "Швидка технічна перевірка основних потоків: структура, викладачі, публікації, дублікати, аудит і зведення.",
    )
    top = st.columns([0.95, 1.05], gap="large")
    with top[0]:
        if st.button("Запустити самоперевірку", use_container_width=True, key="run_data_center_selftest"):
            st.session_state[SELFTEST_KEY] = _run_selftest(service)
            st.rerun()
        st.caption(
            "Цей запуск не змінює дані в базі. Він просто проганяє ключові запити та допомагає швидко зловити регресії після імпорту або нових правок."
        )
    with top[1]:
        results = st.session_state.get(SELFTEST_KEY, [])
        if results:
            ok_count = sum(1 for row in results if row.get("status") == "OK")
            fail_count = sum(1 for row in results if row.get("status") == "FAIL")
            summary = st.columns(2, gap="medium")
            summary[0].metric("Успішні перевірки", ok_count)
            summary[1].metric("Проблемні перевірки", fail_count)
        else:
            render_empty_state("Самоперевірку ще не запускали", "Натисніть кнопку ліворуч, щоб отримати короткий технічний звіт по ключових сценаріях.")

    results = st.session_state.get(SELFTEST_KEY, [])
    if not results:
        return

    results_frame = _selftest_frame(results)
    render_fullscreen_dataframe_heading(
        "Результати самоперевірки",
        results_frame,
        key="data_center_selftest_fullscreen",
        caption="Зведення по технічній перевірці ключових запитів і сценаріїв.",
    )
    st.dataframe(results_frame, use_container_width=True, hide_index=True)
    st.download_button(
        "Експорт результатів самоперевірки CSV",
        _csv_bytes(results_frame),
        file_name="selftest_results.csv",
        mime="text/csv",
        use_container_width=True,
    )
    failed = [row for row in results if row.get("status") == "FAIL"]
    if failed:
        st.warning("Є проблемні перевірки. Найчастіше це означає, що зламався окремий запит або одна зі сторінок чекає іншу форму даних.")


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


def _normalized_duplicate_key(row: dict[str, object]) -> str:
    doi = str(row.get("doi") or "").strip().lower()
    if doi:
        return f"doi::{doi}"
    title = " ".join("".join(char.lower() if char.isalnum() else " " for char in str(row.get("title") or "")).split())
    year = str(row.get("year") or "").strip()
    return f"title::{title}|{year}"


def _build_duplicate_candidates(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        publication_id = str(row.get("id") or "").strip()
        title = str(row.get("title") or "").strip()
        if not publication_id or not title:
            continue
        key = _normalized_duplicate_key(row)
        if key in {"title::|", "title::"}:
            continue
        grouped.setdefault(key, []).append(row)

    results: list[dict[str, object]] = []
    for duplicate_key, items in grouped.items():
        if len(items) < 2:
            continue
        sorted_items = sorted(
            items,
            key=lambda item: (
                str(item.get("doi") or "") == "",
                -(int(item.get("year") or 0)),
                str(item.get("title") or ""),
            ),
        )
        for item in sorted_items:
            results.append(
                {
                    "duplicate_key": duplicate_key,
                    "id": str(item.get("id") or ""),
                    "title": str(item.get("title") or ""),
                    "year": item.get("year"),
                    "doi": str(item.get("doi") or ""),
                    "source": str(item.get("source") or ""),
                    "review_status": str(item.get("status") or ""),
                    "authors": list(item.get("authors") or []),
                    "authors_count": int(item.get("authors_count", 0) or 0),
                }
            )
    return results


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
        render_fullscreen_dataframe_heading(
            "Журнал аудиту",
            audit_frame,
            key="data_center_audit_fullscreen",
            caption="Повний журнал змін і модераційних дій.",
        )
        st.dataframe(audit_frame, use_container_width=True, hide_index=True)
        st.download_button(
            "Експорт аудиту CSV",
            _csv_bytes(audit_frame),
            file_name="audit_log.csv",
            mime="text/csv",
            use_container_width=True,
        )
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


def _render_duplicate_candidates(service, all_publications: list[dict[str, object]]) -> None:
    render_section_heading(
        "Підозра на дублювання",
        "Система показує збіги за DOI або дуже схожі повтори записів, щоб їх можна було швидко перевірити.",
    )
    rows = _build_duplicate_candidates(all_publications)
    duplicate_frame = duplicate_candidates_dataframe(rows)
    if duplicate_frame.empty:
        render_empty_state("Підозрілих дублів не знайдено", "Зараз база не містить повторів, які потрапили під правила пошуку дублювання.")
        return

    top = st.columns([1.18, 0.82], gap="large")
    with top[0]:
        render_fullscreen_dataframe_heading(
            "Підозра на дублювання",
            duplicate_frame,
            key="data_center_duplicates_fullscreen",
            caption="Розширений перегляд підозрілих дублів публікацій.",
        )
        st.dataframe(duplicate_frame, use_container_width=True, hide_index=True)
    with top[1]:
        render_key_value_card(
            "Огляд дублювання",
            [
                ("Підозрілих записів", str(len(rows))),
                ("Ключів дубля", str(len({str(row.get('duplicate_key') or '') for row in rows if row.get('duplicate_key')}))),
            ],
        )
        st.download_button(
            "Експорт CSV",
            _csv_bytes(duplicate_frame),
            file_name="duplicate_candidates.csv",
            mime="text/csv",
            use_container_width=True,
        )

    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        key = str(row.get("duplicate_key") or "").strip()
        grouped.setdefault(key, []).append(row)

    selected_group = st.selectbox("Група дубля", list(grouped.keys()), key="duplicate_group_select")
    group_rows = grouped[selected_group]
    group_options = {
        f"{row.get('title', 'Без назви')} | {row.get('year', 'н/д')} | {row.get('id', '')}": str(row.get("id") or "").strip()
        for row in group_rows
        if row.get("id")
    }
    if len(group_options) >= 2:
        action_columns = st.columns([1.05, 0.95], gap="large")
        with action_columns[0]:
            canonical_label = st.selectbox("Основний запис", list(group_options.keys()), key="duplicate_canonical")
            canonical_id = group_options[canonical_label]
            merge_candidates = {
                label: pub_id
                for label, pub_id in group_options.items()
                if pub_id != canonical_id
            }
            merge_labels = st.multiselect(
                "Записи для злиття",
                list(merge_candidates.keys()),
                key="duplicate_merge_candidates",
                placeholder="Оберіть дублікати, які треба злити",
            )
        with action_columns[1]:
            render_key_value_card(
                "Керування дублями",
                [
                    ("Група", selected_group[:48] + ("…" if len(selected_group) > 48 else "")),
                    ("Записів у групі", str(len(group_rows))),
                    ("Обрано для злиття", str(len(merge_labels))),
                ],
            )
            merge_confirm = st.checkbox(
                "Підтверджую злиття дубльованих записів",
                key="duplicate_merge_confirm",
            )
            if st.button("Злити вибрані дублікати", use_container_width=True, type="primary"):
                if not merge_labels:
                    st.warning("Оберіть хоча б один дубль для злиття.")
                elif not merge_confirm:
                    st.warning("Підтвердіть злиття перед виконанням дії.")
                else:
                    merged = 0
                    for label in merge_labels:
                        duplicate_id = merge_candidates[label]
                        if service.merge_publications(canonical_id, duplicate_id):
                            merged += 1
                    st.session_state[FLASH_KEY] = f"Успішно злито {merged} дубльованих записів."
                    st.rerun()


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

    moderation_tab, manual_tab, audit_tab, selftest_tab = st.tabs(["Модерація", "Ручне додавання", "Аудит", "Самоперевірка"])

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

        export_choice = st.selectbox(
            "Експорт з центру даних",
            ["Проблемні записи", "Викладачі без профілів", "Викладачі без публікацій"],
            key="data_center_export_choice",
        )
        export_frames = {
            "problematic": publications_dataframe(filtered_problematic) if filtered_problematic else pd.DataFrame(columns=["Назва"]),
            "without_profiles": _teacher_gap_frame(teachers_without_profiles) if teachers_without_profiles else pd.DataFrame(columns=["ПІБ"]),
            "without_publications": _teacher_gap_frame(teachers_without_publications) if teachers_without_publications else pd.DataFrame(columns=["ПІБ"]),
        }
        export_file_name, export_key = DATA_CENTER_EXPORT_OPTIONS[export_choice]
        st.download_button(
            f"Завантажити: {export_choice}",
            _csv_bytes(export_frames[export_key]),
            file_name=export_file_name,
            mime="text/csv",
            use_container_width=True,
            key="data_center_export_download",
        )

        moderation_layout = st.columns([1.1, 0.9], gap="large")
        with moderation_layout[0]:
            if filtered_problematic:
                problem_frame = publications_dataframe(filtered_problematic)
                render_fullscreen_dataframe_heading(
                    "Проблемні записи",
                    problem_frame,
                    key="data_center_problematic_fullscreen",
                    caption="Повний список кандидатів, сумнівних і відхилених записів.",
                )
                st.dataframe(problem_frame, use_container_width=True, hide_index=True)
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
            without_profiles_frame = _teacher_gap_frame(teachers_without_profiles)
            if without_profiles_frame.empty:
                render_section_heading("Викладачі без зовнішніх профілів")
                render_empty_state("Усі мають профілі", "Зараз у кожного викладача є хоча б один зовнішній ідентифікатор.")
            else:
                render_fullscreen_dataframe_heading(
                    "Викладачі без зовнішніх профілів",
                    without_profiles_frame,
                    key="data_center_no_profiles_fullscreen",
                    caption="Перелік викладачів, яким ще бракує зовнішніх ідентифікаторів.",
                )
                st.dataframe(without_profiles_frame, use_container_width=True, hide_index=True)

        with teacher_sections[1]:
            without_publications_frame = _teacher_gap_frame(teachers_without_publications)
            if without_publications_frame.empty:
                render_section_heading("Викладачі без знайдених публікацій")
                render_empty_state("Усі мають знайдені роботи", "Зараз у вибірці немає викладачів без жодної публікації.")
            else:
                render_fullscreen_dataframe_heading(
                    "Викладачі без знайдених публікацій",
                    without_publications_frame,
                    key="data_center_no_publications_fullscreen",
                    caption="Перелік викладачів, для яких ще не знайдено публікацій.",
                )
                st.dataframe(without_publications_frame, use_container_width=True, hide_index=True)

        _render_duplicate_candidates(service, all_publications)

    with manual_tab:
        _render_manual_add(service, all_teachers, departments)

    with audit_tab:
        _render_audit_tab(service)

    with selftest_tab:
        _render_selftest_tab(service)
