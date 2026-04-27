from __future__ import annotations

import pandas as pd
import streamlit as st

from config import get_publication_import_config
from data.loaders import load_teachers_seed
from data.seed_data import DEPARTMENTS, FACULTIES
from services.publication_import import PublicationImportService
from ui.components import (
    render_empty_state,
    render_fullscreen_bar_chart_button,
    render_fullscreen_dataframe_button,
    render_header,
    render_section_heading,
    render_summary_strip,
    require_service,
)
from ui.formatters import (
    department_overview_dataframe,
    faculty_overview_dataframe,
    publication_sources_dataframe,
    teachers_dataframe,
)


FLASH_KEY = "structure_flash"


def _show_flash_message() -> None:
    message = st.session_state.pop(FLASH_KEY, "")
    if message:
        st.success(message)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def _teacher_option(row: dict[str, object]) -> str:
    return f"{row.get('full_name', 'Без ПІБ')} | {row.get('department_name', 'Без кафедри')} | {row.get('id', '')}"


def _teacher_has_any_profile(row: dict[str, object]) -> bool:
    return any(
        str(row.get(field) or "").strip()
        for field in ("orcid", "google_scholar", "scopus", "web_of_science", "profile_url")
    )


def _filter_teachers(
    rows: list[dict[str, object]],
    *,
    faculty_code: str,
    profile_mode: str,
) -> list[dict[str, object]]:
    filtered = rows
    if faculty_code:
        filtered = [row for row in filtered if str(row.get("faculty_code") or "") == faculty_code]

    if profile_mode == "З профілями":
        filtered = [row for row in filtered if _teacher_has_any_profile(row)]
    elif profile_mode == "Без профілів":
        filtered = [row for row in filtered if not _teacher_has_any_profile(row)]
    elif profile_mode == "Лише ORCID":
        filtered = [row for row in filtered if str(row.get("orcid") or "").strip()]

    return filtered


