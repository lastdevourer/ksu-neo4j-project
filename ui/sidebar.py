from __future__ import annotations

import streamlit as st

from config import get_publication_import_config
from data.loaders import load_teachers_seed
from data.seed_data import DEPARTMENTS, FACULTIES
from services.neo4j_service import Neo4jService
from services.publication_import import PublicationImportService


def render_sidebar(service: Neo4jService) -> None:
    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-kicker">KSPU / KhDU</div>
                <div class="sidebar-brand-title">Академічна мережа</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        coverage = service.get_profile_coverage()
        total_teachers = int(coverage.get("teachers", 0) or 0)
        total_profiles = int(coverage.get("with_any_profile", 0) or 0)
        if total_teachers:
            render_ratio = f"{total_profiles} / {total_teachers}"
            st.caption(f"Покриття профілів: {render_ratio}")

        with st.expander("Керування базою", expanded=False):
            if st.button("Перевірити підключення", use_container_width=True):
                try:
                    service.verify_connection()
                    st.success("Підключення до Neo4j Aura активне.")
                except Exception as exc:
                    st.error(f"Помилка підключення: {exc}")

            if st.button("Створити схему та індекси", use_container_width=True):
                try:
                    service.prepare_database()
                    st.success("Обмеження та індекси створено.")
                except Exception as exc:
                    st.error(f"Не вдалося підготувати схему: {exc}")

            if st.button("Заповнити факультети та кафедри", use_container_width=True):
                try:
                    service.seed_reference_data(FACULTIES, DEPARTMENTS)
                    st.success("Довідник факультетів і кафедр оновлено.")
                except Exception as exc:
                    st.error(f"Не вдалося заповнити довідник: {exc}")

            if st.button("Завантажити викладачів KSPU", use_container_width=True):
                try:
                    service.seed_reference_data(FACULTIES, DEPARTMENTS)
                    teachers = load_teachers_seed()
                    service.seed_teachers(teachers)
                    st.success(f"Завантажено {len(teachers)} викладачів KSPU.")
                except Exception as exc:
                    st.error(f"Не вдалося завантажити викладачів: {exc}")

            publication_limit = st.number_input(
                "Імпорт публікацій: ліміт викладачів",
                min_value=5,
                max_value=150,
                value=25,
                step=5,
            )
            use_scholar = st.checkbox("Резервний пошук через Google Scholar", value=True)

            if st.button("Завантажити публікації", use_container_width=True):
                try:
                    import_config = get_publication_import_config()
                    importer = PublicationImportService(import_config)
                    teachers_for_import = service.get_teachers_for_publication_import(limit=int(publication_limit))

                    if not teachers_for_import:
                        st.warning("Спочатку завантажте викладачів.")
                    else:
                        with st.spinner("Шукаю публікації через ORCID, OpenAlex, Crossref, Scopus, Web of Science та Google Scholar..."):
                            bundle = importer.import_for_teachers(teachers_for_import, include_scholar=use_scholar)
                            service.seed_publications(bundle.publications, bundle.authorships)

                        provider_summary = ", ".join(
                            f"{name}: {count}" for name, count in sorted(bundle.provider_hits.items())
                        ) or "збігів немає"
                        st.success(
                            f"Оброблено {bundle.processed_teachers} викладачів, "
                            f"публікацій: {len(bundle.publications)}, зв'язків авторства: {len(bundle.authorships)}."
                        )
                        st.caption(f"Джерела: {provider_summary}")
                        if bundle.warnings:
                            st.warning("\n".join(f"- {item}" for item in bundle.warnings[:6]))
                except Exception as exc:
                    st.error(f"Не вдалося завантажити публікації: {exc}")

            available_sources = ["ORCID", "OpenAlex", "Crossref"]
            missing_sources: list[str] = []
            if import_config := get_publication_import_config():
                if import_config.scopus_api_key:
                    available_sources.append("Scopus")
                else:
                    missing_sources.append("Scopus API")
                if import_config.wos_api_key:
                    available_sources.append("Web of Science")
                else:
                    missing_sources.append("Web of Science API")
            if use_scholar:
                available_sources.append("Scholar")
            st.caption(f"Активні джерела імпорту: {', '.join(available_sources)}")
            if missing_sources:
                st.caption(f"Для максимального покриття ще потрібні ключі: {', '.join(missing_sources)}")
