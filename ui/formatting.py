import pandas as pd
import streamlit as st


def apply_global_styles():
    st.markdown("""
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }

    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        margin-bottom: 0.25rem;
        letter-spacing: -0.02em;
    }

    .sub-title {
        color: #94a3b8;
        font-size: 1rem;
        margin-bottom: 0.25rem;
        line-height: 1.5;
    }

    .hero-box {
        padding: 1.25rem 1.25rem 1rem 1.25rem;
        border: 1px solid rgba(148,163,184,0.18);
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(15,23,42,0.85), rgba(2,6,23,0.92));
        margin-bottom: 1rem;
    }

    div[data-testid="stMetric"] {
        background: rgba(15,23,42,0.46);
        border: 1px solid rgba(148,163,184,0.15);
        border-radius: 16px;
        padding: 14px 16px;
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.95rem;
    }

    div.stButton > button {
        border-radius: 12px;
        font-weight: 600;
        min-height: 42px;
    }

    div[data-baseweb="tab-list"] {
        gap: 8px;
    }

    div[data-baseweb="tab"] {
        border-radius: 12px 12px 0 0;
    }
    </style>
    """, unsafe_allow_html=True)


def build_metrics(counts: dict):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Факультети", counts["faculties"])
    c2.metric("Кафедри", counts["departments"])
    c3.metric("Викладачі", counts["teachers"])
    c4.metric("Публікації", counts["publications"])

    c5, c6, c7 = st.columns(3)
    c5.metric("Зв’язки авторства", counts["authored"])
    c6.metric("Зв’язки співавторства", counts["coauthor"])
    c7.metric("Тематичні зв’язки", counts["topics"])


def rename_faculty_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "faculty_id": "Код",
        "name": "Назва факультету",
    })
    cols = [c for c in ["Код", "Назва факультету"] if c in df.columns]
    return df[cols]


def rename_department_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "department_id": "Код",
        "name": "Назва кафедри",
        "faculty_id": "Код факультету",
        "faculty_name": "Факультет",
    })
    cols = [c for c in ["Код", "Назва кафедри", "Код факультету", "Факультет"] if c in df.columns]
    return df[cols]


def rename_teacher_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "teacher_id": "Код",
        "full_name": "ПІБ",
        "position": "Посада",
        "academic_degree": "Науковий ступінь",
        "academic_title": "Вчене звання",
        "department_id": "Код кафедри",
        "department_name": "Кафедра",
        "faculty_id": "Код факультету",
        "orcid": "ORCID",
        "google_scholar": "Google Scholar",
        "scopus": "Scopus",
    })
    cols = [c for c in [
        "Код", "ПІБ", "Посада", "Науковий ступінь", "Вчене звання",
        "Код кафедри", "Кафедра", "Код факультету", "ORCID", "Google Scholar", "Scopus"
    ] if c in df.columns]
    return df[cols]


def rename_publication_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={
        "publication_id": "Код",
        "title": "Назва",
        "year": "Рік",
        "doi": "DOI",
        "pub_type": "Тип",
        "source": "Джерело",
    })
    cols = [c for c in ["Код", "Назва", "Рік", "DOI", "Тип", "Джерело"] if c in df.columns]
    return df[cols]


def rename_top_teachers_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={
        "teacher": "Викладач",
        "publications": "Кількість публікацій",
    })


def rename_top_coauthors_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={
        "teacher_a": "Викладач 1",
        "teacher_b": "Викладач 2",
        "shared_publications": "Спільні публікації",
    })


def rename_department_stats_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={
        "department_id": "Код кафедри",
        "department_name": "Кафедра",
        "teachers": "Кількість викладачів",
        "publications": "Кількість публікацій",
    })


def rename_activity_index_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns={
        "teacher": "Викладач",
        "pubs": "Публікації",
        "coauthor_links": "Кількість зв’язків",
        "coauthor_strength": "Сила співавторства",
        "activity_index": "Індекс наукової активності",
    })
