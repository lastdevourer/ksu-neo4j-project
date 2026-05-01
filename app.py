from __future__ import annotations

import importlib.util
import platform
from datetime import datetime, timezone

import streamlit as st

from config import get_admin_password, get_neo4j_config, get_publication_import_config


def _package_status(package_name: str) -> str:
    return "так" if importlib.util.find_spec(package_name) else "ні"


def _secret_status() -> list[tuple[str, str]]:
    neo4j_config = get_neo4j_config()
    publication_config = get_publication_import_config()
    return [
        ("Neo4j Aura", "так" if neo4j_config else "ні"),
        ("ADMIN_PASSWORD", "так" if get_admin_password() else "ні"),
        ("OPENALEX_API_KEY", "так" if publication_config.openalex_api_key else "ні"),
        ("ORCID_CLIENT_ID", "так" if publication_config.orcid_client_id else "ні"),
        ("CROSSREF_MAILTO", "так" if publication_config.crossref_mailto else "ні"),
    ]


def _set_mode(mode: str) -> None:
    st.session_state["boot_mode"] = mode
    st.query_params["mode"] = mode


def _current_mode() -> str:
    query_mode = str(st.query_params.get("mode", "") or "").strip().lower()
    if query_mode in {"safe", "full"}:
        st.session_state["boot_mode"] = query_mode
        return query_mode
    session_mode = str(st.session_state.get("boot_mode", "") or "").strip().lower()
    if session_mode in {"safe", "full"}:
        return session_mode
    st.session_state["boot_mode"] = "safe"
    st.query_params["mode"] = "safe"
    return "safe"


st.set_page_config(page_title="KSU Boot Check", layout="wide", page_icon=":material/health_and_safety:")

mode = _current_mode()

if mode == "full":
    try:
        from full_app import run as run_full_app

        run_full_app()
        st.stop()
    except Exception as exc:  # pragma: no cover - runtime guard for Streamlit Cloud
        st.session_state["boot_mode"] = "safe"
        st.query_params["mode"] = "safe"
        st.error("Повна версія не запустилася. Показано безпечний режим.")
        st.exception(exc)

st.title("KSU · безпечний запуск")
st.caption("Тимчасовий режим діагностики для Streamlit Cloud. Він не видаляє дані та не змінює базу.")

action_cols = st.columns([1, 1, 3], gap="medium")
if action_cols[0].button("Запустити повну версію", use_container_width=True):
    _set_mode("full")
    st.rerun()
if action_cols[1].button("Оновити діагностику", use_container_width=True):
    st.rerun()

status_cols = st.columns(3, gap="medium")
status_cols[0].metric("Поточний режим", "SAFE")
status_cols[1].metric("Python", platform.python_version())
status_cols[2].metric("UTC", datetime.now(timezone.utc).strftime("%H:%M:%S"))

st.subheader("Стан середовища")
package_rows = [
    {"Пакет": "streamlit", "Доступний": _package_status("streamlit")},
    {"Пакет": "neo4j", "Доступний": _package_status("neo4j")},
    {"Пакет": "pandas", "Доступний": _package_status("pandas")},
    {"Пакет": "networkx", "Доступний": _package_status("networkx")},
    {"Пакет": "pyvis", "Доступний": _package_status("pyvis")},
]
st.dataframe(package_rows, use_container_width=True, hide_index=True)

st.subheader("Стан secrets")
secret_rows = [{"Параметр": key, "Налаштовано": value} for key, value in _secret_status()]
st.dataframe(secret_rows, use_container_width=True, hide_index=True)

st.info(
    "Якщо цей екран відкривається швидко, то Streamlit Cloud вже працює, а проблема була в старті повної версії. "
    "Далі можна натиснути `Запустити повну версію` та побачити вже точну помилку, якщо вона ще залишилась."
)
