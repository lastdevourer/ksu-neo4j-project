from __future__ import annotations

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from ui.components import (
    render_empty_state,
    render_fullscreen_dataframe_button,
    render_fullscreen_html_button,
    render_header,
    render_section_heading,
    render_summary_strip,
    require_service,
)
from ui.formatters import coauthor_graph_dataframe, department_collaboration_dataframe, graph_edges_dataframe
from utils.graph_visualization import (
    build_bipartite_graph_html,
    build_coauthor_graph_html,
    build_department_graph_html,
)


def _department_options(service) -> dict[str, str]:
    rows = service.get_departments()
    options = {"Усі кафедри": ""}
    for row in rows:
        options[f"{row['name']} ({row['code']})"] = row["code"]
    return options


def _faculty_options(service) -> dict[str, str]:
    rows = service.get_faculty_overview()
    options = {"Усі факультети": ""}
    for row in rows:
        options[f"{row['name']} ({row['code']})"] = row["code"]
    return options


def _render_table(title: str, frame: pd.DataFrame) -> None:
    with st.expander(title, expanded=False):
        header_columns = st.columns([0.92, 0.08], gap="small")
        with header_columns[1]:
            render_fullscreen_dataframe_button(
                title,
                frame,
                key=f"graph_table_fullscreen_{title}",
            )
        st.dataframe(frame, use_container_width=True, hide_index=True)


def render() -> None:
    service = require_service()
    render_header("Графова аналітика", subtitle="Перемикайте проєкції мережі між авторством, співавторством та міжкафедральними зв'язками.")

    mode = st.radio(
        "Режим мережі",
        ["Авторство", "Співавторство викладачів", "Зв'язки між кафедрами"],
        horizontal=True,
    )
    controls = st.columns([1.15, 0.85], gap="large")
    edge_limit = controls[1].slider("Ліміт зв'язків", min_value=20, max_value=240, value=120, step=10)

    if mode == "Авторство":
        department_labels = _department_options(service)
        selected_department_label = controls[0].selectbox("Кафедра", list(department_labels.keys()))
        edges = service.get_graph_edges(department_code=department_labels[selected_department_label], limit=edge_limit)
        if not edges:
            render_empty_state("Недостатньо даних для графа", "Після завантаження публікацій тут з'явиться мережа авторства.")
            return

        teacher_count = len({edge["teacher_id"] for edge in edges})
        publication_count = len({edge["publication_id"] for edge in edges})
        summary = st.columns(3, gap="medium")
        summary[0].metric("Вузли викладачів", teacher_count)
        summary[1].metric("Вузли публікацій", publication_count)
        summary[2].metric("Зв'язки графа", len(edges))

        graph_html = build_bipartite_graph_html(edges)
        header_columns = st.columns([0.72, 0.28], gap="small")
        with header_columns[0]:
            render_section_heading("Інтерактивна мережа авторства")
        with header_columns[1]:
            if graph_html:
                render_fullscreen_html_button(
                    "Мережа авторства",
                    graph_html,
                    key="graph_bipartite_fullscreen",
                    height=980,
                )
        if graph_html:
            components.html(graph_html, height=760, scrolling=False)
        else:
            render_empty_state(
                "Інтерактивний граф недоступний",
                "Бібліотека візуалізації не підключилася, тому нижче показано табличне представлення зв'язків авторства.",
            )
            st.dataframe(graph_edges_dataframe(edges), use_container_width=True, hide_index=True)
        _render_table("Показати таблицю зв'язків", graph_edges_dataframe(edges))
        return

    if mode == "Співавторство викладачів":
        department_labels = _department_options(service)
        selected_department_label = controls[0].selectbox("Кафедра", list(department_labels.keys()))
        edges = service.get_teacher_coauthor_graph(
            department_code=department_labels[selected_department_label],
            limit=edge_limit,
        )
        if not edges:
            render_empty_state("Немає зв'язків співавторства", "Потрібні спільні публікації між викладачами, щоб побудувати цю проєкцію.")
            return

        teacher_count = len({edge["source_id"] for edge in edges} | {edge["target_id"] for edge in edges})
        total_weight = sum(int(edge.get("weight", 0) or 0) for edge in edges)
        summary = st.columns(3, gap="medium")
        summary[0].metric("Викладачі в мережі", teacher_count)
        summary[1].metric("Пари співавторів", len(edges))
        summary[2].metric("Сумарні спільні роботи", total_weight)

        graph_html = build_coauthor_graph_html(edges)
        fallback_frame = coauthor_graph_dataframe(edges)
        header_columns = st.columns([0.72, 0.28], gap="small")
        with header_columns[0]:
            render_section_heading("Інтерактивна мережа співавторства")
        with header_columns[1]:
            if graph_html:
                render_fullscreen_html_button(
                    "Мережа співавторства викладачів",
                    graph_html,
                    key="graph_coauthor_fullscreen",
                    height=980,
                )
        if graph_html:
            components.html(graph_html, height=760, scrolling=False)
        else:
            render_empty_state(
                "Інтерактивний граф недоступний",
                "Показано табличне fallback-представлення пар співавторів.",
            )
            st.dataframe(fallback_frame, use_container_width=True, hide_index=True)
        _render_table("Показати таблицю пар співавторів", fallback_frame)
        return

    faculty_labels = _faculty_options(service)
    selected_faculty_label = controls[0].selectbox("Факультет", list(faculty_labels.keys()))
    edges = service.get_department_collaboration_edges(
        faculty_code=faculty_labels[selected_faculty_label],
        limit=edge_limit,
    )
    if not edges:
        render_empty_state("Міжкафедральних зв'язків поки немає", "Ця мережа з'явиться після накопичення спільних робіт між кафедрами.")
        return

    department_count = len({edge["source_id"] for edge in edges} | {edge["target_id"] for edge in edges})
    total_weight = sum(int(edge.get("weight", 0) or 0) for edge in edges)
    summary = st.columns(3, gap="medium")
    summary[0].metric("Кафедри в мережі", department_count)
    summary[1].metric("Міжкафедральні зв'язки", len(edges))
    summary[2].metric("Спільні роботи", total_weight)

    graph_html = build_department_graph_html(edges)
    fallback_frame = department_collaboration_dataframe(edges)
    header_columns = st.columns([0.72, 0.28], gap="small")
    with header_columns[0]:
        render_section_heading("Інтерактивна міжкафедральна мережа")
    with header_columns[1]:
        if graph_html:
            render_fullscreen_html_button(
                "Міжкафедральна мережа",
                graph_html,
                key="graph_department_fullscreen",
                height=980,
            )
    if graph_html:
        components.html(graph_html, height=760, scrolling=False)
    else:
        render_empty_state(
            "Інтерактивний граф недоступний",
            "Показано табличне fallback-представлення міжкафедральних зв'язків.",
        )
        st.dataframe(fallback_frame, use_container_width=True, hide_index=True)
    _render_table("Показати таблицю міжкафедральних зв'язків", fallback_frame)
