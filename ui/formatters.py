from __future__ import annotations

import pandas as pd


def _frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows or [])


def _join_authors(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item)
    return str(value or "")


def _format_confidence(value: object) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except Exception:
        return "0.00"


def department_overview_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "code": "Код кафедри",
            "name": "Кафедра",
            "faculty_code": "Код факультету",
            "faculty_name": "Факультет",
            "teachers": "Викладачі",
            "publications": "Публікації",
        }
    )
    return renamed[["Кафедра", "Факультет", "Викладачі", "Публікації"]]


def department_overview_dataframe_admin(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "code": "Код кафедри",
            "name": "Кафедра",
            "faculty_code": "Код факультету",
            "faculty_name": "Факультет",
            "teachers": "Викладачі",
            "publications": "Публікації",
        }
    )
    return renamed[["Код кафедри", "Кафедра", "Код факультету", "Факультет", "Викладачі", "Публікації"]]


def faculty_overview_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "code": "Код факультету",
            "name": "Факультет",
            "departments": "Кафедри",
            "teachers": "Викладачі",
            "publications": "Публікації",
        }
    )
    return renamed[["Факультет", "Кафедри", "Викладачі", "Публікації"]]


def faculty_overview_dataframe_admin(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "code": "Код факультету",
            "name": "Факультет",
            "departments": "Кафедри",
            "teachers": "Викладачі",
            "publications": "Публікації",
        }
    )
    return renamed[["Код факультету", "Факультет", "Кафедри", "Викладачі", "Публікації"]]


def teachers_dataframe_public(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "full_name": "ПІБ",
            "position": "Посада",
            "academic_degree": "Науковий ступінь",
            "academic_title": "Вчене звання",
            "department_name": "Кафедра",
            "faculty_name": "Факультет",
            "publications": "Публікації",
        }
    )
    return renamed[["ПІБ", "Посада", "Науковий ступінь", "Вчене звання", "Кафедра", "Факультет", "Публікації"]]


def teachers_dataframe_admin(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "id": "ID",
            "full_name": "ПІБ",
            "position": "Посада",
            "academic_degree": "Науковий ступінь",
            "academic_title": "Вчене звання",
            "department_name": "Кафедра",
            "faculty_name": "Факультет",
            "publications": "Публікації",
        }
    )
    return renamed[["ID", "ПІБ", "Посада", "Науковий ступінь", "Вчене звання", "Кафедра", "Факультет", "Публікації"]]


def teacher_publications_dataframe_public(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["authors"] = df["authors"].apply(_join_authors)
    renamed = df.rename(
        columns={
            "title": "Публікація",
            "status": "Статус",
            "year": "Рік",
            "doi": "DOI",
            "pub_type": "Тип",
            "source": "Джерело",
            "authors": "Автори",
        }
    )
    return renamed[["Публікація", "Статус", "Рік", "DOI", "Тип", "Джерело", "Автори"]]


def teacher_publications_dataframe_admin(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["authors"] = df["authors"].apply(_join_authors)
    if "confidence" in df.columns:
        df["confidence"] = df["confidence"].apply(_format_confidence)
    renamed = df.rename(
        columns={
            "id": "ID",
            "title": "Публікація",
            "status": "Статус",
            "confidence": "Рівень довіри",
            "year": "Рік",
            "doi": "DOI",
            "pub_type": "Тип",
            "source": "Джерело",
            "authors": "Автори",
        }
    )
    return renamed[["ID", "Публікація", "Статус", "Рівень довіри", "Рік", "DOI", "Тип", "Джерело", "Автори"]]


def coauthors_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["publication_examples"] = df["publication_examples"].apply(_join_authors)
    renamed = df.rename(
        columns={
            "full_name": "Співавтор",
            "shared_publications": "Спільні публікації",
            "publication_examples": "Приклади публікацій",
        }
    )
    return renamed[["Співавтор", "Спільні публікації", "Приклади публікацій"]]


def publications_dataframe_public(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["authors"] = df["authors"].apply(_join_authors)
    renamed = df.rename(
        columns={
            "title": "Назва",
            "status": "Статус",
            "year": "Рік",
            "doi": "DOI",
            "pub_type": "Тип",
            "source": "Джерело",
            "authors": "Автори",
            "authors_count": "Кількість авторів",
        }
    )
    return renamed[["Назва", "Статус", "Рік", "DOI", "Тип", "Джерело", "Кількість авторів", "Автори"]]


def publications_dataframe_admin(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["authors"] = df["authors"].apply(_join_authors)
    if "confidence" in df.columns:
        df["confidence"] = df["confidence"].apply(_format_confidence)
    renamed = df.rename(
        columns={
            "id": "ID",
            "title": "Назва",
            "status": "Статус",
            "confidence": "Рівень довіри",
            "year": "Рік",
            "doi": "DOI",
            "pub_type": "Тип",
            "source": "Джерело",
            "authors": "Автори",
            "authors_count": "Кількість авторів",
        }
    )
    return renamed[["ID", "Назва", "Статус", "Рівень довіри", "Рік", "DOI", "Тип", "Джерело", "Кількість авторів", "Автори"]]


def graph_edges_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "teacher_name": "Викладач",
            "department_name": "Кафедра",
            "publication_title": "Публікація",
            "year": "Рік",
        }
    )
    return renamed[["Викладач", "Кафедра", "Публікація", "Рік"]]


def top_teachers_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "teacher": "Викладач",
            "department": "Кафедра",
            "publications": "Кількість публікацій",
        }
    )
    return renamed[["Викладач", "Кафедра", "Кількість публікацій"]]


