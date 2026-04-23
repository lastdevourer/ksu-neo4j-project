import re

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}


def fetch_html(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding
    return resp.text


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_doi(text: str) -> str:
    m = re.search(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", text, re.IGNORECASE)
    return m.group(1) if m else ""


def extract_year(text: str):
    years = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    if years:
        try:
            return int(years[0])
        except Exception:
            return None
    return None


def split_candidates(text: str) -> list[str]:
    parts = re.split(r"\n|(?=\d+\.)", text)
    cleaned = []
    for part in parts:
        part = clean_text(part)
        part = re.sub(r"^\d+[\.\)]\s*", "", part)
        if len(part) < 25:
            continue
        cleaned.append(part)
    return cleaned
def scrape_publications_from_teacher(teacher_row: dict) -> list[dict]:
    publication_url = teacher_row.get("publication_url", "")
    source_url = teacher_row.get("source_url", "")

    if publication_url:
        return scrape_publications_from_profile(publication_url)

    if source_url:
        return scrape_publications_from_profile(source_url)

    return []


def scrape_publications_from_profile(profile_url: str) -> list[dict]:
    html = fetch_html(profile_url)
    soup = BeautifulSoup(html, "html.parser")
    full_text = clean_text(soup.get_text("\n", strip=True))

    markers = [
        "Публікації",
        "Основні публікації",
        "Наукові публікації",
        "Наукові праці",
        "Publication",
        "Publications",
    ]

    publication_block = ""
    for marker in markers:
        m = re.search(rf"{marker}\s*(.+)", full_text, re.IGNORECASE)
        if m:
            publication_block = m.group(1)
            break

    if not publication_block:
        publication_block = full_text

    lines = split_candidates(publication_block)

    results = []
    seen = set()

    for line in lines:
        year = extract_year(line)
        doi = extract_doi(line)

        if len(line) > 500:
            line = line[:500].strip()

        key = (line.lower(), year, doi.lower())
        if key in seen:
            continue
        seen.add(key)

        results.append({
            "title": line,
            "year": year,
            "doi": doi,
            "pub_type": "наукова публікація",
            "source": "Профіль викладача KSPU",
            "source_url": profile_url,
            "notes": "",
            "topics": [],
        })

    return results
