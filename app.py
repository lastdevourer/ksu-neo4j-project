from __future__ import annotations

from importlib import import_module

import streamlit as st

from config import is_admin_mode
from ui.components import setup_page
from ui.sidebar import render_sidebar


PAGES: dict[str, dict[str, object]] = {
    "dashboard": {"title": "Дашборд", "section": "Огляд", "module": "views.dashboard"},
    "graph": {"title": "Граф", "section": "Огляд", "module": "views.graph"},
    "analytics": {"title": "Аналітика", "section": "Огляд", "module": "views.analytics"},
    "teachers": {"title": "Викладачі", "section": "Каталог", "module": "views.teachers"},
    "publications": {"title": "Публікації", "section": "Каталог", "module": "views.publications"},
    "structure": {"title": "Структура", "section": "Адміністрування", "module": "views.structure"},
    "data-center": {"title": "Центр даних", "section": "Адміністрування", "module": "views.data_center"},
}

DEFAULT_PAGE = "dashboard"


def _visible_pages() -> dict[str, dict[str, object]]:
    admin_mode = is_admin_mode()
    return {
        key: page
        for key, page in PAGES.items()
        if admin_mode or page["section"] != "Адміністрування"
    }


def _resolve_current_page(visible_pages: dict[str, dict[str, object]]) -> str:
    raw_query_page = str(st.query_params.get("page", "") or "").strip()
    session_page = str(st.session_state.get("current_page", "") or "").strip()

    if raw_query_page in visible_pages:
        page = raw_query_page
    elif session_page in visible_pages:
        page = session_page
    else:
        page = DEFAULT_PAGE

    st.session_state["current_page"] = page
    st.query_params["page"] = page
    return page


def _render_page(page_meta: dict[str, object]) -> None:
    module = import_module(str(page_meta["module"]))
    render = getattr(module, "render")
    render()


setup_page("Академічна мережа KSU")
visible_pages = _visible_pages()
current_page = _resolve_current_page(visible_pages)
selected_page = render_sidebar(current_page=current_page, pages=visible_pages)

if selected_page != current_page:
    st.session_state["current_page"] = selected_page
    st.query_params["page"] = selected_page
    st.rerun()

_render_page(visible_pages[current_page])
