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
    out = []
    for ch in text:
        if ch in replacements:
            out.append(replacements[ch])
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("-")
    return re.sub(r"-+", "-", "".join(out)).strip("-")


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_inline_staff(soup: BeautifulSoup) -> list[dict]:
    results = []

    current = None
    for tag in soup.find_all(["h3", "p", "a"]):
        text = clean_text(tag.get_text(" ", strip=True))
        if not text:
            continue

        if tag.name == "h3":
            if current and current.get("full_name"):
                results.append(current)

            name = text
            name = re.sub(r"\s*\(.*?\)\s*$", "", name).strip()

            if len(name.split()) >= 2:
                current = {
                    "full_name": name,
                    "position": "",
                    "academic_degree": "",
                    "academic_title": "",
                    "orcid": "",
                    "google_scholar": "",
                    "scopus": "",
                    "publication_url": "",
                    "source_url": "",
                }
            else:
                current = None
            continue

        if current is None:
            continue

        if tag.name == "a":
            href = tag.get("href", "").strip()
            href_lower = href.lower()
            label_lower = text.lower()

            if "orcid.org" in href_lower or "orcid" in label_lower:
                current["orcid"] = href
            elif "scholar.google" in href_lower or "g-scholar" in label_lower or "google scholar" in label_lower:
                current["google_scholar"] = href
            elif "scopus" in href_lower:
                current["scopus"] = href
            elif "publication" in label_lower or "publication.kspu.edu" in href_lower:
                current["publication_url"] = href

        else:
            low = text.lower()

            if "закінчив" in low or "закінчила" in low or "спеціальність" in low or "e-mail" in low:
                continue

            if not current["position"]:
                current["position"] = text
                continue

            if not current["academic_degree"] and (
                "кандидат" in low or "доктор" in low or "магістр" in low
            ):
                current["academic_degree"] = text

                if "доцент" in low or "професор" in low:
                    parts = [x.strip() for x in text.split(",")]
                    if len(parts) >= 2:
                        current["academic_degree"] = ", ".join(
                            [p for p in parts if "доцент" not in p.lower() and "професор" not in p.lower()]
                        ).strip(", ")
                        current["academic_title"] = ", ".join(
                            [p for p in parts if "доцент" in p.lower() or "професор" in p.lower()]
                        ).strip(", ")
                continue

            if not current["academic_title"] and ("доцент" in low or "професор" in low):
                current["academic_title"] = text

    if current and current.get("full_name"):
        results.append(current)

    cleaned = []
    seen = set()
    for row in results:
        key = row["full_name"].lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(row)

    return cleaned


def extract_profile_links(soup: BeautifulSoup) -> dict:
    profile_links = {}
    for a in soup.find_all("a", href=True):
        text = clean_text(a.get_text(" ", strip=True))
        href = urljoin("https://www.kspu.edu/", a["href"].strip())

        if len(text.split()) < 2 or len(text.split()) > 5:
            continue

        if not re.search(r"[А-ЯІЇЄҐ][а-яіїєґ'\-]+", text):
            continue

        profile_links[text.lower()] = href

    return profile_links


def scrape_department_teachers(department_id: str, faculty_id: str) -> list[dict]:
    if department_id not in STAFF_URLS:
        return []

    html = fetch_html(STAFF_URLS[department_id])
    soup = BeautifulSoup(html, "html.parser")

    inline_rows = extract_inline_staff(soup)
    profile_map = extract_profile_links(soup)

    results = []
    for row in inline_rows:
        full_name = row["full_name"]
        profile_url = profile_map.get(full_name.lower(), STAFF_URLS[department_id])

        teacher_id = f"T_{department_id}_{slugify(full_name)}"

        results.append({
            "teacher_id": teacher_id,
            "full_name": full_name,
            "position": row["position"],
            "academic_degree": row["academic_degree"],
            "academic_title": row["academic_title"],
            "department_id": department_id,
            "faculty_id": faculty_id,
            "orcid": row["orcid"],
            "google_scholar": row["google_scholar"],
            "scopus": row["scopus"],
            "source_url": profile_url,
            "publication_url": row["publication_url"],
        })
    def scrape_all_f07_teachers() -> list[dict]:
    all_rows = []

    department_map = {
        "D001": "F07",
        "D002": "F07",
        "D003": "F07",
    }

    for department_id, faculty_id in department_map.items():
        try:
            rows = scrape_department_teachers(
                department_id=department_id,
                faculty_id=faculty_id,
            )
            all_rows.extend(rows)
        except Exception:
            continue

    unique = {}
    for row in all_rows:
        key = (row.get("department_id", ""), row.get("full_name", "").strip().lower())
        if key not in unique:
            unique[key] = row

    return list(unique.values())

    return results
