import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}

STAFF_URLS = {
    "D001": "https://www.kspu.edu/About/Faculty/FPhysMathemInformatics/ChairAlgGeomMathAnalysis/Staff.aspx",
    "D002": "https://www.kspu.edu/About/Faculty/FPhysMathemInformatics/ChairPhysics/Staff.aspx",
    "D003": "https://www.kspu.edu/About/Faculty/FPhysMathemInformatics/ChairInformatics/Staff.aspx",
}


def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding
    return response.text


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str) -> str:
    text = text.lower().strip()
    replacements = {
        "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g",
        "д": "d", "е": "e", "є": "ie", "ж": "zh", "з": "z",
        "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k",
        "л": "l", "м": "m", "н": "n", "о": "o", "п": "p",
        "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
        "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
        "ь": "", "ю": "iu", "я": "ia",
        "'": "", "’": "", "`": "", "ʼ": "",
    }
    result = []
    for ch in text:
        if ch in replacements:
            result.append(replacements[ch])
        elif ch.isalnum():
            result.append(ch)
        else:
            result.append("-")
    return re.sub(r"-+", "-", "".join(result)).strip("-")


def is_probable_name(text: str) -> bool:
    parts = text.split()
    if len(parts) < 2 or len(parts) > 5:
        return False
    return bool(re.search(r"[А-ЯІЇЄҐ][а-яіїєґ'\-]+", text))


def is_archived_text(text: str) -> bool:
    lowered = text.lower()
    archive_markers = [
        "архів",
        "працював",
        "працювала",
        "по вересень",
        "до 2021",
        "до 2022",
        "до 2023",
        "до 2024",
        "до 2025",
        "звільнен",
        "колиш",
    ]
    return any(marker in lowered for marker in archive_markers)


def extract_links_map(soup: BeautifulSoup) -> tuple[dict, dict]:
    profile_links = {}
    publication_links = {}

    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        href = urljoin("https://www.kspu.edu/", a["href"].strip())
        lowered = text.lower()

        if is_probable_name(text):
            profile_links[text.lower()] = href

        if "publication" in lowered or "публікац" in lowered:
            publication_links[href.lower()] = href

    return profile_links, publication_links


def extract_teacher_blocks(soup: BeautifulSoup) -> list[dict]:
    teachers = []
    current = None

    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "a", "div", "span"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue

        if is_archived_text(text):
            if current and current.get("full_name"):
                current["archived"] = True
            continue

        if tag.name in {"h2", "h3", "h4"} and is_probable_name(text):
            if current and current.get("full_name") and not current.get("archived"):
                teachers.append(current)

            current = {
                "full_name": text,
                "position": "",
                "academic_degree": "",
                "academic_title": "",
                "orcid": "",
                "google_scholar": "",
                "scopus": "",
                "source_url": "",
                "publication_url": "",
                "archived": False,
            }
            continue

        if current is None:
            continue

        lowered = text.lower()

        if tag.name == "a":
            href = urljoin("https://www.kspu.edu/", tag.get("href", "").strip())
            href_lower = href.lower()

            if "orcid.org" in href_lower or "orcid" in lowered:
                current["orcid"] = href
            elif "scholar.google" in href_lower or "google scholar" in lowered or "g-scholar" in lowered:
                current["google_scholar"] = href
            elif "scopus" in href_lower:
                current["scopus"] = href
            elif "publication" in href_lower or "публікац" in lowered:
                current["publication_url"] = href

            continue

        if not current["position"]:
            banned_prefixes = [
                "закінчив",
                "закінчила",
                "освіта",
                "e-mail",
                "email",
                "робоча адреса",
                "наукові інтереси",
                "публікації",
            ]
            if not any(lowered.startswith(prefix) for prefix in banned_prefixes):
                current["position"] = text
                continue

        if not current["academic_degree"] and (
            "кандидат" in lowered or "доктор" in lowered or "магістр" in lowered
        ):
            current["academic_degree"] = text
            continue

        if not current["academic_title"] and (
            "доцент" in lowered or "професор" in lowered or "старший викладач" in lowered
        ):
            current["academic_title"] = text
            continue

    if current and current.get("full_name") and not current.get("archived"):
        teachers.append(current)

    unique = {}
    for row in teachers:
        key = row["full_name"].strip().lower()
        if key not in unique:
            unique[key] = row

    return list(unique.values())


def normalize_teachers(raw_teachers: list[dict], department_id: str, faculty_id: str) -> list[dict]:
    normalized = []

    for row in raw_teachers:
        full_name = row.get("full_name", "").strip()
        if not full_name:
            continue

        if is_archived_text(full_name):
            continue

        teacher_id = f"T_{department_id}_{slugify(full_name)}"

        normalized.append({
            "teacher_id": teacher_id,
            "full_name": full_name,
            "position": row.get("position", "").strip(),
            "academic_degree": row.get("academic_degree", "").strip(),
            "academic_title": row.get("academic_title", "").strip(),
            "department_id": department_id,
            "faculty_id": faculty_id,
            "orcid": row.get("orcid", "").strip(),
            "google_scholar": row.get("google_scholar", "").strip(),
            "scopus": row.get("scopus", "").strip(),
            "source_url": row.get("source_url", "").strip(),
            "publication_url": row.get("publication_url", "").strip(),
        })

    return normalized


def scrape_department_teachers(department_id: str, faculty_id: str) -> list[dict]:
    if department_id not in STAFF_URLS:
        return []

    html = fetch_html(STAFF_URLS[department_id])
    soup = BeautifulSoup(html, "html.parser")

    profile_links, _ = extract_links_map(soup)
    teacher_blocks = extract_teacher_blocks(soup)

    for row in teacher_blocks:
        profile_url = profile_links.get(row["full_name"].lower(), "")
        if profile_url:
            row["source_url"] = profile_url
        else:
            row["source_url"] = STAFF_URLS[department_id]

    return normalize_teachers(teacher_blocks, department_id, faculty_id)


def scrape_all_f07_teachers() -> list[dict]:
    result = []
    departments = {
        "D001": "F07",
        "D002": "F07",
        "D003": "F07",
    }

    for department_id, faculty_id in departments.items():
        rows = scrape_department_teachers(department_id, faculty_id)
        result.extend(rows)

    unique = {}
    for row in result:
        key = (row["department_id"], row["full_name"].lower())
        if key not in unique:
            unique[key] = row

    return list(unique.values())
