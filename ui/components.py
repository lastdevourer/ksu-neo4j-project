from __future__ import annotations

from html import escape

import streamlit as st

from config import get_connection_help_text, get_neo4j_config
from data.seed_data import DEPARTMENTS, FACULTIES
from services.neo4j_service import Neo4jService


def setup_page(title: str) -> None:
    st.set_page_config(
        page_title=title,
        layout="wide",
        page_icon=":material/account_tree:",
        initial_sidebar_state="expanded",
    )
    apply_theme()


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(234, 179, 8, 0.10), transparent 32%),
                radial-gradient(circle at top right, rgba(15, 118, 110, 0.10), transparent 26%),
                linear-gradient(180deg, #fffaf0 0%, #f7f3e8 100%);
            color: #1f2937;
            font-family: "Trebuchet MS", "Verdana", sans-serif;
        }

        .block-container {
            max-width: 1320px;
            padding-top: 1.6rem;
            padding-bottom: 2rem;
        }

        h1, h2, h3 {
            font-family: Georgia, "Times New Roman", serif;
            color: #102a43;
            letter-spacing: -0.02em;
        }

        .hero-card {
            border: 1px solid rgba(15, 118, 110, 0.15);
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.94), rgba(250, 244, 230, 0.98));
            border-radius: 24px;
            padding: 1.5rem 1.6rem;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
            margin-bottom: 1rem;
        }

        .hero-kicker {
            display: inline-block;
            border-radius: 999px;
            padding: 0.35rem 0.75rem;
            background: rgba(15, 118, 110, 0.10);
            color: #0f766e;
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.75rem;
        }

        .hero-title {
            font-size: 2.3rem;
            font-weight: 800;
            line-height: 1.08;
            margin-bottom: 0.5rem;
        }

        .hero-subtitle {
            font-size: 1.02rem;
            line-height: 1.65;
            color: #425466;
            max-width: 980px;
        }

        .info-card {
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.82);
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
        }

        .kv-card {
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.88);
            padding: 1rem 1.1rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
        }

        .kv-title {
            font-family: Georgia, "Times New Roman", serif;
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 0.6rem;
            color: #102a43;
        }

        .kv-row {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            border-top: 1px dashed rgba(148, 163, 184, 0.35);
            padding: 0.55rem 0;
            font-size: 0.96rem;
        }

        .kv-row:first-of-type {
            border-top: none;
            padding-top: 0;
        }

        .kv-label {
            color: #52606d;
        }

        .kv-value {
            font-weight: 700;
            color: #102a43;
            text-align: right;
        }

        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(148, 163, 184, 0.18);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.04);
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.92rem;
            color: #52606d;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.6rem;
            color: #102a43;
        }

        div.stButton > button {
            min-height: 2.8rem;
            border-radius: 14px;
            border: 1px solid rgba(15, 118, 110, 0.24);
            background: linear-gradient(180deg, #ffffff, #f3f6f4);
            color: #102a43;
            font-weight: 700;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"] > div {
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="hero-card">
            <div class="hero-kicker">Streamlit + Neo4j MVP</div>
            <div class="hero-title">{escape(title)}</div>
            <div class="hero-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_info_card(title: str, body: str) -> None:
    st.markdown(
        f"""
        <div class="info-card">
            <h3>{escape(title)}</h3>
            <div>{escape(body)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_key_value_card(title: str, items: list[tuple[str, str]]) -> None:
    rows = "".join(
        f"""
        <div class="kv-row">
            <div class="kv-label">{escape(label)}</div>
            <div class="kv-value">{escape(value or "—")}</div>
        </div>
        """
        for label, value in items
    )
    st.markdown(
        f"""
        <div class="kv-card">
            <div class="kv-title">{escape(title)}</div>
            {rows}
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource(show_spinner=False)
def _build_service(uri: str, user: str, password: str, database: str) -> Neo4jService:
    service = Neo4jService(uri=uri, user=user, password=password, database=database)
    service.verify_connection()
    return service


def require_service() -> Neo4jService:
    config = get_neo4j_config()
    if not config:
        st.error("Не знайдено налаштування підключення до Neo4j Aura.")
        st.code(get_connection_help_text())
        st.stop()

    try:
        return _build_service(config.uri, config.user, config.password, config.database)
    except Exception as exc:
        st.error(f"Не вдалося підключитися до Neo4j Aura: {exc}")
        if config.database:
            st.caption(
                "Порада: якщо в `Secrets` вказано `NEO4J_DATABASE`, перевірте назву бази або тимчасово приберіть "
                "цей параметр, щоб Aura використала домашню базу автоматично."
            )
        else:
            st.caption("Перевірте `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` і права доступу до Neo4j Aura.")
        st.stop()


def render_sidebar(service: Neo4jService) -> None:
    with st.sidebar:
        st.markdown("## Керування")
        st.caption("Основний сценарій: Streamlit Cloud + `Secrets`, база даних — Neo4j Aura.")

        if st.button("Перевірити підключення", use_container_width=True):
            try:
                service.verify_connection()
                st.success("Підключення до Neo4j Aura активне.")
            except Exception as exc:
                st.error(f"Помилка підключення: {exc}")

        if st.button("Створити схему та індекси", use_container_width=True):
            try:
                service.prepare_database()
                st.success("Constraints та indexes створено.")
            except Exception as exc:
                st.error(f"Не вдалося підготувати схему: {exc}")

        if st.button("Заповнити факультети та кафедри", use_container_width=True):
            try:
                service.seed_reference_data(FACULTIES, DEPARTMENTS)
                st.success("Довідник факультетів і кафедр оновлено.")
            except Exception as exc:
                st.error(f"Не вдалося заповнити довідник: {exc}")

        st.markdown("---")
        st.caption(
            "Модель даних: `(:Faculty)-[:HAS_DEPARTMENT]->(:Department)` -> "
            "`(:Department)-[:HAS_TEACHER]->(:Teacher)` -> `(:Teacher)-[:AUTHORED]->(:Publication)`"
        )
