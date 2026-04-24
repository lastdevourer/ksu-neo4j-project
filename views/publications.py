from __future__ import annotations

import streamlit as st

from services.publication_sources import search_openalex_publications
from services.scholar_sources import (
    find_best_scholar_profile,
    find_scholar_profiles_for_teacher,
    load_publications_from_scholar_id,
    scholar_author_id_from_url,
)
from ui.components import (
    render_empty_state,
    render_header,
    render_key_value_card,
    render_section_heading,
    render_summary_strip,
    require_service,
)
from ui.formatters import publications_dataframe


def save_teacher_scholar_profile(service, teacher_id: str, profile_url: str) -> None:
    service.execute(
        """
        MATCH (t:Teacher)
        WHERE coalesce(t.id, t.teacher_id) = $teacher_id
        SET t.google_scholar = $profile_url
        """,
        {
            "teacher_id": teacher_id,
            "profile_url": profile_url,
        },
    )


def render_import_block(service) -> None:
    render_section_heading("Імпорт публікацій")

    departments = service.get_departments()
    department_labels = {"Усі кафедри": ""}

    for row in departments:
        department_labels[f"{row['name']} ({row['code']})"] = row["code"]

    cols = st.columns([1.1, 1.1, 0.8], gap="medium")

    selected_department_label = cols[0].selectbox(
        "Кафедра для імпорту",
        list(department_labels.keys()),
        key="publication_import_department",
    )
    selected_department_code = department_labels[selected_department_label]

    from_year = cols[1].number_input(
        "З якого року шукати в OpenAlex",
        min_value=1990,
        max_value=2030,
        value=2010,
        step=1,
    )

    per_page = cols[2].slider(
        "Ліміт публікацій",
        min_value=3,
        max_value=50,
        value=25,
        step=1,
    )

    teachers = service.get_teacher_import_options(department_code=selected_department_code)

    if not teachers:
        render_empty_state(
            "Викладачів для імпорту не знайдено",
            "Спочатку завантажте викладачів або змініть фільтр кафедри.",
        )
        return

    teacher_labels = {
        f"{row['full_name']} | {row['department_name']} | зараз публікацій: {row['publications']}": row
        for row in teachers
    }

    selected_teacher_label = st.selectbox(
        "Обрати викладача",
        list(teacher_labels.keys()),
        key="publication_import_teacher",
    )
    selected_teacher = teacher_labels[selected_teacher_label]

    tabs = st.tabs(
        [
            "Google Scholar профіль",
            "OpenAlex",
            "Масово по кафедрі",
        ]
    )

    with tabs[0]:
        render_section_heading(
            "Google Scholar",
            "Основний варіант: спочатку знаходимо точний профіль викладача, потім завантажуємо публікації з профілю.",
        )

        scholar_url = st.text_input(
            "Scholar URL викладача, якщо він уже відомий",
            value=selected_teacher.get("google_scholar", "") or "",
            placeholder="https://scholar.google.com/citations?user=...",
        )

        col_1, col_2 = st.columns(2, gap="medium")

        with col_1:
            find_profile = st.button("Знайти Scholar-профіль викладача", type="secondary")

        with col_2:
            load_from_profile = st.button("Завантажити публікації з Scholar", type="primary")

        if find_profile:
            with st.spinner("Шукаю Scholar-профілі..."):
                profiles = find_scholar_profiles_for_teacher(selected_teacher["full_name"], limit=6)

            st.session_state["scholar_profile_candidates"] = profiles

        profiles = st.session_state.get("scholar_profile_candidates", [])

        if profiles:
            st.write("Знайдені профілі:")

            profile_labels = {
                f"{profile['name']} | {profile['affiliation']} | score: {profile['match_score']}": profile
                for profile in profiles
            }

            selected_profile_label = st.selectbox(
                "Обери правильний профіль",
                list(profile_labels.keys()),
            )
            selected_profile = profile_labels[selected_profile_label]

            st.caption(selected_profile["profile_url"])

            if st.button("Зберегти цей Scholar-профіль викладачу"):
                save_teacher_scholar_profile(
                    service,
                    selected_teacher["id"],
                    selected_profile["profile_url"],
                )
                st.success("Scholar-профіль збережено викладачу.")
                st.cache_data.clear()

        if load_from_profile:
            scholar_id = scholar_author_id_from_url(scholar_url)

            if not scholar_id:
                best_profile = find_best_scholar_profile(selected_teacher["full_name"])
                if best_profile:
                    scholar_id = best_profile["scholar_id"]
                    scholar_url = best_profile["profile_url"]
                    save_teacher_scholar_profile(service, selected_teacher["id"], scholar_url)

            if not scholar_id:
                st.error("Не вдалося визначити Scholar ID. Встав URL профілю або спочатку знайди профіль.")
            else:
                with st.spinner("Завантажую публікації з Google Scholar..."):
                    publications = load_publications_from_scholar_id(
                        scholar_id,
                        limit=int(per_page),
                    )

                if not publications:
                    st.warning("Scholar не повернув публікації. Можлива капча/блокування або порожній профіль.")
                else:
                    imported = service.import_teacher_publications(
                        teacher_id=selected_teacher["id"],
                        publications=publications,
                    )

                    st.success(f"Імпортовано / оновлено публікацій: {imported}")
                    st.cache_data.clear()
                    st.rerun()

    with tabs[1]:
        render_section_heading(
            "OpenAlex",
            "Запасний варіант. Може знаходити не всі роботи або плутати однофамільців.",
        )

        if st.button("Знайти публікації в OpenAlex для одного викладача", type="secondary"):
            with st.spinner("Шукаю публікації в OpenAlex..."):
                found_publications = search_openalex_publications(
                    selected_teacher["full_name"],
                    from_year=int(from_year),
                    per_page=int(per_page),
                )

            st.session_state["openalex_preview_teacher_id"] = selected_teacher["id"]
            st.session_state["openalex_preview_publications"] = found_publications

        preview_publications = st.session_state.get("openalex_preview_publications", [])
        preview_teacher_id = st.session_state.get("openalex_preview_teacher_id")

        if preview_publications:
            st.success(f"Знайдено публікацій: {len(preview_publications)}")

            preview_rows = [
                {
                    "id": row["id"],
                    "title": row["title"],
                    "year": row["year"],
                    "doi": row["doi"],
                    "pub_type": row["pub_type"],
                    "source": row["source"],
                    "authors": row["authors"],
                    "authors_count": len(row["authors"]),
                }
                for row in preview_publications
            ]

            st.dataframe(publications_dataframe(preview_rows), use_container_width=True, hide_index=True)

            if st.button("Зберегти ці OpenAlex-публікації в Neo4j", type="primary"):
                imported = service.import_teacher_publications(
                    teacher_id=preview_teacher_id,
                    publications=preview_publications,
                )
                st.success(f"Імпортовано / оновлено публікацій: {imported}")
                st.cache_data.clear()
                st.rerun()

    with tabs[2]:
        render_section_heading(
            "Масовий Scholar-імпорт по кафедрі",
            "Для кожного викладача система спробує знайти Scholar-профіль, зберегти його і завантажити публікації.",
        )

        st.warning(
            "Цей режим може впертися в капчу Google Scholar. Для захисту краще запускати по одній кафедрі."
        )

        if st.button("Знайти профілі та завантажити публікації всім у вибраній кафедрі", type="primary"):
            total_imported = 0
            processed = 0
            failed = 0

            progress = st.progress(0)
            status = st.empty()

            for index, teacher in enumerate(teachers):
                status.write(f"Обробка: {teacher['full_name']}")

                try:
                    profile = find_best_scholar_profile(teacher["full_name"])

                    if not profile:
                        failed += 1
                        progress.progress((index + 1) / len(teachers))
                        continue

                    save_teacher_scholar_profile(service, teacher["id"], profile["profile_url"])

                    publications = load_publications_from_scholar_id(
                        profile["scholar_id"],
                        limit=int(per_page),
                    )

                    imported = service.import_teacher_publications(
                        teacher_id=teacher["id"],
                        publications=publications,
                    )

                    total_imported += imported
                    processed += 1

                except Exception as error:
                    failed += 1
                    st.error(f"Помилка для {teacher['full_name']}: {error}")

                progress.progress((index + 1) / len(teachers))

            status.write("Готово")

            st.success(
                f"Оброблено викладачів: {processed}. "
                f"Помилок / без профілю: {failed}. "
                f"Імпортовано / оновлено публікацій: {total_imported}."
            )

            st.cache_data.clear()


