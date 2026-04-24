from __future__ import annotations

import hashlib
import json
import re
import urllib.parse
import urllib.request
from typing import Any


OPENALEX_API = "https://api.openalex.org/works"


TRANSLIT_VARIANTS = {
    "а": ["a"], "б": ["b"], "в": ["v"], "г": ["h", "g"], "ґ": ["g"],
    "д": ["d"], "е": ["e"], "є": ["ye", "ie"], "ж": ["zh"], "з": ["z"],
    "и": ["y", "i"], "і": ["i"], "ї": ["yi", "i"], "й": ["i", "y"],
    "к": ["k"], "л": ["l"], "м": ["m"], "н": ["n"], "о": ["o"],
    "п": ["p"], "р": ["r"], "с": ["s"], "т": ["t"], "у": ["u"],
    "ф": ["f"], "х": ["kh", "h"], "ц": ["ts", "c"], "ч": ["ch"],
    "ш": ["sh"], "щ": ["shch"], "ю": ["yu", "iu"], "я": ["ya", "ia"],
    "ь": [""], "ъ": [""],
}


SPECIAL_NAME_VARIANTS = {
    "геннадій": ["hennadii", "gennadiy", "gennady", "gennadii", "henadii"],
    "геннадий": ["hennadii", "gennadiy", "gennady", "gennadii", "henadii"],
    "михайлович": ["mykhailovych", "mikhailovich", "mykhaylovych"],
    "олександр": ["oleksandr", "alexander", "alexandr"],
    "александр": ["oleksandr", "alexander", "alexandr"],
    "олександра": ["oleksandra", "alexandra"],
    "сергій": ["serhii", "sergii", "sergey", "sergei"],
    "сергей": ["serhii", "sergii", "sergey", "sergei"],
    "віталій": ["vitalii", "vitaliy", "vitaly"],
    "виталий": ["vitalii", "vitaliy", "vitaly"],
    "наталія": ["nataliia", "natalia", "nataliya"],
    "татьяна": ["tetiana", "tatyana", "tatiana"],
    "тетяна": ["tetiana", "tetyana", "tatiana"],
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
    return (
        doi.strip()
        .replace("https://doi.org/", "")
        .replace("http://doi.org/", "")
        .lower()
    )


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

    variants = {part}
    variants.add(simple_translit(part))
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

    surname_variants = get_name_variants(surname)
    given_variants = get_name_variants(given)
    patronymic_variants = get_name_variants(patronymic)

    surname_ok = token_matches(author_name, surname_variants, allow_initial=False)
    if not surname_ok:
        return False

    given_ok = True
    if given_variants:
        given_ok = token_matches(author_name, given_variants, allow_initial=True)

    if not given_ok:
        return False

    # Отчество не обязательно, потому что в международных базах его часто нет.
    # Но если оно совпало — это просто усиливает уверенность.
    return True


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

    authors = []

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
