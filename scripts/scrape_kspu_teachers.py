from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "seed_teachers.csv"


@dataclass(frozen=True)
class SourcePage:
    department_code: str
    department_name: str
    faculty_code: str
    url: str


def build_teacher_id(department_code: str, full_name: str) -> str:
    payload = f"{department_code}|{full_name}".encode("utf-8")
    return f"T-{department_code}-{hashlib.md5(payload).hexdigest()[:8].upper()}"


def manual_teacher(
    department_code: str,
    full_name: str,
    position: str,
    academic_degree: str,
    academic_title: str,
    profile_url: str,
    orcid: str = "",
    google_scholar: str = "",
    scopus: str = "",
    web_of_science: str = "",
) -> dict[str, str]:
    return {
        "id": build_teacher_id(department_code, full_name),
        "full_name": full_name,
        "department_code": department_code,
        "position": position,
        "academic_degree": academic_degree,
        "academic_title": academic_title,
        "orcid": orcid,
        "google_scholar": google_scholar,
        "scopus": scopus,
        "web_of_science": web_of_science,
        "profile_url": profile_url,
    }


SOURCES: list[SourcePage] = [
    SourcePage(
        department_code="D001",
        department_name="Кафедра алгебри, геометрії та математичного аналізу",
        faculty_code="F07",
        url="https://www.kspu.edu/About/Faculty/FPhysMathemInformatics/ChairAlgGeomMathAnalysis/Staff.aspx",
    ),
    SourcePage(
        department_code="D002",
        department_name="Кафедра фізики",
        faculty_code="F07",
        url="https://www.kspu.edu/About/Faculty/FPhysMathemInformatics/ChairPhysics/Staff.aspx",
    ),
    SourcePage(
        department_code="D003",
        department_name="Кафедра комп'ютерних наук та програмної інженерії",
        faculty_code="F07",
        url="https://www.kspu.edu/About/Faculty/FPhysMathemInformatics/ChairInformatics/Staff.aspx",
    ),
    SourcePage(
        department_code="D004",
        department_name="Кафедра теорії та методики фізичного виховання",
        faculty_code="F08",
        url="https://www.kspu.edu/About/Faculty/FPhysicalEduSport/ChairTheoryMethodsPhysicalEdu/Staff.aspx",
    ),
    SourcePage(
        department_code="D005",
        department_name="Кафедра олімпійського та професійного спорту",
        faculty_code="F08",
        url="https://www.kspu.edu/About/Faculty/FPhysicalEduSport/ChairOlympicProfSport/sclad.aspx",
    ),
    SourcePage(
        department_code="D006",
        department_name="Кафедра медико-біологічних основ фізичного виховання та спорту",
        faculty_code="F08",
        url="https://www.kspu.edu/About/Faculty/FPhysicalEduSport/Medbiol/Staff.aspx",
    ),
    SourcePage(
        department_code="D007",
        department_name="Кафедра готельно-ресторанного та туристичного бізнесу",
        faculty_code="F03",
        url="https://www.kspu.edu/About/Faculty/FBP/ChairGenengineerTraining.aspx",
    ),
    SourcePage(
        department_code="D009",
        department_name="Кафедра національного, міжнародного права та правоохоронної діяльності",
        faculty_code="F03",
        url="https://www.kspu.edu/About/Faculty/FBP/ChairBranchLaw/vukladachi.aspx",
    ),
    SourcePage(
        department_code="D010",
        department_name="Кафедра фінансів, обліку та підприємництва",
        faculty_code="F03",
        url="https://www.kspu.edu/About/Faculty/FBP/FOP/Teaching_staff.aspx?lang=uk",
    ),
    SourcePage(
        department_code="D011",
        department_name="Кафедра педагогіки та психології дошкільної та початкової освіти",
        faculty_code="F02",
        url="https://www.kspu.edu/About/Faculty/FElementaryEdu/ChairPedagogics/Staff.aspx",
    ),
    SourcePage(
        department_code="D012",
        department_name="Кафедра теорії та методики дошкільної та початкової освіти",
        faculty_code="F02",
        url="https://www.kspu.edu/About/Faculty/FElementaryEdu/ChairPhilology/Staff.aspx",
    ),
    SourcePage(
        department_code="D013",
        department_name="Кафедра спеціальної освіти",
        faculty_code="F02",
        url="https://www.kspu.edu/About/Faculty/FElementaryEdu/ChairCorrectingEdu/Staff.aspx",
    ),
    SourcePage(
        department_code="D014",
        department_name="Кафедра педагогіки, психології й освітнього менеджменту імені проф. Є. Петухова",
        faculty_code="F02",
        url="https://www.kspu.edu/About/Faculty/FElementaryEdu/ChairPedagPsychology/Staff.aspx",
    ),
    SourcePage(
        department_code="D015",
        department_name="Кафедра медицини",
        faculty_code="F05",
        url="https://www.kspu.edu/About/Faculty/Medicine/DepartmentOfMedicine.aspx",
    ),
    SourcePage(
        department_code="D016",
        department_name="Кафедра хімії та фармації",
        faculty_code="F05",
        url="https://www.kspu.edu/About/Faculty/Medicine/ChairChemistryFarmacy.aspx?lang=uk",
    ),
    SourcePage(
        department_code="D017",
        department_name="Кафедра фізичної терапії та ерготерапії",
        faculty_code="F05",
        url="https://www.kspu.edu/About/Faculty/Medicine/Ab.aspx",
    ),
    SourcePage(
        department_code="D018",
        department_name="Кафедра психології",
        faculty_code="F06",
        url="https://www.kspu.edu/About/Faculty/IPHS/ChairGenSocialPsychology/Cadre.aspx",
    ),
    SourcePage(
        department_code="D019",
        department_name="Кафедра філософії, соціології та соціальної роботи",
        faculty_code="F06",
        url="https://www.kspu.edu/About/Faculty/IPHS/ChairSocialWork/Staff_of_the_department.aspx",
    ),
    SourcePage(
        department_code="D020",
        department_name="Кафедра історії, археології та методики викладання",
        faculty_code="F06",
        url="https://www.kspu.edu/About/Faculty/IPHS/ChairHistoryUkraine.aspx",
    ),
    SourcePage(
        department_code="D021",
        department_name="Кафедра географії та екології",
        faculty_code="F01",
        url="https://www.kspu.edu/About/Faculty/Faculty_of_biolog_geograf_ecol/ChairEcoGeography/department.aspx",
    ),
    SourcePage(
        department_code="D022",
        department_name="Кафедра біології людини та імунології",
        faculty_code="F01",
        url="https://www.kspu.edu/About/Faculty/Faculty_of_biolog_geograf_ecol/DepartmentofHumanBiologyandImmunology/Human_resource_staff.aspx?lang=uk",
    ),
    SourcePage(
        department_code="D023",
        department_name="Кафедра ботаніки",
        faculty_code="F01",
        url="https://www.kspu.edu/About/Faculty/Faculty_of_biolog_geograf_ecol/ChairBotany/ChairBotany_Kadry.aspx",
    ),
    SourcePage(
        department_code="D024",
        department_name="Кафедра англійської філології та світової літератури імені професора Олега Мішукова",
        faculty_code="F04",
        url="https://www.kspu.edu/About/Faculty/IUkrForeignPhilology/ChairTranslation/Staff.aspx",
    ),
    SourcePage(
        department_code="D025",
        department_name="Кафедра німецької та романської філології",
        faculty_code="F04",
        url="https://www.kspu.edu/About/Faculty/IUkrForeignPhilology/ChairGermRomLan/TeachingStaff.aspx",
    ),
    SourcePage(
        department_code="D026",
        department_name="Кафедра української і слов'янської філології та журналістики",
        faculty_code="F04",
        url="https://www.kspu.edu/About/Faculty/IUkrForeignPhilology/IPhilologyJournalizm/Staff.aspx",
    ),
]