def top_coauthor_pairs_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["sample_publications"] = df["sample_publications"].apply(_join_authors)
    renamed = df.rename(
        columns={
            "teacher_a": "Викладач 1",
            "teacher_b": "Викладач 2",
            "shared_publications": "Спільні публікації",
            "sample_publications": "Приклади",
        }
    )
    return renamed[["Викладач 1", "Викладач 2", "Спільні публікації", "Приклади"]]


def centrality_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "teacher": "Викладач",
            "connections": "Кількість зв'язків",
            "weighted_connections": "Зважені зв'язки",
            "degree_centrality": "Degree centrality",
            "betweenness_centrality": "Betweenness centrality",
        }
    )
    return renamed[
        [
            "Викладач",
            "Кількість зв'язків",
            "Зважені зв'язки",
            "Degree centrality",
            "Betweenness centrality",
        ]
    ]


def publication_sources_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(columns={"source": "Джерело", "publications": "Публікації"})
    return renamed[["Джерело", "Публікації"]]


def audit_events_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    renamed = df.rename(
        columns={
            "created_at": "Час",
            "action": "Дія",
            "entity_type": "Сутність",
            "entity_id": "ID сутності",
            "summary": "Опис",
            "details": "Деталі",
            "actor": "Ініціатор",
        }
    )
    return renamed[["Час", "Дія", "Сутність", "ID сутності", "Опис", "Деталі", "Ініціатор"]]


def coauthor_graph_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["sample_titles"] = df["sample_titles"].apply(_join_authors)
    renamed = df.rename(
        columns={
            "source_name": "Викладач 1",
            "source_department": "Кафедра 1",
            "target_name": "Викладач 2",
            "target_department": "Кафедра 2",
            "weight": "Спільні публікації",
            "sample_titles": "Приклади робіт",
        }
    )
    return renamed[["Викладач 1", "Кафедра 1", "Викладач 2", "Кафедра 2", "Спільні публікації", "Приклади робіт"]]


def department_collaboration_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["sample_titles"] = df["sample_titles"].apply(_join_authors)
    renamed = df.rename(
        columns={
            "source_name": "Кафедра 1",
            "source_faculty": "Факультет 1",
            "target_name": "Кафедра 2",
            "target_faculty": "Факультет 2",
            "weight": "Спільні публікації",
            "sample_titles": "Приклади робіт",
        }
    )
    return renamed[["Кафедра 1", "Факультет 1", "Кафедра 2", "Факультет 2", "Спільні публікації", "Приклади робіт"]]


def duplicate_candidates_dataframe(rows: list[dict]) -> pd.DataFrame:
    df = _frame(rows)
    if df.empty:
        return df
    df["authors"] = df["authors"].apply(_join_authors)
    renamed = df.rename(
        columns={
            "duplicate_key": "Ключ дубля",
            "id": "ID",
            "title": "Назва",
            "year": "Рік",
            "doi": "DOI",
            "source": "Джерело",
            "review_status": "Статус",
            "authors_count": "Кількість авторів",
            "authors": "Автори",
        }
    )
    return renamed[["Ключ дубля", "ID", "Назва", "Рік", "DOI", "Джерело", "Статус", "Кількість авторів", "Автори"]]
