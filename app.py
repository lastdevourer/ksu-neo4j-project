import pandas as pd
import streamlit as st

from data.seed_data import SEEDED_DEPARTMENTS, SEEDED_FACULTIES
from services.neo4j_service import Neo4jService
from services.publication_scraper import scrape_publications_from_profile
from services.teacher_scraper import STAFF_URLS, scrape_department_teachers
from ui.formatting import (
    apply_global_styles,
    build_metrics,
    rename_activity_index_df,
    rename_department_df,
    rename_department_stats_df,
    rename_faculty_df,
    rename_publication_df,
    rename_teacher_df,
    rename_top_coauthors_df,
    rename_top_teachers_df,
)

st.set_page_config(
    page_title="Програмний модуль обліку наукових публікацій викладачів",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_global_styles()

st.markdown(
    """
    <div class="hero-box">
        <div class="main-title">Програмний модуль обліку наукових публікацій викладачів</div>
        <div class="sub-title">
            Система забезпечує структуроване зберігання відомостей про факультети, кафедри,
            викладачів і публікації, формування зв’язків співавторства та аналітичне
            дослідження структури наукової взаємодії на основі графової моделі Neo4j.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

required_secrets = ["NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD"]
missing = [key for key in required_secrets if key not in st.secrets]
if missing:
    st.error(f"Додай у Streamlit Secrets: {', '.join(missing)}")
    st.stop()

service = Neo4jService(
    uri=st.secrets["NEO4J_URI"],
    user=st.secrets["NEO4J_USER"],
    password=st.secrets["NEO4J_PASSWORD"],
)

c1, c2, c3 = st.columns([1.2, 1.1, 1])

with c1:
    if st.button("Початково заповнити структуру", use_container_width=True):
        try:
            service.create_constraints()
            service.seed_structure(SEEDED_FACULTIES, SEEDED_DEPARTMENTS)
            st.success("Факультети та кафедри додано.")
            st.rerun()
        except Exception as e:
            st.error(f"Помилка: {e}")

with c2:
    if st.button("Створити обмеження унікальності", use_container_width=True):
        try:
            service.create_constraints()
            st.success("Обмеження створено.")
        except Exception as e:
            st.error(f"Помилка: {e}")

with c3:
    if st.button("Перевірити підключення", use_container_width=True):
        try:
            cnt = service.count_all_nodes()
            st.success(f"Підключено. Вузлів у базі: {cnt}")
        except Exception as e:
            st.error(f"Помилка підключення: {e}")

counts = service.get_counts()
build_metrics(counts)

tab1, tab2, tab3, tab4 = st.tabs([
    "Структура університету",
    "Викладачі",
    "Публікації",
    "Аналітика",
])

with tab1:
    st.markdown("### Факультети та кафедри")

    left, right = st.columns(2)

    with left:
        st.markdown("#### Факультети")
        faculty_rows = service.get_faculties()
        if faculty_rows:
            df = rename_faculty_df(pd.DataFrame(faculty_rows))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Факультети ще не додано.")

        with st.expander("Додати факультет"):
            next_faculty_id = service.get_next_id("F", "Faculty", "faculty_id", 2)
            with st.form("faculty_form", clear_on_submit=True):
                faculty_id = st.text_input("Код факультету", value=next_faculty_id)
                faculty_name = st.text_input("Назва факультету")
                save_faculty = st.form_submit_button("Зберегти")

                if save_faculty:
                    if not faculty_id.strip() or not faculty_name.strip():
                        st.warning("Заповни код і назву.")
                    else:
                        try:
                            service.upsert_faculty(
                                faculty_id=faculty_id.strip(),
                                name=faculty_name.strip(),
                            )
                            st.success("Факультет додано.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Помилка: {e}")

    with right:
        st.markdown("#### Кафедри")
        department_rows = service.get_departments()
        if department_rows:
            df = rename_department_df(pd.DataFrame(department_rows))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Кафедри ще не додано.")

        faculty_options = service.get_faculty_options()
        faculty_map = {
            f"{row['faculty_id']} — {row['name']}": row["faculty_id"]
            for row in faculty_options
        }

        with st.expander("Додати кафедру"):
            next_department_id = service.get_next_id("D", "Department", "department_id", 3)
            with st.form("department_form", clear_on_submit=True):
                department_id = st.text_input("Код кафедри", value=next_department_id)
                department_name = st.text_input("Назва кафедри")
                faculty_choice = st.selectbox(
                    "Факультет",
                    options=list(faculty_map.keys()),
                    index=None,
                    placeholder="Оберіть факультет",
                )
                save_department = st.form_submit_button("Зберегти")

                if save_department:
                    if not department_id.strip() or not department_name.strip() or not faculty_choice:
                        st.warning("Заповни всі поля.")
                    else:
                        try:
                            service.upsert_department(
                                department_id=department_id.strip(),
                                faculty_id=faculty_map[faculty_choice],
                                name=department_name.strip(),
                            )
                            st.success("Кафедру додано.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Помилка: {e}")

with tab2:
    st.markdown("### База викладачів")

    supported_department_ids = {"D001", "D002", "D003"}

    department_options = [
        row for row in service.get_department_options()
        if row["department_id"] in supported_department_ids
    ]

    department_map = {
        f"{row['department_id']} — {row['name']}": row
        for row in department_options
    }

    auto_col1, auto_col2 = st.columns([1.35, 1])

    with auto_col1:
        selected_department = st.selectbox(
            "Оберіть кафедру для автоматичного імпорту викладачів",
            options=list(department_map.keys()),
            index=None,
            placeholder="Оберіть кафедру"
        )

    with auto_col2:
        st.write("")
        st.write("")
        if st.button("Автоматично завантажити викладачів кафедри", use_container_width=True):
            if not selected_department:
                st.warning("Спочатку обери кафедру.")
            else:
                dep = department_map[selected_department]
                try:
                    teachers = scrape_department_teachers(
                        department_id=dep["department_id"],
                        faculty_id=dep["faculty_id"],
                    )
                    if not teachers:
                        st.warning("Для цієї кафедри даних не знайдено.")
                    else:
                        service.import_teachers(teachers)
                        st.success(f"Імпортовано викладачів: {len(teachers)}")
                        st.rerun()
                except Exception as e:
                    st.error(f"Помилка автоматичного імпорту: {e}")

    if selected_department:
        dep = department_map[selected_department]
        if dep["department_id"] in STAFF_URLS:
            st.caption(f"Джерело: {STAFF_URLS[dep['department_id']]}")

    teacher_rows = service.get_teachers()
    if teacher_rows:
        df = rename_teacher_df(pd.DataFrame(teacher_rows))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Викладачів ще не додано.")

    all_department_options = service.get_department_options()
    all_department_map = {
        f"{row['department_id']} — {row['name']}": row
        for row in all_department_options
    }

    with st.expander("Додати викладача вручну"):
        next_teacher_id = service.get_next_id("T", "Teacher", "teacher_id", 4)

        with st.form("teacher_form", clear_on_submit=True):
            teacher_id = st.text_input("Код викладача", value=next_teacher_id)
            full_name = st.text_input("ПІБ")
            position = st.text_input("Посада")
            academic_degree = st.text_input("Науковий ступінь")
            academic_title = st.text_input("Вчене звання")

            department_choice = st.selectbox(
                "Кафедра",
                options=list(all_department_map.keys()),
                index=None,
                placeholder="Оберіть кафедру",
                key="manual_teacher_department"
            )

            col1, col2 = st.columns(2)
            with col1:
                orcid = st.text_input("ORCID")
                google_scholar = st.text_input("Google Scholar")
            with col2:
                scopus = st.text_input("Scopus")
                source_url = st.text_input("Посилання на профіль")

            save_teacher = st.form_submit_button("Зберегти")

            if save_teacher:
                if not teacher_id.strip() or not full_name.strip() or not department_choice:
                    st.warning("Заповни код, ПІБ і кафедру.")
                else:
                    dep = all_department_map[department_choice]
                    try:
                        service.upsert_teacher(
                            teacher_id=teacher_id.strip(),
                            full_name=full_name.strip(),
                            position=position.strip(),
                            academic_degree=academic_degree.strip(),
                            academic_title=academic_title.strip(),
                            department_id=dep["department_id"],
                            faculty_id=dep["faculty_id"],
                            orcid=orcid.strip(),
                            google_scholar=google_scholar.strip(),
                            scopus=scopus.strip(),
                            source_url=source_url.strip(),
                        )
                        st.success("Викладача додано.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Помилка: {e}")

with tab3:
    st.markdown("### База публікацій")

    teacher_rows_full = service.get_teachers()
    teacher_rows = [row for row in teacher_rows_full if row.get("source_url")]

    teacher_profile_map = {
        f"{row['teacher_id']} — {row['full_name']}": row
        for row in teacher_rows
    }

    auto_p1, auto_p2 = st.columns([1.35, 1])

    with auto_p1:
        selected_teacher_for_publications = st.selectbox(
            "Оберіть викладача для автоматичного пошуку публікацій",
            options=list(teacher_profile_map.keys()),
            index=None,
            placeholder="Оберіть викладача"
        )

    with auto_p2:
        st.write("")
        st.write("")
        if st.button("Автоматично знайти публікації викладача", use_container_width=True):
            if not selected_teacher_for_publications:
                st.warning("Спочатку обери викладача.")
            else:
                teacher_row = teacher_profile_map[selected_teacher_for_publications]
                try:
                    found = scrape_publications_from_profile(
                        profile_url=teacher_row["source_url"]
                    )
                    st.session_state["found_publications"] = found
                    st.session_state["found_publications_teacher_id"] = teacher_row["teacher_id"]
                    st.success(f"Знайдено записів: {len(found)}")
                except Exception as e:
                    st.error(f"Помилка пошуку публікацій: {e}")

    found_publications = st.session_state.get("found_publications", [])
    found_teacher_id = st.session_state.get("found_publications_teacher_id")

    if found_publications:
        st.markdown("#### Попередній перегляд знайдених публікацій")
        preview_df = pd.DataFrame(found_publications)
        preview_df = preview_df.rename(columns={
            "title": "Назва",
            "year": "Рік",
            "doi": "DOI",
            "source": "Джерело",
        })
        st.dataframe(preview_df, use_container_width=True, hide_index=True)

        if st.button("Імпортувати знайдені публікації", use_container_width=True):
            try:
                for item in found_publications:
                    pub_id = service.get_next_id("P", "Publication", "publication_id", 5)
                    service.upsert_publication(
                        publication_id=pub_id,
                        title=item.get("title", "").strip(),
                        year=item.get("year"),
                        doi=item.get("doi", "").strip(),
                        pub_type=item.get("pub_type", "").strip(),
                        source=item.get("source", "").strip(),
                        source_url=item.get("source_url", "").strip(),
                        notes=item.get("notes", "").strip(),
                        teacher_ids=[found_teacher_id] if found_teacher_id else [],
                        topics=item.get("topics", []),
                    )
                st.success("Публікації імпортовано без дублювання.")
                st.session_state["found_publications"] = []
                st.session_state["found_publications_teacher_id"] = None
                st.rerun()
            except Exception as e:
                st.error(f"Помилка імпорту публікацій: {e}")

    publication_rows = service.get_publications()
    if publication_rows:
        df = rename_publication_df(pd.DataFrame(publication_rows))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("Публікацій ще не додано.")

    teacher_options = service.get_teacher_options()
    teacher_map = {
        f"{row['teacher_id']} — {row['full_name']}": row["teacher_id"]
        for row in teacher_options
    }

    with st.expander("Додати публікацію вручну"):
        next_publication_id = service.get_next_id("P", "Publication", "publication_id", 5)

        with st.form("publication_form", clear_on_submit=True):
            publication_id = st.text_input("Код публікації", value=next_publication_id)
            title = st.text_area("Назва публікації")
            year_raw = st.text_input("Рік")
            doi = st.text_input("DOI")
            pub_type = st.text_input("Тип публікації")
            source = st.text_input("Джерело")
            source_url = st.text_input("Посилання")
            notes = st.text_area("Примітки")

            selected_teachers = st.multiselect(
                "Автори",
                options=list(teacher_map.keys()),
            )
            topics_raw = st.text_input("Теми через кому")

            save_publication = st.form_submit_button("Зберегти")

            if save_publication:
                if not publication_id.strip() or not title.strip():
                    st.warning("Заповни код і назву публікації.")
                elif not selected_teachers:
                    st.warning("Оберіть хоча б одного автора.")
                else:
                    year_value = None
                    if year_raw.strip():
                        try:
                            year_value = int(year_raw.strip())
                        except ValueError:
                            st.warning("Рік має бути числом.")
                            st.stop()

                    author_ids = [teacher_map[label] for label in selected_teachers]
                    topics = [x.strip() for x in topics_raw.split(",") if x.strip()]

                    try:
                        service.upsert_publication(
                            publication_id=publication_id.strip(),
                            title=title.strip(),
                            year=year_value,
                            doi=doi.strip(),
                            pub_type=pub_type.strip(),
                            source=source.strip(),
                            source_url=source_url.strip(),
                            notes=notes.strip(),
                            teacher_ids=author_ids,
                            topics=topics,
                        )
                        st.success("Публікацію додано, дублікати не створено.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Помилка: {e}")

with tab4:
    st.markdown("### Аналітика наукової взаємодії")

    a1, a2, a3, a4 = st.tabs([
        "Найпродуктивніші викладачі",
        "Найсильніші зв’язки співавторства",
        "Статистика по кафедрах",
        "Індекс наукової активності",
    ])

    with a1:
        limit_teachers = st.number_input(
            "Кількість записів",
            min_value=1,
            max_value=100,
            value=10,
            step=1,
            key="limit_teachers",
        )
        if st.button("Показати", key="show_top_teachers"):
            rows = service.get_top_teachers_by_publications(int(limit_teachers))
            if rows:
                df = rename_top_teachers_df(pd.DataFrame(rows))
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Недостатньо даних.")

    with a2:
        limit_links = st.number_input(
            "Кількість зв’язків",
            min_value=1,
            max_value=100,
            value=10,
            step=1,
            key="limit_links",
        )
        if st.button("Показати", key="show_top_coauthors"):
            rows = service.get_top_coauthors(int(limit_links))
            if rows:
                df = rename_top_coauthors_df(pd.DataFrame(rows))
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Недостатньо даних.")

    with a3:
        if st.button("Показати статистику кафедр", key="show_department_stats"):
            rows = service.get_department_stats()
            if rows:
                df = rename_department_stats_df(pd.DataFrame(rows))
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Недостатньо даних.")

    with a4:
        if st.button("Розрахувати індекс активності", key="show_activity_index"):
            rows = service.get_teacher_activity_index()
            if rows:
                df = rename_activity_index_df(pd.DataFrame(rows))
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("Недостатньо даних.")