MANUAL_TEACHERS: list[dict[str, str]] = [
    manual_teacher(
        "D008",
        "Ушкаренко Юлія Вікторівна",
        "Завідувачка кафедри",
        "Докторка економічних наук",
        "Професорка",
        "https://www.kspu.edu/About/Faculty/FBP/ChairEconomicTheory/Staff/Ushkarenko.aspx?lang=uk",
        orcid="https://orcid.org/0000-0002-7231-5277",
    ),
    manual_teacher(
        "D008",
        "Соловйов Андрій Ігорович",
        "Професор кафедри",
        "Доктор економічних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/FBP/Chair_of_Management_and_Administration/Lecturer/Solovyov.aspx",
    ),
    manual_teacher(
        "D008",
        "Синякова Катерина Миколаївна",
        "Доцентка кафедри",
        "Кандидатка економічних наук",
        "Доцентка",
        "https://www.kspu.edu/About/Faculty/FBP/Chair_of_Management_and_Administration/Lecturer/Syniakova.aspx?lang=uk",
        orcid="https://orcid.org/0000-0002-4439-9717",
        google_scholar="https://scholar.google.com.ua/citations?user=Rlxvs4AAAAAJ&hl=uk",
    ),
    manual_teacher(
        "D008",
        "Адвокатова Надія Олександрівна",
        "Доцентка кафедри",
        "Кандидатка економічних наук",
        "Доцентка",
        "https://www.kspu.edu/About/Faculty/FBP/Chair_of_Management_and_Administration/Lecturer.aspx?lang=uk",
    ),
    manual_teacher(
        "D008",
        "Чмут Анна Володимирівна",
        "Старша викладачка кафедри",
        "Кандидатка економічних наук",
        "Доцентка",
        "https://www.kspu.edu/About/Faculty/FBP/ChairEconomicTheory/Staff/Chmut.aspx",
        orcid="https://orcid.org/0000-0002-5947-728X",
        google_scholar="https://scholar.google.com.ua/citations?user=91H9CK0AAAAJ&hl=uk",
    ),
    manual_teacher(
        "D010",
        "Петренко Вікторія Сергіївна",
        "Завідувачка кафедри",
        "Докторка економічних наук",
        "Доцентка",
        "https://www.kspu.edu/About/Faculty/FBP/FOP.aspx?lang=uk",
        orcid="https://orcid.org/0000-0001-8336-7665",
    ),
    manual_teacher(
        "D010",
        "Мельникова Катерина Вікторівна",
        "Доцентка кафедри",
        "Кандидатка економічних наук",
        "Доцентка",
        "https://www.kspu.edu/About/Faculty/FBP.aspx?lang=uk",
    ),
    manual_teacher(
        "D010",
        "Мохненко Андрій Сергійович",
        "Професор кафедри",
        "Доктор економічних наук",
        "Професор",
        "https://www.kspu.edu/About/Faculty/FBP/Conference.aspx?lang=uk",
        orcid="https://orcid.org/0000-0001-6981-2283",
    ),
    manual_teacher(
        "D010",
        "Ковальов Віталій Валерійович",
        "Доцент кафедри",
        "Кандидат економічних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/FBP/FOP.aspx?lang=uk",
    ),
    manual_teacher(
        "D016",
        "Попович Тетяна Анатоліївна",
        "Завідувачка кафедри",
        "Кандидатка технічних наук",
        "Доцентка",
        "https://www.kspu.edu/About/Faculty/Medicine/ChairChemistryFarmacy.aspx?lang=uk",
        orcid="https://orcid.org/0000-0001-7449-9949",
        google_scholar="https://scholar.google.com.ua/citations?hl=ru&user=79q51_kAAAAJ",
        scopus="https://www.scopus.com/authid/detail.uri?authorId=57211424278",
        web_of_science="https://www.webofscience.com/wos/author/record/AAQ-2872-2020",
    ),
    manual_teacher(
        "D022",
        "Гасюк Олена Миколаївна",
        "Завідувачка кафедри",
        "Кандидатка біологічних наук",
        "Доцентка",
        "https://www.kspu.edu/About/Faculty/Faculty_of_biolog_geograf_ecol/DepartmentofHumanBiologyandImmunology/Human_resource_staff.aspx?lang=uk",
        orcid="https://orcid.org/0000-0003-1055-2848",
        google_scholar="https://scholar.google.com.ua/citations?hl=ru&user=DnToaW0AAAAJ",
        scopus="https://www.scopus.com/authid/detail.uri?authorId=56380597000",
        web_of_science="https://app.webofknowledge.com/author/#/record/13883535",
    ),
    manual_teacher(
        "D022",
        "Спринь Олександр Борисович",
        "Доцент кафедри",
        "Кандидат біологічних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/Faculty_of_biolog_geograf_ecol/DepartmentofHumanBiologyandImmunology/Human_resource_staff.aspx?lang=uk",
    ),
    manual_teacher(
        "D022",
        "Головченко Ігор Валентинович",
        "Доцент кафедри",
        "Кандидат біологічних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/Medicine/DepartmentOfMedicine.aspx",
    ),
    manual_teacher(
        "D022",
        "Бесчасний Сергій Павлович",
        "Доцент кафедри",
        "Кандидат біологічних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/Medicine/DepartmentOfMedicine.aspx",
    ),
    manual_teacher(
        "D017",
        "Лаврикова Оксана Валентинівна",
        "Завідувач кафедри",
        "Кандидатка біологічних наук",
        "Професор",
        "https://www.kspu.edu/About/Faculty/Medicine/Ab.aspx",
    ),
    manual_teacher(
        "D017",
        "Данильченко Світлана Іванівна",
        "Доцент кафедри",
        "Кандидатка медичних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/Medicine/Ab.aspx",
    ),
    manual_teacher(
        "D017",
        "Козій Тетяна Петрівна",
        "Доцент кафедри",
        "Кандидатка біологічних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/Medicine/Ab.aspx",
    ),
    manual_teacher(
        "D017",
        "Васильєва Наталія Олегівна",
        "Доцент кафедри",
        "Кандидатка біологічних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/Medicine/Ab.aspx",
    ),
    manual_teacher(
        "D017",
        "Верещакіна Вікторія Вікторівна",
        "Доцент кафедри",
        "Кандидатка медичних наук",
        "Доцент",
        "https://www.kspu.edu/About/Faculty/Medicine/Ab.aspx",
    ),
    manual_teacher(
        "D017",
        "Фурсенко Артемій Олександрович",
        "Викладач",
        "",
        "Викладач",
        "https://www.kspu.edu/About/Faculty/Medicine/Ab.aspx",
    ),
]


