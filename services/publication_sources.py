from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover - optional runtime import
    st = None


OPENALEX_WORKS_API = "https://api.openalex.org/works"
OPENALEX_AUTHORS_API = "https://api.openalex.org/authors"

TRANSLIT_VARIANTS = {
    "Ð°": ["a"], "Ð±": ["b"], "Ð²": ["v"], "Ð³": ["h", "g"], "Ò‘": ["g"],
    "Ð´": ["d"], "Ðµ": ["e"], "Ñ”": ["ye", "ie"], "Ð¶": ["zh"], "Ð·": ["z"],
    "Ð¸": ["y", "i"], "Ñ–": ["i"], "Ñ—": ["yi", "i"], "Ð¹": ["i", "y"],
    "Ðº": ["k"], "Ð»": ["l"], "Ð¼": ["m"], "Ð½": ["n"], "Ð¾": ["o"],
    "Ð¿": ["p"], "Ñ€": ["r"], "Ñ": ["s"], "Ñ‚": ["t"], "Ñƒ": ["u"],
    "Ñ„": ["f"], "Ñ…": ["kh", "h"], "Ñ†": ["ts", "c"], "Ñ‡": ["ch"],
    "Ñˆ": ["sh"], "Ñ‰": ["shch"], "ÑŽ": ["yu", "iu"], "Ñ": ["ya", "ia"],
    "ÑŒ": [""], "ÑŠ": [""],
}

SPECIAL_NAME_VARIANTS = {
    "Ð³ÐµÐ½Ð½Ð°Ð´Ñ–Ð¹": ["hennadii", "gennadiy", "gennady", "gennadii", "henadii"],
    "Ð³ÐµÐ½Ð½Ð°Ð´Ð¸Ð¹": ["hennadii", "gennadiy", "gennady", "gennadii", "henadii"],
    "Ð¼Ð¸Ñ…Ð°Ð¹Ð»Ð¾Ð²Ð¸Ñ‡": ["mykhailovych", "mikhailovich", "mykhaylovych"],
    "Ð¾Ð»ÐµÐºÑÐ°Ð½Ð´Ñ€": ["oleksandr", "alexander", "alexandr"],
    "Ð°Ð»ÐµÐºÑÐ°Ð½Ð´Ñ€": ["oleksandr", "alexander", "alexandr"],
    "Ð¾Ð»ÐµÐºÑÐ°Ð½Ð´Ñ€Ð°": ["oleksandra", "alexandra"],
    "ÑÐµÑ€Ð³Ñ–Ð¹": ["serhii", "sergii", "sergey", "sergei"],
    "ÑÐµÑ€Ð³ÐµÐ¹": ["serhii", "sergii", "sergey", "sergei"],
    "Ð²Ñ–Ñ‚Ð°Ð»Ñ–Ð¹": ["vitalii", "vitaliy", "vitaly"],
    "Ð²Ð¸Ñ‚Ð°Ð»Ð¸Ð¹": ["vitalii", "vitaliy", "vitaly"],
    "Ð½Ð°Ñ‚Ð°Ð»Ñ–Ñ": ["nataliia", "natalia", "nataliya"],
    "Ñ‚Ð°Ñ‚ÑŒÑÐ½Ð°": ["tetiana", "tatyana", "tatiana"],
    "Ñ‚ÐµÑ‚ÑÐ½Ð°": ["tetiana", "tetyana", "tatiana"],
}

NOISY_OPENALEX_TYPES = {"reference-entry", "paratext", "peer-review"}
KHERSON_TOKENS = {
    "kherson",
    "kherson state university",
    "khersonskyi derzhavnyi universytet",
    "Ñ…ÐµÑ€ÑÐ¾Ð½",
    "Ñ…ÐµÑ€ÑÐ¾Ð½ÑÑŒÐºÐ¸Ð¹ Ð´ÐµÑ€Ð¶Ð°Ð²Ð½Ð¸Ð¹ ÑƒÐ½Ñ–Ð²ÐµÑ€ÑÐ¸Ñ‚ÐµÑ‚",
    "ksu",
    "khdu",
}


def _read_secret_or_env(key: str) -> str:
    if st is not None:
        try:
            value = st.secrets[key]
            if value:
                return str(value).strip()
        except Exception:
            pass
    return os.getenv(key, "").strip()


