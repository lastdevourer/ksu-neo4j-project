from __future__ import annotations

from typing import Any

from neo4j import GraphDatabase


SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT faculty_code_unique IF NOT EXISTS FOR (f:Faculty) REQUIRE f.code IS UNIQUE",
    "CREATE CONSTRAINT department_code_unique IF NOT EXISTS FOR (d:Department) REQUIRE d.code IS UNIQUE",
    "CREATE CONSTRAINT teacher_id_unique IF NOT EXISTS FOR (t:Teacher) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT publication_id_unique IF NOT EXISTS FOR (p:Publication) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT system_state_key_unique IF NOT EXISTS FOR (s:SystemState) REQUIRE s.key IS UNIQUE",
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
            {"rows": teachers},
        )

    def seed_publications(self, publications: list[dict[str, Any]], authorships: list[dict[str, Any]]) -> None:
        self.prepare_database()
        if publications:
            self.execute(
                """
                UNWIND $rows AS row
                MERGE (p:Publication {id: row.id})
                SET
                    p.publication_id = row.id,
                    p.title = row.title,
                    p.year = row.year,
                    p.doi = coalesce(row.doi, ""),
                    p.pub_type = coalesce(row.pub_type, ""),
                    p.source = coalesce(row.source, ""),
                    p.url = coalesce(row.url, ""),
                    p.canonical_key = coalesce(row.canonical_key, ""),
                    p.external_ids = coalesce(row.external_ids, []),
                    p.authors_snapshot = coalesce(row.authors_snapshot, []),
                    p.confidence = coalesce(row.confidence, 0.0),
                    p.match_info = coalesce(row.matched_by, "")
                """,
                {"rows": publications},
            )

        if authorships:
            self.execute(
                """
                UNWIND $rows AS row
                MATCH (t:Teacher {id: row.teacher_id})
                MATCH (p:Publication {id: row.publication_id})
                MERGE (t)-[r:AUTHORED]->(p)
                SET
                    r.source = coalesce(row.source, ""),
                    r.confidence = coalesce(row.confidence, 0.0),
                    r.matched_by = coalesce(row.matched_by, "")
                """,
                {"rows": authorships},
            )

    def import_teacher_publications(self, teacher_id: str, publications: list[dict[str, Any]]) -> int:
        if not teacher_id or not publications:
            return 0

        normalized_publications: list[dict[str, Any]] = []
        authorships: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for row in publications:
            publication_id = str(row.get("id") or row.get("publication_id") or "").strip()
            title = str(row.get("title") or "").strip()
            if not publication_id or not title or publication_id in seen_ids:
                continue

            seen_ids.add(publication_id)
            normalized_publications.append(
                {
                    "id": publication_id,
                    "title": title,
                    "year": row.get("year"),
                    "doi": str(row.get("doi") or "").strip(),
                    "pub_type": str(row.get("pub_type") or "").strip(),
                    "source": str(row.get("source") or "").strip(),
                    "url": str(row.get("external_url") or row.get("url") or "").strip(),
                    "canonical_key": str(
                        row.get("canonical_key")
                        or row.get("openalex_id")
                        or row.get("doi")
                        or publication_id
                    ).strip(),
                    "external_ids": [
                        value
                        for value in [
                            str(row.get("openalex_id") or "").strip(),
                            str(row.get("doi") or "").strip(),
                        ]
                        if value
                    ],
                    "authors_snapshot": list(row.get("authors") or []),
                    "confidence": float(row.get("confidence") or 0.82),
                    "matched_by": str(row.get("matched_by") or "manual_preview").strip(),
                }
            )
            authorships.append(
                {
                    "teacher_id": teacher_id,
                    "publication_id": publication_id,
                    "source": str(row.get("source") or "").strip(),
                    "confidence": float(row.get("confidence") or 0.82),
                    "matched_by": str(row.get("matched_by") or "manual_preview").strip(),
                }
            )

        self.seed_publications(normalized_publications, authorships)
        return len(normalized_publications)

    def get_publication_management_details(self, publication_id: str) -> dict[str, Any] | None:
        rows = self.run_query(
            """
            MATCH (p:Publication)
            WHERE coalesce(p.id, p.publication_id) = $publication_id
            OPTIONAL MATCH (t:Teacher)-[:AUTHORED]->(p)
            RETURN
                coalesce(p.id, p.publication_id) AS id,
                p.title AS title,
                p.year AS year,
                coalesce(p.source, "") AS source,
                count(DISTINCT t) AS linked_teachers_count,
                collect(DISTINCT coalesce(t.full_name, t.name)) AS linked_teachers
            LIMIT 1
            """,
            {"publication_id": publication_id},
        )
        return rows[0] if rows else None

    def delete_teacher_publication_link(self, teacher_id: str, publication_id: str) -> bool:
        rows = self.run_query(
            """
            MATCH (t:Teacher)-[r:AUTHORED]->(p:Publication)
            WHERE coalesce(t.id, t.teacher_id) = $teacher_id
              AND coalesce(p.id, p.publication_id) = $publication_id
            DELETE r
            WITH p
            OPTIONAL MATCH (:Teacher)-[:AUTHORED]->(p)
            WITH p, count(*) AS remaining_links
            FOREACH (_ IN CASE WHEN remaining_links = 0 THEN [1] ELSE [] END | DETACH DELETE p)
            RETURN true AS deleted
            LIMIT 1
            """,
            {"teacher_id": teacher_id, "publication_id": publication_id},
        )
        return bool(rows)

    def delete_publication(self, publication_id: str) -> bool:
        rows = self.run_query(
            """
            MATCH (p:Publication)
            WHERE coalesce(p.id, p.publication_id) = $publication_id
            DETACH DELETE p
            RETURN true AS deleted
            LIMIT 1
            """,
            {"publication_id": publication_id},
        )
        return bool(rows)

    def upsert_system_state(self, key: str, values: dict[str, Any]) -> None:
        self.execute(
            """
            MERGE (s:SystemState {key: $key})
            SET s += $values
            """,
            {"key": key, "values": values},
        )

    def get_system_state(self, key: str) -> dict[str, Any] | None:
        rows = self.run_query(
            """
            MATCH (s:SystemState {key: $key})
            RETURN properties(s) AS state
            LIMIT 1
            """,
            {"key": key},
        )
        return rows[0]["state"] if rows else None

    def mark_teachers_publication_sync(
        self,
        teacher_ids: list[str],
        *,
        synced_at: str,
        trigger: str,
        status: str,
    ) -> None:
        if not teacher_ids:
            return
        self.execute(
            """
            UNWIND $teacher_ids AS teacher_id
            MATCH (t:Teacher {id: teacher_id})
            SET
                t.last_publication_sync_at = $synced_at,
                t.last_publication_sync_trigger = $trigger,
                t.last_publication_sync_status = $status
            """,
            {
                "teacher_ids": teacher_ids,
                "synced_at": synced_at,
                "trigger": trigger,
                "status": status,
            },
        )

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

    def get_profile_coverage(self) -> dict[str, int]:
        rows = self.run_query(
            """
            MATCH (t:Teacher)
            RETURN
                count(DISTINCT t) AS teachers,
                count(DISTINCT CASE WHEN coalesce(t.orcid, "") <> "" THEN t END) AS with_orcid,
                count(DISTINCT CASE WHEN coalesce(t.google_scholar, "") <> "" THEN t END) AS with_scholar,
                count(DISTINCT CASE WHEN coalesce(t.scopus, "") <> "" THEN t END) AS with_scopus,
                count(DISTINCT CASE WHEN coalesce(t.web_of_science, "") <> "" THEN t END) AS with_wos,
                count(DISTINCT CASE WHEN coalesce(t.orcid, "") <> "" OR coalesce(t.google_scholar, "") <> "" OR coalesce(t.scopus, "") <> "" OR coalesce(t.web_of_science, "") <> "" THEN t END) AS with_any_profile
            """
        )
        return rows[0] if rows else {
            "teachers": 0,
            "with_orcid": 0,
            "with_scholar": 0,
            "with_scopus": 0,
            "with_wos": 0,
            "with_any_profile": 0,
        }

    def get_publication_source_summary(self) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (p:Publication)
            WITH p, [source IN split(coalesce(p.source, ""), ";") | trim(source)] AS sources
            UNWIND CASE WHEN size(sources) = 0 THEN ["Невідомо"] ELSE sources END AS source_name
            RETURN
                source_name AS source,
                count(DISTINCT p) AS publications
            ORDER BY publications DESC, source
            """
        )

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
        return self.run_query(
            """
            MATCH (t:Teacher)
            OPTIONAL MATCH (d:Department)-[:HAS_TEACHER]->(t)
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

    def get_teachers_for_publication_import(self, limit: int = 25, stale_before: str = "") -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (t:Teacher)
            OPTIONAL MATCH (d:Department)-[:HAS_TEACHER]->(t)
            OPTIONAL MATCH (f:Faculty)-[:HAS_DEPARTMENT]->(d)
            OPTIONAL MATCH (t)-[:AUTHORED]->(p:Publication)
            WITH
                t,
                d,
                f,
                count(DISTINCT p) AS publications,
                CASE WHEN coalesce(t.orcid, "") <> "" THEN 1 ELSE 0 END +
                CASE WHEN coalesce(t.google_scholar, "") <> "" THEN 1 ELSE 0 END +
                CASE WHEN coalesce(t.scopus, "") <> "" THEN 1 ELSE 0 END +
                CASE WHEN coalesce(t.web_of_science, "") <> "" THEN 1 ELSE 0 END AS profile_score
            WHERE (
                $stale_before = ""
                OR coalesce(t.last_publication_sync_at, "") = ""
                OR coalesce(t.last_publication_sync_at, "") < $stale_before
            )
            RETURN
                coalesce(t.id, t.teacher_id) AS id,
                coalesce(t.full_name, t.name) AS full_name,
                coalesce(d.name, t.department_name, "") AS department_name,
                coalesce(f.name, "") AS faculty_name,
                coalesce(t.orcid, "") AS orcid,
                coalesce(t.google_scholar, "") AS google_scholar,
                coalesce(t.scopus, "") AS scopus,
                coalesce(t.web_of_science, "") AS web_of_science,
                coalesce(t.profile_url, "") AS profile_url,
                publications,
                coalesce(t.last_publication_sync_at, "") AS last_publication_sync_at,
                profile_score
            ORDER BY profile_score DESC, publications ASC, last_publication_sync_at ASC, full_name
            LIMIT $limit
            """,
            {"limit": int(limit), "stale_before": stale_before.strip()},
        )

    def get_teacher_import_options(self, department_code: str = "", limit: int = 200) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (t:Teacher)
            OPTIONAL MATCH (d:Department)-[:HAS_TEACHER]->(t)
            OPTIONAL MATCH (f:Faculty)-[:HAS_DEPARTMENT]->(d)
            OPTIONAL MATCH (t)-[:AUTHORED]->(p:Publication)
            WITH
                t,
                d,
                f,
                count(DISTINCT p) AS publications,
                CASE WHEN coalesce(t.orcid, "") <> "" THEN 1 ELSE 0 END +
                CASE WHEN coalesce(t.google_scholar, "") <> "" THEN 1 ELSE 0 END +
                CASE WHEN coalesce(t.scopus, "") <> "" THEN 1 ELSE 0 END +
                CASE WHEN coalesce(t.web_of_science, "") <> "" THEN 1 ELSE 0 END AS profile_score
            WHERE ($department_code = "" OR coalesce(d.code, d.department_id) = $department_code)
            RETURN
                coalesce(t.id, t.teacher_id) AS id,
                coalesce(t.full_name, t.name) AS full_name,
                coalesce(d.code, d.department_id, t.department_code, t.department_id) AS department_code,
                coalesce(d.name, t.department_name, "") AS department_name,
                coalesce(f.name, "") AS faculty_name,
                coalesce(t.orcid, "") AS orcid,
                coalesce(t.google_scholar, "") AS google_scholar,
                coalesce(t.scopus, "") AS scopus,
                coalesce(t.web_of_science, "") AS web_of_science,
                coalesce(t.profile_url, "") AS profile_url,
                publications,
                profile_score
            ORDER BY profile_score DESC, full_name
            LIMIT $limit
            """,
            {"department_code": department_code.strip(), "limit": int(limit)},
        )

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
                coalesce(t.last_publication_sync_at, "") AS last_publication_sync_at,
                coalesce(t.last_publication_sync_trigger, "") AS last_publication_sync_trigger,
                coalesce(t.last_publication_sync_status, "") AS last_publication_sync_status,
                coalesce(d.code, d.department_id, t.department_code, t.department_id) AS department_code,
                coalesce(d.name, t.department_name, "") AS department_name,
                coalesce(f.code, f.faculty_id, t.faculty_code, t.faculty_id) AS faculty_code,
                coalesce(f.name, "") AS faculty_name
            LIMIT 1
            """,
            {"teacher_id": teacher_id},
        )
        return rows[0] if rows else None

    def get_teacher_publications(self, teacher_id: str) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (t:Teacher)-[:AUTHORED]->(p:Publication)
            WHERE coalesce(t.id, t.teacher_id) = $teacher_id
            OPTIONAL MATCH (co:Teacher)-[:AUTHORED]->(p)
            WITH p, collect(DISTINCT coalesce(co.full_name, co.name)) AS linked_authors
            WITH
                p,
                linked_authors,
                [source IN split(coalesce(p.source, ""), ";") | trim(source)] AS source_names
            RETURN
                coalesce(p.id, p.publication_id) AS id,
                p.title AS title,
                p.year AS year,
                coalesce(p.doi, "") AS doi,
                coalesce(p.pub_type, "") AS pub_type,
                coalesce(p.source, "") AS source,
                coalesce(p.confidence, 0.0) AS confidence,
                CASE
                    WHEN any(source_name IN source_names WHERE source_name IN ["Scopus", "Web of Science"]) THEN "Офіційно підтверджено"
                    WHEN coalesce(p.confidence, 0.0) >= 0.9 THEN "Підтверджено"
                    WHEN coalesce(p.confidence, 0.0) >= 0.72 THEN "Кандидат"
                    ELSE "Потребує перевірки"
                END AS status,
                CASE
                    WHEN size(linked_authors) > 0 THEN linked_authors
                    ELSE coalesce(p.authors_snapshot, [])
                END AS authors
            ORDER BY coalesce(p.year, 0) DESC, title
            """,
            {"teacher_id": teacher_id},
        )

    def get_teacher_coauthors(self, teacher_id: str) -> list[dict[str, Any]]:
        return self.run_query(
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
        return self.run_query(
            """
            MATCH (p:Publication)
            WHERE ($year IS NULL OR p.year = $year)
            OPTIONAL MATCH (t:Teacher)-[:AUTHORED]->(p)
            WITH p, collect(DISTINCT coalesce(t.full_name, t.name)) AS linked_authors
            WITH
                p,
                linked_authors,
                [source IN split(coalesce(p.source, ""), ";") | trim(source)] AS source_names
            RETURN
                coalesce(p.id, p.publication_id) AS id,
                p.title AS title,
                p.year AS year,
                coalesce(p.doi, "") AS doi,
                coalesce(p.pub_type, "") AS pub_type,
                coalesce(p.source, "") AS source,
                coalesce(p.confidence, 0.0) AS confidence,
                CASE
                    WHEN any(source_name IN source_names WHERE source_name IN ["Scopus", "Web of Science"]) THEN "Офіційно підтверджено"
                    WHEN coalesce(p.confidence, 0.0) >= 0.9 THEN "Підтверджено"
                    WHEN coalesce(p.confidence, 0.0) >= 0.72 THEN "Кандидат"
                    ELSE "Потребує перевірки"
                END AS status,
                CASE
                    WHEN size(linked_authors) > 0 THEN linked_authors
                    ELSE coalesce(p.authors_snapshot, [])
                END AS authors,
                CASE
                    WHEN size(linked_authors) > 0 THEN size(linked_authors)
                    ELSE size(coalesce(p.authors_snapshot, []))
                END AS authors_count
            ORDER BY coalesce(p.year, 0) DESC, title
            """,
            {"year": year},
        )

    def get_graph_edges(self, department_code: str = "", limit: int = 160) -> list[dict[str, Any]]:
        return self.run_query(
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

    def get_top_teachers_by_publications(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.run_query(
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

    def get_top_coauthor_pairs(self, limit: int = 10) -> list[dict[str, Any]]:
        return self.run_query(
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

    def get_coauthor_edges(self) -> list[dict[str, Any]]:
        return self.run_query(
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