START_MARKERS = (
    "професорсько-викладацький склад",
    "професорсько-викладацький склад кафедри",
    "кадровий склад кафедри",
    "кадровий склад",
    "склад кафедри",
    "співробітники кафедри",
    "співробітники",
    "штатні співробітники",
    "викладацький склад",
    "внутрішні сумісники",
    "teaching staff",
)
END_MARKERS = (
    "навігація",
    "кількість відвідувань",
    "всі новини",
    "all news",
    "copyright",
    "powered by ksu",
    "пропозиції та коментарі",
)
NAME_TOKEN_RE = r"[А-ЯІЇЄҐ][А-ЯІЇЄҐа-яіїєґ'’\\-]+"
NAME_RE = re.compile(rf"^{NAME_TOKEN_RE}(?:\s+{NAME_TOKEN_RE}){{1,3}}$")
URL_RE = re.compile(r"^(https?://|orcid\.org/)", re.IGNORECASE)
PATRONYMIC_SUFFIXES = ("ович", "евич", "йович", "ич", "івна", "ївна", "овна", "евна", "їчна")
INLINE_ROLE_HINTS = (
    "завідувач",
    "професор",
    "доцент",
    "старш",
    "викладач",
    "асистент",
    "доктор",
    "кандидат",
    "гарант",
    "член",
    "фахів",
    "керівник",
    "лаборант",
)