def _render_faculty_department_tab(service) -> None:
    render_section_heading("Довідник структури", "Офіційний контур університетської структури з пошуком, фільтрацією та ручним редагуванням.")

    with st.expander("Сервісні дії зі структурою", expanded=False):
        action_columns = st.columns(3, gap="medium")
        if action_columns[0].button("Створити схему та індекси", use_container_width=True):
            service.prepare_database()
            st.session_state[FLASH_KEY] = "Обмеження та індекси Neo4j підготовлено."
            st.rerun()
        if action_columns[1].button("Оновити факультети та кафедри", use_container_width=True):
            service.seed_reference_data(FACULTIES, DEPARTMENTS)
            st.session_state[FLASH_KEY] = "Довідник факультетів і кафедр оновлено."
            st.rerun()
        action_columns[2].download_button(
            "Експорт seed-структури",
            _csv_bytes(pd.DataFrame(DEPARTMENTS)),
            file_name="departments_seed.csv",
            mime="text/csv",
            use_container_width=True,
        )

    faculties = service.get_faculties()
    departments = service.get_departments()
    raw_faculty_rows = service.get_faculty_overview()
    raw_department_rows = service.get_department_overview()

    filter_columns = st.columns([0.8, 1.2, 0.75], gap="medium")
    faculty_search = filter_columns[0].text_input("Пошук факультету", placeholder="Назва або код").strip().lower()
    faculty_options = {"Усі факультети": ""} | {
        f"{row['name']} ({row['code']})": str(row["code"]) for row in faculties if row.get("code")
    }
    selected_faculty_code = filter_columns[1].selectbox(
        "Фільтр кафедр за факультетом",
        list(faculty_options.keys()),
        key="structure_faculty_filter",
    )
    department_search = filter_columns[2].text_input("Пошук кафедри", placeholder="Назва або код").strip().lower()

    filtered_faculty_rows = raw_faculty_rows
    if faculty_search:
        filtered_faculty_rows = [
            row
            for row in filtered_faculty_rows
            if faculty_search in str(row.get("name") or "").lower()
            or faculty_search in str(row.get("code") or "").lower()
        ]

    filtered_department_rows = raw_department_rows
    faculty_filter_code = faculty_options[selected_faculty_code]
    if faculty_filter_code:
        filtered_department_rows = [
            row for row in filtered_department_rows if str(row.get("faculty_code") or "") == faculty_filter_code
        ]
    if department_search:
        filtered_department_rows = [
            row
            for row in filtered_department_rows
            if department_search in str(row.get("name") or "").lower()
            or department_search in str(row.get("code") or "").lower()
        ]

    faculty_frame = faculty_overview_dataframe(filtered_faculty_rows)
    department_frame = department_overview_dataframe(filtered_department_rows)

    summary = st.columns(3, gap="medium")
    with summary[0]:
        render_summary_strip("У фокусі", str(len(filtered_faculty_rows)), "факультетів у поточному зрізі")
    with summary[1]:
        render_summary_strip("Кафедри у фокусі", str(len(filtered_department_rows)), "після пошуку та фільтрів")
    with summary[2]:
        render_summary_strip("Повна структура", f"{len(raw_faculty_rows)} / {len(raw_department_rows)}", "факультети / кафедри в базі")

    tables = st.columns([0.92, 1.08], gap="large")
    with tables[0]:
        header_columns = st.columns([0.72, 0.28], gap="small")
        with header_columns[0]:
            render_section_heading("Факультети")
        with header_columns[1]:
            if not faculty_frame.empty:
                actions = st.columns(2, gap="small")
                with actions[0]:
                    render_fullscreen_dataframe_button(
                        "Факультети",
                        faculty_frame,
                        key="structure_faculties_fullscreen",
                        caption="Повний перегляд факультетного зрізу.",
                    )
                with actions[1]:
                    st.download_button(
                        "CSV",
                        _csv_bytes(faculty_frame),
                        file_name="faculties_filtered.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_filtered_faculties",
                    )
        if faculty_frame.empty:
            render_empty_state("Факультети не знайдено", "Змініть пошук або оновіть довідник структури.")
        else:
            st.dataframe(faculty_frame, use_container_width=True, hide_index=True)

    with tables[1]:
        header_columns = st.columns([0.72, 0.28], gap="small")
        with header_columns[0]:
            render_section_heading("Кафедри")
        with header_columns[1]:
            if not department_frame.empty:
                actions = st.columns(2, gap="small")
                with actions[0]:
                    render_fullscreen_dataframe_button(
                        "Кафедри",
                        department_frame,
                        key="structure_departments_fullscreen",
                        caption="Повний перелік кафедр з поточними фільтрами.",
                    )
                with actions[1]:
                    st.download_button(
                        "CSV",
                        _csv_bytes(department_frame),
                        file_name="departments_filtered.csv",
                        mime="text/csv",
                        use_container_width=True,
                        key="download_filtered_departments",
                    )
        if department_frame.empty:
            render_empty_state("Кафедри не знайдено", "Спробуйте інший факультет або скоригуйте пошук.")
        else:
            st.dataframe(department_frame, use_container_width=True, hide_index=True)

    edit_columns = st.columns(2, gap="large")
    faculty_edit_map = {"Новий факультет": None} | {
        f"{row['name']} ({row['code']})": row for row in faculties if row.get("code")
    }
    with edit_columns[0]:
        with st.expander("Додати або редагувати факультет", expanded=False):
            selected_faculty_label = st.selectbox("Факультет", list(faculty_edit_map.keys()), key="structure_faculty_select")
            selected_faculty = faculty_edit_map[selected_faculty_label]
            faculty_code_default = str(selected_faculty.get("code") or "") if selected_faculty else ""
            faculty_name_default = str(selected_faculty.get("name") or "") if selected_faculty else ""

            faculty_code = st.text_input("Код факультету", value=faculty_code_default, key="structure_faculty_code").strip()
            faculty_name = st.text_input("Назва факультету", value=faculty_name_default, key="structure_faculty_name").strip()
            faculty_actions = st.columns(2, gap="medium")
            if faculty_actions[0].button("Зберегти факультет", use_container_width=True, key="structure_save_faculty"):
                if not faculty_code or not faculty_name:
                    st.warning("Вкажіть код і назву факультету.")
                elif service.upsert_faculty(code=faculty_code, name=faculty_name):
                    st.session_state[FLASH_KEY] = f"Факультет '{faculty_name}' збережено."
                    st.rerun()
            delete_faculty_confirm = st.checkbox(
                "Підтверджую видалення факультету без кафедр",
                key="structure_delete_faculty_confirm",
            )
            if faculty_actions[1].button(
                "Видалити факультет",
                use_container_width=True,
                key="structure_delete_faculty",
                type="primary",
            ):
                if not selected_faculty:
                    st.warning("Спочатку оберіть факультет для видалення.")
                elif not delete_faculty_confirm:
                    st.warning("Підтвердіть видалення факультету.")
                else:
                    result = service.delete_faculty(str(selected_faculty.get("code") or ""))
                    if result.get("deleted"):
                        st.session_state[FLASH_KEY] = "Факультет видалено."
                        st.rerun()
                    elif result.get("reason") == "has_departments":
                        st.error(f"Факультет не можна видалити: до нього прив'язано кафедр {result.get('departments', 0)}.")
                    else:
                        st.error("Не вдалося видалити факультет.")

    department_edit_map = {"Нова кафедра": None} | {
        f"{row['name']} ({row['code']})": row for row in departments if row.get("code")
    }
    faculty_choice_map = {f"{row['name']} ({row['code']})": str(row["code"]) for row in faculties if row.get("code")}
    with edit_columns[1]:
        with st.expander("Додати або редагувати кафедру", expanded=False):
            selected_department_label = st.selectbox(
                "Кафедра",
                list(department_edit_map.keys()),
                key="structure_department_select",
            )
            selected_department = department_edit_map[selected_department_label]
            department_code_default = str(selected_department.get("code") or "") if selected_department else ""
            department_name_default = str(selected_department.get("name") or "") if selected_department else ""
            department_faculty_default = str(selected_department.get("faculty_code") or "") if selected_department else ""
            department_faculty_label_default = next(
                (label for label, code in faculty_choice_map.items() if code == department_faculty_default),
                next(iter(faculty_choice_map.keys()), None),
            )

            department_code = st.text_input("Код кафедри", value=department_code_default, key="structure_department_code").strip()
            department_name = st.text_input("Назва кафедри", value=department_name_default, key="structure_department_name").strip()
            selected_faculty_label_for_department = (
                st.selectbox(
                    "Факультет для кафедри",
                    list(faculty_choice_map.keys()),
                    index=(list(faculty_choice_map.keys()).index(department_faculty_label_default) if department_faculty_label_default in faculty_choice_map else 0),
                    key="structure_department_faculty",
                )
                if faculty_choice_map
                else None
            )

            department_actions = st.columns(2, gap="medium")
            if department_actions[0].button("Зберегти кафедру", use_container_width=True, key="structure_save_department"):
                if not faculty_choice_map:
                    st.warning("Спочатку створіть хоча б один факультет.")
                elif not department_code or not department_name:
                    st.warning("Вкажіть код і назву кафедри.")
                else:
                    faculty_code = faculty_choice_map[selected_faculty_label_for_department]
                    if service.upsert_department(code=department_code, faculty_code=faculty_code, name=department_name):
                        st.session_state[FLASH_KEY] = f"Кафедру '{department_name}' збережено."
                        st.rerun()
                    st.error("Не вдалося зберегти кафедру. Перевірте, чи існує вибраний факультет.")

            delete_department_confirm = st.checkbox(
                "Підтверджую видалення кафедри без викладачів",
                key="structure_delete_department_confirm",
            )
            if department_actions[1].button(
                "Видалити кафедру",
                use_container_width=True,
                key="structure_delete_department",
                type="primary",
            ):
                if not selected_department:
                    st.warning("Спочатку оберіть кафедру для видалення.")
                elif not delete_department_confirm:
                    st.warning("Підтвердіть видалення кафедри.")
                else:
                    result = service.delete_department(str(selected_department.get("code") or ""))
                    if result.get("deleted"):
                        st.session_state[FLASH_KEY] = "Кафедру видалено."
                        st.rerun()
                    elif result.get("reason") == "has_teachers":
                        st.error(f"Кафедру не можна видалити: до неї прив'язано викладачів {result.get('teachers', 0)}.")
                    else:
                        st.error("Не вдалося видалити кафедру.")


