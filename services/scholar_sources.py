from __future__ import annotations

import hashlib
import re
from typing import Any

from rapidfuzz import fuzz
from scholarly import scholarly


def clean_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_name(value: str | None) -> str:
    value = clean_text(value).lower()
    value = value.replace("’", "'").replace("ʼ", "'")
    value = re.sub(r"[^a-zа-яіїєґё\s'-]", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def title_case_name(value: str | None) -> str:
    value = clean_text(value)
    if not value:
        return ""

    parts = re.split(r"(\s+|-)", value.lower())
    result = []

    for part in parts:
        if part.isspace() or part == "-":
            result.append(part)
        elif part:
            result.append(part[:1].upper() + part[1:])

    return "".join(result)


def stable_publication_id(title: str, year: int | None) -> str:
    raw = f"{clean_text(title).lower()}|{year or ''}"
    return "pub:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def scholar_author_id_from_url(url: str) -> str:
    match = re.search(r"[?&]user=([^&]+)", url or "")
    return match.group(1) if match else ""


def split_authors(authors_raw: Any) -> list[str]:
    if isinstance(authors_raw, list):
        return [title_case_name(author) for author in authors_raw if author]

    if not isinstance(authors_raw, str):
        return []

    parts = re.split(r"\s+and\s+|,\s*", authors_raw)
    return [title_case_name(part) for part in parts if clean_text(part)]


def is_kherson_profile(author: dict[str, Any]) -> bool:
    affiliation = normalize_name(author.get("affiliation", ""))
    return (
        "kherson state university" in affiliation
        or "khersonskyi derzhavnyi universytet" in affiliation
        or "херсонський державний університет" in affiliation
        or "херсонский государственный университет" in affiliation
        or "ksu" in affiliation
    )


def profile_score(teacher_name: str, author: dict[str, Any]) -> int:
    teacher = normalize_name(teacher_name)
    candidate = normalize_name(author.get("name", ""))

    if not teacher or not candidate:
        return 0

    score = fuzz.token_sort_ratio(teacher, candidate)

    if is_kherson_profile(author):
        score += 15

    return min(score, 100)


def find_scholar_profiles_for_teacher(teacher_name: str, limit: int = 5) -> list[dict[str, Any]]:
    queries = [
        f"{teacher_name} Kherson State University",
        f"{teacher_name} Херсонський державний університет",
        teacher_name,
    ]

    profiles: dict[str, dict[str, Any]] = {}

    for query in queries:
        try:
            search_results = scholarly.search_author(query)
        except Exception:
            continue

        for _ in range(limit):
            try:
                author = next(search_results)
            except StopIteration:
                break
            except Exception:
                break

            scholar_id = author.get("scholar_id") or author.get("id") or ""
            if not scholar_id:
                continue

            score = profile_score(teacher_name, author)

            profiles[scholar_id] = {
                "scholar_id": scholar_id,
                "name": title_case_name(author.get("name", "")),
                "affiliation": clean_text(author.get("affiliation", "")),
                "interests": author.get("interests", []),
                "citedby": author.get("citedby", 0),
                "profile_url": f"https://scholar.google.com/citations?user={scholar_id}",
                "match_score": score,
            }

    return sorted(
        profiles.values(),
        key=lambda row: (row["match_score"], row.get("citedby") or 0),
        reverse=True,
    )


def find_best_scholar_profile(teacher_name: str) -> dict[str, Any] | None:
    profiles = find_scholar_profiles_for_teacher(teacher_name)

    if not profiles:
        return None

    best = profiles[0]

    if best["match_score"] < 72:
        return None

    return best


def load_publications_from_scholar_id(scholar_id: str, limit: int = 50) -> list[dict[str, Any]]:
    if not scholar_id:
        return []

    try:
        author = scholarly.search_author_id(scholar_id)
        filled_author = scholarly.fill(author, sections=["publications"])
    except Exception:
        return []

    publications = []

    for pub in filled_author.get("publications", [])[:limit]:
        try:
            filled_pub = scholarly.fill(pub)
        except Exception:
            filled_pub = pub

        bib = filled_pub.get("bib", {}) or {}

        title = clean_text(bib.get("title"))
        if not title:
            continue

        year_raw = bib.get("pub_year") or bib.get("year")
        try:
            year = int(year_raw) if year_raw else None
        except Exception:
            year = None

        authors = split_authors(bib.get("author", ""))

        publications.append(
            {
                "id": stable_publication_id(title, year),
                "title": title,
                "year": year,
                "doi": "",
                "openalex_id": "",
                "source": "Google Scholar",
                "pub_type": "scholarly publication",
                "authors": authors,
                "external_url": filled_pub.get("pub_url", ""),
                "cited_by_count": int(filled_pub.get("num_citations") or 0),
            }
        )

    return publications
