from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from hashlib import sha1
from typing import Any

from config import PublicationImportConfig


ORCID_TOKEN_URL = "https://orcid.org/oauth/token"
ORCID_WORKS_URL = "https://pub.orcid.org/v3.0/{orcid}/works"
OPENALEX_AUTHOR_URL = "https://api.openalex.org/authors"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"
SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"
WOS_STARTER_URL = "https://api.clarivate.com/apis/wos-starter/v1/documents"
SCHOLAR_PROFILE_URL = "https://scholar.google.com/citations"
SCHOLAR_SEARCH_URL = "https://scholar.google.com/citations"

APOSTROPHES = {"â€™": "'", "`": "'", "Ê¼": "'", "Õš": "'"}
SPACE_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^0-9A-Za-zÐ-Ð¯Ð°-ÑÐ†Ñ–Ð‡Ñ—Ð„Ñ”ÒÒ‘']")
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
SCOPUS_ID_RE = re.compile(r"(?:authorid|authorId|authorID)=(\d+)|(?:scopus|author)/(\d+)", re.IGNORECASE)
WOS_ID_RE = re.compile(r"(?:researcherid|researcherId|rid)=([^&]+)|/record/([^/?#]+)|/researcher/([^/?#]+)", re.IGNORECASE)
SCHOLAR_ROW_RE = re.compile(
    r'<tr class="gsc_a_tr".*?<a[^>]*class="gsc_a_at"[^>]*>(?P<title>.*?)</a>.*?'
    r'<div class="gs_gray">(?P<meta1>.*?)</div>.*?<div class="gs_gray">(?P<meta2>.*?)</div>.*?'
    r'<span class="gsc_a_h gsc_a_hc gs_ibl">(?P<year>\d{4})?</span>',
    re.DOTALL,
)
SCHOLAR_PROFILE_RE = re.compile(
    r'<div class="gsc_1usr".*?<h3 class="gs_ai_name"><a href="(?P<href>[^"]+)">(?P<name>.*?)</a></h3>.*?'
    r'<div class="gs_ai_aff">(?P<affiliation>.*?)</div>',
    re.DOTALL,
)

TRANSLIT_VARIANTS = {
    "Ð°": "a", "Ð±": "b", "Ð²": "v", "Ð³": "h", "Ò‘": "g",
    "Ð´": "d", "Ðµ": "e", "Ñ”": "ie", "Ð¶": "zh", "Ð·": "z",
    "Ð¸": "y", "Ñ–": "i", "Ñ—": "i", "Ð¹": "i", "Ðº": "k",
    "Ð»": "l", "Ð¼": "m", "Ð½": "n", "Ð¾": "o", "Ð¿": "p",
    "Ñ€": "r", "Ñ": "s", "Ñ‚": "t", "Ñƒ": "u", "Ñ„": "f",
    "Ñ…": "kh", "Ñ†": "ts", "Ñ‡": "ch", "Ñˆ": "sh", "Ñ‰": "shch",
    "ÑŽ": "iu", "Ñ": "ia", "ÑŒ": "", "ÑŠ": "", "Ñ‘": "e",
}

SPECIAL_NAME_VARIANTS = {
    "Ð¾Ð»ÐµÐºÑÐ°Ð½Ð´Ñ€": {"oleksandr", "alexander", "alexandr"},
    "Ð°Ð»ÐµÐºÑÐ°Ð½Ð´Ñ€": {"oleksandr", "alexander", "alexandr"},
    "ÑÐµÑ€Ð³Ñ–Ð¹": {"serhii", "sergii", "sergey", "sergei"},
    "ÑÐµÑ€Ð³ÐµÐ¹": {"serhii", "sergii", "sergey", "sergei"},
    "Ð²Ñ–Ñ‚Ð°Ð»Ñ–Ð¹": {"vitalii", "vitaliy", "vitaly"},
    "Ð²Ð¸Ñ‚Ð°Ð»Ð¸Ð¹": {"vitalii", "vitaliy", "vitaly"},
    "Ñ‚ÐµÑ‚ÑÐ½Ð°": {"tetiana", "tetyana", "tatiana"},
    "Ñ‚Ð°Ñ‚ÑŒÑÐ½Ð°": {"tetiana", "tetyana", "tatiana"},
    "ÑŽÑ€Ñ–Ð¹": {"yurii", "yuriy", "yuri"},
    "ÑŽÑ€Ð¸Ð¹": {"yurii", "yuriy", "yuri"},
}