def render() -> None:
    service = require_service()
    render_header("Публікації", "")

    with st.expander("Додати публікації", expanded=False):
        render_import_block(service)

    years = service.get_publication_years()
    year_options = ["Усі роки"] + [str(year) for year in years]
    selected_year = st.selectbox("Фільтр за роком", year_options)
    year_value = None if selected_year == "Усі роки" else int(selected_year)

    publication_rows = service.get_publications(year=year_value)
    publications_table = publications_dataframe(publication_rows)

    if publications_table.empty:
        render_empty_state(
            "Публікацій не знайдено",
            "Спробуйте імпортувати публікації через Google Scholar-профіль або OpenAlex.",
        )
        return

    publications_count = len(publication_rows)
    authorship_links = sum(int(row.get("authors_count", 0) or 0) for row in publication_rows)
    covered_years = len({row.get("year") for row in publication_rows if row.get("year") is not None})

    metrics = st.columns(3, gap="medium")

    with metrics[0]:
        render_summary_strip("Публікації", str(publications_count))

    with metrics[1]:
        render_summary_strip("Авторські входження", str(authorship_links))

    with metrics[2]:
        render_summary_strip("Охоплені роки", str(covered_years))

    publication_map = {
        f"{row['title']} ({row['year'] if row['year'] is not None else 'н/д'})": row
        for row in publication_rows
    }

    layout = st.columns([1.16, 0.94], gap="large")

    with layout[0]:
        render_section_heading("Таблиця публікацій")
        st.dataframe(publications_table, use_container_width=True, hide_index=True)

    with layout[1]:
        render_section_heading("Деталі публікації")

        selected_publication_label = st.selectbox(
            "Обрати публікацію",
            list(publication_map.keys()),
        )

        selected_publication = publication_map[selected_publication_label]

        render_key_value_card(
            "Коротка інформація",
            [
                ("Назва", selected_publication["title"]),
                ("Рік", str(selected_publication["year"] or "н/д")),
                ("Тип", selected_publication["pub_type"]),
                ("Джерело", selected_publication["source"]),
                ("DOI", selected_publication["doi"]),
                ("Кількість авторів", str(selected_publication["authors_count"] or 0)),
            ],
        )

        render_key_value_card(
            "Авторський склад",
            [
                (
                    "Автори",
                    ", ".join(selected_publication["authors"])
                    if selected_publication["authors"]
                    else "—",
                ),
            ],
        )