SECTION_HINTS = {
    "професори": "Професор",
    "професори кафедри": "Професор",
    "доценти": "Доцент",
    "доценти кафедри": "Доцент",
    "старші викладачі": "Старший викладач",
    "старші викладачі кафедри": "Старший викладач",
    "викладачі": "Викладач",
    "викладачі кафедри": "Викладач",
    "асистенти": "Асистент",
    "асистенти кафедри": "Асистент",
}
NON_TEACHING_WORDS = (
    "аспірант",
    "лаборант",
    "провідн",
    "фахівець",
    "декан факультету",
    "секретар",
)
NAME_BLACKLIST = {
    "кафедра",
    "факультет",
    "професори",
    "доценти",
    "асистенти",
    "викладачі",
    "контакти",
    "навігація",
    "склад",
    "google",
    "semantic",
    "scholar",
    "orcid",
    "id",
    "модуль",
    "нагороджується",
    "херсонський",
    "державний",
    "університет",
    "image",
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attributes = dict(attrs)
        href = (attributes.get("href") or "").strip()
        if href.startswith(("http://", "https://")):
            self.texts.append(href)

    def handle_data(self, data: str) -> None:
        normalized = " ".join(data.split())
        if normalized:
            self.texts.append(normalized)


def fetch_lines(url: str) -> list[str]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=50) as response:
                html = response.read().decode("utf-8", errors="ignore")
            parser = TextExtractor()
            parser.feed(html)
            return parser.texts
        except Exception as exc:  # pragma: no cover - network instability branch
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Не вдалося отримати {url}")


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("’", "'").split())