@dataclass(frozen=True)
class TeacherIdentity:
    id: str
    full_name: str
    department_name: str
    faculty_name: str
    orcid: str = ""
    google_scholar: str = ""
    scopus: str = ""
    web_of_science: str = ""
    profile_url: str = ""


@dataclass
class PublicationCandidate:
    provider: str
    source_priority: int
    title: str
    year: int | None
    doi: str = ""
    pub_type: str = ""
    url: str = ""
    authors: list[str] = field(default_factory=list)
    external_id: str = ""
    confidence: float = 0.0
    matched_by: str = ""


@dataclass
class PublicationBundle:
    publications: list[dict[str, Any]]
    authorships: list[dict[str, Any]]
    processed_teachers: int
    teachers_with_publications: int
    warnings: list[str]
    provider_hits: dict[str, int]


def normalize_text(value: str) -> str:
    result = (value or "").strip()
    for source, target in APOSTROPHES.items():
        result = result.replace(source, target)
    result = NON_WORD_RE.sub(" ", result)
    result = SPACE_RE.sub(" ", result)
    return result.casefold().strip()


def normalize_title(value: str) -> str:
    return normalize_text(value).replace(" ", "")


def transliterate_text(value: str) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    result = []
    for char in normalized:
        if char in TRANSLIT_VARIANTS:
            result.append(TRANSLIT_VARIANTS[char])
        else:
            result.append(char)
    return "".join(result)


def strip_orcid(value: str) -> str:
    text = (value or "").strip().rstrip("/")
    if not text:
        return ""
    if "/" in text:
        text = text.rsplit("/", 1)[-1]
    return text.upper()


def extract_scopus_id(value: str) -> str:
    match = SCOPUS_ID_RE.search(value or "")
    if not match:
        return ""
    return next((group for group in match.groups() if group), "")


def extract_wos_id(value: str) -> str:
    match = WOS_ID_RE.search(value or "")
    if not match:
        return ""
    return next((group for group in match.groups() if group), "")


def extract_scholar_user(value: str) -> str:
    if not value:
        return ""
    parsed = urllib.parse.urlparse(value)
    params = urllib.parse.parse_qs(parsed.query)
    return (params.get("user") or [""])[0]


def parse_html_text(value: str) -> str:
    return SPACE_RE.sub(" ", html.unescape(re.sub(r"<.*?>", "", value or ""))).strip()


def split_person_tokens(value: str) -> list[str]:
    return [token for token in normalize_text(value).split(" ") if token]


def token_variants(token: str) -> set[str]:
    if not token:
        return set()
    variants = {normalize_text(token), transliterate_text(token)}
    variants.update(SPECIAL_NAME_VARIANTS.get(normalize_text(token), set()))
    return {variant for variant in variants if variant}


def build_name_variants(full_name: str) -> set[str]:
    tokens = split_person_tokens(full_name)
    if not tokens:
        return set()
    variants = {
        normalize_text(full_name),
        transliterate_text(full_name),
    }
    if len(tokens) >= 2:
        surname = tokens[0]
        given = tokens[1]
        variants.add(normalize_text(f"{given} {surname}"))
        variants.add(normalize_text(f"{surname} {given}"))
        variants.add(transliterate_text(f"{given} {surname}"))
        variants.add(transliterate_text(f"{surname} {given}"))
    if len(tokens) >= 3:
        surname = tokens[0]
        given = tokens[1]
        patronymic = tokens[2]
        variants.add(normalize_text(f"{given} {surname} {patronymic}"))
        variants.add(normalize_text(f"{given} {patronymic} {surname}"))
        variants.add(normalize_text(f"{surname} {given} {patronymic}"))
        variants.add(transliterate_text(f"{given} {surname} {patronymic}"))
        variants.add(transliterate_text(f"{given} {patronymic} {surname}"))
        variants.add(transliterate_text(f"{surname} {given} {patronymic}"))
    return {value for value in variants if value}


def best_name_similarity(left: str, right_variants: set[str]) -> float:
    normalized_candidates = {normalize_text(left), transliterate_text(left)}
    normalized_candidates = {value for value in normalized_candidates if value}
    if not normalized_candidates or not right_variants:
        return 0.0
    best_score = 0.0
    for candidate in normalized_candidates:
        for variant in right_variants:
            best_score = max(best_score, SequenceMatcher(None, candidate, variant).ratio())
    return best_score


def extract_doi(value: str) -> str:
    match = DOI_RE.search(value or "")
    return match.group(0).lower() if match else ""


def safe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except Exception:
        return None