def _base_openalex_params() -> dict[str, str]:
    params: dict[str, str] = {}
    api_key = _read_secret_or_env("OPENALEX_API_KEY")
    mailto = _read_secret_or_env("CROSSREF_MAILTO")
    if api_key:
        params["api_key"] = api_key
    if mailto:
        params["mailto"] = mailto
    return params


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
    return doi.strip().replace("https://doi.org/", "").replace("http://doi.org/", "").lower()


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
    value = value.lower().replace("â€™", "'").replace("Ê¼", "'")
    value = re.sub(r"[^a-zÐ°-ÑÑ–Ñ—Ñ”Ò‘Ñ‘\s'-]", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def split_name(value: str | None) -> list[str]:
    return [part for part in normalize_person_name(value).split(" ") if part]


def simple_translit(value: str) -> str:
    result = ""
    for char in normalize_person_name(value):
        if char in TRANSLIT_VARIANTS:
            result += TRANSLIT_VARIANTS[char][0]
        else:
            result += char
    return result.strip()


def get_name_variants(name_part: str) -> set[str]:
    part = normalize_person_name(name_part)
    if not part:
        return set()
    variants = {part, simple_translit(part)}
    variants.update(SPECIAL_NAME_VARIANTS.get(part, []))
    return {variant for variant in variants if variant}


def make_search_queries(teacher_name: str) -> list[str]:
    parts = split_name(teacher_name)
    if not parts:
        return []

    surname = parts[0]
    given = parts[1] if len(parts) > 1 else ""
    patronymic = parts[2] if len(parts) > 2 else ""
    surname_variants = get_name_variants(surname)
    given_variants = get_name_variants(given)
    patronymic_variants = get_name_variants(patronymic)

    queries = {teacher_name}
    for surname_variant in surname_variants:
        queries.add(surname_variant)
        for given_variant in given_variants:
            queries.add(f"{surname_variant} {given_variant}")
            queries.add(f"{given_variant} {surname_variant}")
            queries.add(f"{surname_variant} {given_variant[:1]}")
            queries.add(f"{given_variant[:1]} {surname_variant}")
            for patronymic_variant in patronymic_variants:
                queries.add(f"{surname_variant} {given_variant} {patronymic_variant}")
                queries.add(f"{surname_variant} {given_variant[:1]} {patronymic_variant[:1]}")
                queries.add(f"{surname_variant} {given_variant[:1]}.{patronymic_variant[:1]}.")
    return [query for query in queries if query.strip()]


def token_matches(value: str, variants: set[str], allow_initial: bool = True) -> bool:
    tokens = split_name(value)
    text = " ".join(tokens)
    for variant in variants:
        if not variant:
            continue
        if variant in tokens or variant in text:
            return True
        if allow_initial and len(variant) > 0:
            for token in tokens:
                if token.startswith(variant[:1]):
                    return True
    return False


def author_matches_teacher(author_name: str, teacher_name: str) -> bool:
    teacher_parts = split_name(teacher_name)
    if not teacher_parts:
        return False

    surname = teacher_parts[0]
    given = teacher_parts[1] if len(teacher_parts) > 1 else ""
    patronymic = teacher_parts[2] if len(teacher_parts) > 2 else ""

    surname_ok = token_matches(author_name, get_name_variants(surname), allow_initial=False)
    if not surname_ok:
        return False

    if given and not token_matches(author_name, get_name_variants(given), allow_initial=True):
        return False

    if patronymic and token_matches(author_name, get_name_variants(patronymic), allow_initial=True):
        return True

    return True


def make_publication_id(title: str, year: int | None, doi: str = "", openalex_id: str = "") -> str:
    if doi:
        return f"doi:{normalize_doi(doi)}"
    if openalex_id:
        return f"openalex:{openalex_id.rsplit('/', 1)[-1]}"
    raw = f"{title}|{year or ''}".lower().strip()
    return "pub:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _institution_score(author: dict[str, Any]) -> int:
    institution_names = []
    for institution in author.get("last_known_institutions") or []:
        institution_names.append(normalize_person_name(institution.get("display_name") or ""))
    joined = " | ".join(institution_names)
    return 18 if any(token in joined for token in KHERSON_TOKENS) else 0


def _candidate_author_score(author: dict[str, Any], teacher_name: str) -> int:
    display_name = title_case_name(author.get("display_name") or "")
    if not author_matches_teacher(display_name, teacher_name):
        return 0

    score = 75 + _institution_score(author)
    works_count = int(author.get("works_count") or 0)
    cited_by = int(author.get("cited_by_count") or 0)
    if works_count > 0:
        score += min(works_count // 20, 5)
    if cited_by > 0:
        score += min(cited_by // 200, 4)
    return min(score, 100)


def _fetch_openalex_author_ids(teacher_name: str, limit: int = 3) -> list[str]:
    scored: list[tuple[int, str]] = []
    seen: set[str] = set()

    for query in make_search_queries(teacher_name)[:10]:
        params = {
            "search": query,
            "per-page": "5",
            **_base_openalex_params(),
        }
        url = f"{OPENALEX_AUTHORS_API}?{urllib.parse.urlencode(params)}"
        try:
            data = _get_json(url)
        except Exception:
            continue

        for author in data.get("results", []):
            author_id = str(author.get("id") or "")
            if not author_id or author_id in seen:
                continue
            seen.add(author_id)
            score = _candidate_author_score(author, teacher_name)
            if score >= 75:
                scored.append((score, author_id))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [author_id for _, author_id in scored[:limit]]


def parse_openalex_item(item: dict[str, Any]) -> dict[str, Any] | None:
    title = clean_title(item.get("title") or item.get("display_name"))
    if not title:
        return None

    authors: list[str] = []
    for authorship in item.get("authorships") or []:
        author = authorship.get("author") or {}
        display_name = title_case_name(author.get("display_name"))
        if display_name and display_name not in authors:
            authors.append(display_name)

    year = item.get("publication_year")
    doi = normalize_doi(item.get("doi"))
    openalex_id = item.get("id", "")
    primary_location = item.get("primary_location") or {}
    source_obj = primary_location.get("source") or {}
    source = source_obj.get("display_name") if source_obj else ""
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
        "external_url": primary_location.get("landing_page_url") or item.get("id", ""),
        "cited_by_count": int(item.get("cited_by_count") or 0),
    }


def _is_reliable_openalex_match(publication: dict[str, Any], teacher_name: str) -> bool:
    authors = publication.get("authors") or []
    if not authors:
        return False

    if publication.get("pub_type") in NOISY_OPENALEX_TYPES:
        return False

    matched_authors = [author for author in authors if author_matches_teacher(author, teacher_name)]
    if not matched_authors:
        return False

    if publication.get("pub_type") == "book" and not publication.get("doi") and len(authors) == 1:
        return False

    return True


def _collect_openalex_results(params: dict[str, str]) -> list[dict[str, Any]]:
    url = f"{OPENALEX_WORKS_API}?{urllib.parse.urlencode(params)}"
    try:
        data = _get_json(url)
    except Exception:
        return []
    return list(data.get("results", []))


def search_openalex_publications(
    teacher_name: str,
    from_year: int | None = None,
    per_page: int = 10,
) -> list[dict[str, Any]]:
    teacher_name = title_case_name(teacher_name)
    found: dict[str, dict[str, Any]] = {}

    common_params = {
        "per-page": str(per_page),
        "sort": "publication_year:desc",
        **_base_openalex_params(),
    }
    if from_year:
        common_params["filter"] = f"from_publication_date:{from_year}-01-01"

    author_ids = _fetch_openalex_author_ids(teacher_name)
    for author_id in author_ids:
        params = dict(common_params)
        author_filter = f"author.id:{author_id}"
        params["filter"] = f"{params['filter']},{author_filter}" if "filter" in params else author_filter
        for item in _collect_openalex_results(params):
            publication = parse_openalex_item(item)
            if publication and _is_reliable_openalex_match(publication, teacher_name):
                found[publication["id"]] = publication

    if len(found) < per_page:
        for search_query in make_search_queries(teacher_name)[:8]:
            params = dict(common_params)
            params["search"] = search_query
            for item in _collect_openalex_results(params):
                publication = parse_openalex_item(item)
                if publication and _is_reliable_openalex_match(publication, teacher_name):
                    found[publication["id"]] = publication

    return sorted(
        found.values(),
        key=lambda row: (row.get("year") or 0, row.get("cited_by_count") or 0),
        reverse=True,
    )