def _render_teachers_tab(service) -> None:
    render_section_heading("Керування викладачами", "Створюйте, редагуйте, фільтруйте, масово очищуйте та швидко вивантажуйте склад викладачів.")

    all_teachers = service.get_teachers()
    departments = service.get_departments()
    faculties = service.get_faculties()

    with st.expander("Сервісні дії з викладачами", expanded=False):
        action_columns = st.columns([1.0, 1.0, 1.1], gap="medium")
        if action_columns[0].button("Завантажити викладачів KSPU", use_container_width=True):
            service.seed_reference_data(FACULTIES, DEPARTMENTS)
            seed_teachers = load_teachers_seed()
            service.seed_teachers(seed_teachers)
            st.session_state[FLASH_KEY] = f"Завантажено {len(seed_teachers)} викладачів KSPU."
            st.rerun()

        action_columns[1].download_button(
            "Експорт усіх викладачів CSV",
            _csv_bytes(teachers_dataframe(all_teachers) if all_teachers else pd.DataFrame(columns=["ID"])),
            file_name="teachers_export.csv",
            mime="text/csv",
            use_container_width=True,
        )

        delete_teachers_confirm = action_columns[2].checkbox(
            "Підтверджую повне очищення викладачів і публікацій",
            key="delete_teachers_confirm",
        )
        if st.button(
            "Очистити всіх викладачів і публікації",
            use_container_width=True,
            type="primary",
            key="structure_delete_all_teachers",
        ):
            if not delete_teachers_confirm:
                st.warning("Підтвердіть очищення викладачів і публікацій перед виконанням дії.")
            else:
                result = service.delete_all_teachers_and_publications()
                st.session_state[FLASH_KEY] = (
                    f"Очищено викладачів: {result['teachers']}, публікацій: {result['publications']}."
                )
                st.rerun()

    teacher_filter_columns = st.columns([1.0, 1.0, 1.0, 0.85], gap="medium")
    teacher_search = teacher_filter_columns[0].text_input("Пошук викладача", placeholder="ПІБ або ID").strip()
    faculty_filter_options = {"Усі факультети": ""} | {
        f"{row['name']} ({row['code']})": str(row["code"]) for row in faculties if row.get("code")
    }
    faculty_filter_label = teacher_filter_columns[1].selectbox(
        "Факультет",
        list(faculty_filter_options.keys()),
        key="structure_teacher_faculty_filter",
    )
    department_filter_options = {"Усі кафедри": ""} | {
        f"{row['name']} ({row['code']})": str(row["code"]) for row in departments if row.get("code")
    }
    department_filter_label = teacher_filter_columns[2].selectbox(
        "Кафедра",
        list(department_filter_options.keys()),
        key="structure_teacher_department_filter",
    )
    profile_mode = teacher_filter_columns[3].selectbox(
        "Профіль",
        ["Усі", "З профілями", "Без профілів", "Лише ORCID"],
        key="structure_teacher_profile_filter",
    )

    base_teachers = service.get_teachers(
        search=teacher_search,
        department_code=department_filter_options[department_filter_label],
    )
    filtered_teachers = _filter_teachers(
        base_teachers,
        faculty_code=faculty_filter_options[faculty_filter_label],
        profile_mode=profile_mode,
    )

    teachers_with_profiles = sum(1 for row in filtered_teachers if _teacher_has_any_profile(row))
    teachers_without_profiles = len(filtered_teachers) - teachers_with_profiles
    total_publications = sum(int(row.get("publications") or 0) for row in filtered_teachers)

    summary = st.columns(3, gap="medium")
    with summary[0]:
        render_summary_strip("Викладачі у фокусі", str(len(filtered_teachers)), "поточний відфільтрований список")
    with summary[1]:
        render_summary_strip("З профілями", str(teachers_with_profiles), "ORCID, Scholar, Scopus, WoS або профіль кафедри")
    with summary[2]:
        render_summary_strip("Публікації у зрізі", str(total_publications), "сума робіт у поточному списку")

    department_options = {f"{row['name']} ({row['code']})": str(row["code"]) for row in departments if row.get("code")}
    teacher_map = {"Новий викладач": None} | {
        _teacher_option(row): row for row in all_teachers if row.get("id")
    }

    edit_columns = st.columns([1.05, 0.95], gap="large")
    with edit_columns[0]:
        with st.expander("Додати або редагувати викладача", expanded=False):
            selected_teacher_label = st.selectbox("Профіль викладача", list(teacher_map.keys()), key="structure_teacher_select")
            selected_teacher = teacher_map[selected_teacher_label]
            teacher_id_default = str(selected_teacher.get("id") or "") if selected_teacher else ""
            full_name_default = str(selected_teacher.get("full_name") or "") if selected_teacher else ""
            position_default = str(selected_teacher.get("position") or "") if selected_teacher else ""
            degree_default = str(selected_teacher.get("academic_degree") or "") if selected_teacher else ""
            title_default = str(selected_teacher.get("academic_title") or "") if selected_teacher else ""
            orcid_default = str(selected_teacher.get("orcid") or "") if selected_teacher else ""
            scholar_default = str(selected_teacher.get("google_scholar") or "") if selected_teacher else ""
            scopus_default = str(selected_teacher.get("scopus") or "") if selected_teacher else ""
            wos_default = str(selected_teacher.get("web_of_science") or "") if selected_teacher else ""
            profile_url_default = str(selected_teacher.get("profile_url") or "") if selected_teacher else ""
            department_code_default = str(selected_teacher.get("department_code") or "") if selected_teacher else ""
            department_label_default = next(
                (label for label, code in department_options.items() if code == department_code_default),
                next(iter(department_options.keys()), None),
            )

            teacher_id = st.text_input("ID викладача", value=teacher_id_default, key="structure_teacher_id").strip()
            full_name = st.text_input("ПІБ", value=full_name_default, key="structure_teacher_name").strip()
            department_label = (
                st.selectbox(
                    "Кафедра",
                    list(department_options.keys()),
                    index=(list(department_options.keys()).index(department_label_default) if department_label_default in department_options else 0),
                    key="structure_teacher_department",
                )
                if department_options
                else None
            )
            profile_columns = st.columns(2, gap="medium")
            position = profile_columns[0].text_input("Посада", value=position_default, key="structure_teacher_position").strip()
            academic_degree = profile_columns[1].text_input("Науковий ступінь", value=degree_default, key="structure_teacher_degree").strip()
            academic_title = st.text_input("Вчене звання", value=title_default, key="structure_teacher_title").strip()

            links_columns = st.columns(2, gap="medium")
            orcid = links_columns[0].text_input("ORCID", value=orcid_default, key="structure_teacher_orcid").strip()
            google_scholar = links_columns[1].text_input("Google Scholar", value=scholar_default, key="structure_teacher_scholar").strip()
            ext_columns = st.columns(2, gap="medium")
            scopus = ext_columns[0].text_input("Scopus", value=scopus_default, key="structure_teacher_scopus").strip()
            web_of_science = ext_columns[1].text_input("Web of Science", value=wos_default, key="structure_teacher_wos").strip()
            profile_url = st.text_input("Посилання на профіль", value=profile_url_default, key="structure_teacher_profile_url").strip()

            teacher_actions = st.columns(2, gap="medium")
            if teacher_actions[0].button("Зберегти викладача", use_container_width=True, key="structure_save_teacher"):
                if not department_options:
                    st.warning("Спочатку створіть кафедру для прив'язки викладача.")
                elif not teacher_id or not full_name:
                    st.warning("Вкажіть ID і ПІБ викладача.")
                else:
                    saved = service.upsert_teacher(
                        teacher_id=teacher_id,
                        full_name=full_name,
                        department_code=department_options[department_label],
                        position=position,
                        academic_degree=academic_degree,
                        academic_title=academic_title,
                        orcid=orcid,
                        google_scholar=google_scholar,
                        scopus=scopus,
                        web_of_science=web_of_science,
                        profile_url=profile_url,
                    )
                    if saved:
                        st.session_state[FLASH_KEY] = f"Профіль викладача '{full_name}' збережено."
                        st.rerun()
                    st.error("Не вдалося зберегти викладача. Перевірте дані кафедри.")

            delete_teacher_confirm = st.checkbox(
                "Підтверджую видалення цього викладача",
                key="structure_delete_teacher_confirm",
            )
            if teacher_actions[1].button(
                "Видалити викладача",
                use_container_width=True,
                key="structure_delete_teacher",
                type="primary",
            ):
                if not selected_teacher:
                    st.warning("Спочатку оберіть викладача для видалення.")
                elif not delete_teacher_confirm:
                    st.warning("Підтвердіть видалення викладача.")
                else:
                    result = service.delete_teacher(str(selected_teacher.get("id") or ""))
                    if result.get("deleted"):
                        st.session_state[FLASH_KEY] = (
                            f"Викладача видалено. Осиротілих публікацій очищено: {result.get('orphan_publications', 0)}."
                        )
                        st.rerun()
                    st.error("Не вдалося видалити викладача.")

    with edit_columns[1]:
        with st.expander("Масове видалення викладачів", expanded=False):
            bulk_teacher_map = {_teacher_option(row): str(row["id"]) for row in filtered_teachers if row.get("id")}
            selected_bulk_teachers = st.multiselect(
                "Оберіть викладачів",
                list(bulk_teacher_map.keys()),
                placeholder="Позначте профілі для видалення",
            )
            bulk_delete_confirm = st.checkbox(
                "Підтверджую масове видалення вибраних викладачів",
                key="structure_bulk_delete_teachers_confirm",
            )
            if st.button(
                "Видалити вибраних викладачів",
                use_container_width=True,
                key="structure_bulk_delete_teachers",
                type="primary",
            ):
                teacher_ids = [bulk_teacher_map[label] for label in selected_bulk_teachers if label in bulk_teacher_map]
                if not teacher_ids:
                    st.warning("Не обрано жодного викладача.")
                elif not bulk_delete_confirm:
                    st.warning("Підтвердіть масове видалення перед виконанням дії.")
                else:
                    deleted = service.bulk_delete_teachers(teacher_ids)
                    st.session_state[FLASH_KEY] = f"Масово видалено викладачів: {deleted}."
                    st.rerun()

        if filtered_teachers:
            filtered_frame = teachers_dataframe(filtered_teachers)
            header_columns = st.columns([0.8, 0.2], gap="small")
            with header_columns[1]:
                render_fullscreen_dataframe_button(
                    "Поточний склад викладачів",
                    filtered_frame,
                    key="structure_teachers_fullscreen",
                    caption="Повний перелік викладачів з активними фільтрами.",
                )
            st.download_button(
                "Експорт поточного зрізу CSV",
                _csv_bytes(filtered_frame),
                file_name="teachers_filtered.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_filtered_teachers",
            )
        st.caption(f"Без профілів у поточному зрізі: {teachers_without_profiles}")

    teacher_frame = teachers_dataframe(filtered_teachers)
    if teacher_frame.empty:
        render_empty_state("Викладачів не знайдено", "Спробуйте змінити фільтри, завантажте seed-викладачів або створіть профіль вручну.")
    else:
        header_columns = st.columns([0.92, 0.08], gap="small")
        with header_columns[0]:
            render_section_heading("Поточний склад викладачів")
        with header_columns[1]:
            render_fullscreen_dataframe_button(
                "Поточний склад викладачів",
                teacher_frame,
                key="structure_teachers_table_fullscreen",
                caption="Розширений перегляд таблиці викладачів.",
            )
        st.dataframe(teacher_frame, use_container_width=True, hide_index=True)


