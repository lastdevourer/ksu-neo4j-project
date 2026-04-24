from __future__ import annotations

import re
from typing import Any

from neo4j import GraphDatabase


SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT faculty_code_unique IF NOT EXISTS FOR (f:Faculty) REQUIRE f.code IS UNIQUE",
    "CREATE CONSTRAINT department_code_unique IF NOT EXISTS FOR (d:Department) REQUIRE d.code IS UNIQUE",
    "CREATE CONSTRAINT teacher_id_unique IF NOT EXISTS FOR (t:Teacher) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT publication_id_unique IF NOT EXISTS FOR (p:Publication) REQUIRE p.id IS UNIQUE",
    "CREATE RANGE INDEX faculty_name_idx IF NOT EXISTS FOR (f:Faculty) ON (f.name)",
    "CREATE RANGE INDEX department_name_idx IF NOT EXISTS FOR (d:Department) ON (d.name)",
    "CREATE RANGE INDEX teacher_full_name_idx IF NOT EXISTS FOR (t:Teacher) ON (t.full_name)",
    "CREATE RANGE INDEX publication_year_idx IF NOT EXISTS FOR (p:Publication) ON (p.year)",
]


LEGACY_MIGRATION_STATEMENTS = [
    "MATCH (f:Faculty) WHERE f.code IS NULL AND f.faculty_id IS NOT NULL SET f.code = f.faculty_id",
    "MATCH (d:Department) WHERE d.code IS NULL AND d.department_id IS NOT NULL SET d.code = d.department_id",
    "MATCH (t:Teacher) WHERE t.id IS NULL AND t.teacher_id IS NOT NULL SET t.id = t.teacher_id",
    "MATCH (p:Publication) WHERE p.id IS NULL AND p.publication_id IS NOT NULL SET p.id = p.publication_id",
    "MATCH (t:Teacher) WHERE t.full_name IS NULL AND t.name IS NOT NULL SET t.full_name = t.name",
    """
    MATCH (f:Faculty)-[:HAS_DEPARTMENT]->(d:Department)
    WHERE d.faculty_code IS NULL
    SET d.faculty_code = coalesce(d.faculty_id, f.code, f.faculty_id)
    """,
]


def title_case_name(value: str | None) -> str:
    if not value:
        return ""

    value = str(value).strip()
    if not value:
        return ""

    parts = re.split(r"(\s+|-)", value.lower())
    fixed: list[str] = []

    for part in parts:
        if part.isspace() or part == "-":
            fixed.append(part)
        elif part:
            fixed.append(part[:1].upper() + part[1:])

    return "".join(fixed)


def normalize_authors(authors: Any) -> list[str]:
    if not isinstance(authors, list):
        return []

    result: list[str] = []
    for author in authors:
        fixed = title_case_name(str(author))
        if fixed and fixed not in result:
            result.append(fixed)

    return result


def normalize_teacher_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)

    for key in [
        "full_name",
        "teacher",
        "teacher_a",
        "teacher_b",
        "source_name",
        "target_name",
    ]:
        if key in normalized:
            normalized[key] = title_case_name(normalized.get(key))

    if "authors" in normalized:
        normalized["authors"] = normalize_authors(normalized.get("authors"))

    return normalized


