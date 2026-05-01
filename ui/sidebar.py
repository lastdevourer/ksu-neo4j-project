from __future__ import annotations

import streamlit as st

from config import get_admin_password, is_admin_mode


def render_sidebar(
    *,
    current_page: str,
    pages: dict[str, dict[str, object]],
) -> str:
    selected_page = current_page
    section_order = ["Огляд", "Каталог", "Адміністрування"]
    admin_password = get_admin_password()

    with st.sidebar:
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-kicker">KSU</div>
                <div class="sidebar-brand-title">Наукові публікації</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        for section_name in section_order:
            section_pages = [
                (page_key, page_meta)
                for page_key, page_meta in pages.items()
                if page_meta.get("section") == section_name
            ]
            if not section_pages:
                continue

            st.markdown(f"**{section_name}**")
            for page_key, page_meta in section_pages:
                button_type = "primary" if page_key == current_page else "secondary"
                if st.button(
                    str(page_meta["title"]),
                    key=f"sidebar_nav_{page_key}",
                    use_container_width=True,
                    type=button_type,
                ):
                    selected_page = page_key

        if admin_password:
            st.markdown("---")
            st.markdown("**Режим керування**")
            if is_admin_mode():
                st.success("Адмінрежим розблоковано для поточної сесії.")
                if st.button(
                    "Закрити адмінрежим",
                    key="sidebar_lock_admin_mode",
                    use_container_width=True,
                ):
                    st.session_state["admin_unlocked"] = False
                    if current_page in {"structure", "data-center"}:
                        st.session_state["current_page"] = "dashboard"
                        st.query_params["page"] = "dashboard"
                    st.rerun()
            else:
                entered_password = st.text_input(
                    "Пароль адміністратора",
                    type="password",
                    key="sidebar_admin_password",
                    placeholder="Введіть пароль для редагування",
                )
                if st.button(
                    "Розблокувати адмінрежим",
                    key="sidebar_unlock_admin_mode",
                    use_container_width=True,
                ):
                    if entered_password == admin_password:
                        st.session_state["admin_unlocked"] = True
                        st.session_state.pop("sidebar_admin_password", None)
                        st.rerun()
                    st.error("Невірний пароль адміністратора.")

    return selected_page