def _render_publications_tab(service) -> None:
    render_section_heading("Керування публікаціями", "Імпорт, контроль покриття джерел і швидке очищення публікаційного контуру.")
    with st.expander("Дії з публікаціями", expanded=False):
        import_columns = st.columns(3, gap="medium")
        publication_limit = import_columns[0].number_input(
            "Ліміт викладачів для імпорту",
            min_value=5,
            max_value=150,
            value=25,
            step=5,
        )
        use_scholar = import_columns[1].checkbox("Google Scholar як резерв", value=True)
        delete_publications_confirm = import_columns[2].checkbox(
            "Підтверджую очищення всіх публікацій",
            key="delete_publications_confirm",
        )

        action_columns = st.columns(2, gap="medium")
        if action_columns[0].button("Запустити імпорт публікацій", use_container_width=True):
            import_config = get_publication_import_config()
            importer = PublicationImportService(import_config)
            teachers_for_import = service.get_teachers_for_publication_import(limit=int(publication_limit))
            if not teachers_for_import:
                st.warning("Спочатку завантажте викладачів, щоб запустити імпорт.")
            else:
                with st.spinner("Шукаю публікації через доступні джерела..."):
                    bundle = importer.import_for_teachers(teachers_for_import, include_scholar=use_scholar)
                    service.seed_publications(bundle.publications, bundle.authorships)
                provider_summary = ", ".join(
                    f"{name}: {count}" for name, count in sorted(bundle.provider_hits.items())
                ) or "збігів немає"
                st.session_state[FLASH_KEY] = (
                    f"Оброблено {bundle.processed_teachers} викладачів, публікацій: {len(bundle.publications)}. "
                    f"Джерела: {provider_summary}"
                )
                st.rerun()

        if action_columns[1].button("Очистити всі публікації", use_container_width=True, type="primary"):
            if not delete_publications_confirm:
                st.warning("Підтвердіть очищення всіх публікацій перед виконанням дії.")
            else:
                deleted = service.delete_all_publications()
                st.session_state[FLASH_KEY] = f"Очищено {deleted} публікацій."
                st.rerun()

    publication_sources = publication_sources_dataframe(service.get_publication_source_summary())
    counts = service.get_overview_counts()

    summary = st.columns(3, gap="medium")
    with summary[0]:
        render_summary_strip("Публікації в базі", str(counts["publications"]), "збережені записи")
    with summary[1]:
        render_summary_strip("Зв'язки авторства", str(counts["authorship_links"]), "поточний контур авторів")
    with summary[2]:
        render_summary_strip("Джерела", str(len(publication_sources.index)), "активні типи джерел у базі")

    if publication_sources.empty:
        render_empty_state("Публікаційний контур порожній", "Запустіть імпорт або додайте публікації вручну, щоб побачити джерела.")
    else:
        source_columns = st.columns([0.95, 1.05], gap="large")
        with source_columns[0]:
            header_columns = st.columns([0.9, 0.1], gap="small")
            with header_columns[1]:
                render_fullscreen_bar_chart_button(
                    "Розподіл джерел публікацій",
                    publication_sources,
                    key="structure_publication_sources_chart_fullscreen",
                    caption="Графік покриття публікацій за джерелами.",
                )
            st.bar_chart(publication_sources.set_index("Джерело"), use_container_width=True, height=280)
        with source_columns[1]:
            header_columns = st.columns([0.9, 0.1], gap="small")
            with header_columns[1]:
                render_fullscreen_dataframe_button(
                    "Джерела публікацій",
                    publication_sources,
                    key="structure_publication_sources_fullscreen",
                    caption="Таблиця зведення по джерелах імпорту.",
                )
            st.dataframe(publication_sources, use_container_width=True, hide_index=True)
            st.download_button(
                "Експорт джерел CSV",
                _csv_bytes(publication_sources),
                file_name="publication_sources.csv",
                mime="text/csv",
                use_container_width=True,
                key="download_publication_sources",
            )


def render() -> None:
    service = require_service()
    render_header("Структура", subtitle="Робочий простір для керування факультетами, кафедрами, викладачами та публікаційним контуром.")
    _show_flash_message()

    counts = service.get_overview_counts()
    summary = st.columns(4, gap="medium")
    summary[0].metric("Факультети", counts["faculties"])
    summary[1].metric("Кафедри", counts["departments"])
    summary[2].metric("Викладачі", counts["teachers"])
    summary[3].metric("Публікації", counts["publications"])

    faculty_tab, teacher_tab, publication_tab = st.tabs(["Факультети й кафедри", "Викладачі", "Публікації"])

    with faculty_tab:
        _render_faculty_department_tab(service)

    with teacher_tab:
        _render_teachers_tab(service)

    with publication_tab:
        _render_publications_tab(service)