class Neo4jService:
    def __init__(self, uri: str, user: str, password: str, database: str = ""):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def _session_kwargs(self) -> dict[str, str]:
        return {"database": self.database} if self.database else {}

    def verify_connection(self) -> None:
        self.driver.verify_connectivity()
        with self.driver.session(**self._session_kwargs()) as session:
            session.run("RETURN 1 AS ok").consume()

    def run_query(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with self.driver.session(**self._session_kwargs()) as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]

    def execute(self, query: str, params: dict[str, Any] | None = None) -> None:
        with self.driver.session(**self._session_kwargs()) as session:
            session.run(query, params or {})

    def prepare_database(self) -> None:
        for statement in LEGACY_MIGRATION_STATEMENTS:
            self.execute(statement)
        for statement in SCHEMA_STATEMENTS:
            self.execute(statement)
        self.normalize_teacher_names_in_database()

    def seed_reference_data(self, faculties: list[dict[str, str]], departments: list[dict[str, str]]) -> None:
        self.prepare_database()
        self.execute(
            """
            UNWIND $rows AS row
            MERGE (f:Faculty {code: row.code})
            SET f.name = row.name,
                f.faculty_id = row.code
            """,
            {"rows": faculties},
        )
        self.execute(
            """
            UNWIND $rows AS row
            MATCH (f:Faculty {code: row.faculty_code})
            MERGE (d:Department {code: row.code})
            SET d.name = row.name,
                d.department_id = row.code,
                d.faculty_code = row.faculty_code,
                d.faculty_id = row.faculty_code
            MERGE (f)-[:HAS_DEPARTMENT]->(d)
            """,
            {"rows": departments},
        )

    def seed_teachers(self, teachers: list[dict[str, str]]) -> None:
        self.prepare_database()

        normalized_teachers = []
        for row in teachers:
            normalized_row = dict(row)
            normalized_row["full_name"] = title_case_name(row.get("full_name", ""))
            normalized_teachers.append(normalized_row)

        self.execute(
            """
            UNWIND $rows AS row
            MATCH (d:Department {code: row.department_code})
            MERGE (t:Teacher {id: row.id})
            SET
                t.teacher_id = row.id,
                t.full_name = row.full_name,
                t.name = row.full_name,
                t.position = coalesce(row.position, ""),
                t.academic_degree = coalesce(row.academic_degree, ""),
                t.academic_title = coalesce(row.academic_title, ""),
                t.orcid = coalesce(row.orcid, ""),
                t.google_scholar = coalesce(row.google_scholar, ""),
                t.scopus = coalesce(row.scopus, ""),
                t.web_of_science = coalesce(row.web_of_science, ""),
                t.profile_url = coalesce(row.profile_url, ""),
                t.department_code = row.department_code
            MERGE (d)-[:HAS_TEACHER]->(t)
            """,
            {"rows": normalized_teachers},
        )

    def normalize_teacher_names_in_database(self) -> None:
        rows = self.run_query(
            """
            MATCH (t:Teacher)
            RETURN coalesce(t.id, t.teacher_id) AS id,
                   coalesce(t.full_name, t.name) AS full_name
            """
        )

        normalized_rows = []
        for row in rows:
            normalized_rows.append(
                {
                    "id": row["id"],
                    "full_name": title_case_name(row["full_name"]),
                }
            )

        if not normalized_rows:
            return

        self.execute(
            """
            UNWIND $rows AS row
            MATCH (t:Teacher)
            WHERE coalesce(t.id, t.teacher_id) = row.id
            SET t.full_name = row.full_name,
                t.name = row.full_name
            """,
            {"rows": normalized_rows},
        )

    def import_teacher_publications(self, teacher_id: str, publications: list[dict[str, Any]]) -> int:
        if not publications:
            return 0

        normalized_publications = []
        for row in publications:
            normalized_row = dict(row)
            normalized_row["authors"] = normalize_authors(row.get("authors"))
            normalized_publications.append(normalized_row)

        self.prepare_database()
        self.execute(
            """
            MATCH (t:Teacher)
            WHERE coalesce(t.id, t.teacher_id) = $teacher_id
            UNWIND $rows AS row
            MERGE (p:Publication {id: row.id})
            SET
                p.publication_id = row.id,
                p.title = row.title,
                p.year = row.year,
                p.doi = coalesce(row.doi, ""),
                p.openalex_id = coalesce(row.openalex_id, ""),
                p.pub_type = coalesce(row.pub_type, ""),
                p.source = coalesce(row.source, "OpenAlex"),
                p.external_url = coalesce(row.external_url, ""),
                p.cited_by_count = coalesce(row.cited_by_count, 0),
                p.authors = coalesce(row.authors, [])
            MERGE (t)-[:AUTHORED]->(p)
            """,
            {
                "teacher_id": teacher_id,
                "rows": normalized_publications,
            },
        )
        return len(normalized_publications)

    def get_teacher_import_options(self, department_code: str = "") -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (d:Department)-[:HAS_TEACHER]->(t:Teacher)
            WHERE ($department_code = "" OR coalesce(d.code, d.department_id) = $department_code)
            OPTIONAL MATCH (t)-[:AUTHORED]->(p:Publication)
            RETURN
                coalesce(t.id, t.teacher_id) AS id,
                coalesce(t.full_name, t.name) AS full_name,
                coalesce(d.name, "") AS department_name,
                coalesce(t.orcid, "") AS orcid,
                coalesce(t.google_scholar, "") AS google_scholar,
                count(DISTINCT p) AS publications
            ORDER BY publications ASC, full_name
            """,
            {"department_code": department_code.strip()},
        )
        return [normalize_teacher_row(row) for row in rows]

    def get_overview_counts(self) -> dict[str, int]:
        rows = self.run_query(
            """
            CALL {
                MATCH (f:Faculty)
                RETURN count(DISTINCT f) AS faculties
            }
            CALL {
                MATCH (d:Department)
                RETURN count(DISTINCT d) AS departments
            }
            CALL {
                MATCH (t:Teacher)
                RETURN count(DISTINCT t) AS teachers
            }
            CALL {
                MATCH (p:Publication)
                RETURN count(DISTINCT p) AS publications
            }
            CALL {
                MATCH (:Teacher)-[r:AUTHORED]->(:Publication)
                RETURN count(r) AS authorship_links
            }
            CALL {
                MATCH (a:Teacher)-[:AUTHORED]->(:Publication)<-[:AUTHORED]-(b:Teacher)
                WHERE coalesce(a.id, a.teacher_id) < coalesce(b.id, b.teacher_id)
                RETURN count(DISTINCT coalesce(a.id, a.teacher_id) + "|" + coalesce(b.id, b.teacher_id)) AS coauthor_pairs
            }
            RETURN faculties, departments, teachers, publications, authorship_links, coauthor_pairs
            """
        )
        if not rows:
            return {
                "faculties": 0,
                "departments": 0,
                "teachers": 0,
                "publications": 0,
                "authorship_links": 0,
                "coauthor_pairs": 0,
            }
        return rows[0]

    def get_departments(self) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (d:Department)
            OPTIONAL MATCH (f:Faculty)-[:HAS_DEPARTMENT]->(d)
            RETURN
                coalesce(d.code, d.department_id) AS code,
                d.name AS name,
                coalesce(f.code, f.faculty_id, d.faculty_code, d.faculty_id) AS faculty_code,
                f.name AS faculty_name
            ORDER BY d.name
            """
        )

    def get_department_overview(self) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (d:Department)
            OPTIONAL MATCH (f:Faculty)-[:HAS_DEPARTMENT]->(d)
            OPTIONAL MATCH (d)-[:HAS_TEACHER]->(t:Teacher)
            OPTIONAL MATCH (t)-[:AUTHORED]->(p:Publication)
            RETURN
                coalesce(d.code, d.department_id) AS code,
                d.name AS name,
                coalesce(f.code, f.faculty_id) AS faculty_code,
                f.name AS faculty_name,
                count(DISTINCT t) AS teachers,
                count(DISTINCT p) AS publications
            ORDER BY publications DESC, teachers DESC, name
            """
        )

    def get_faculty_overview(self) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (f:Faculty)
            OPTIONAL MATCH (f)-[:HAS_DEPARTMENT]->(d:Department)
            OPTIONAL MATCH (d)-[:HAS_TEACHER]->(t:Teacher)
            OPTIONAL MATCH (t)-[:AUTHORED]->(p:Publication)
            RETURN
                coalesce(f.code, f.faculty_id) AS code,
                f.name AS name,
                count(DISTINCT d) AS departments,
                count(DISTINCT t) AS teachers,
                count(DISTINCT p) AS publications
            ORDER BY teachers DESC, publications DESC, name
            """
        )

    def get_teachers(self, search: str = "", department_code: str = "") -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (d:Department)-[:HAS_TEACHER]->(t:Teacher)
            OPTIONAL MATCH (f:Faculty)-[:HAS_DEPARTMENT]->(d)
            WHERE ($search = "" OR toLower(coalesce(t.full_name, t.name, "")) CONTAINS toLower($search))
              AND ($department_code = "" OR coalesce(d.code, d.department_id) = $department_code)
            OPTIONAL MATCH (t)-[:AUTHORED]->(p:Publication)
            RETURN
                coalesce(t.id, t.teacher_id) AS id,
                coalesce(t.full_name, t.name) AS full_name,
                coalesce(t.position, "") AS position,
                coalesce(t.academic_degree, "") AS academic_degree,
                coalesce(t.academic_title, "") AS academic_title,
                coalesce(t.orcid, "") AS orcid,
                coalesce(t.google_scholar, "") AS google_scholar,
                coalesce(t.scopus, "") AS scopus,
                coalesce(t.web_of_science, "") AS web_of_science,
                coalesce(t.profile_url, "") AS profile_url,
                coalesce(d.code, d.department_id, t.department_code, t.department_id) AS department_code,
                coalesce(d.name, t.department_name, "") AS department_name,
                coalesce(f.code, f.faculty_id, t.faculty_code, t.faculty_id) AS faculty_code,
                coalesce(f.name, "") AS faculty_name,
                count(DISTINCT p) AS publications
            ORDER BY full_name
            """,
            {"search": search.strip(), "department_code": department_code.strip()},
        )
        return [normalize_teacher_row(row) for row in rows]

    def get_teacher_profile(self, teacher_id: str) -> dict[str, Any] | None:
        rows = self.run_query(
            """
            MATCH (t:Teacher)
            WHERE coalesce(t.id, t.teacher_id) = $teacher_id
            OPTIONAL MATCH (d:Department)-[:HAS_TEACHER]->(t)
            OPTIONAL MATCH (f:Faculty)-[:HAS_DEPARTMENT]->(d)
            RETURN
                coalesce(t.id, t.teacher_id) AS id,
                coalesce(t.full_name, t.name) AS full_name,
                coalesce(t.position, "") AS position,
                coalesce(t.academic_degree, "") AS academic_degree,
                coalesce(t.academic_title, "") AS academic_title,
                coalesce(t.orcid, "") AS orcid,
                coalesce(t.google_scholar, "") AS google_scholar,
                coalesce(t.scopus, "") AS scopus,
                coalesce(t.web_of_science, "") AS web_of_science,
                coalesce(t.profile_url, "") AS profile_url,
                coalesce(d.code, d.department_id, t.department_code, t.department_id) AS department_code,
                coalesce(d.name, t.department_name, "") AS department_name,
                coalesce(f.code, f.faculty_id, t.faculty_code, t.faculty_id) AS faculty_code,
                coalesce(f.name, "") AS faculty_name
            LIMIT 1
            """,
            {"teacher_id": teacher_id},
        )
        return normalize_teacher_row(rows[0]) if rows else None

    def get_teacher_publications(self, teacher_id: str) -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (t:Teacher)-[:AUTHORED]->(p:Publication)
            WHERE coalesce(t.id, t.teacher_id) = $teacher_id
            OPTIONAL MATCH (co:Teacher)-[:AUTHORED]->(p)
            WITH p, collect(DISTINCT coalesce(co.full_name, co.name)) AS graph_authors
            RETURN
                coalesce(p.id, p.publication_id) AS id,
                p.title AS title,
                p.year AS year,
                coalesce(p.doi, "") AS doi,
                coalesce(p.pub_type, "") AS pub_type,
                coalesce(p.source, "") AS source,
                CASE
                    WHEN p.authors IS NOT NULL AND size(p.authors) > 0 THEN p.authors
                    ELSE graph_authors
                END AS authors
            ORDER BY coalesce(p.year, 0) DESC, title
            """,
            {"teacher_id": teacher_id},
        )
        return [normalize_teacher_row(row) for row in rows]

    def get_teacher_coauthors(self, teacher_id: str) -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (t:Teacher)-[:AUTHORED]->(p:Publication)<-[:AUTHORED]-(co:Teacher)
            WHERE coalesce(t.id, t.teacher_id) = $teacher_id
              AND coalesce(co.id, co.teacher_id) <> $teacher_id
            RETURN
                coalesce(co.id, co.teacher_id) AS id,
                coalesce(co.full_name, co.name) AS full_name,
                count(DISTINCT p) AS shared_publications,
                collect(DISTINCT p.title)[0..5] AS publication_examples
            ORDER BY shared_publications DESC, full_name
            """,
            {"teacher_id": teacher_id},
        )
        return [normalize_teacher_row(row) for row in rows]

    def get_publication_years(self) -> list[int]:
        rows = self.run_query(
            """
            MATCH (p:Publication)
            WHERE p.year IS NOT NULL
            RETURN DISTINCT p.year AS year
            ORDER BY year DESC
            """
        )
        return [int(row["year"]) for row in rows if row.get("year") is not None]

    def get_publications(self, year: int | None = None) -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (p:Publication)
            WHERE ($year IS NULL OR p.year = $year)
            OPTIONAL MATCH (t:Teacher)-[:AUTHORED]->(p)
            WITH p, collect(DISTINCT coalesce(t.full_name, t.name)) AS graph_authors
            RETURN
                coalesce(p.id, p.publication_id) AS id,
                p.title AS title,
                p.year AS year,
                coalesce(p.doi, "") AS doi,
                coalesce(p.pub_type, "") AS pub_type,
                coalesce(p.source, "") AS source,
                CASE
                    WHEN p.authors IS NOT NULL AND size(p.authors) > 0 THEN p.authors
                    ELSE graph_authors
                END AS authors,
                CASE
                    WHEN p.authors IS NOT NULL AND size(p.authors) > 0 THEN size(p.authors)
                    ELSE size(graph_authors)
                END AS authors_count
            ORDER BY coalesce(p.year, 0) DESC, title
            """,
            {"year": year},
        )
        return [normalize_teacher_row(row) for row in rows]

    def get_graph_edges(self, department_code: str = "", limit: int = 160) -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (d:Department)-[:HAS_TEACHER]->(t:Teacher)-[:AUTHORED]->(p:Publication)
            WHERE ($department_code = "" OR coalesce(d.code, d.department_id) = $department_code)
            RETURN
                coalesce(t.id, t.teacher_id) AS teacher_id,
                coalesce(t.full_name, t.name) AS teacher_name,
                d.name AS department_name,
                coalesce(p.id, p.publication_id) AS publication_id,
                p.title AS publication_title,
                p.year AS year
            ORDER BY coalesce(p.year, 0) DESC, teacher_name
            LIMIT $limit
            """,
            {"department_code": department_code.strip(), "limit": int(limit)},
        )

        for row in rows:
            row["teacher_name"] = title_case_name(row.get("teacher_name"))

        return rows

    def get_top_teachers_by_publications(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (t:Teacher)
            OPTIONAL MATCH (d:Department)-[:HAS_TEACHER]->(t)
            OPTIONAL MATCH (t)-[:AUTHORED]->(p:Publication)
            RETURN
                coalesce(t.full_name, t.name) AS teacher,
                coalesce(d.name, "") AS department,
                count(DISTINCT p) AS publications
            ORDER BY publications DESC, teacher
            LIMIT $limit
            """,
            {"limit": int(limit)},
        )
        return [normalize_teacher_row(row) for row in rows]

    def get_top_coauthor_pairs(self, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (a:Teacher)-[:AUTHORED]->(p:Publication)<-[:AUTHORED]-(b:Teacher)
            WHERE coalesce(a.id, a.teacher_id) < coalesce(b.id, b.teacher_id)
            WITH a, b, count(DISTINCT p) AS shared_publications, collect(DISTINCT p.title)[0..5] AS sample_publications
            RETURN
                coalesce(a.full_name, a.name) AS teacher_a,
                coalesce(b.full_name, b.name) AS teacher_b,
                shared_publications,
                sample_publications
            ORDER BY shared_publications DESC, teacher_a, teacher_b
            LIMIT $limit
            """,
            {"limit": int(limit)},
        )
        return [normalize_teacher_row(row) for row in rows]

    def get_coauthor_edges(self) -> list[dict[str, Any]]:
        rows = self.run_query(
            """
            MATCH (a:Teacher)-[:AUTHORED]->(p:Publication)<-[:AUTHORED]-(b:Teacher)
            WHERE coalesce(a.id, a.teacher_id) < coalesce(b.id, b.teacher_id)
            RETURN
                coalesce(a.id, a.teacher_id) AS source_id,
                coalesce(a.full_name, a.name) AS source_name,
                coalesce(b.id, b.teacher_id) AS target_id,
                coalesce(b.full_name, b.name) AS target_name,
                count(DISTINCT p) AS weight
            ORDER BY weight DESC, source_name, target_name
            """
        )
        return [normalize_teacher_row(row) for row in rows]