def looks_like_name(line: str) -> bool:
    candidate = line.strip().rstrip(" -–—")
    if not NAME_RE.match(candidate):
        return False
    return is_probable_person_name(candidate)


def is_name_token(token: str) -> bool:
    cleaned = token.strip(".,:;!?()[]{}\"").replace("’", "'")
    return bool(cleaned) and bool(re.fullmatch(NAME_TOKEN_RE, cleaned))


def clean_profile_line(line: str) -> str:
    cleaned = line.replace("|", " ").replace("Image", " ").replace(" ", " ")
    return " ".join(cleaned.split())


def is_probable_person_name(name: str) -> bool:
    cleaned = clean_profile_line(name).strip(" ,.;:–—-")
    tokens = cleaned.split()
    if not 3 <= len(tokens) <= 4:
        return False
    if not all(is_name_token(token) for token in tokens):
        return False

    lowered = [normalize(token).strip(".,:;") for token in tokens]
    if any(token in NAME_BLACKLIST for token in lowered):
        return False

    return lowered[-1].endswith(PATRONYMIC_SUFFIXES)


def extract_inline_name(line: str) -> tuple[str, str] | None:
    cleaned = clean_profile_line(line)
    if looks_like_name(cleaned):
        return cleaned.rstrip(" -–—"), ""

    tokens = cleaned.split()
    if len(tokens) < 4:
        return None

    token_count = 4 if len(tokens) >= 5 and all(is_name_token(token) for token in tokens[:4]) else 3
    if len(tokens) <= token_count or not all(is_name_token(token) for token in tokens[:token_count]):
        return None

    candidate_name = " ".join(tokens[:token_count]).strip(" ,.;:–—-")
    if not is_probable_person_name(candidate_name):
        return None

    remainder = " ".join(tokens[token_count:]).lstrip(" ,.;:–—-")
    if not remainder:
        return None

    first_word = normalize(remainder.split()[0]).strip(".,:;")
    if not any(first_word.startswith(hint) for hint in INLINE_ROLE_HINTS):
        return None

    return candidate_name, remainder


