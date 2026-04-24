from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from typing import Any


OPENALEX_API = "https://api.openalex.org/works"


def _get_json(url: str, timeout: int = 20) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "kspu-neo4j-publication-import/1.0"
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def normalize_doi(doi: str | None) -> str:
    if not doi:
        return ""
    value = doi.strip()
    value = value.replace("https://doi.org/", "")
    value = value.replace("http://doi.org/", "")
    return value.lower()


def make_publication_id(title: str, year: int | None, doi: str = "", openalex_id: str = "") -> str:
    if doi:
        return f"doi:{normalize_doi(doi)}"
    if openalex_id:
        return f"openalex:{openalex_id.rsplit('/', 1)[-1]}"
    raw = f"{title}|{year or ''}".lower().strip()
    return "pub:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def clean_title(title: str | None) -> str:
    return re.sub(r"\s+", " ", title or "").strip()


def search_openalex_publications(
    teacher_name: str,
    from_year: int | None = None,
    per_page: int = 10,
) -> list[dict[str, Any]]:
    """
    Ищет публикации по ФИО преподавателя через OpenAlex.
    Это безопаснее, чем парсить Google Scholar напрямую.
    """
    search_query = urllib.parse.quote(teacher_name.strip())
    params = {
        "search": search_query,
        "per-page": str(per_page),
        "sort": "publication_year:desc",
    }

    if from_year:
        params["filter"] = f"from_publication_date:{from_year}-01-01"

    query = "&".join(f"{key}={value}" for key, value in params.items())
    url = f"{OPENALEX_API}?{query}"

    data = _get_json(url)
    results = data.get("results", [])

    publications: list[dict[str, Any]] = []

    for item in results:
        title = clean_title(item.get("title"))
        if not title:
            continue

        year = item.get("publication_year")
        doi = normalize_doi(item.get("doi"))
        openalex_id = item.get("id", "")

        source = ""
        primary_location = item.get("primary_location") or {}
        source_obj = primary_location.get("source") or {}
        if source_obj:
            source = source_obj.get("display_name") or ""

        authorships = item.get("authorships") or []
        authors = []
        for authorship in authorships:
            author = authorship.get("author") or {}
            display_name = author.get("display_name")
            if display_name:
                authors.append(display_name)

        pub_type = item.get("type") or item.get("type_crossref") or ""

        publications.append(
            {
                "id": make_publication_id(title, year, doi=doi, openalex_id=openalex_id),
                "title": title,
                "year": int(year) if year else None,
                "doi": doi,
                "openalex_id": openalex_id,
                "source": source or "OpenAlex",
                "pub_type": pub_type,
                "authors": authors,
                "external_url": item.get("id", ""),
                "cited_by_count": int(item.get("cited_by_count") or 0),
            }
        )

    return publications