def canonical_publication_id(candidate: PublicationCandidate) -> tuple[str, str]:
    doi = extract_doi(candidate.doi or candidate.url or "")
    if doi:
        slug = doi.replace("/", "_").replace(".", "_").replace(":", "_")
        return f"P-DOI-{slug.upper()}", f"doi:{doi}"

    fingerprint = f"{normalize_title(candidate.title)}|{candidate.year or 'nd'}"
    digest = sha1(fingerprint.encode("utf-8")).hexdigest()[:16].upper()
    return f"P-HASH-{digest}", fingerprint


def publication_aliases(candidate: PublicationCandidate, publication_id: str, canonical_key: str) -> set[str]:
    aliases = {f"id:{publication_id}", f"canon:{canonical_key}"}
    normalized_title = normalize_title(candidate.title)
    if normalized_title:
        aliases.add(f"title:{normalized_title}")
        aliases.add(f"titleyear:{normalized_title}|{candidate.year or 'nd'}")
    doi = extract_doi(candidate.doi or candidate.url or "")
    if doi:
        aliases.add(f"doi:{doi}")
    if candidate.external_id:
        aliases.add(f"ext:{candidate.provider}:{normalize_text(candidate.external_id)}")
    return aliases


def candidate_author_matches(candidate: PublicationCandidate, teacher: TeacherIdentity) -> bool:
    if not candidate.authors:
        return True

    teacher_tokens = split_person_tokens(teacher.full_name)
    variants = build_name_variants(teacher.full_name)
    surname_variants = token_variants(teacher_tokens[0]) if teacher_tokens else set()
    given_variants = token_variants(teacher_tokens[1]) if len(teacher_tokens) > 1 else set()

    for author in candidate.authors:
        author_normalized = normalize_text(author)
        author_translit = transliterate_text(author)
        author_tokens = set(split_person_tokens(author))
        author_tokens.update(token for token in author_translit.split(" ") if token)
        if not author_normalized and not author_translit:
            continue

        surname_ok = bool(surname_variants) and any(
            variant in author_tokens or variant in author_normalized or variant in author_translit
            for variant in surname_variants
        )
        given_ok = True
        if given_variants:
            given_ok = any(
                variant in author_tokens
                or variant in author_normalized
                or variant in author_translit
                or any(token.startswith(variant[:1]) for token in author_tokens if variant)
                for variant in given_variants
            )

        if surname_ok and given_ok:
            return True
        if best_name_similarity(author, variants) >= 0.72:
            return True
    return False


