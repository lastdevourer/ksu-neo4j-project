from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from typing import Any


OPENALEX_API = "https://api.openalex.org/works"


TRANSLIT_VARIANTS = {
    "геннадій": ["hennadii", "gennadiy", "gennady", "gennadii", "henadii"],
    "геннадий": ["hennadii", "gennadiy", "gennady", "gennadii", "henadii"],
    "михайлович": ["mykhailovych", "mikhailovich", "mykhaylovych"],
    "краўцов": ["kravtsov", "kravcov"],
    "кравцов": ["kravtsov", "kravcov"],
}


def _get_json(url: str, timeout: int = 25) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "kspu-neo4j-publication-import/1.0"},
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


def clean_title(title: str | None) -> str:
    return re.sub(r"\s+", " ", title or "").strip()


def title_case_name(value: str | None) -> str:
    if not value:
        return ""

    parts = re.split(r"(\s+|-)", value.strip().lower())
    fixed = []

    for part in parts:
        if part.isspace() or part == "-":
            fixed.append(part)
        elif part:
            fixed.append(part[:1].upper() + part[1:])

    return "".join(fixed)


def normalize_person_name(value: str | None) -> str:
    if not value:
        return ""

    value = value.lower().replace("’", "'").replace("ʼ", "'")
    value = re.sub(r"[^a-zа-яіїєґё\s'-]", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def split_name(value: str | None) -> list[str]:
    normalized = normalize_person_name(value)
    return [part for part in re.split(r"\s+", normalized) if part]


def get_name_variants(name_part: str) -> set[str]:
    part = normalize_person_name(name_part)
    variants = {part}

    if part in TRANSLIT_VARIANTS:
        variants.update(TRANSLIT_VARIANTS[part])

    return {variant for variant in variants if variant}


def make_search_queries(teacher_name: str) -> list[str]:
    parts = split_name(teacher_name)

    if not parts:
        return []

    surname = parts[0]
    given = parts[1] if len(parts) > 1 else ""

    queries = {teacher_name}

    surname_variants = get_name_variants(surname)
    given_variants = get_name_variants(given)

    for s in surname_variants:
        queries.add(s)

        for g in given_variants:
            queries.add(f"{s} {g}")
            queries.add(f"{g} {s}")
            queries.add(f"{s} {g[:1]}")
            queries.add(f"{g[:1]} {s}")

    return [query for query in queries if query.strip()]


def author_matches_teacher(author_name: str, teacher_name: str) -> bool:
    teacher_parts = split_name(teacher_name)
    author_parts = split_name(author_name)

    if not teacher_parts or not author_parts:
        return False

    teacher_surname = teacher_parts[0]
    teacher_given = teacher_parts[1] if len(teacher_parts) > 1 else ""

    surname_variants = get_name_variants(teacher_surname)
    given_variants = get_name_variants(teacher_given)

    author_text = " ".join(author_parts)

    surname_ok = any(
        variant in author_parts or variant in author_text
        for variant in surname_variants
    )

    if not surname_ok:
        return False

    if not given_variants:
        return True

    given_ok = any(
        variant in author_parts
        or variant in author_text
        or any(part.startswith(variant[:1]) for part in author_parts if variant)
        for variant in given_variants
    )

    return given_ok


def make_publication_id(title: str, year: int | None, doi: str = "", openalex_id: str = "") -> str:
    if doi:
        return f"doi:{normalize_doi(doi)}"

    if openalex_id:
        return f"openalex:{openalex_id.rsplit('/', 1)[-1]}"

    raw = f"{title}|{year or ''}".lower().strip()
    return "pub:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def parse_openalex_item(item: dict[str, Any]) -> dict[str, Any] | None:
    title = clean_title(item.get("title"))
    if not title:
        return None

    authorships = item.get("authorships") or []
    authors = []

    for authorship in authorships:
        author = authorship.get("author") or {}
        display_name = title_case_name(author.get("display_name"))
        if display_name and display_name not in authors:
            authors.append(display_name)

    year = item.get("publication_year")
    doi = normalize_doi(item.get("doi"))
    openalex_id = item.get("id", "")

    source = ""
    primary_location = item.get("primary_location") or {}
    source_obj = primary_location.get("source") or {}

    if source_obj:
        source = source_obj.get("display_name") or ""

    pub_type = item.get("type") or item.get("type_crossref") or ""

    return {
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


def search_openalex_publications(
    teacher_name: str,
    from_year: int | None = None,
    per_page: int = 10,
) -> list[dict[str, Any]]:
    teacher_name = title_case_name(teacher_name)
    queries = make_search_queries(teacher_name)

    found: dict[str, dict[str, Any]] = {}

    for search_query in queries:
        params = {
            "search": search_query,
            "per-page": str(per_page),
            "sort": "publication_year:desc",
        }

        if from_year:
            params["filter"] = f"from_publication_date:{from_year}-01-01"

        url = f"{OPENALEX_API}?{urllib.parse.urlencode(params)}"

        try:
            data = _get_json(url)
        except Exception:
            continue

        for item in data.get("results", []):
            publication = parse_openalex_item(item)
            if not publication:
                continue

            authors = publication.get("authors", [])

            if authors and not any(author_matches_teacher(author, teacher_name) for author in authors):
                continue

            found[publication["id"]] = publication

    return sorted(
        found.values(),
        key=lambda row: (row.get("year") or 0, row.get("cited_by_count") or 0),
        reverse=True,
    )
