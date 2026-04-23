from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from ui.components import render_header, require_service
from ui.formatters import graph_edges_dataframe
from utils.graph_visualization import build_graph_html


def render() -> None:
    service = require_service()
    render_header(
        "Граф співавторства",
        "Інтерактивна візуалізація мережі авторства, де вузли представляють викладачів і публікації, "
        "а ребра показують зв'язки авторства.",
    )

    departments = service.get_departments()
    department_labels = {"Усі кафедри": ""}
    for row in departments:
        department_labels[f"{row['name']} ({row['code']})"] = row["code"]

    controls = st.columns([1.15, 0.85], gap="large")
    selected_department_label = controls[0].selectbox("Область перегляду", list(department_labels.keys()))
    edge_limit = controls[1].slider("Кількість зв'язків", min_value=30, max_value=240, value=120, step=10)

    edges = service.get_graph_edges(
        department_code=department_labels[selected_department_label],
        limit=edge_limit,
    )

    if not edges:
        st.info("Для побудови графа поки що недостатньо даних.")
        return

    teacher_count = len({edge["teacher_id"] for edge in edges})
    publication_count = len({edge["publication_id"] for edge in edges})
    summary_columns = st.columns(2)
    summary_columns[0].metric("Вузли Teacher", teacher_count)
    summary_columns[1].metric("Вузли Publication", publication_count)

    graph_html = build_graph_html(edges)
    if graph_html:
        components.html(graph_html, height=760, scrolling=False)
    else:
        st.warning(
            "Бібліотека для інтерактивного графа недоступна. Показано табличний fallback зі зв'язками авторства."
        )
        st.dataframe(graph_edges_dataframe(edges), use_container_width=True, hide_index=True)

    with st.expander("Показати таблицю зв'язків", expanded=False):
        st.dataframe(graph_edges_dataframe(edges), use_container_width=True, hide_index=True)
