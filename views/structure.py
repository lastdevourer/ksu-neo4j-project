from __future__ import annotations

import pandas as pd
import streamlit as st

from config import get_publication_import_config
from data.loaders import load_teachers_seed
from data.seed_data import DEPARTMENTS, FACULTIES
from services.publication_import import PublicationImportService
from ui.components import render_empty_state, render_header, render_section_heading, require_service
from ui.formatters import department_overview_dataframe, faculty_overview_dataframe, publication_sources_dataframe, teachers_dataframe


FLASH_KEY = "structure_flash"


def _show_flash_message() -> None:
    message = st.session_state.pop(FLASH_KEY, "")
    if message:
        st.success(message)


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def render() -> None:
    service = require_service()
    render_header("Структура", subtitle="Керуйте довідниками, викладачами, публікаціями та сервісними діями з одного місця.")
    _show_flash_message()

    counts = service.get_overview_counts()
    summary = st.columns(4, gap="medium")
    summary[0].metric("Факультети", counts["faculties"])
    summary[1].metric("Кафедри", counts["departments"])
    summary[2].metric("Викладачі", counts["teachers"])
    summary[3].metric("Публікації", counts["publications"])

    tabs = st.tabs(["Факультети й кафедри", "Викладачі", "Публікації"])

    with tabs[0]:
        render_section_heading("Довідник структури", "Офіційний контур університетської структури та інструменти її оновлення.")
        with st.expander("Дії зі структурою", expanded=False):
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

        faculty_frame = faculty_overview_dataframe(service.get_faculty_overview())
        department_frame = department_overview_dataframe(service.get_department_overview())
        tables = st.columns([0.92, 1.08], gap="large")
        with tables[0]:
            render_section_heading("Факультети")
            if faculty_frame.empty:
                render_empty_state("Факультети відсутні", "Скористайтеся оновленням структури, щоб заповнити довідник.")
            else:
                st.dataframe(faculty_frame, use_container_width=True, hide_index=True)
        with tables[1]:
            render_section_heading("Кафедри")
            if department_frame.empty:
                render_empty_state("Кафедри відсутні", "Після оновлення структури тут з'являться підрозділи.")
            else:
                st.dataframe(department_frame, use_container_width=True, hide_index=True)

    with tabs[1]:
        render_section_heading("Керування викладачами", "Оновлюйте seed-викладачів або повністю очищуйте викладацький контур.")
        teachers = service.get_teachers()
        teachers_frame = teachers_dataframe(teachers)

        with st.expander("Дії з викладачами", expanded=False):
            action_columns = st.columns([1.0, 1.0, 1.1], gap="medium")
            if action_columns[0].button("Завантажити викладачів KSPU", use_container_width=True):
                service.seed_reference_data(FACULTIES, DEPARTMENTS)
                seed_teachers = load_teachers_seed()
                service.seed_teachers(seed_teachers)
                st.session_state[FLASH_KEY] = f"Завантажено {len(seed_teachers)} викладачів KSPU."
                st.rerun()

            delete_teachers_confirm = action_columns[1].checkbox(
                "Підтверджую очищення викладачів і публікацій",
                key="delete_teachers_confirm",
            )
            if action_columns[2].button("Очистити викладачів і публікації", use_container_width=True, type="primary"):
                if not delete_teachers_confirm:
                    st.warning("Підтвердіть очищення викладачів і публікацій перед виконанням дії.")
                else:
                    result = service.delete_all_teachers_and_publications()
                    st.session_state[FLASH_KEY] = (
                        f"Очищено викладачів: {result['teachers']}, публікацій: {result['publications']}."
                    )
                    st.rerun()

        if teachers_frame.empty:
            render_empty_state("Викладачів немає", "Завантажте seed-викладачів, щоб побачити кадровий склад у системі.")
        else:
            st.dataframe(teachers_frame, use_container_width=True, hide_index=True)

    with tabs[2]:
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
        if publication_sources.empty:
            render_empty_state("Публікаційний контур порожній", "Запустіть імпорт або додайте публікації вручну, щоб побачити джерела.")
        else:
            source_columns = st.columns([1.0, 1.0], gap="large")
            with source_columns[0]:
                st.bar_chart(publication_sources.set_index("Джерело"), use_container_width=True, height=280)
            with source_columns[1]:
                st.dataframe(publication_sources, use_container_width=True, hide_index=True)
