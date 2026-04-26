from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from neo4j import GraphDatabase


SCHEMA_STATEMENTS = [
    "CREATE CONSTRAINT faculty_code_unique IF NOT EXISTS FOR (f:Faculty) REQUIRE f.code IS UNIQUE",
    "CREATE CONSTRAINT department_code_unique IF NOT EXISTS FOR (d:Department) REQUIRE d.code IS UNIQUE",
    "CREATE CONSTRAINT teacher_id_unique IF NOT EXISTS FOR (t:Teacher) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT publication_id_unique IF NOT EXISTS FOR (p:Publication) REQUIRE p.id IS UNIQUE",
    "CREATE CONSTRAINT system_state_key_unique IF NOT EXISTS FOR (s:SystemState) REQUIRE s.key IS UNIQUE",
    "CREATE CONSTRAINT audit_event_id_unique IF NOT EXISTS FOR (a:AuditEvent) REQUIRE a.id IS UNIQUE",
    "CREATE RANGE INDEX faculty_name_idx IF NOT EXISTS FOR (f:Faculty) ON (f.name)",
    "CREATE RANGE INDEX department_name_idx IF NOT EXISTS FOR (d:Department) ON (d.name)",
    "CREATE RANGE INDEX teacher_full_name_idx IF NOT EXISTS FOR (t:Teacher) ON (t.full_name)",
    "CREATE RANGE INDEX publication_year_idx IF NOT EXISTS FOR (p:Publication) ON (p.year)",
    "CREATE RANGE INDEX audit_event_created_at_idx IF NOT EXISTS FOR (a:AuditEvent) ON (a.created_at)",
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

    @staticmethod
    def _now_utc() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _unique_strings(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = str(value or "").strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                result.append(cleaned)
        return result

    @staticmethod
    def _normalize_publication_key(title: str, year: int | None = None) -> str:
        normalized = "".join(char.lower() if char.isalnum() else " " for char in str(title or ""))
        compact = " ".join(normalized.split())
        return f"{compact}|{year or ''}"

    def log_audit_event(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: str,
        summary: str,
        details: str = "",
        actor: str = "streamlit_ui",
    ) -> None:
        self.execute(
            """
            CREATE (a:AuditEvent {
                id: $id,
                created_at: $created_at,
                action: $action,
                entity_type: $entity_type,
                entity_id: $entity_id,
                summary: $summary,
                details: $details,
                actor: $actor
            })
            """,
            {
                "id": f"audit:{uuid4().hex}",
                "created_at": self._now_utc(),
                "action": action.strip(),
                "entity_type": entity_type.strip(),
                "entity_id": entity_id.strip(),
                "summary": summary.strip(),
                "details": details.strip(),
                "actor": actor.strip(),
            },
        )

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
                coalesce(p.doi, "") AS doi,
                coalesce(p.pub_type, "") AS pub_type,
                coalesce(p.source, "") AS source,
                coalesce(p.confidence, 0.0) AS confidence,
                coalesce(p.review_status, "") AS review_status,
                coalesce(p.review_note, "") AS review_note,
                coalesce(p.authors_snapshot, []) AS authors_snapshot,
                count(DISTINCT t) AS linked_teachers_count,
                collect(DISTINCT coalesce(t.full_name, t.name)) AS linked_teachers,
                collect(DISTINCT coalesce(t.id, t.teacher_id)) AS linked_teacher_ids
            LIMIT 1
            """,
            {"publication_id": publication_id},
        )
        return rows[0] if rows else None

    def create_teacher_publication_link(
        self,
        teacher_id: str,
        publication_id: str,
        *,
        source: str = "Ручне прив'язування",
        confidence: float = 1.0,
        matched_by: str = "manual_link",
    ) -> bool:
        rows = self.run_query(
            """
            MATCH (t:Teacher)
            WHERE coalesce(t.id, t.teacher_id) = $teacher_id
            MATCH (p:Publication)
            WHERE coalesce(p.id, p.publication_id) = $publication_id
            MERGE (t)-[r:AUTHORED]->(p)
            SET
                r.source = $source,
                r.confidence = $confidence,
                r.matched_by = $matched_by,
                p.authors_snapshot = CASE
                    WHEN coalesce(t.full_name, t.name) IN coalesce(p.authors_snapshot, [])
                    THEN coalesce(p.authors_snapshot, [])
                    ELSE coalesce(p.authors_snapshot, []) + coalesce(t.full_name, t.name)
                END
            RETURN true AS created
            LIMIT 1
            """,
            {
                "teacher_id": teacher_id,
                "publication_id": publication_id,
                "source": source.strip() or "Ручне прив'язування",
                "confidence": max(0.0, min(float(confidence), 1.0)),
                "matched_by": matched_by.strip() or "manual_link",
            },
        )
        if rows:
            self.log_audit_event(
                action="publication.link.create",
                entity_type="Authorship",
                entity_id=f"{teacher_id}|{publication_id}",
                summary="Створено ручний зв'язок викладача з публікацією.",
                details=f"Teacher: {teacher_id} | Publication: {publication_id}",
            )
        return bool(rows)

    def update_publication_metadata(
        self,
        publication_id: str,
        *,
        title: str,
        year: int | None,
        doi: str,
        pub_type: str,
        source: str,
        confidence: float,
        review_note: str = "",
    ) -> bool:
        rows = self.run_query(
            """
            MATCH (p:Publication)
            WHERE coalesce(p.id, p.publication_id) = $publication_id
            SET
                p.title = $title,
                p.year = $year,
                p.doi = $doi,
                p.pub_type = $pub_type,
                p.source = $source,
                p.confidence = $confidence,
                p.review_note = $review_note
            RETURN true AS updated
            LIMIT 1
            """,
            {
                "publication_id": publication_id,
                "title": title.strip(),
                "year": year,
                "doi": doi.strip(),
                "pub_type": pub_type.strip(),
                "source": source.strip(),
                "confidence": max(0.0, min(float(confidence), 1.0)),
                "review_note": review_note.strip(),
            },
        )
        if rows:
            self.log_audit_event(
                action="publication.update",
                entity_type="Publication",
                entity_id=publication_id,
                summary=f"Оновлено метадані публікації '{title.strip()}'.",
                details=f"Рік: {year or 'н/д'} | DOI: {doi.strip() or 'немає'} | Джерело: {source.strip() or 'невідомо'}",
            )
        return bool(rows)

    def set_publication_review_status(self, publication_id: str, review_status: str, review_note: str = "") -> bool:
        rows = self.run_query(
            """
            MATCH (p:Publication)
            WHERE coalesce(p.id, p.publication_id) = $publication_id
            SET
                p.review_status = $review_status,
                p.review_note = CASE
                    WHEN $review_note = "" THEN coalesce(p.review_note, "")
                    ELSE $review_note
                END
            RETURN true AS updated
            LIMIT 1
            """,
            {
                "publication_id": publication_id,
                "review_status": review_status.strip(),
                "review_note": review_note.strip(),
            },
        )
        if rows:
            self.log_audit_event(
                action="publication.review_status.set",
                entity_type="Publication",
                entity_id=publication_id,
                summary=f"Для публікації встановлено статус '{review_status.strip()}'.",
                details=review_note.strip(),
            )
        return bool(rows)

    def clear_publication_review_status(self, publication_id: str) -> bool:
        rows = self.run_query(
            """
            MATCH (p:Publication)
            WHERE coalesce(p.id, p.publication_id) = $publication_id
            REMOVE p.review_status
            RETURN true AS updated
            LIMIT 1
            """,
            {"publication_id": publication_id},
        )
        if rows:
            self.log_audit_event(
                action="publication.review_status.clear",
                entity_type="Publication",
                entity_id=publication_id,
                summary="Ручний статус публікації скинуто.",
            )
        return bool(rows)

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
        if rows:
            self.log_audit_event(
                action="publication.link.delete",
                entity_type="Authorship",
                entity_id=f"{teacher_id}|{publication_id}",
                summary="Видалено зв'язок викладача з публікацією.",
                details=f"Teacher: {teacher_id} | Publication: {publication_id}",
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
        if rows:
            self.log_audit_event(
                action="publication.delete",
                entity_type="Publication",
                entity_id=publication_id,
                summary="Публікацію повністю видалено з бази.",
            )
        return bool(rows)

    def create_manual_publication(
        self,
        *,
        title: str,
        year: int | None,
        doi: str,
        pub_type: str,
        source: str,
        teacher_ids: list[str],
        authors_snapshot: list[str] | None = None,
        confidence: float = 1.0,
        review_status: str = "Підтверджено",
        review_note: str = "",
        url: str = "",
    ) -> dict[str, Any]:
        cleaned_title = title.strip()
        cleaned_doi = doi.strip().lower()
        cleaned_teacher_ids = self._unique_strings(teacher_ids)
        cleaned_authors = self._unique_strings(list(authors_snapshot or []))
        if not cleaned_title or not cleaned_teacher_ids:
            return {"created": False, "publication_id": "", "matched_existing": False}

        existing_rows = self.run_query(
            """
            MATCH (p:Publication)
            WHERE (
                $doi <> "" AND toLower(coalesce(p.doi, "")) = $doi
            ) OR (
                $doi = ""
                AND coalesce(p.canonical_key, "") = $canonical_key
            )
            RETURN coalesce(p.id, p.publication_id) AS id
            LIMIT 1
            """,
            {
                "doi": cleaned_doi,
                "canonical_key": self._normalize_publication_key(cleaned_title, year),
            },
        )
        publication_id = (
            str(existing_rows[0]["id"]).strip()
            if existing_rows and existing_rows[0].get("id")
            else f"manual:{uuid4().hex}"
        )
        matched_existing = bool(existing_rows)

        teacher_rows = self.run_query(
            """
            MATCH (t:Teacher)
            WHERE coalesce(t.id, t.teacher_id) IN $teacher_ids
            RETURN coalesce(t.full_name, t.name) AS full_name
            ORDER BY full_name
            """,
            {"teacher_ids": cleaned_teacher_ids},
        )
        teacher_names = [str(row.get("full_name") or "").strip() for row in teacher_rows]
        final_authors = self._unique_strings(teacher_names + cleaned_authors)
        final_source = source.strip() or "Ручне додавання"
        final_confidence = max(0.0, min(float(confidence), 1.0))
        canonical_key = cleaned_doi or self._normalize_publication_key(cleaned_title, year)

        self.seed_publications(
            [
                {
                    "id": publication_id,
                    "title": cleaned_title,
                    "year": year,
                    "doi": cleaned_doi,
                    "pub_type": pub_type.strip(),
                    "source": final_source,
                    "url": url.strip(),
                    "canonical_key": canonical_key,
                    "external_ids": [cleaned_doi] if cleaned_doi else [],
                    "authors_snapshot": final_authors,
                    "confidence": final_confidence,
                    "matched_by": "manual_entry",
                }
            ],
            [
                {
                    "teacher_id": teacher_id,
                    "publication_id": publication_id,
                    "source": final_source,
                    "confidence": final_confidence,
                    "matched_by": "manual_entry",
                }
                for teacher_id in cleaned_teacher_ids
            ],
        )
        self.set_publication_review_status(publication_id, review_status, review_note=review_note)
        self.log_audit_event(
            action="publication.manual_create",
            entity_type="Publication",
            entity_id=publication_id,
            summary=(
                f"Публікацію {'повторно використано' if matched_existing else 'додано вручну'}: "
                f"'{cleaned_title}'."
            ),
            details=(
                f"Викладачів: {len(cleaned_teacher_ids)} | DOI: {cleaned_doi or 'немає'} | "
                f"Джерело: {final_source}"
            ),
        )
        return {
            "created": True,
            "publication_id": publication_id,
            "matched_existing": matched_existing,
            "teacher_links": len(cleaned_teacher_ids),
        }

    def get_audit_events(self, limit: int = 80) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (a:AuditEvent)
            RETURN
                a.created_at AS created_at,
                a.action AS action,
                a.entity_type AS entity_type,
                a.entity_id AS entity_id,
                a.summary AS summary,
                coalesce(a.details, "") AS details,
                coalesce(a.actor, "") AS actor
            ORDER BY a.created_at DESC
            LIMIT $limit
            """,
            {"limit": int(limit)},
        )

    def bulk_set_publication_review_status(
        self,
        publication_ids: list[str],
        review_status: str,
        review_note: str = "",
    ) -> int:
        updated = 0
        for publication_id in self._unique_strings(publication_ids):
            if self.set_publication_review_status(publication_id, review_status, review_note=review_note):
                updated += 1
        if updated:
            self.log_audit_event(
                action="publication.bulk_review_status",
                entity_type="Publication",
                entity_id="bulk",
                summary=f"Масово оновлено статус для {updated} публікацій.",
                details=f"Новий статус: {review_status}",
            )
        return updated

    def bulk_delete_publications(self, publication_ids: list[str]) -> int:
        deleted = 0
        for publication_id in self._unique_strings(publication_ids):
            if self.delete_publication(publication_id):
                deleted += 1
        if deleted:
            self.log_audit_event(
                action="publication.bulk_delete",
                entity_type="Publication",
                entity_id="bulk",
                summary=f"Масово видалено {deleted} публікацій.",
            )
        return deleted

    def merge_publications(self, canonical_publication_id: str, duplicate_publication_id: str) -> bool:
        if not canonical_publication_id or not duplicate_publication_id:
            return False
        if canonical_publication_id.strip() == duplicate_publication_id.strip():
            return False

        rows = self.run_query(
            """
            MATCH (canonical:Publication)
            WHERE coalesce(canonical.id, canonical.publication_id) = $canonical_id
            MATCH (duplicate:Publication)
            WHERE coalesce(duplicate.id, duplicate.publication_id) = $duplicate_id
            OPTIONAL MATCH (t:Teacher)-[r:AUTHORED]->(duplicate)
            WITH canonical, duplicate, collect({
                teacher: t,
                source: coalesce(r.source, ""),
                confidence: coalesce(r.confidence, 0.0),
                matched_by: coalesce(r.matched_by, "")
            }) AS links
            FOREACH (link IN links |
                FOREACH (_ IN CASE WHEN link.teacher IS NULL THEN [] ELSE [1] END |
                    MERGE (link.teacher)-[new_r:AUTHORED]->(canonical)
                    SET
                        new_r.source = CASE
                            WHEN coalesce(new_r.source, "") = "" THEN link.source
                            WHEN link.source = "" OR new_r.source CONTAINS link.source THEN new_r.source
                            ELSE new_r.source + "; " + link.source
                        END,
                        new_r.confidence = CASE
                            WHEN coalesce(link.confidence, 0.0) > coalesce(new_r.confidence, 0.0)
                            THEN link.confidence
                            ELSE coalesce(new_r.confidence, 0.0)
                        END,
                        new_r.matched_by = CASE
                            WHEN coalesce(new_r.matched_by, "") <> "" THEN new_r.matched_by
                            ELSE link.matched_by
                        END
                )
            )
            SET
                canonical.title = CASE WHEN coalesce(canonical.title, "") <> "" THEN canonical.title ELSE duplicate.title END,
                canonical.year = CASE WHEN canonical.year IS NOT NULL THEN canonical.year ELSE duplicate.year END,
                canonical.doi = CASE WHEN coalesce(canonical.doi, "") <> "" THEN canonical.doi ELSE coalesce(duplicate.doi, "") END,
                canonical.pub_type = CASE WHEN coalesce(canonical.pub_type, "") <> "" THEN canonical.pub_type ELSE coalesce(duplicate.pub_type, "") END,
                canonical.url = CASE WHEN coalesce(canonical.url, "") <> "" THEN canonical.url ELSE coalesce(duplicate.url, "") END,
                canonical.canonical_key = CASE WHEN coalesce(canonical.canonical_key, "") <> "" THEN canonical.canonical_key ELSE coalesce(duplicate.canonical_key, "") END,
                canonical.confidence = CASE
                    WHEN coalesce(duplicate.confidence, 0.0) > coalesce(canonical.confidence, 0.0)
                    THEN duplicate.confidence
                    ELSE coalesce(canonical.confidence, 0.0)
                END,
                canonical.review_status = CASE
                    WHEN coalesce(canonical.review_status, "") <> "" THEN canonical.review_status
                    ELSE coalesce(duplicate.review_status, "")
                END,
                canonical.review_note = CASE
                    WHEN coalesce(canonical.review_note, "") <> "" THEN canonical.review_note
                    ELSE coalesce(duplicate.review_note, "")
                END,
                canonical.source = CASE
                    WHEN coalesce(canonical.source, "") = "" THEN coalesce(duplicate.source, "")
                    WHEN coalesce(duplicate.source, "") = "" OR canonical.source CONTAINS duplicate.source THEN canonical.source
                    ELSE canonical.source + "; " + duplicate.source
                END,
                canonical.external_ids = reduce(
                    acc = coalesce(canonical.external_ids, []),
                    item IN coalesce(duplicate.external_ids, []) |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END
                ),
                canonical.authors_snapshot = reduce(
                    acc = coalesce(canonical.authors_snapshot, []),
                    item IN coalesce(duplicate.authors_snapshot, []) |
                    CASE WHEN item IN acc THEN acc ELSE acc + item END
                )
            DETACH DELETE duplicate
            RETURN true AS merged
            LIMIT 1
            """,
            {
                "canonical_id": canonical_publication_id.strip(),
                "duplicate_id": duplicate_publication_id.strip(),
            },
        )
        if rows:
            self.log_audit_event(
                action="publication.merge",
                entity_type="Publication",
                entity_id=canonical_publication_id.strip(),
                summary="Виконано злиття дубльованих публікацій.",
                details=f"Canonical: {canonical_publication_id.strip()} | Duplicate: {duplicate_publication_id.strip()}",
            )
        return bool(rows)

    def delete_all_publications(self) -> int:
        rows = self.run_query("MATCH (p:Publication) RETURN count(p) AS total")
        total = int(rows[0]["total"] or 0) if rows else 0
        if total:
            self.execute("MATCH (p:Publication) DETACH DELETE p")
            self.log_audit_event(
                action="publication.delete_all",
                entity_type="Publication",
                entity_id="all",
                summary=f"Повністю очищено всі публікації з бази ({total}).",
            )
        return total

    def delete_all_teachers_and_publications(self) -> dict[str, int]:
        teacher_rows = self.run_query("MATCH (t:Teacher) RETURN count(t) AS total")
        publication_rows = self.run_query("MATCH (p:Publication) RETURN count(p) AS total")
        teacher_total = int(teacher_rows[0]["total"] or 0) if teacher_rows else 0
        publication_total = int(publication_rows[0]["total"] or 0) if publication_rows else 0

        if teacher_total:
            self.execute("MATCH (t:Teacher) DETACH DELETE t")
        if publication_total:
            self.execute("MATCH (p:Publication) DETACH DELETE p")

        if teacher_total or publication_total:
            self.log_audit_event(
                action="teacher.delete_all",
                entity_type="Teacher",
                entity_id="all",
                summary="Очищено всіх викладачів і пов'язані публікації.",
                details=f"Teachers: {teacher_total} | Publications: {publication_total}",
            )
        return {"teachers": teacher_total, "publications": publication_total}

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
                    WHEN coalesce(p.review_status, "") <> "" THEN p.review_status
                    WHEN any(source_name IN source_names WHERE source_name IN ["Scopus", "Web of Science"]) THEN "Офіційно підтверджено"
                    WHEN coalesce(p.confidence, 0.0) >= 0.9 THEN "Підтверджено"
                    WHEN coalesce(p.confidence, 0.0) >= 0.72 THEN "Кандидат"
                    ELSE "Потребує перевірки"
                END AS status,
                coalesce(p.review_note, "") AS review_note,
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
                    WHEN coalesce(p.review_status, "") <> "" THEN p.review_status
                    WHEN any(source_name IN source_names WHERE source_name IN ["Scopus", "Web of Science"]) THEN "Офіційно підтверджено"
                    WHEN coalesce(p.confidence, 0.0) >= 0.9 THEN "Підтверджено"
                    WHEN coalesce(p.confidence, 0.0) >= 0.72 THEN "Кандидат"
                    ELSE "Потребує перевірки"
                END AS status,
                coalesce(p.review_note, "") AS review_note,
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

    def get_teacher_coauthor_graph(self, department_code: str = "", limit: int = 120) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (d1:Department)-[:HAS_TEACHER]->(a:Teacher)-[:AUTHORED]->(p:Publication)<-[:AUTHORED]-(b:Teacher)<-[:HAS_TEACHER]-(d2:Department)
            WHERE coalesce(a.id, a.teacher_id) < coalesce(b.id, b.teacher_id)
              AND ($department_code = "" OR coalesce(d1.code, d1.department_id) = $department_code OR coalesce(d2.code, d2.department_id) = $department_code)
            WITH a, b, d1, d2, count(DISTINCT p) AS weight, collect(DISTINCT p.title)[0..4] AS sample_titles
            RETURN
                coalesce(a.id, a.teacher_id) AS source_id,
                coalesce(a.full_name, a.name) AS source_name,
                d1.name AS source_department,
                coalesce(b.id, b.teacher_id) AS target_id,
                coalesce(b.full_name, b.name) AS target_name,
                d2.name AS target_department,
                weight,
                sample_titles
            ORDER BY weight DESC, source_name, target_name
            LIMIT $limit
            """,
            {"department_code": department_code.strip(), "limit": int(limit)},
        )

    def get_department_collaboration_edges(self, faculty_code: str = "", limit: int = 80) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (f1:Faculty)-[:HAS_DEPARTMENT]->(d1:Department)-[:HAS_TEACHER]->(a:Teacher)-[:AUTHORED]->(p:Publication)<-[:AUTHORED]-(b:Teacher)<-[:HAS_TEACHER]-(d2:Department)<-[:HAS_DEPARTMENT]-(f2:Faculty)
            WHERE coalesce(d1.code, d1.department_id) < coalesce(d2.code, d2.department_id)
              AND ($faculty_code = "" OR coalesce(f1.code, f1.faculty_id) = $faculty_code OR coalesce(f2.code, f2.faculty_id) = $faculty_code)
            WITH d1, d2, f1, f2, count(DISTINCT p) AS weight, collect(DISTINCT p.title)[0..5] AS sample_titles
            RETURN
                coalesce(d1.code, d1.department_id) AS source_id,
                d1.name AS source_name,
                f1.name AS source_faculty,
                coalesce(d2.code, d2.department_id) AS target_id,
                d2.name AS target_name,
                f2.name AS target_faculty,
                weight,
                sample_titles
            ORDER BY weight DESC, source_name, target_name
            LIMIT $limit
            """,
            {"faculty_code": faculty_code.strip(), "limit": int(limit)},
        )

    def get_duplicate_publication_candidates(self, limit: int = 120) -> list[dict[str, Any]]:
        return self.run_query(
            """
            MATCH (p:Publication)
            WITH
                p,
                toLower(trim(coalesce(p.doi, ""))) AS doi_key,
                toLower(trim(coalesce(p.title, ""))) AS title_key
            WITH doi_key, title_key, collect(p) AS publications
            WHERE
                (doi_key <> "" AND size(publications) > 1)
                OR (doi_key = "" AND title_key <> "" AND size(publications) > 1)
            UNWIND publications AS p
            OPTIONAL MATCH (t:Teacher)-[:AUTHORED]->(p)
            WITH doi_key, title_key, p, collect(DISTINCT coalesce(t.full_name, t.name)) AS authors
            RETURN
                CASE WHEN doi_key <> "" THEN doi_key ELSE title_key END AS duplicate_key,
                coalesce(p.id, p.publication_id) AS id,
                p.title AS title,
                p.year AS year,
                coalesce(p.doi, "") AS doi,
                coalesce(p.source, "") AS source,
                coalesce(p.review_status, "") AS review_status,
                authors,
                size(authors) AS authors_count
            ORDER BY duplicate_key, year DESC, title
            LIMIT $limit
            """
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