class JsonHttpClient:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout

    def _request(self, url: str, *, headers: dict[str, str] | None = None, data: bytes | None = None) -> str:
        request = urllib.request.Request(url, headers=headers or {}, data=data)
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return response.read().decode("utf-8", errors="ignore")
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise
                time.sleep(1.4 * (attempt + 1))
            except Exception as exc:  # pragma: no cover - runtime network branch
                last_error = exc
                time.sleep(1.4 * (attempt + 1))
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"ÐÐµ Ð²Ð´Ð°Ð»Ð¾ÑÑ Ð¾Ñ‚Ñ€Ð¸Ð¼Ð°Ñ‚Ð¸ Ð²Ñ–Ð´Ð¿Ð¾Ð²Ñ–Ð´ÑŒ Ð²Ñ–Ð´ {url}")

    def get_json(self, base_url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict:
        query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in ("", None)})
        url = f"{base_url}?{query}" if query else base_url
        payload = self._request(url, headers=headers)
        return json.loads(payload)

    def get_text(self, base_url: str, *, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> str:
        query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in ("", None)})
        url = f"{base_url}?{query}" if query else base_url
        return self._request(url, headers=headers)

    def post_form_json(self, url: str, *, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict:
        encoded = urllib.parse.urlencode(payload).encode("utf-8")
        merged_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if headers:
            merged_headers.update(headers)
        response = self._request(url, headers=merged_headers, data=encoded)
        return json.loads(response)


class BasePublicationProvider:
    name = "base"
    priority = 99

    def __init__(self, config: PublicationImportConfig, client: JsonHttpClient):
        self.config = config
        self.client = client

    def fetch(self, teacher: TeacherIdentity) -> list[PublicationCandidate]:
        raise NotImplementedError


class OrcidPublicationProvider(BasePublicationProvider):
    name = "ORCID"
    priority = 1

    def __init__(self, config: PublicationImportConfig, client: JsonHttpClient):
        super().__init__(config, client)
        self._access_token = ""

    def _get_access_token(self) -> str:
        if self._access_token:
            return self._access_token
        if not (self.config.orcid_client_id and self.config.orcid_client_secret):
            return ""
        response = self.client.post_form_json(
            ORCID_TOKEN_URL,
            payload={
                "client_id": self.config.orcid_client_id,
                "client_secret": self.config.orcid_client_secret,
                "grant_type": "client_credentials",
                "scope": "/read-public",
            },
            headers={"Accept": "application/json"},
        )
        self._access_token = str(response.get("access_token") or "")
        return self._access_token

    def fetch(self, teacher: TeacherIdentity) -> list[PublicationCandidate]:
        orcid_id = strip_orcid(teacher.orcid)
        token = self._get_access_token()
        if not (orcid_id and token):
            return []

        payload = self.client.get_json(
            ORCID_WORKS_URL.format(orcid=orcid_id),
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        candidates: list[PublicationCandidate] = []
        for group in payload.get("group", []):
            summaries = group.get("work-summary", [])
            if not summaries:
                continue
            summary = summaries[0]
            title = (((summary.get("title") or {}).get("title") or {}).get("value") or "").strip()
            if not title:
                continue

            external_ids = (((summary.get("external-ids") or {}).get("external-id")) or [])
            doi = ""
            work_url = ""
            for item in external_ids:
                if str(item.get("external-id-type") or "").lower() == "doi":
                    doi = str(item.get("external-id-value") or "")
                if str(item.get("external-id-type") or "").lower() in {"uri", "url"}:
                    work_url = str(item.get("external-id-value") or "")

            publication_date = summary.get("publication-date") or {}
            year = safe_int((publication_date.get("year") or {}).get("value"))
            work_url = work_url or ((summary.get("url") or {}).get("value") or "")
            if not work_url and doi:
                work_url = f"https://doi.org/{doi}"

            candidates.append(
                PublicationCandidate(
                    provider=self.name,
                    source_priority=self.priority,
                    title=title,
                    year=year,
                    doi=doi,
                    pub_type=str(summary.get("type") or ""),
                    url=work_url,
                    authors=[teacher.full_name],
                    external_id=str(summary.get("put-code") or ""),
                    confidence=0.98,
                    matched_by="orcid",
                )
            )
        return candidates[: self.config.max_works_per_teacher]


class OpenAlexPublicationProvider(BasePublicationProvider):
    name = "OpenAlex"
    priority = 2

    def _polite_params(self) -> dict[str, str]:
        params: dict[str, str] = {}
        if self.config.crossref_mailto:
            params["mailto"] = self.config.crossref_mailto
        if self.config.openalex_api_key:
            params["api_key"] = self.config.openalex_api_key
        return params

    def _select_author_id(self, teacher: TeacherIdentity) -> tuple[str, str]:
        variants = build_name_variants(teacher.full_name)
        orcid_id = strip_orcid(teacher.orcid)
        scopus_id = extract_scopus_id(teacher.scopus)

        if orcid_id:
            payload = self.client.get_json(
                OPENALEX_AUTHOR_URL,
                params={
                    "filter": f"orcid:https://orcid.org/{orcid_id}",
                    "per-page": 1,
                    **self._polite_params(),
                },
            )
            results = payload.get("results") or []
            if results:
                return str(results[0].get("id") or ""), "openalex_orcid"

        if scopus_id:
            payload = self.client.get_json(
                OPENALEX_AUTHOR_URL,
                params={
                    "filter": f"scopus:{scopus_id}",
                    "per-page": 1,
                    **self._polite_params(),
                },
            )
            results = payload.get("results") or []
            if results:
                return str(results[0].get("id") or ""), "openalex_scopus"

        payload = self.client.get_json(
            OPENALEX_AUTHOR_URL,
            params={
                "search": teacher.full_name,
                "per-page": 5,
                **self._polite_params(),
            },
        )
        best_id = ""
        best_score = 0.0
        for result in payload.get("results") or []:
            score = best_name_similarity(str(result.get("display_name") or ""), variants)
            if score > best_score:
                best_score = score
                best_id = str(result.get("id") or "")
        if best_score >= 0.62:
            return best_id, "openalex_name"
        return "", ""

    def fetch(self, teacher: TeacherIdentity) -> list[PublicationCandidate]:
        matched_by = ""
        orcid_id = strip_orcid(teacher.orcid)
        if orcid_id:
            payload = self.client.get_json(
                OPENALEX_WORKS_URL,
                params={
                    "filter": f"author.orcid:https://orcid.org/{orcid_id}",
                    "per-page": min(self.config.max_works_per_teacher, 100),
                    "sort": "publication_year:desc",
                    **self._polite_params(),
                },
            )
            matched_by = "openalex_orcid"
        else:
            author_id, matched_by = self._select_author_id(teacher)
            if not author_id:
                return []
            payload = self.client.get_json(
                OPENALEX_WORKS_URL,
                params={
                    "filter": f"author.id:{author_id}",
                    "per-page": min(self.config.max_works_per_teacher, 100),
                    "sort": "publication_year:desc",
                    **self._polite_params(),
                },
            )

        candidates: list[PublicationCandidate] = []
        for result in payload.get("results") or []:
            title = str(result.get("display_name") or "").strip()
            if not title:
                continue
            authors = [
                str(((item.get("author") or {}).get("display_name")) or "").strip()
                for item in result.get("authorships") or []
                if ((item.get("author") or {}).get("display_name"))
            ]
            candidate = PublicationCandidate(
                provider=self.name,
                source_priority=self.priority,
                title=title,
                year=safe_int(result.get("publication_year")),
                doi=extract_doi(str(result.get("doi") or "")),
                pub_type=str(result.get("type") or ""),
                url=str(((result.get("primary_location") or {}).get("landing_page_url")) or result.get("id") or ""),
                authors=authors,
                external_id=str(result.get("id") or ""),
                confidence=0.94 if matched_by != "openalex_name" else 0.82,
                matched_by=matched_by,
            )
            if matched_by != "openalex_name" or candidate_author_matches(candidate, teacher):
                candidates.append(candidate)
        return candidates


class CrossrefPublicationProvider(BasePublicationProvider):
    name = "Crossref"
    priority = 3

    def fetch(self, teacher: TeacherIdentity) -> list[PublicationCandidate]:
        params: dict[str, Any] = {
            "rows": min(self.config.max_works_per_teacher, 100),
            "select": "DOI,title,author,issued,type,URL",
        }
        if self.config.crossref_mailto:
            params["mailto"] = self.config.crossref_mailto

        orcid_id = strip_orcid(teacher.orcid)
        if orcid_id:
            params["filter"] = f"orcid:{orcid_id}"
            matched_by = "crossref_orcid"
        else:
            params["query.author"] = teacher.full_name
            params["sort"] = "score"
            params["order"] = "desc"
            matched_by = "crossref_name"

        payload = self.client.get_json(CROSSREF_WORKS_URL, params=params)
        items = ((payload.get("message") or {}).get("items")) or []

        candidates: list[PublicationCandidate] = []
        for item in items:
            titles = item.get("title") or []
            title = str(titles[0] if titles else "").strip()
            if not title:
                continue
            authors = []
            for author in item.get("author") or []:
                person = " ".join(part for part in [author.get("family"), author.get("given")] if part).strip()
                if person:
                    authors.append(person)
            candidate = PublicationCandidate(
                provider=self.name,
                source_priority=self.priority,
                title=title,
                year=safe_int((((item.get("issued") or {}).get("date-parts")) or [[None]])[0][0]),
                doi=extract_doi(str(item.get("DOI") or "")),
                pub_type=str(item.get("type") or ""),
                url=str(item.get("URL") or ""),
                authors=authors,
                external_id=str(item.get("DOI") or ""),
                confidence=0.88 if matched_by == "crossref_orcid" else 0.72,
                matched_by=matched_by,
            )
            if matched_by == "crossref_orcid" or candidate_author_matches(candidate, teacher):
                candidates.append(candidate)
        return candidates


class ScopusPublicationProvider(BasePublicationProvider):
    name = "Scopus"
    priority = 4

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "X-ELS-APIKey": self.config.scopus_api_key,
        }
        if self.config.scopus_insttoken:
            headers["X-ELS-Insttoken"] = self.config.scopus_insttoken
        return headers

    def fetch(self, teacher: TeacherIdentity) -> list[PublicationCandidate]:
        if not self.config.scopus_api_key:
            return []

        scopus_id = extract_scopus_id(teacher.scopus)
        orcid_id = strip_orcid(teacher.orcid)
        if scopus_id:
            query = f"AU-ID({scopus_id})"
            matched_by = "scopus_author_id"
        elif orcid_id:
            query = f"ORCID({orcid_id})"
            matched_by = "scopus_orcid"
        else:
            return []

        payload = self.client.get_json(
            SCOPUS_SEARCH_URL,
            params={
                "query": query,
                "count": min(self.config.max_works_per_teacher, 100),
                "sort": "-coverDate",
            },
            headers=self._headers(),
        )
        items = ((payload.get("search-results") or {}).get("entry")) or []

        candidates: list[PublicationCandidate] = []
        for item in items:
            title = str(item.get("dc:title") or "").strip()
            if not title:
                continue

            raw_authors = item.get("author") or []
            authors = []
            if isinstance(raw_authors, list):
                for author in raw_authors:
                    given = str(author.get("given-name") or "").strip()
                    surname = str(author.get("surname") or "").strip()
                    full_name = " ".join(part for part in [given, surname] if part).strip()
                    if full_name:
                        authors.append(full_name)
            if not authors and item.get("dc:creator"):
                authors = [part.strip() for part in str(item.get("dc:creator") or "").split(";") if part.strip()]

            cover_date = str(item.get("prism:coverDate") or "")
            candidate = PublicationCandidate(
                provider=self.name,
                source_priority=self.priority,
                title=title,
                year=safe_int(cover_date[:4]),
                doi=extract_doi(str(item.get("prism:doi") or "")),
                pub_type=str(item.get("subtypeDescription") or item.get("prism:aggregationType") or ""),
                url=str(item.get("prism:url") or item.get("link") or ""),
                authors=authors,
                external_id=str(item.get("dc:identifier") or item.get("eid") or ""),
                confidence=0.91,
                matched_by=matched_by,
            )
            if candidate_author_matches(candidate, teacher):
                candidates.append(candidate)
        return candidates


class WebOfSciencePublicationProvider(BasePublicationProvider):
    name = "Web of Science"
    priority = 5

    def fetch(self, teacher: TeacherIdentity) -> list[PublicationCandidate]:
        if not self.config.wos_api_key:
            return []

        wos_id = extract_wos_id(teacher.web_of_science)
        orcid_id = strip_orcid(teacher.orcid)
        if wos_id:
            query = f'AI=("{wos_id}")'
            matched_by = "wos_researcher_id"
        elif orcid_id:
            query = f'AI=("{orcid_id}")'
            matched_by = "wos_orcid"
        else:
            query = f'AU=("{teacher.full_name}")'
            matched_by = "wos_name"

        payload = self.client.get_json(
            WOS_STARTER_URL,
            params={
                "q": query,
                "limit": min(self.config.max_works_per_teacher, 50),
                "page": 1,
                "db": "WOS",
            },
            headers={
                "Accept": "application/json",
                "X-ApiKey": self.config.wos_api_key,
            },
        )
        items = payload.get("hits") or payload.get("data") or []

        candidates: list[PublicationCandidate] = []
        for item in items:
            title = str(item.get("title") or item.get("sourceTitle") or "").strip()
            if not title:
                continue

            names = item.get("names") or item.get("authors") or []
            authors = []
            if isinstance(names, list):
                for author in names:
                    display_name = str(
                        author.get("displayName")
                        or author.get("fullName")
                        or author.get("wosStandard")
                        or author.get("name")
                        or ""
                    ).strip()
                    if display_name:
                        authors.append(display_name)

            candidate = PublicationCandidate(
                provider=self.name,
                source_priority=self.priority,
                title=title,
                year=safe_int(item.get("publishYear") or item.get("year")),
                doi=extract_doi(str(item.get("doi") or item.get("identifiers", {}).get("doi") or "")),
                pub_type=str(item.get("documentType") or ""),
                url=str(item.get("links", {}).get("record") or item.get("url") or ""),
                authors=authors,
                external_id=str(item.get("uid") or item.get("id") or ""),
                confidence=0.86 if matched_by != "wos_name" else 0.7,
                matched_by=matched_by,
            )
            if matched_by != "wos_name" or candidate_author_matches(candidate, teacher):
                candidates.append(candidate)
        return candidates


class ScholarPublicationProvider(BasePublicationProvider):
    name = "Scholar"
    priority = 6

    def _resolve_user_id(self, teacher: TeacherIdentity) -> str:
        user_id = extract_scholar_user(teacher.google_scholar)
        if user_id:
            return user_id

        query = " ".join(
            part
            for part in [
                teacher.full_name,
                teacher.department_name,
                "Kherson State University",
            ]
            if part
        )
        html_payload = self.client.get_text(
            SCHOLAR_SEARCH_URL,
            params={
                "view_op": "search_authors",
                "mauthors": query,
                "hl": "en",
            },
            headers={"User-Agent": "Mozilla/5.0"},
        )

        best_user_id = ""
        best_score = 0.0
        variants = build_name_variants(teacher.full_name)
        for match in SCHOLAR_PROFILE_RE.finditer(html_payload):
            href = html.unescape(match.group("href"))
            name = parse_html_text(match.group("name"))
            affiliation = parse_html_text(match.group("affiliation"))
            candidate_user = extract_scholar_user(f"https://scholar.google.com{href}")
            if not candidate_user:
                continue

            name_score = best_name_similarity(name, variants)
            affiliation_text = normalize_text(affiliation)
            affiliation_score = 0.0
            if any(token in affiliation_text for token in {"kherson", "kspu", "khdu", "Ñ…ÐµÑ€ÑÐ¾Ð½", "ÐºÑÐ¿Ñƒ", "Ñ…Ð´Ñƒ"}):
                affiliation_score = 0.18
            total_score = name_score + affiliation_score
            if total_score > best_score:
                best_score = total_score
                best_user_id = candidate_user

        return best_user_id if best_score >= 0.8 else ""

    def fetch(self, teacher: TeacherIdentity) -> list[PublicationCandidate]:
        user_id = self._resolve_user_id(teacher)
        if not user_id:
            return []

        html_payload = self.client.get_text(
            SCHOLAR_PROFILE_URL,
            params={
                "user": user_id,
                "hl": "en",
                "cstart": 0,
                "pagesize": min(self.config.max_works_per_teacher, 100),
                "view_op": "list_works",
            },
            headers={"User-Agent": "Mozilla/5.0"},
        )

        candidates: list[PublicationCandidate] = []
        for match in SCHOLAR_ROW_RE.finditer(html_payload):
            title = parse_html_text(match.group("title"))
            if not title:
                continue
            meta1 = parse_html_text(match.group("meta1"))
            meta2 = parse_html_text(match.group("meta2"))
            authors = [part.strip() for part in meta1.split(",") if part.strip()]
            year = safe_int(match.group("year"))
            candidates.append(
                PublicationCandidate(
                    provider=self.name,
                    source_priority=self.priority,
                    title=title,
                    year=year,
                    pub_type="scholar",
                    url=teacher.google_scholar,
                    authors=authors or [teacher.full_name],
                    external_id=f"{user_id}:{normalize_title(title)}",
                    confidence=0.58,
                    matched_by=f"scholar_profile|{meta2}",
                )
            )
        return candidates


class PublicationImportService:
    def __init__(self, config: PublicationImportConfig):
        self.config = config
        self.client = JsonHttpClient()
        self.providers: list[BasePublicationProvider] = [
            OrcidPublicationProvider(config, self.client),
            OpenAlexPublicationProvider(config, self.client),
            CrossrefPublicationProvider(config, self.client),
            ScopusPublicationProvider(config, self.client),
            WebOfSciencePublicationProvider(config, self.client),
            ScholarPublicationProvider(config, self.client),
        ]

    def _to_teacher_identity(self, row: dict[str, Any]) -> TeacherIdentity:
        return TeacherIdentity(
            id=str(row.get("id") or ""),
            full_name=str(row.get("full_name") or ""),
            department_name=str(row.get("department_name") or ""),
            faculty_name=str(row.get("faculty_name") or ""),
            orcid=str(row.get("orcid") or ""),
            google_scholar=str(row.get("google_scholar") or ""),
            scopus=str(row.get("scopus") or ""),
            web_of_science=str(row.get("web_of_science") or ""),
            profile_url=str(row.get("profile_url") or ""),
        )

    def import_for_teachers(self, teacher_rows: list[dict[str, Any]], *, include_scholar: bool = True) -> PublicationBundle:
        processed_teachers = 0
        teachers_with_publications = 0
        provider_hits: dict[str, int] = {}
        warnings: list[str] = []
        publication_map: dict[str, dict[str, Any]] = {}
        publication_lookup: dict[str, str] = {}
        authorship_map: dict[tuple[str, str], dict[str, Any]] = {}

        for row in teacher_rows:
            teacher = self._to_teacher_identity(row)
            if not (teacher.id and teacher.full_name):
                continue

            processed_teachers += 1
            teacher_has_hits = False

            for provider in self.providers:
                if provider.name == "Scholar" and not include_scholar:
                    continue
                try:
                    candidates = provider.fetch(teacher)
                except Exception as exc:  # pragma: no cover - depends on runtime network/API state
                    warnings.append(f"{provider.name}: {teacher.full_name} â€” {exc}")
                    continue

                provider_hits[provider.name] = provider_hits.get(provider.name, 0) + len(candidates)
                for candidate in candidates:
                    if not candidate.title:
                        continue
                    if provider.name in {"Crossref", "Scholar"} and not candidate_author_matches(candidate, teacher):
                        continue

                    publication_id, canonical_key = canonical_publication_id(candidate)
                    alias_keys = publication_aliases(candidate, publication_id, canonical_key)
                    resolved_publication_id = next(
                        (publication_lookup[alias] for alias in alias_keys if alias in publication_lookup),
                        publication_id,
                    )
                    existing = publication_map.get(resolved_publication_id)
                    source_names = set(existing.get("source_names", [])) if existing else set()
                    source_names.add(candidate.provider)

                    merged_authors = list(existing.get("authors_snapshot", [])) if existing else []
                    for author in candidate.authors:
                        if author and author not in merged_authors:
                            merged_authors.append(author)

                    base_row = {
                        "id": resolved_publication_id,
                        "title": candidate.title,
                        "year": candidate.year,
                        "doi": extract_doi(candidate.doi or ""),
                        "pub_type": candidate.pub_type,
                        "source": "; ".join(sorted(source_names)) if source_names else candidate.provider,
                        "url": candidate.url,
                        "canonical_key": canonical_key,
                        "external_ids": [candidate.external_id] if candidate.external_id else [],
                        "authors_snapshot": merged_authors,
                        "confidence": candidate.confidence,
                        "matched_by": candidate.matched_by,
                        "source_priority": candidate.source_priority,
                        "source_names": list(source_names),
                    }

                    if existing:
                        if candidate.source_priority < existing["source_priority"]:
                            existing.update(
                                {
                                    "title": candidate.title or existing["title"],
                                    "year": candidate.year or existing["year"],
                                    "pub_type": candidate.pub_type or existing["pub_type"],
                                    "url": candidate.url or existing["url"],
                                    "confidence": max(existing["confidence"], candidate.confidence),
                                    "matched_by": existing["matched_by"] or candidate.matched_by,
                                    "source_priority": candidate.source_priority,
                                }
                            )
                        else:
                            existing["confidence"] = max(existing["confidence"], candidate.confidence)
                            if not existing["year"] and candidate.year:
                                existing["year"] = candidate.year
                            if not existing["url"] and candidate.url:
                                existing["url"] = candidate.url
                            if not existing["pub_type"] and candidate.pub_type:
                                existing["pub_type"] = candidate.pub_type

                        if candidate.doi and not existing["doi"]:
                            existing["doi"] = extract_doi(candidate.doi)
                        if candidate.external_id and candidate.external_id not in existing["external_ids"]:
                            existing["external_ids"].append(candidate.external_id)
                        existing["authors_snapshot"] = merged_authors
                        updated_sources = set(existing.get("source_names", []))
                        updated_sources.add(candidate.provider)
                        existing["source_names"] = list(updated_sources)
                        existing["source"] = "; ".join(sorted(updated_sources))
                    else:
                        publication_map[resolved_publication_id] = base_row

                    resolved_aliases = publication_aliases(candidate, resolved_publication_id, canonical_key)
                    for alias in resolved_aliases:
                        publication_lookup[alias] = resolved_publication_id

                    authorship_key = (teacher.id, resolved_publication_id)
                    current_authorship = authorship_map.get(authorship_key)
                    if current_authorship is None or candidate.source_priority < current_authorship["source_priority"]:
                        authorship_map[authorship_key] = {
                            "teacher_id": teacher.id,
                            "publication_id": resolved_publication_id,
                            "source": candidate.provider,
                            "confidence": round(candidate.confidence, 4),
                            "matched_by": candidate.matched_by,
                            "source_priority": candidate.source_priority,
                        }
                    teacher_has_hits = True

            if teacher_has_hits:
                teachers_with_publications += 1

        publications = []
        for row in publication_map.values():
            publications.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "year": row["year"],
                    "doi": row["doi"],
                    "pub_type": row["pub_type"],
                    "source": row["source"],
                    "url": row["url"],
                    "canonical_key": row["canonical_key"],
                    "external_ids": row["external_ids"],
                    "authors_snapshot": row["authors_snapshot"],
                    "confidence": round(float(row["confidence"]), 4),
                    "matched_by": row["matched_by"],
                }
            )

        authorships = [
            {
                "teacher_id": row["teacher_id"],
                "publication_id": row["publication_id"],
                "source": row["source"],
                "confidence": row["confidence"],
                "matched_by": row["matched_by"],
            }
            for row in authorship_map.values()
        ]

        publications.sort(key=lambda item: (-(item["year"] or 0), item["title"]))
        authorships.sort(key=lambda item: (item["teacher_id"], item["publication_id"]))
        return PublicationBundle(
            publications=publications,
            authorships=authorships,
            processed_teachers=processed_teachers,
            teachers_with_publications=teachers_with_publications,
            warnings=warnings,
            provider_hits=provider_hits,
        )