def extract_role_first_name(line: str) -> tuple[str, str] | None:
    cleaned = clean_profile_line(line)
    if not cleaned:
        return None

    first_word = normalize(cleaned.split()[0]).strip(".,:;")
    if not any(first_word.startswith(hint) for hint in INLINE_ROLE_HINTS):
        return None

    matches = list(re.finditer(rf"{NAME_TOKEN_RE}(?:\s+{NAME_TOKEN_RE}){{2,3}}", cleaned))
    if not matches:
        return None

    match = matches[-1]
    name = match.group(0).strip(" -–—,;")
    if not is_probable_person_name(name):
        return None

    prefix = cleaned[: match.start()].strip(" -–—,;")
    suffix = cleaned[match.end() :].strip(" -–—,;")
    description = " ".join(part for part in (prefix, suffix) if part)
    return name, description


def infer_academic_degree(description: str) -> str:
    patterns = (
        r"доктор(?:ка)?\s+[а-яіїєґ'’\-\s]+?наук",
        r"кандидат(?:ка)?\s+[а-яіїєґ'’\-\s]+?наук",
        r"доктор\s+філософії[^,.]*",
        r"phd[^,.]*",
    )
    desc = description.lower()
    for pattern in patterns:
        match = re.search(pattern, desc)
        if match:
            value = match.group(0).strip(" ,.;")
            return value[:1].upper() + value[1:]
    return ""


def infer_academic_title(description: str, section_hint: str) -> str:
    desc = description.lower()
    if "професор" in desc:
        return "Професор"
    if "доцент" in desc:
        return "Доцент"
    if "старш" in desc and "виклада" in desc:
        return "Старший викладач"
    if "асистент" in desc:
        return "Асистент"
    if "викладач" in desc:
        return "Викладач"
    return section_hint


def infer_position(description: str, section_hint: str) -> str:
    desc = description.lower()
    if "аспірант" in desc:
        return "Аспірант"
    if "навчальною лабораторією" in desc:
        return "Лаборант"
    if "лаборант" in desc:
        return "Лаборант"
    if "провідн" in desc and "фахів" in desc:
        return "Провідний фахівець"
    if "завідувач" in desc:
        return "Завідувач кафедри"
    if "професор" in desc:
        return "Професор кафедри"
    if "доцент" in desc:
        return "Доцент кафедри"
    if "старш" in desc and "виклада" in desc:
        return "Старший викладач"
    if "асистент" in desc:
        return "Асистент"
    if "викладач" in desc:
        return "Викладач"
    if section_hint:
        return f"{section_hint} кафедри"
    return "Викладач"


def select_url(urls: list[str], needle: str) -> str:
    for url in urls:
        if needle in url.lower():
            return url
    return ""


def slice_staff_lines(lines: list[str]) -> list[str]:
    marker_indexes = [index for index, line in enumerate(lines) if any(marker in normalize(line) for marker in START_MARKERS)]
    if marker_indexes:
        start = next((index for index in marker_indexes if index >= 100), marker_indexes[-1])
    else:
        start = 0

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if any(marker in normalize(lines[index]) for marker in END_MARKERS):
            end = index
            break
    return lines[start:end]


def is_teacher_boundary(line: str) -> bool:
    normalized = normalize(line)
    return (
        normalized in SECTION_HINTS
        or looks_like_name(line)
        or extract_inline_name(line) is not None
        or extract_role_first_name(line) is not None
    )


