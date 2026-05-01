from __future__ import annotations

import re
from textwrap import dedent
from html import escape, unescape
from typing import TYPE_CHECKING, Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import get_connection_help_text, get_neo4j_config
from data.loaders import load_teachers_seed
from data.seed_data import DEPARTMENTS, FACULTIES

if TYPE_CHECKING:
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
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

        :root {
            --bg-main: #07111f;
            --bg-shell: rgba(7, 17, 31, 0.86);
            --bg-card: rgba(10, 25, 47, 0.78);
            --bg-card-strong: rgba(14, 34, 61, 0.92);
            --bg-card-soft: rgba(11, 29, 53, 0.62);
            --line-soft: rgba(148, 163, 184, 0.16);
            --line-strong: rgba(96, 165, 250, 0.20);
            --text-main: #e5eefb;
            --text-soft: #9fb3c9;
            --text-muted: #6f88a5;
            --teal: #2dd4bf;
            --cyan: #38bdf8;
            --amber: #f59e0b;
            --shadow: 0 22px 60px rgba(2, 8, 23, 0.38);
        }

        html, body, [class*="css"] {
            font-family: "Manrope", sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at 12% 18%, rgba(45, 212, 191, 0.16), transparent 28%),
                radial-gradient(circle at 86% 14%, rgba(56, 189, 248, 0.14), transparent 26%),
                radial-gradient(circle at 52% 88%, rgba(245, 158, 11, 0.10), transparent 24%),
                linear-gradient(180deg, #07111f 0%, #081526 42%, #091827 100%);
            color: var(--text-main);
        }

        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background-image:
                linear-gradient(rgba(148, 163, 184, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(148, 163, 184, 0.05) 1px, transparent 1px);
            background-size: 72px 72px;
            mask-image: radial-gradient(circle at center, black 38%, transparent 88%);
            opacity: 0.24;
        }

        [data-testid="stAppViewContainer"] {
            background: transparent;
        }

        [data-testid="stHeader"] {
            background: rgba(7, 17, 31, 0.82);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(96, 165, 250, 0.08);
        }

        .block-container {
            max-width: 1320px;
            padding-top: 4.4rem;
            padding-bottom: 2.4rem;
        }

        h1, h2, h3 {
            font-family: "Space Grotesk", "Manrope", sans-serif;
            color: var(--text-main);
            letter-spacing: -0.04em;
        }

        h3 {
            font-size: 1.55rem;
            margin-bottom: 0.7rem;
        }

        p, li, label, span, div {
            color: inherit;
        }

        .hero-card {
            position: relative;
            overflow: hidden;
            border: 1px solid var(--line-strong);
            background:
                linear-gradient(135deg, rgba(18, 38, 63, 0.94), rgba(8, 24, 43, 0.96)),
                radial-gradient(circle at top right, rgba(56, 189, 248, 0.22), transparent 32%);
            border-radius: 30px;
            padding: 1.55rem 1.8rem;
            box-shadow: var(--shadow);
            margin-bottom: 1.1rem;
            isolation: isolate;
        }

        .hero-card::before {
            content: "";
            position: absolute;
            width: 360px;
            height: 360px;
            right: -120px;
            top: -120px;
            border-radius: 999px;
            background: radial-gradient(circle, rgba(45, 212, 191, 0.20) 0%, rgba(45, 212, 191, 0.02) 58%, transparent 70%);
            filter: blur(6px);
            animation: drift 16s ease-in-out infinite;
            z-index: -1;
        }

        .hero-kicker {
            display: inline-block;
            border-radius: 999px;
            padding: 0.45rem 0.85rem;
            background: rgba(45, 212, 191, 0.10);
            color: #8cf0df;
            font-size: 0.8rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.12em;
            margin-bottom: 0.9rem;
            border: 1px solid rgba(45, 212, 191, 0.16);
        }

        .hero-title {
            max-width: 980px;
            font-size: clamp(1.75rem, 2.35vw, 2.8rem);
            font-weight: 800;
            line-height: 1.02;
            margin-bottom: 0.22rem;
        }

        .hero-subtitle {
            font-size: 1.02rem;
            line-height: 1.72;
            color: var(--text-soft);
            max-width: 920px;
        }

        .info-card {
            border: 1px solid var(--line-soft);
            border-radius: 24px;
            background:
                linear-gradient(180deg, rgba(10, 25, 47, 0.88), rgba(8, 22, 41, 0.92));
            padding: 1.15rem 1.2rem;
            box-shadow: var(--shadow);
            backdrop-filter: blur(16px);
            margin-bottom: 0.9rem;
        }

        .info-card h3 {
            margin-top: 0.1rem;
            margin-bottom: 0.7rem;
        }

        .info-card div {
            color: var(--text-soft);
            line-height: 1.72;
        }

        .section-heading {
            margin: 0.05rem 0 0.7rem;
        }

        .section-heading-title {
            font-family: "Space Grotesk", "Manrope", sans-serif;
            font-size: 1.25rem;
            font-weight: 700;
            letter-spacing: -0.04em;
            color: var(--text-main);
        }

        .section-heading-subtitle {
            margin-top: 0.28rem;
            color: var(--text-soft);
            font-size: 0.95rem;
            line-height: 1.65;
        }

        .empty-state {
            border: 1px dashed rgba(148, 163, 184, 0.18);
            border-radius: 24px;
            background: rgba(8, 22, 41, 0.72);
            padding: 1.2rem 1.2rem;
            box-shadow: var(--shadow);
        }

        .empty-state-title {
            font-family: "Space Grotesk", "Manrope", sans-serif;
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-main);
            margin-bottom: 0.4rem;
        }

        .empty-state-body {
            color: var(--text-soft);
            line-height: 1.7;
        }

        .summary-strip {
            border: 1px solid var(--line-soft);
            border-radius: 24px;
            background: linear-gradient(180deg, rgba(10, 25, 47, 0.78), rgba(8, 22, 41, 0.92));
            padding: 1rem 1.05rem;
            box-shadow: var(--shadow);
            margin-bottom: 0.9rem;
        }

        .summary-strip-title {
            color: var(--text-soft);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.75rem;
            font-weight: 800;
            margin-bottom: 0.4rem;
        }

        .summary-strip-value {
            font-family: "Space Grotesk", "Manrope", sans-serif;
            font-size: clamp(1.1rem, 1.55vw, 1.55rem);
            font-weight: 700;
            letter-spacing: -0.04em;
            color: var(--text-main);
            word-break: break-word;
            line-height: 1.15;
        }

        .summary-strip-caption {
            margin-top: 0.35rem;
            color: var(--text-muted);
            font-size: 0.88rem;
            line-height: 1.55;
        }

        .kv-card {
            border: 1px solid var(--line-soft);
            border-radius: 24px;
            background:
                linear-gradient(180deg, rgba(10, 25, 47, 0.88), rgba(8, 22, 41, 0.94));
            padding: 1.1rem 1.2rem;
            box-shadow: var(--shadow);
            backdrop-filter: blur(16px);
        }

        .kv-title {
            font-family: "Space Grotesk", "Manrope", sans-serif;
            font-size: 1.15rem;
            font-weight: 700;
            margin-bottom: 0.75rem;
            color: var(--text-main);
        }

        .kv-row {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            border-top: 1px dashed rgba(148, 163, 184, 0.14);
            padding: 0.72rem 0;
            font-size: 0.96rem;
        }

        .kv-row:first-of-type {
            border-top: none;
            padding-top: 0;
        }

        .kv-label {
            color: var(--text-soft);
        }

        .kv-value {
            font-weight: 700;
            color: var(--text-main);
            text-align: right;
            word-break: break-word;
            max-width: 64%;
        }

        div[data-testid="stMetric"] {
            position: relative;
            overflow: hidden;
            background:
                linear-gradient(180deg, rgba(10, 25, 47, 0.84), rgba(8, 22, 41, 0.96));
            border: 1px solid var(--line-soft);
            border-radius: 24px;
            padding: 1.05rem 1.1rem;
            min-height: 7.4rem;
            box-shadow: var(--shadow);
        }

        div[data-testid="stMetric"]::after {
            content: "";
            position: absolute;
            inset: auto 0 0 0;
            height: 3px;
            background: linear-gradient(90deg, var(--teal), var(--cyan), var(--amber));
            opacity: 0.92;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.84rem;
            color: var(--text-soft);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            line-height: 1.35;
        }

        div[data-testid="stMetricLabel"] p {
            line-height: 1.35;
            margin-bottom: 0;
        }

        div[data-testid="stMetricValue"] {
            font-size: 2rem;
            color: var(--text-main);
            font-family: "Space Grotesk", "Manrope", sans-serif;
            letter-spacing: -0.04em;
        }

        div.stButton > button {
            min-height: 3rem;
            border-radius: 18px;
            border: 1px solid rgba(56, 189, 248, 0.24);
            background: linear-gradient(180deg, rgba(17, 39, 66, 0.95), rgba(10, 25, 47, 0.98));
            color: var(--text-main);
            font-weight: 700;
            box-shadow: 0 18px 32px rgba(2, 8, 23, 0.28);
            transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
        }

        div.stButton > button:hover {
            border-color: rgba(45, 212, 191, 0.5);
            box-shadow: 0 18px 42px rgba(45, 212, 191, 0.10);
            transform: translateY(-1px);
        }

        div.stButton > button[kind="tertiary"] {
            min-height: auto;
            min-width: auto;
            padding: 0;
            border: none;
            background: transparent;
            color: var(--text-main);
            box-shadow: none;
            font-size: 1.25rem;
            font-weight: 700;
            line-height: 1.2;
            justify-content: flex-start;
        }

        div.stButton > button[kind="tertiary"]:hover {
            background: transparent;
            box-shadow: none;
            color: #8cf0df;
            text-decoration: underline;
            transform: none;
        }

        div[data-baseweb="select"] > div,
        div[data-baseweb="base-input"] > div,
        .stTextInput > div > div,
        .stNumberInput > div > div {
            border-radius: 18px;
            background: rgba(9, 24, 43, 0.88);
            border: 1px solid rgba(96, 165, 250, 0.15);
            color: var(--text-main);
            box-shadow: 0 14px 26px rgba(2, 8, 23, 0.18);
        }

        label[data-testid="stWidgetLabel"] p {
            color: var(--text-soft);
            font-weight: 700;
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(4, 13, 26, 0.96), rgba(8, 22, 41, 0.98));
            border-right: 1px solid rgba(96, 165, 250, 0.10);
        }

        [data-testid="stSidebar"] > div:first-child {
            background: transparent;
        }

        [data-testid="stSidebarNav"] {
            background: transparent;
            padding-top: 0.4rem;
        }

        [data-testid="stSidebarNav"] ul {
            gap: 0.38rem;
        }

        [data-testid="stSidebarNavLink"] {
            border-radius: 16px;
            background: rgba(255, 255, 255, 0.01);
            border: 1px solid transparent;
            transition: background 0.18s ease, border-color 0.18s ease, transform 0.18s ease;
        }

        [data-testid="stSidebarNavLink"]:hover {
            background: rgba(45, 212, 191, 0.08);
            border-color: rgba(45, 212, 191, 0.16);
            transform: translateX(2px);
        }

        [data-testid="stSidebarNavLink"] span {
            color: var(--text-soft);
            font-weight: 700;
        }

        [data-testid="stSidebarNavLink"][aria-current="page"] {
            background: linear-gradient(90deg, rgba(45, 212, 191, 0.14), rgba(56, 189, 248, 0.08));
            border-color: rgba(45, 212, 191, 0.22);
            box-shadow: inset 0 0 0 1px rgba(45, 212, 191, 0.06);
        }

        [data-testid="stSidebarNavLink"][aria-current="page"] span {
            color: #f3fbff;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--line-soft);
            border-radius: 24px;
            overflow: hidden;
            box-shadow: var(--shadow);
            background: rgba(8, 22, 41, 0.84);
        }

        [data-testid="stTable"] {
            border-radius: 24px;
            overflow: hidden;
        }

        [data-testid="stAlert"] {
            background: rgba(14, 34, 61, 0.92);
            color: var(--text-main);
            border: 1px solid rgba(96, 165, 250, 0.16);
            border-radius: 20px;
            box-shadow: var(--shadow);
        }

        .stAlert p {
            color: var(--text-soft);
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--line-soft);
            border-radius: 20px;
            background: rgba(9, 24, 43, 0.74);
        }

        [data-testid="stExpander"] details summary p {
            color: var(--text-main);
            font-weight: 700;
        }

        div[role="dialog"] {
            width: min(96vw, 1520px) !important;
            max-width: 96vw !important;
            border-radius: 28px !important;
            border: 1px solid rgba(96, 165, 250, 0.18) !important;
            background:
                linear-gradient(180deg, rgba(8, 22, 41, 0.97), rgba(7, 19, 35, 0.98)) !important;
            box-shadow: 0 28px 100px rgba(2, 8, 23, 0.52) !important;
            backdrop-filter: blur(18px);
        }

        div[role="dialog"] [data-testid="stVerticalBlock"] {
            gap: 0.8rem;
        }

        div[role="dialog"] h1,
        div[role="dialog"] h2,
        div[role="dialog"] h3,
        div[role="dialog"] label,
        div[role="dialog"] p,
        div[role="dialog"] span {
            color: var(--text-main);
        }

        div[role="dialog"]::before {
            content: "";
            position: absolute;
            inset: 0;
            border-radius: 28px;
            pointer-events: none;
            background:
                radial-gradient(circle at top right, rgba(45, 212, 191, 0.12), transparent 24%),
                radial-gradient(circle at bottom left, rgba(56, 189, 248, 0.10), transparent 28%);
        }

        [data-testid="stMarkdownContainer"] p code,
        code {
            background: rgba(45, 212, 191, 0.10);
            color: #94f5e7;
            border-radius: 10px;
            padding: 0.16rem 0.42rem;
            border: 1px solid rgba(45, 212, 191, 0.12);
        }

        .sidebar-brand {
            margin-bottom: 1.1rem;
            padding: 0.1rem 0 0.95rem;
            border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        }

        .sidebar-brand-kicker {
            color: var(--text-muted);
            text-transform: uppercase;
            font-size: 0.7rem;
            letter-spacing: 0.16em;
            font-weight: 800;
            margin-bottom: 0.24rem;
        }

        .sidebar-brand-title {
            font-family: "Space Grotesk", "Manrope", sans-serif;
            font-size: 1.02rem;
            font-weight: 700;
            color: var(--text-main);
            line-height: 1.28;
        }

        .sidebar-section-label {
            margin: 1rem 0 0.55rem;
            color: var(--text-soft);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-size: 0.76rem;
            font-weight: 800;
        }

        .sidebar-model {
            margin-top: 1.25rem;
            padding-top: 1rem;
            border-top: 1px solid rgba(148, 163, 184, 0.10);
            color: var(--text-muted);
            font-size: 0.82rem;
            line-height: 1.7;
        }

        @keyframes drift {
            0% { transform: translate3d(0, 0, 0) scale(1); }
            50% { transform: translate3d(-24px, 18px, 0) scale(1.05); }
            100% { transform: translate3d(0, 0, 0) scale(1); }
        }

        @media (max-width: 960px) {
            .block-container {
                padding-top: 3.05rem;
                padding-bottom: 1.4rem;
            }

            .hero-card {
                padding: 1.3rem 1.1rem;
                border-radius: 24px;
            }

            div[data-testid="stMetricValue"] {
                font-size: 1.65rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title: str, subtitle: str = "", kicker: str = "") -> None:
    normalized_title = str(title or "").strip()
    normalized_subtitle = str(subtitle or "").strip()
    combined = "\n".join(part for part in [normalized_title, normalized_subtitle] if part)
    if "hero-title" in combined or "hero-subtitle" in combined:
        title_match = re.search(r'hero-title[^>]*>(.*?)</div>', combined, re.IGNORECASE | re.DOTALL)
        subtitle_match = re.search(r'hero-subtitle[^>]*>(.*?)</div>', combined, re.IGNORECASE | re.DOTALL)
        if title_match:
            normalized_title = title_match.group(1)
        if subtitle_match:
            normalized_subtitle = subtitle_match.group(1)

    normalized_title = re.sub(r"<[^>]+>", "", normalized_title)
    normalized_subtitle = re.sub(r"<[^>]+>", "", normalized_subtitle)
    normalized_kicker = re.sub(r"<[^>]+>", "", str(kicker or "").strip())

    content_lines = ['<div class="hero-card">']
    if normalized_kicker:
        content_lines.append(f'<div class="hero-kicker">{escape(unescape(normalized_kicker))}</div>')
    content_lines.append(f'<div class="hero-title">{escape(unescape(normalized_title))}</div>')
    if normalized_subtitle:
        content_lines.append(f'<div class="hero-subtitle">{escape(unescape(normalized_subtitle))}</div>')
    content_lines.append("</div>")
    st.markdown("\n".join(content_lines), unsafe_allow_html=True)


def render_info_card(title: str, body: str) -> None:
    st.markdown(
        dedent(
            f"""
            <div class="info-card">
                <h3>{escape(title)}</h3>
                <div>{escape(body)}</div>
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_section_heading(title: str, subtitle: str = "") -> None:
    subtitle_markup = f'<div class="section-heading-subtitle">{escape(subtitle)}</div>' if subtitle else ""
    st.markdown(
        dedent(
            f"""
            <div class="section-heading">
                <div class="section-heading-title">{escape(title)}</div>
                {subtitle_markup}
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_fullscreen_dataframe_heading(
    title: str,
    frame: pd.DataFrame,
    *,
    key: str,
    subtitle: str = "",
    caption: str = "",
) -> None:
    if frame.empty:
        render_section_heading(title, subtitle)
        return
    if st.button(title, key=key, type="tertiary", help="Відкрити на весь екран"):
        _fullscreen_dataframe_dialog(title, frame, caption)
    if subtitle:
        st.markdown(
            f'<div class="section-heading-subtitle">{escape(subtitle)}</div>',
            unsafe_allow_html=True,
        )


def render_fullscreen_bar_chart_heading(
    title: str,
    data: pd.DataFrame,
    *,
    key: str,
    subtitle: str = "",
    caption: str = "",
) -> None:
    if data.empty:
        render_section_heading(title, subtitle)
        return
    if st.button(title, key=key, type="tertiary", help="Відкрити на весь екран"):
        _fullscreen_bar_chart_dialog(title, data, caption)
    if subtitle:
        st.markdown(
            f'<div class="section-heading-subtitle">{escape(subtitle)}</div>',
            unsafe_allow_html=True,
        )


def render_fullscreen_html_heading(
    title: str,
    html: str,
    *,
    key: str,
    subtitle: str = "",
    caption: str = "",
    height: int = 980,
) -> None:
    if not html.strip():
        render_section_heading(title, subtitle)
        return
    if st.button(title, key=key, type="tertiary", help="Відкрити на весь екран"):
        _fullscreen_html_dialog(title, html, height, caption)
    if subtitle:
        st.markdown(
            f'<div class="section-heading-subtitle">{escape(subtitle)}</div>',
            unsafe_allow_html=True,
        )


def render_empty_state(title: str, body: str) -> None:
    st.markdown(
        dedent(
            f"""
            <div class="empty-state">
                <div class="empty-state-title">{escape(title)}</div>
                <div class="empty-state-body">{escape(body)}</div>
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_summary_strip(title: str, value: str, caption: str = "") -> None:
    caption_markup = f'<div class="summary-strip-caption">{escape(caption)}</div>' if caption else ""
    st.markdown(
        dedent(
            f"""
            <div class="summary-strip">
                <div class="summary-strip-title">{escape(title)}</div>
                <div class="summary-strip-value">{escape(value)}</div>
                {caption_markup}
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )


def render_key_value_card(title: str, items: list[tuple[str, str]]) -> None:
    rows = "".join(
        [
            f'<div class="kv-row"><div class="kv-label">{escape(label)}</div><div class="kv-value">{escape(value or "—")}</div></div>'
            for label, value in items
        ]
    )
    st.markdown(
        dedent(
            f"""
            <div class="kv-card">
                <div class="kv-title">{escape(title)}</div>
                {rows}
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )


if hasattr(st, "dialog"):
    @st.dialog("Перегляд на весь екран", width="large")
    def _fullscreen_dataframe_dialog(title: str, frame: pd.DataFrame, caption: str = "") -> None:
        render_section_heading(title, caption)
        st.dataframe(frame, use_container_width=True, hide_index=True, height=760)


    @st.dialog("Перегляд на весь екран", width="large")
    def _fullscreen_bar_chart_dialog(title: str, data: pd.DataFrame, caption: str = "") -> None:
        render_section_heading(title, caption)
        st.bar_chart(data, use_container_width=True, height=760)


    @st.dialog("Перегляд на весь екран", width="large")
    def _fullscreen_html_dialog(title: str, html: str, height: int, caption: str = "") -> None:
        render_section_heading(title, caption)
        components.html(html, height=height, scrolling=False)
else:
    def _fullscreen_dataframe_dialog(title: str, frame: pd.DataFrame, caption: str = "") -> None:
        st.info("Повноекранний перегляд недоступний у цьому середовищі.")
        st.dataframe(frame, use_container_width=True, hide_index=True)


    def _fullscreen_bar_chart_dialog(title: str, data: pd.DataFrame, caption: str = "") -> None:
        st.info("Повноекранний перегляд недоступний у цьому середовищі.")
        st.bar_chart(data, use_container_width=True)


    def _fullscreen_html_dialog(title: str, html: str, height: int, caption: str = "") -> None:
        st.info("Повноекранний перегляд недоступний у цьому середовищі.")
        components.html(html, height=height, scrolling=False)


@st.cache_resource(show_spinner=False)
def _build_service(uri: str, user: str, password: str, database: str) -> Neo4jService:
    from services.neo4j_service import Neo4jService

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
    except ModuleNotFoundError as exc:
        st.error("Не вдалося запустити клієнт Neo4j у середовищі Streamlit Cloud.")
        st.caption(
            "Найімовірніше, залежність `neo4j` ще не встановилася або збірка середовища завершилася з помилкою. "
            "Перевірте `Logs` і виконайте `Redeploy` після завершення встановлення залежностей."
        )
        st.code(str(exc))
        st.stop()
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
        st.markdown(
            """
            <div class="sidebar-brand">
                <div class="sidebar-brand-kicker">KSU</div>
                <div class="sidebar-brand-title">Академічна мережа</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.expander("Керування базою", expanded=False):
            if st.button("Перевірити підключення", use_container_width=True):
                try:
                    service.verify_connection()
                    st.success("Підключення до Neo4j Aura активне.")
                except Exception as exc:
                    st.error(f"Помилка підключення: {exc}")

            if st.button("Створити схему та індекси", use_container_width=True):
                try:
                    service.prepare_database()
                    st.success("Обмеження та індекси створено.")
                except Exception as exc:
                    st.error(f"Не вдалося підготувати схему: {exc}")

            if st.button("Заповнити факультети та кафедри", use_container_width=True):
                try:
                    service.seed_reference_data(FACULTIES, DEPARTMENTS)
                    st.success("Довідник факультетів і кафедр оновлено.")
                except Exception as exc:
                    st.error(f"Не вдалося заповнити довідник: {exc}")

            if st.button("Завантажити викладачів KSU", use_container_width=True):
                try:
                    service.seed_reference_data(FACULTIES, DEPARTMENTS)
                    teachers = load_teachers_seed()
                    service.seed_teachers(teachers)
                    st.success(f"Завантажено {len(teachers)} викладачів KSU.")
                except Exception as exc:
                    st.error(f"Не вдалося завантажити викладачів: {exc}")
