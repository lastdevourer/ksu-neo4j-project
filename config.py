from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
import streamlit as st


load_dotenv()


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str = ""


@dataclass(frozen=True)
class PublicationImportConfig:
    openalex_api_key: str = ""
    crossref_mailto: str = ""
    orcid_client_id: str = ""
    orcid_client_secret: str = ""
    scopus_api_key: str = ""
    scopus_insttoken: str = ""
    wos_api_key: str = ""
    max_works_per_teacher: int = 40
    auto_sync_enabled: bool = False
    auto_sync_interval_hours: int = 24
    auto_sync_teacher_limit: int = 25
    auto_sync_include_scholar: bool = False


def _read_streamlit_secret(key: str) -> str:
    try:
        value = st.secrets[key]
    except Exception:
        return ""
    return str(value).strip()


def _read_bool_setting(key: str, default: bool = False) -> bool:
    raw = _read_streamlit_secret(key) or os.getenv(key, "").strip()
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def is_admin_mode() -> bool:
    if bool(st.session_state.get("admin_unlocked", False)):
        return True
    return _read_bool_setting("ADMIN_MODE", default=False)


def get_admin_password() -> str:
    return _read_streamlit_secret("ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", "").strip()


def get_neo4j_config() -> Neo4jConfig | None:
    uri = _read_streamlit_secret("NEO4J_URI") or os.getenv("NEO4J_URI", "").strip()
    user = _read_streamlit_secret("NEO4J_USER") or os.getenv("NEO4J_USER", "").strip()
    password = _read_streamlit_secret("NEO4J_PASSWORD") or os.getenv("NEO4J_PASSWORD", "").strip()
    database = _read_streamlit_secret("NEO4J_DATABASE") or os.getenv("NEO4J_DATABASE", "").strip()

    if not (uri and user and password):
        return None

    return Neo4jConfig(uri=uri, user=user, password=password, database=database)


def get_publication_import_config() -> PublicationImportConfig:
    max_works_value = _read_streamlit_secret("PUB_IMPORT_MAX_WORKS_PER_TEACHER") or os.getenv(
        "PUB_IMPORT_MAX_WORKS_PER_TEACHER",
        "",
    ).strip()
    try:
        max_works_per_teacher = max(5, min(int(max_works_value or "40"), 200))
    except ValueError:
        max_works_per_teacher = 40

    interval_value = _read_streamlit_secret("PUB_AUTO_SYNC_INTERVAL_HOURS") or os.getenv(
        "PUB_AUTO_SYNC_INTERVAL_HOURS",
        "",
    ).strip()
    teacher_limit_value = _read_streamlit_secret("PUB_AUTO_SYNC_TEACHER_LIMIT") or os.getenv(
        "PUB_AUTO_SYNC_TEACHER_LIMIT",
        "",
    ).strip()

    try:
        auto_sync_interval_hours = max(1, min(int(interval_value or "24"), 720))
    except ValueError:
        auto_sync_interval_hours = 24

    try:
        auto_sync_teacher_limit = max(5, min(int(teacher_limit_value or "25"), 200))
    except ValueError:
        auto_sync_teacher_limit = 25

    openalex_api_key = _read_streamlit_secret("OPENALEX_API_KEY") or os.getenv("OPENALEX_API_KEY", "").strip()
    crossref_mailto = _read_streamlit_secret("CROSSREF_MAILTO") or os.getenv("CROSSREF_MAILTO", "").strip()
    orcid_client_id = _read_streamlit_secret("ORCID_CLIENT_ID") or os.getenv("ORCID_CLIENT_ID", "").strip()
    orcid_client_secret = _read_streamlit_secret("ORCID_CLIENT_SECRET") or os.getenv("ORCID_CLIENT_SECRET", "").strip()
    scopus_api_key = _read_streamlit_secret("SCOPUS_API_KEY") or os.getenv("SCOPUS_API_KEY", "").strip()
    scopus_insttoken = _read_streamlit_secret("SCOPUS_INSTTOKEN") or os.getenv("SCOPUS_INSTTOKEN", "").strip()
    wos_api_key = _read_streamlit_secret("WOS_API_KEY") or os.getenv("WOS_API_KEY", "").strip()

    has_any_source = bool(
        openalex_api_key
        or crossref_mailto
        or orcid_client_id
        or scopus_api_key
        or wos_api_key
    )
    auto_sync_enabled = _read_bool_setting("PUB_AUTO_SYNC_ENABLED", default=has_any_source)
    auto_sync_include_scholar = _read_bool_setting("PUB_AUTO_SYNC_INCLUDE_SCHOLAR", default=False)

    return PublicationImportConfig(
        openalex_api_key=openalex_api_key,
        crossref_mailto=crossref_mailto,
        orcid_client_id=orcid_client_id,
        orcid_client_secret=orcid_client_secret,
        scopus_api_key=scopus_api_key,
        scopus_insttoken=scopus_insttoken,
        wos_api_key=wos_api_key,
        max_works_per_teacher=max_works_per_teacher,
        auto_sync_enabled=auto_sync_enabled,
        auto_sync_interval_hours=auto_sync_interval_hours,
        auto_sync_teacher_limit=auto_sync_teacher_limit,
        auto_sync_include_scholar=auto_sync_include_scholar,
    )


def get_connection_help_text() -> str:
    return (
        "Для Streamlit Cloud додайте параметри підключення до Neo4j Aura через `Secrets`.\n"
        "Локально можна використовувати `st.secrets` або `.env`:\n\n"
        "`NEO4J_URI`\n"
        "`NEO4J_USER`\n"
        "`NEO4J_PASSWORD`\n"
        "`NEO4J_DATABASE` (необов'язково; якщо є помилка маршрутизації, краще прибрати цей параметр і дати Aura "
        "вибрати домашню базу автоматично)\n"
        "`ADMIN_PASSWORD` (пароль для розблокування режиму керування всередині тієї ж app)\n"
        "`ADMIN_MODE` (`true` лише якщо хочете примусово тримати адмінрежим увімкненим для всіх відвідувачів)"
    )