def extract_teachers(source: SourcePage) -> list[dict[str, str]]:
    lines = slice_staff_lines(fetch_lines(source.url))
    rows: list[dict[str, str]] = []
    current_section = ""
    index = 0

    while index < len(lines):
        line = lines[index].strip()
        normalized = normalize(line)

        if normalized in SECTION_HINTS:
            current_section = normalized
            index += 1
            continue

        candidate = extract_inline_name(line) or extract_role_first_name(line)
        if looks_like_name(line) or candidate:
            clean_name = (line if candidate is None else candidate[0]).strip(" ,.;:–—-")
            if not is_probable_person_name(clean_name):
                index += 1
                continue
            block: list[str] = []
            if candidate and candidate[1]:
                block.append(candidate[1])
            cursor = index + 1
            while cursor < len(lines):
                nxt = lines[cursor].strip()
                next_normalized = normalize(nxt)
                if is_teacher_boundary(nxt):
                    break
                if any(marker in next_normalized for marker in END_MARKERS):
                    break
                block.append(nxt)
                cursor += 1

            urls = [item for item in block if URL_RE.match(item)]
            description_parts: list[str] = []
            for item in block:
                item_normalized = normalize(item)
                if not item or item.startswith("document.write("):
                    continue
                if item.endswith(".pdf") or item in {",", ".", ":", "@", ";"}:
                    continue
                if item_normalized.startswith(("e-mail", "email", "ел.пошта", "тел.")):
                    continue
                if item_normalized in {
                    "orcid",
                    "scopus",
                    "google scholar",
                    "g-scholar",
                    "wos",
                    "web of science",
                    "semantic scholar",
                    "publications",
                    "авторський профіль",
                    "науковий профіль",
                    "науковий профіль кафедри доступний за покликанням",
                    "архів",
                    "співробітники",
                    "професорсько-викладацький склад кафедри",
                }:
                    continue
                if URL_RE.match(item):
                    continue
                description_parts.append(item)

            description = " ".join(description_parts).strip(" ,.;")
            position = infer_position(description, SECTION_HINTS.get(current_section, ""))
            if any(word in position.lower() for word in NON_TEACHING_WORDS):
                index = cursor
                continue

            academic_title = infer_academic_title(description, SECTION_HINTS.get(current_section, ""))
            if any(word in academic_title.lower() for word in NON_TEACHING_WORDS):
                index = cursor
                continue

            rows.append(
                {
                    "id": build_teacher_id(source.department_code, clean_name),
                    "full_name": clean_name,
                    "department_code": source.department_code,
                    "position": position,
                    "academic_degree": infer_academic_degree(description),
                    "academic_title": academic_title,
                    "orcid": select_url(urls, "orcid.org"),
                    "google_scholar": select_url(urls, "scholar.google"),
                    "scopus": select_url(urls, "scopus.com"),
                    "web_of_science": select_url(urls, "webofscience"),
                    "profile_url": source.url,
                }
            )
            index = cursor
            continue

        index += 1

    unique_rows: dict[str, dict[str, str]] = {}
    for row in rows:
        unique_rows.setdefault(row["id"], row)
    return list(unique_rows.values())


def scrape_all() -> list[dict[str, str]]:
    teachers: list[dict[str, str]] = []
    for source in SOURCES:
        try:
            teachers.extend(extract_teachers(source))
        except Exception as exc:
            print(f"[WARN] Не вдалося обробити {source.department_code} {source.url}: {exc}", file=sys.stderr)
    teachers.extend(MANUAL_TEACHERS)
    unique_teachers: dict[str, dict[str, str]] = {}
    for row in teachers:
        unique_teachers[row["id"]] = row
    rows = list(unique_teachers.values())
    rows.sort(key=lambda row: (row["department_code"], row["full_name"]))
    return rows


def write_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "full_name",
        "department_code",
        "position",
        "academic_degree",
        "academic_title",
        "orcid",
        "google_scholar",
        "scopus",
        "web_of_science",
        "profile_url",
    ]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Scrape initial KSPU teacher seed data from official staff pages.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = scrape_all()
    write_csv(rows, args.output)
    print(f"Збережено {len(rows)} записів до {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
