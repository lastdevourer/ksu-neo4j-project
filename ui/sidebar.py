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
                <div class="sidebar-brand-title">ÐÐºÐ°Ð´ÐµÐ¼Ñ–Ñ‡Ð½Ð° Ð¼ÐµÑ€ÐµÐ¶Ð°</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("ÐšÐµÑ€ÑƒÐ²Ð°Ð½Ð½Ñ Ð±Ð°Ð·Ð¾ÑŽ", expanded=False):
            if st.button("ÐŸÐµÑ€ÐµÐ²Ñ–Ñ€Ð¸Ñ‚Ð¸ Ð¿Ñ–Ð´ÐºÐ»ÑŽÑ‡ÐµÐ½Ð½Ñ", use_container_width=True):
                try:
                    service.verify_connection()
                    st.success("ÐŸÑ–Ð´ÐºÐ»ÑŽÑ‡ÐµÐ½Ð½Ñ Ð´Ð¾ Neo4j Aura Ð°ÐºÑ‚Ð¸Ð²Ð½Ðµ.")
                except Exception as exc:
                    st.error(f"ÐŸÐ¾Ð¼Ð¸Ð»ÐºÐ° Ð¿Ñ–Ð´ÐºÐ»ÑŽÑ‡ÐµÐ½Ð½Ñ: {exc}")

            if st.button("Ð¡Ñ‚Ð²Ð¾Ñ€Ð¸Ñ‚Ð¸ ÑÑ…ÐµÐ¼Ñƒ Ñ‚Ð° Ñ–Ð½Ð´ÐµÐºÑÐ¸", use_container_width=True):
                try:
                    service.prepare_database()
                    st.success("ÐžÐ±Ð¼ÐµÐ¶ÐµÐ½Ð½Ñ Ñ‚Ð° Ñ–Ð½Ð´ÐµÐºÑÐ¸ ÑÑ‚Ð²Ð¾Ñ€ÐµÐ½Ð¾.")
                except Exception as exc:
                    st.error(f"ÐÐµ Ð²Ð´Ð°Ð»Ð¾ÑÑ Ð¿Ñ–Ð´Ð³Ð¾Ñ‚ÑƒÐ²Ð°Ñ‚Ð¸ ÑÑ…ÐµÐ¼Ñƒ: {exc}")

            if st.button("Ð—Ð°Ð¿Ð¾Ð²Ð½Ð¸Ñ‚Ð¸ Ñ„Ð°ÐºÑƒÐ»ÑŒÑ‚ÐµÑ‚Ð¸ Ñ‚Ð° ÐºÐ°Ñ„ÐµÐ´Ñ€Ð¸", use_container_width=True):
                try:
                    service.seed_reference_data(FACULTIES, DEPARTMENTS)
                    st.success("Ð”Ð¾Ð²Ñ–Ð´Ð½Ð¸Ðº Ñ„Ð°ÐºÑƒÐ»ÑŒÑ‚ÐµÑ‚Ñ–Ð² Ñ– ÐºÐ°Ñ„ÐµÐ´Ñ€ Ð¾Ð½Ð¾Ð²Ð»ÐµÐ½Ð¾.")
                except Exception as exc:
                    st.error(f"ÐÐµ Ð²Ð´Ð°Ð»Ð¾ÑÑ Ð·Ð°Ð¿Ð¾Ð²Ð½Ð¸Ñ‚Ð¸ Ð´Ð¾Ð²Ñ–Ð´Ð½Ð¸Ðº: {exc}")

            if st.button("Ð—Ð°Ð²Ð°Ð½Ñ‚Ð°Ð¶Ð¸Ñ‚Ð¸ Ð²Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–Ð² KSPU", use_container_width=True):
                try:
                    service.seed_reference_data(FACULTIES, DEPARTMENTS)
                    teachers = load_teachers_seed()
                    service.seed_teachers(teachers)
                    st.success(f"Ð—Ð°Ð²Ð°Ð½Ñ‚Ð°Ð¶ÐµÐ½Ð¾ {len(teachers)} Ð²Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–Ð² KSPU.")
                except Exception as exc:
                    st.error(f"ÐÐµ Ð²Ð´Ð°Ð»Ð¾ÑÑ Ð·Ð°Ð²Ð°Ð½Ñ‚Ð°Ð¶Ð¸Ñ‚Ð¸ Ð²Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–Ð²: {exc}")

            publication_limit = st.number_input(
                "Ð†Ð¼Ð¿Ð¾Ñ€Ñ‚ Ð¿ÑƒÐ±Ð»Ñ–ÐºÐ°Ñ†Ñ–Ð¹: Ð»Ñ–Ð¼Ñ–Ñ‚ Ð²Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–Ð²",
                min_value=5,
                max_value=150,
                value=25,
                step=5,
            )
            use_scholar = st.checkbox("Ð ÐµÐ·ÐµÑ€Ð²Ð½Ð¸Ð¹ Ð¿Ð¾ÑˆÑƒÐº Ñ‡ÐµÑ€ÐµÐ· Google Scholar", value=True)

            if st.button("Ð—Ð°Ð²Ð°Ð½Ñ‚Ð°Ð¶Ð¸Ñ‚Ð¸ Ð¿ÑƒÐ±Ð»Ñ–ÐºÐ°Ñ†Ñ–Ñ—", use_container_width=True):
                try:
                    import_config = get_publication_import_config()
                    importer = PublicationImportService(import_config)
                    teachers_for_import = service.get_teachers_for_publication_import(limit=int(publication_limit))

                    if not teachers_for_import:
                        st.warning("Ð¡Ð¿Ð¾Ñ‡Ð°Ñ‚ÐºÑƒ Ð·Ð°Ð²Ð°Ð½Ñ‚Ð°Ð¶Ñ‚Ðµ Ð²Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–Ð².")
                    else:
                        with st.spinner("Ð¨ÑƒÐºÐ°ÑŽ Ð¿ÑƒÐ±Ð»Ñ–ÐºÐ°Ñ†Ñ–Ñ— Ñ‡ÐµÑ€ÐµÐ· ORCID, OpenAlex, Crossref, Scopus, Web of Science Ñ‚Ð° Google Scholar..."):
                            bundle = importer.import_for_teachers(teachers_for_import, include_scholar=use_scholar)
                            service.seed_publications(bundle.publications, bundle.authorships)

                        provider_summary = ", ".join(
                            f"{name}: {count}" for name, count in sorted(bundle.provider_hits.items())
                        ) or "Ð·Ð±Ñ–Ð³Ñ–Ð² Ð½ÐµÐ¼Ð°Ñ”"
                        st.success(
                            f"ÐžÐ±Ñ€Ð¾Ð±Ð»ÐµÐ½Ð¾ {bundle.processed_teachers} Ð²Ð¸ÐºÐ»Ð°Ð´Ð°Ñ‡Ñ–Ð², "
                            f"Ð¿ÑƒÐ±Ð»Ñ–ÐºÐ°Ñ†Ñ–Ð¹: {len(bundle.publications)}, Ð·Ð²'ÑÐ·ÐºÑ–Ð² Ð°Ð²Ñ‚Ð¾Ñ€ÑÑ‚Ð²Ð°: {len(bundle.authorships)}."
                        )
                        st.caption(f"Ð”Ð¶ÐµÑ€ÐµÐ»Ð°: {provider_summary}")
                        if bundle.warnings:
                            st.warning("\n".join(f"- {item}" for item in bundle.warnings[:6]))
                except Exception as exc:
                    st.error(f"ÐÐµ Ð²Ð´Ð°Ð»Ð¾ÑÑ Ð·Ð°Ð²Ð°Ð½Ñ‚Ð°Ð¶Ð¸Ñ‚Ð¸ Ð¿ÑƒÐ±Ð»Ñ–ÐºÐ°Ñ†Ñ–Ñ—: {exc}")

            available_sources = ["ORCID", "OpenAlex", "Crossref"]
            if import_config := get_publication_import_config():
                if import_config.scopus_api_key:
                    available_sources.append("Scopus")
                if import_config.wos_api_key:
                    available_sources.append("Web of Science")
            if use_scholar:
                available_sources.append("Scholar")
            st.caption(f"ÐÐºÑ‚Ð¸Ð²Ð½Ñ– Ð´Ð¶ÐµÑ€ÐµÐ»Ð° Ñ–Ð¼Ð¿Ð¾Ñ€Ñ‚Ñƒ: {', '.join(available_sources)}")
