"""SQLite Local Storage Repository for Crawl State and File Metadata."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from app.core.config import get_settings
from app.core.logging import get_logger
from app.indexer.embeddings import cosine_similarity
from app.indexer.models import (
    AgentMessage,
    AgentThread,
    DocumentChunk,
    DocumentDiff,
    DocumentVersion,
    DriveFileMetadata,
    DriveLabel,
    DrivePermission,
)

logger = get_logger("panopticon.indexer.storage")


class CrawlStorage:
    """Encapsulated SQLite repository providing ACID durability for crawl metadata and watermarks."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Initialize CrawlStorage with database path.

        Args:
            db_path: Path to SQLite database file. If None, uses CRAWL_DB_PATH from settings.
        """
        if db_path is not None:
            self.db_path = Path(db_path).resolve()
        else:
            self.db_path = get_settings().crawl_database_path

        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        """Create and configure a connection with WAL mode and Row factory."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def init_db(self) -> None:
        """Create tables and indices if they do not exist."""
        with self.get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sync_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS file_records (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    modified_time TEXT,
                    created_time TEXT,
                    owners_json TEXT,
                    last_modifying_user TEXT,
                    shared INTEGER NOT NULL DEFAULT 0,
                    web_view_link TEXT,
                    icon_link TEXT,
                    size_bytes INTEGER,
                    trashed INTEGER NOT NULL DEFAULT 0,
                    parents_json TEXT,
                    drive_id TEXT,
                    sharing_status TEXT NOT NULL DEFAULT 'private',
                    permissions_json TEXT,
                    labels_json TEXT,
                    project_tags_json TEXT,
                    content_snippet TEXT,
                    export_status TEXT,
                    last_seen_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS document_versions (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    content_hash TEXT NOT NULL,
                    snapshot_text TEXT NOT NULL,
                    modified_time TEXT,
                    editor TEXT,
                    char_count INTEGER NOT NULL DEFAULT 0,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES file_records(id) ON DELETE CASCADE,
                    UNIQUE(file_id, version_number)
                );

                CREATE TABLE IF NOT EXISTS document_diffs (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    from_version_id TEXT,
                    to_version_id TEXT NOT NULL,
                    patch_text TEXT NOT NULL,
                    ai_summary TEXT,
                    lines_added INTEGER NOT NULL DEFAULT 0,
                    lines_removed INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES file_records(id) ON DELETE CASCADE,
                    FOREIGN KEY (from_version_id) REFERENCES document_versions(id) ON DELETE SET NULL,
                    FOREIGN KEY (to_version_id) REFERENCES document_versions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS document_chunks (
                    id TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    version_id TEXT,
                    chunk_index INTEGER NOT NULL,
                    section_heading TEXT,
                    content_text TEXT NOT NULL,
                    char_start INTEGER NOT NULL DEFAULT 0,
                    char_end INTEGER NOT NULL DEFAULT 0,
                    word_count INTEGER NOT NULL DEFAULT 0,
                    embedding_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (file_id) REFERENCES file_records(id) ON DELETE CASCADE,
                    FOREIGN KEY (version_id) REFERENCES document_versions(id) ON DELETE CASCADE,
                    UNIQUE(file_id, chunk_index)
                );

                CREATE INDEX IF NOT EXISTS idx_file_modified_time ON file_records(modified_time);
                CREATE INDEX IF NOT EXISTS idx_file_sharing_status ON file_records(sharing_status);
                CREATE INDEX IF NOT EXISTS idx_file_trashed ON file_records(trashed);
                CREATE INDEX IF NOT EXISTS idx_file_last_seen_at ON file_records(last_seen_at);

                CREATE INDEX IF NOT EXISTS idx_versions_file_id ON document_versions(file_id);
                CREATE INDEX IF NOT EXISTS idx_versions_file_version ON document_versions(file_id, version_number DESC);
                CREATE INDEX IF NOT EXISTS idx_versions_content_hash ON document_versions(content_hash);
                CREATE INDEX IF NOT EXISTS idx_diffs_file_id ON document_diffs(file_id);
                CREATE INDEX IF NOT EXISTS idx_diffs_versions ON document_diffs(from_version_id, to_version_id);
                CREATE INDEX IF NOT EXISTS idx_chunks_file_idx ON document_chunks(file_id, chunk_index);
                CREATE INDEX IF NOT EXISTS idx_chunks_version ON document_chunks(version_id);

                CREATE TABLE IF NOT EXISTS agent_threads (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    model TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_messages (
                    id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    trace_json TEXT,
                    citations_json TEXT,
                    model TEXT,
                    latency_ms REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (thread_id) REFERENCES agent_threads(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_threads_updated_at ON agent_threads(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_messages_thread_id ON agent_messages(thread_id, created_at ASC);
                """
            )
        logger.debug("Initialized SQLite storage schema at %s", self.db_path)

    def get_watermark(self, key: str = "last_crawl_time") -> datetime | None:
        """Retrieve stored watermark timestamp as UTC datetime.

        Args:
            key: Watermark identifier key.

        Returns:
            datetime | None: Stored UTC datetime or None if not set.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT value FROM sync_state WHERE key = ?", (key,)
            )
            row = cursor.fetchone()
            if row and row["value"]:
                try:
                    iso_str = row["value"]
                    return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning("Corrupt watermark format: %s", row["value"])
                    return None
        return None

    def set_watermark(
        self,
        watermark: datetime,
        key: str = "last_crawl_time",
    ) -> None:
        """Store or update watermark timestamp.

        Args:
            watermark: UTC datetime object.
            key: Watermark identifier key.
        """
        iso_val = watermark.astimezone(timezone.utc).isoformat()
        now_str = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sync_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, iso_val, now_str),
            )
        logger.debug("Updated sync watermark '%s' to %s", key, iso_val)

    def _model_to_row_tuple(
        self, file: DriveFileMetadata, last_seen_iso: str
    ) -> tuple[Any, ...]:
        """Serialize DriveFileMetadata to a database row tuple."""
        mod_time = (
            file.modified_time.astimezone(timezone.utc).isoformat()
            if file.modified_time
            else None
        )
        create_time = (
            file.created_time.astimezone(timezone.utc).isoformat()
            if file.created_time
            else None
        )
        owners_json = json.dumps(file.owners)
        parents_json = json.dumps(file.parents)
        permissions_json = json.dumps([p.model_dump() for p in file.permissions])
        labels_json = json.dumps([lbl.model_dump() for lbl in file.labels])
        project_tags_json = json.dumps(file.project_tags)

        return (
            file.id,
            file.name,
            file.mime_type,
            mod_time,
            create_time,
            owners_json,
            file.last_modifying_user,
            1 if file.shared else 0,
            file.web_view_link,
            file.icon_link,
            file.size_bytes,
            1 if file.trashed else 0,
            parents_json,
            file.drive_id,
            file.sharing_status,
            permissions_json,
            labels_json,
            project_tags_json,
            file.content_snippet,
            file.export_status,
            last_seen_iso,
        )

    def _row_to_model(self, row: sqlite3.Row) -> DriveFileMetadata:
        """Deserialize an SQLite Row into a validated DriveFileMetadata domain entity."""
        mod_time = (
            datetime.fromisoformat(row["modified_time"].replace("Z", "+00:00"))
            if row["modified_time"]
            else None
        )
        create_time = (
            datetime.fromisoformat(row["created_time"].replace("Z", "+00:00"))
            if row["created_time"]
            else None
        )
        owners: list[str] = json.loads(row["owners_json"]) if row["owners_json"] else []
        parents: list[str] = json.loads(row["parents_json"]) if row["parents_json"] else []
        project_tags: list[str] = (
            json.loads(row["project_tags_json"]) if row["project_tags_json"] else []
        )

        raw_perms = json.loads(row["permissions_json"]) if row["permissions_json"] else []
        permissions = [DrivePermission(**p) for p in raw_perms]

        raw_labels = json.loads(row["labels_json"]) if row["labels_json"] else []
        labels = [DriveLabel(**lbl) for lbl in raw_labels]

        return DriveFileMetadata(
            id=row["id"],
            name=row["name"],
            mime_type=row["mime_type"],
            modified_time=mod_time,
            created_time=create_time,
            owners=owners,
            last_modifying_user=row["last_modifying_user"],
            shared=bool(row["shared"]),
            web_view_link=row["web_view_link"],
            icon_link=row["icon_link"],
            size_bytes=row["size_bytes"],
            trashed=bool(row["trashed"]),
            parents=parents,
            drive_id=row["drive_id"],
            sharing_status=row["sharing_status"],
            permissions=permissions,
            labels=labels,
            project_tags=project_tags,
            content_snippet=row["content_snippet"],
            export_status=row["export_status"],
        )

    def upsert_file(
        self,
        file: DriveFileMetadata,
        last_seen_at: datetime | None = None,
    ) -> None:
        """Insert or update a single file record atomically."""
        self.upsert_files([file], last_seen_at=last_seen_at)

    def upsert_files(
        self,
        files: list[DriveFileMetadata],
        last_seen_at: datetime | None = None,
    ) -> int:
        """Insert or update multiple file records in a single ACID transaction.

        Args:
            files: List of DriveFileMetadata objects to store.
            last_seen_at: Optional timestamp to tag active presence (defaults to UTC now).

        Returns:
            int: Number of records upserted.
        """
        if not files:
            return 0

        last_seen_iso = (
            last_seen_at or datetime.now(timezone.utc)
        ).astimezone(timezone.utc).isoformat()

        row_tuples = [
            self._model_to_row_tuple(file, last_seen_iso) for file in files
        ]

        sql = """
        INSERT INTO file_records (
            id, name, mime_type, modified_time, created_time,
            owners_json, last_modifying_user, shared, web_view_link,
            icon_link, size_bytes, trashed, parents_json, drive_id,
            sharing_status, permissions_json, labels_json, project_tags_json,
            content_snippet, export_status, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            mime_type = excluded.mime_type,
            modified_time = excluded.modified_time,
            created_time = excluded.created_time,
            owners_json = excluded.owners_json,
            last_modifying_user = excluded.last_modifying_user,
            shared = excluded.shared,
            web_view_link = excluded.web_view_link,
            icon_link = excluded.icon_link,
            size_bytes = excluded.size_bytes,
            trashed = excluded.trashed,
            parents_json = excluded.parents_json,
            drive_id = excluded.drive_id,
            sharing_status = excluded.sharing_status,
            permissions_json = excluded.permissions_json,
            labels_json = excluded.labels_json,
            project_tags_json = excluded.project_tags_json,
            content_snippet = COALESCE(excluded.content_snippet, file_records.content_snippet),
            export_status = COALESCE(excluded.export_status, file_records.export_status),
            last_seen_at = excluded.last_seen_at;
        """

        with self.get_connection() as conn:
            conn.executemany(sql, row_tuples)

        logger.debug("Upserted %d files into SQLite storage", len(files))
        return len(files)

    def get_file(self, file_id: str) -> DriveFileMetadata | None:
        """Lookup a file record by ID.

        Args:
            file_id: Google Drive unique file ID.

        Returns:
            DriveFileMetadata | None: Found domain entity or None.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM file_records WHERE id = ?", (file_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_model(row)
        return None

    def get_all_file_ids(self) -> set[str]:
        """Return a set of all active file IDs stored in SQLite."""
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT id FROM file_records WHERE trashed = 0")
            return {row["id"] for row in cursor.fetchall()}

    def list_files(
        self, limit: int | None = None, offset: int = 0
    ) -> list[DriveFileMetadata]:
        """List active file records sorted by modified_time descending.

        Args:
            limit: Maximum records to return.
            offset: Record offset for pagination.

        Returns:
            list[DriveFileMetadata]: List of domain entities.
        """
        sql = "SELECT * FROM file_records WHERE trashed = 0 ORDER BY modified_time DESC"
        params: list[Any] = []
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        with self.get_connection() as conn:
            cursor = conn.execute(sql, params)
            return [self._row_to_model(row) for row in cursor.fetchall()]

    def get_all_files(self) -> list[DriveFileMetadata]:
        """Return all active file records currently in SQLite storage."""
        return self.list_files()

    def delete_files(self, file_ids: list[str] | set[str]) -> int:
        """Permanently delete file records by ID list.

        Args:
            file_ids: Collection of file IDs to delete.

        Returns:
            int: Number of rows deleted.
        """
        if not file_ids:
            return 0

        id_list = list(file_ids)
        placeholders = ",".join("?" for _ in id_list)
        sql = f"DELETE FROM file_records WHERE id IN ({placeholders})"

        with self.get_connection() as conn:
            cursor = conn.execute(sql, id_list)
            deleted_count = cursor.rowcount

        logger.info("Deleted %d stale records from SQLite storage", deleted_count)
        return deleted_count

    def count_files(self) -> int:
        """Return total count of active non-trashed files in storage."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) as count FROM file_records WHERE trashed = 0"
            )
            row = cursor.fetchone()
            return int(row["count"]) if row else 0

    def list_documents_paginated(
        self,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "modified_time:desc",
        file_type: str | None = None,
        mime_type: str | None = None,
        sharing_status: str | None = None,
        project_tag: str | None = None,
        primary_owner: str | None = None,
    ) -> tuple[list[DriveFileMetadata], int]:
        """List active file records with parameterized filtering, sorting, and total count.

        Args:
            limit: Number of records to return.
            offset: Record offset for pagination.
            sort_by: Sorting field and direction (e.g. 'modified_time:desc', 'name:asc').
            file_type: Optional category filter ('document', 'spreadsheet', 'other').
            mime_type: Optional exact MIME type filter.
            sharing_status: Optional sharing status filter ('private', 'shared', 'domain', 'anyone').
            project_tag: Optional tag filter (searches within project_tags_json).
            primary_owner: Optional owner email filter.

        Returns:
            tuple[list[DriveFileMetadata], int]: (matching_items_page, total_matching_count).
        """
        where_clauses: list[str] = ["trashed = 0"]
        params: list[Any] = []

        if mime_type:
            where_clauses.append("mime_type = ?")
            params.append(mime_type)
        elif file_type:
            if file_type == "document":
                where_clauses.append("mime_type = 'application/vnd.google-apps.document'")
            elif file_type == "spreadsheet":
                where_clauses.append("mime_type = 'application/vnd.google-apps.spreadsheet'")
            elif file_type == "other":
                where_clauses.append(
                    "mime_type NOT IN ('application/vnd.google-apps.document', 'application/vnd.google-apps.spreadsheet')"
                )

        if sharing_status:
            where_clauses.append("sharing_status = ?")
            params.append(sharing_status)

        if project_tag:
            where_clauses.append("project_tags_json LIKE ?")
            params.append(f'%"{project_tag.strip()}"%')

        if primary_owner:
            where_clauses.append("owners_json LIKE ?")
            params.append(f"%{primary_owner.strip()}%")

        where_sql = " AND ".join(where_clauses)

        # Sort order whitelist mapping
        sort_map = {
            "modified_time:desc": "modified_time DESC NULLS LAST",
            "modified_time:asc": "modified_time ASC NULLS LAST",
            "name:asc": "name COLLATE NOCASE ASC",
            "name:desc": "name COLLATE NOCASE DESC",
            "created_time:desc": "created_time DESC NULLS LAST",
            "created_time:asc": "created_time ASC NULLS LAST",
        }
        order_by_clause = sort_map.get(sort_by, "modified_time DESC NULLS LAST")

        count_sql = f"SELECT COUNT(*) as total FROM file_records WHERE {where_sql}"
        data_sql = f"SELECT * FROM file_records WHERE {where_sql} ORDER BY {order_by_clause} LIMIT ? OFFSET ?"

        with self.get_connection() as conn:
            # 1. Total matching count
            count_cursor = conn.execute(count_sql, params)
            count_row = count_cursor.fetchone()
            total_count = int(count_row["total"]) if count_row else 0

            # 2. Paginated rows
            data_params = list(params) + [limit, offset]
            data_cursor = conn.execute(data_sql, data_params)
            items = [self._row_to_model(row) for row in data_cursor.fetchall()]

        return items, total_count

    def _version_model_to_row(self, v: DocumentVersion) -> tuple[Any, ...]:
        """Serialize DocumentVersion to database row tuple."""
        mod_time = (
            v.modified_time.astimezone(timezone.utc).isoformat()
            if v.modified_time
            else None
        )
        created_iso = v.created_at.astimezone(timezone.utc).isoformat()
        char_count = v.char_count or len(v.snapshot_text)
        word_count = v.word_count or len(v.snapshot_text.split())
        return (
            v.id,
            v.file_id,
            v.version_number,
            v.content_hash,
            v.snapshot_text,
            mod_time,
            v.editor,
            char_count,
            word_count,
            created_iso,
        )

    def _row_to_version_model(self, row: sqlite3.Row) -> DocumentVersion:
        """Deserialize an SQLite Row into a validated DocumentVersion domain entity."""
        mod_time = (
            datetime.fromisoformat(row["modified_time"].replace("Z", "+00:00"))
            if row["modified_time"]
            else None
        )
        created_at = (
            datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            if row["created_at"]
            else datetime.now(timezone.utc)
        )
        return DocumentVersion(
            id=row["id"],
            file_id=row["file_id"],
            version_number=row["version_number"],
            content_hash=row["content_hash"],
            snapshot_text=row["snapshot_text"],
            modified_time=mod_time,
            editor=row["editor"],
            char_count=row["char_count"],
            word_count=row["word_count"],
            created_at=created_at,
        )

    def _diff_model_to_row(self, d: DocumentDiff) -> tuple[Any, ...]:
        """Serialize DocumentDiff to database row tuple."""
        created_iso = d.created_at.astimezone(timezone.utc).isoformat()
        return (
            d.id,
            d.file_id,
            d.from_version_id,
            d.to_version_id,
            d.patch_text,
            d.ai_summary,
            d.lines_added,
            d.lines_removed,
            created_iso,
        )

    def _row_to_diff_model(self, row: sqlite3.Row) -> DocumentDiff:
        """Deserialize an SQLite Row into a validated DocumentDiff domain entity."""
        created_at = (
            datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            if row["created_at"]
            else datetime.now(timezone.utc)
        )
        return DocumentDiff(
            id=row["id"],
            file_id=row["file_id"],
            from_version_id=row["from_version_id"],
            to_version_id=row["to_version_id"],
            patch_text=row["patch_text"],
            ai_summary=row["ai_summary"],
            lines_added=row["lines_added"],
            lines_removed=row["lines_removed"],
            created_at=created_at,
        )

    def save_version(self, version: DocumentVersion) -> DocumentVersion:
        """Persist a new immutable document version snapshot.

        If version_number <= 0, automatically assigns next monotonic version number.

        Args:
            version: DocumentVersion instance to store.

        Returns:
            DocumentVersion: The stored version entity with updated fields if calculated.
        """
        with self.get_connection() as conn:
            # If version number is <= 0, check if existing versions exist to increment
            version_num = version.version_number
            if version_num <= 0:
                cursor = conn.execute(
                    "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_ver FROM document_versions WHERE file_id = ?",
                    (version.file_id,),
                )
                row = cursor.fetchone()
                version_num = int(row["next_ver"]) if row else 1

            char_count = version.char_count or len(version.snapshot_text)
            word_count = version.word_count or len(version.snapshot_text.split())

            version_to_save = version.model_copy(
                update={
                    "version_number": version_num,
                    "char_count": char_count,
                    "word_count": word_count,
                }
            )

            row_tuple = self._version_model_to_row(version_to_save)
            conn.execute(
                """
                INSERT INTO document_versions (
                    id, file_id, version_number, content_hash, snapshot_text,
                    modified_time, editor, char_count, word_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    snapshot_text = excluded.snapshot_text,
                    content_hash = excluded.content_hash,
                    modified_time = excluded.modified_time,
                    editor = excluded.editor,
                    char_count = excluded.char_count,
                    word_count = excluded.word_count
                """,
                row_tuple,
            )

        logger.debug(
            "Saved document version snapshot '%s' (ver=%d, file=%s)",
            version_to_save.id,
            version_to_save.version_number,
            version_to_save.file_id,
        )
        return version_to_save

    def get_latest_version(self, file_id: str) -> DocumentVersion | None:
        """Retrieve the most recent version snapshot for a given file.

        Args:
            file_id: Google Drive unique file ID.

        Returns:
            DocumentVersion | None: Most recent version snapshot or None.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_versions WHERE file_id = ? ORDER BY version_number DESC LIMIT 1",
                (file_id,),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_version_model(row)
        return None

    def get_unversioned_file_ids(self) -> list[str]:
        """Return list of active, non-trashed file IDs that do not yet have a recorded version snapshot.

        Used to automatically bootstrap initial v1 version baselines for historical documents.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT f.id
                FROM file_records f
                LEFT JOIN document_versions v ON f.id = v.file_id
                WHERE f.trashed = 0 AND v.id IS NULL
                ORDER BY f.modified_time DESC
                """
            )
            return [row["id"] for row in cursor.fetchall()]

    def get_version(self, version_id: str) -> DocumentVersion | None:
        """Lookup a specific version snapshot by its unique ID.

        Args:
            version_id: Unique version ID (e.g. 'ver_xxx').

        Returns:
            DocumentVersion | None: Found domain entity or None.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_versions WHERE id = ?", (version_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_version_model(row)
        return None

    def get_version_history(
        self, file_id: str, limit: int = 50, offset: int = 0
    ) -> list[DocumentVersion]:
        """Retrieve paginated chronological version history for a file (newest first).

        Args:
            file_id: Google Drive unique file ID.
            limit: Maximum version records to return.
            offset: Record offset for pagination.

        Returns:
            list[DocumentVersion]: List of version snapshots ordered by version_number DESC.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_versions WHERE file_id = ? ORDER BY version_number DESC LIMIT ? OFFSET ?",
                (file_id, limit, offset),
            )
            return [self._row_to_version_model(row) for row in cursor.fetchall()]

    def count_versions(self, file_id: str | None = None) -> int:
        """Return total count of version snapshots stored (optionally filtered by file_id)."""
        with self.get_connection() as conn:
            if file_id is not None:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM document_versions WHERE file_id = ?",
                    (file_id,),
                )
            else:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM document_versions"
                )
            row = cursor.fetchone()
            return int(row["count"]) if row else 0

    def save_diff(self, diff: DocumentDiff) -> DocumentDiff:
        """Persist a structured document difference record.

        Args:
            diff: DocumentDiff instance to store.

        Returns:
            DocumentDiff: Stored diff entity.
        """
        row_tuple = self._diff_model_to_row(diff)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO document_diffs (
                    id, file_id, from_version_id, to_version_id, patch_text,
                    ai_summary, lines_added, lines_removed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    patch_text = excluded.patch_text,
                    ai_summary = excluded.ai_summary,
                    lines_added = excluded.lines_added,
                    lines_removed = excluded.lines_removed
                """,
                row_tuple,
            )
        logger.debug(
            "Saved document diff '%s' for file %s (from=%s, to=%s)",
            diff.id,
            diff.file_id,
            diff.from_version_id,
            diff.to_version_id,
        )
        return diff

    def get_diffs(
        self, file_id: str, limit: int = 50, offset: int = 0
    ) -> list[DocumentDiff]:
        """Retrieve paginated diff history for a given file ordered by newest first.

        Args:
            file_id: Google Drive unique file ID.
            limit: Maximum diff records to return.
            offset: Record offset for pagination.

        Returns:
            list[DocumentDiff]: List of diff delta records.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_diffs WHERE file_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (file_id, limit, offset),
            )
            return [self._row_to_diff_model(row) for row in cursor.fetchall()]

    def get_diff_between(
        self, from_version_id: str, to_version_id: str
    ) -> DocumentDiff | None:
        """Lookup a specific pre-computed diff record between two versions.

        Args:
            from_version_id: Origin version snapshot ID.
            to_version_id: Destination version snapshot ID.

        Returns:
            DocumentDiff | None: Matching diff record or None.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_diffs WHERE from_version_id = ? AND to_version_id = ?",
                (from_version_id, to_version_id),
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_diff_model(row)
        return None

    def count_diffs(self, file_id: str | None = None) -> int:
        """Return total count of diff records stored (optionally filtered by file_id)."""
        with self.get_connection() as conn:
            if file_id is not None:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM document_diffs WHERE file_id = ?",
                    (file_id,),
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) as count FROM document_diffs")
            row = cursor.fetchone()
            return int(row["count"]) if row else 0

    # --------------------------------------------------------------------------
    # Semantic Document Chunk Operations
    # --------------------------------------------------------------------------

    def save_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Insert or replace semantic chunks for a document.

        Args:
            chunks: List of DocumentChunk models to persist.

        Returns:
            int: Number of chunks successfully saved.
        """
        if not chunks:
            return 0

        with self.get_connection() as conn:
            with conn:
                for c in chunks:
                    embed_str = json.dumps(c.embedding) if c.embedding is not None else None
                    conn.execute(
                        """
                        INSERT INTO document_chunks (
                            id, file_id, version_id, chunk_index, section_heading,
                            content_text, char_start, char_end, word_count,
                            embedding_json, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(file_id, chunk_index) DO UPDATE SET
                            id=excluded.id,
                            version_id=excluded.version_id,
                            section_heading=excluded.section_heading,
                            content_text=excluded.content_text,
                            char_start=excluded.char_start,
                            char_end=excluded.char_end,
                            word_count=excluded.word_count,
                            embedding_json=excluded.embedding_json,
                            created_at=excluded.created_at
                        """,
                        (
                            c.id,
                            c.file_id,
                            c.version_id,
                            c.chunk_index,
                            c.section_heading,
                            c.content_text,
                            c.char_start,
                            c.char_end,
                            c.word_count,
                            embed_str,
                            c.created_at.isoformat(),
                        ),
                    )
        return len(chunks)

    def get_chunks_for_file(self, file_id: str) -> list[DocumentChunk]:
        """Retrieve all semantic chunks for a document ordered by sequential index."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM document_chunks WHERE file_id = ? ORDER BY chunk_index ASC",
                (file_id,),
            )
            return [self._row_to_chunk_model(row) for row in cursor.fetchall()]

    def delete_chunks_for_file(self, file_id: str) -> int:
        """Delete all semantic chunks associated with a file ID."""
        with self.get_connection() as conn:
            with conn:
                cursor = conn.execute(
                    "DELETE FROM document_chunks WHERE file_id = ?",
                    (file_id,),
                )
                return cursor.rowcount

    def search_similar_chunks(
        self,
        query_vector: list[float],
        limit: int = 5,
        file_id_filter: str | None = None,
        min_similarity: float = 0.05,
    ) -> list[tuple[DocumentChunk, float]]:
        """Search document chunks using vector cosine similarity.

        Args:
            query_vector: Normalized embedding vector of the search query.
            limit: Maximum matching chunks to return.
            file_id_filter: Optional Google Drive file ID to restrict search scope.
            min_similarity: Minimum cosine similarity score threshold.

        Returns:
            list[tuple[DocumentChunk, float]]: Top matching chunks and their similarity scores.
        """
        if not query_vector:
            return []

        with self.get_connection() as conn:
            if file_id_filter is not None:
                cursor = conn.execute(
                    "SELECT * FROM document_chunks WHERE file_id = ? AND embedding_json IS NOT NULL",
                    (file_id_filter,),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM document_chunks WHERE embedding_json IS NOT NULL"
                )
            rows = cursor.fetchall()

        scored: list[tuple[DocumentChunk, float]] = []
        for row in rows:
            chunk = self._row_to_chunk_model(row)
            if chunk.embedding:
                sim = cosine_similarity(query_vector, chunk.embedding)
                if sim >= min_similarity:
                    scored.append((chunk, round(sim, 4)))

        # Sort by similarity descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    def count_chunks(self, file_id: str | None = None) -> int:
        """Return total count of chunks stored (optionally filtered by file_id)."""
        with self.get_connection() as conn:
            if file_id is not None:
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM document_chunks WHERE file_id = ?",
                    (file_id,),
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) as count FROM document_chunks")
            row = cursor.fetchone()
            return int(row["count"]) if row else 0

    @staticmethod
    def _row_to_chunk_model(row: sqlite3.Row) -> DocumentChunk:
        """Convert a database row into a DocumentChunk domain entity."""
        embed_raw = row["embedding_json"]
        embedding = json.loads(embed_raw) if embed_raw else None
        return DocumentChunk(
            id=row["id"],
            file_id=row["file_id"],
            version_id=row["version_id"],
            chunk_index=row["chunk_index"],
            section_heading=row["section_heading"],
            content_text=row["content_text"],
            char_start=row["char_start"],
            char_end=row["char_end"],
            word_count=row["word_count"],
            embedding=embedding,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    # -------------------------------------------------------------------------
    # Multi-Turn Agent Threads & Messages Repository Methods (Task 9.8 / RFC-0002)
    # -------------------------------------------------------------------------

    def create_thread(
        self,
        title: str = "New Conversation",
        model: str | None = None,
        thread_id: str | None = None,
    ) -> AgentThread:
        """Create and persist a new conversation thread.

        Args:
            title: Human-readable title of the thread.
            model: Optional model identifier.
            thread_id: Optional explicit thread identifier. If None, generated.

        Returns:
            AgentThread: Created thread domain model.
        """
        now = datetime.now(timezone.utc)
        thread = AgentThread(
            id=thread_id or f"th_{uuid.uuid4().hex[:12]}",
            title=title.strip() if title else "New Conversation",
            model=model.strip() if model else None,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_threads (id, title, model, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    thread.id,
                    thread.title,
                    thread.model,
                    thread.created_at.isoformat(),
                    thread.updated_at.isoformat(),
                ),
            )
        logger.debug("Created agent thread %s with title '%s'", thread.id, thread.title)
        return thread

    def get_thread(self, thread_id: str) -> AgentThread | None:
        """Retrieve a thread by its identifier, including its total message count.

        Args:
            thread_id: Thread unique identifier.

        Returns:
            AgentThread | None: Domain model if found, else None.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT t.*, COUNT(m.id) as message_count
                FROM agent_threads t
                LEFT JOIN agent_messages m ON t.id = m.thread_id
                WHERE t.id = ?
                GROUP BY t.id
                """,
                (thread_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_thread_model(row)

    def list_threads(self, limit: int = 50, offset: int = 0) -> list[AgentThread]:
        """List conversation threads ordered by last updated time descending.

        Args:
            limit: Maximum number of threads to return.
            offset: Pagination offset.

        Returns:
            list[AgentThread]: Ordered list of threads.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT t.*, COUNT(m.id) as message_count
                FROM agent_threads t
                LEFT JOIN agent_messages m ON t.id = m.thread_id
                GROUP BY t.id
                ORDER BY t.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            return [self._row_to_thread_model(row) for row in cursor.fetchall()]

    def update_thread_title(self, thread_id: str, title: str) -> AgentThread | None:
        """Update the title of an existing thread and bump its updated_at timestamp.

        Args:
            thread_id: Target thread identifier.
            title: New thread title.

        Returns:
            AgentThread | None: Updated thread if found, else None.
        """
        now = datetime.now(timezone.utc).isoformat()
        clean_title = title.strip() if title else "Untitled Conversation"
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE agent_threads
                SET title = ?, updated_at = ?
                WHERE id = ?
                """,
                (clean_title, now, thread_id),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_thread(thread_id)

    def touch_thread(self, thread_id: str) -> bool:
        """Bump the updated_at timestamp of a thread.

        Args:
            thread_id: Target thread identifier.

        Returns:
            bool: True if thread was updated, False if not found.
        """
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            cursor = conn.execute(
                "UPDATE agent_threads SET updated_at = ? WHERE id = ?",
                (now, thread_id),
            )
            return cursor.rowcount > 0

    def delete_thread(self, thread_id: str) -> bool:
        """Delete a conversation thread and all its messages (via ON DELETE CASCADE).

        Args:
            thread_id: Target thread identifier.

        Returns:
            bool: True if thread was found and deleted, False otherwise.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_threads WHERE id = ?",
                (thread_id,),
            )
            deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted agent thread %s and its cascaded messages", thread_id)
        return deleted

    def save_message(self, message: AgentMessage) -> AgentMessage:
        """Persist a conversation turn message and bump the parent thread's updated_at.

        Args:
            message: Message domain model to persist.

        Returns:
            AgentMessage: Persisted message model.
        """
        now_str = message.created_at.isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO agent_messages (
                    id, thread_id, role, content, trace_json, citations_json, model, latency_ms, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.thread_id,
                    message.role,
                    message.content,
                    message.trace_json,
                    message.citations_json,
                    message.model,
                    message.latency_ms,
                    now_str,
                ),
            )
            # Bump parent thread updated_at
            conn.execute(
                "UPDATE agent_threads SET updated_at = ? WHERE id = ?",
                (now_str, message.thread_id),
            )
        return message

    def get_thread_messages(self, thread_id: str) -> list[AgentMessage]:
        """Retrieve all chronological messages for a conversation thread.

        Args:
            thread_id: Target thread identifier.

        Returns:
            list[AgentMessage]: Chronologically ordered messages (ASC).
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM agent_messages
                WHERE thread_id = ?
                ORDER BY created_at ASC
                """,
                (thread_id,),
            )
            return [self._row_to_message_model(row) for row in cursor.fetchall()]

    def delete_thread_messages(self, thread_id: str) -> bool:
        """Delete all messages belonging to a thread without deleting the thread itself.

        Args:
            thread_id: Target thread identifier.

        Returns:
            bool: True if messages were deleted.
        """
        with self.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_messages WHERE thread_id = ?",
                (thread_id,),
            )
            return cursor.rowcount > 0

    def get_catalog_stats(self) -> dict[str, Any]:
        """Aggregate high-level corpus inventory statistics from SQLite tables.

        Returns:
            dict containing file counts, type breakdown, versions, chunks, and tags.
        """
        with self.get_connection() as conn:
            # 1. File counts by MIME type (only non-trashed files)
            mime_cursor = conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN mime_type = 'application/vnd.google-apps.document' THEN 1 ELSE 0 END) as docs_count,
                    SUM(CASE WHEN mime_type = 'application/vnd.google-apps.spreadsheet' THEN 1 ELSE 0 END) as sheets_count,
                    SUM(CASE WHEN mime_type NOT IN (
                        'application/vnd.google-apps.document',
                        'application/vnd.google-apps.spreadsheet'
                    ) THEN 1 ELSE 0 END) as other_count
                FROM file_records
                WHERE trashed = 0
                """
            )
            mime_row = mime_cursor.fetchone()
            total_files = int(mime_row["total"] or 0)
            docs_count = int(mime_row["docs_count"] or 0)
            sheets_count = int(mime_row["sheets_count"] or 0)
            other_count = int(mime_row["other_count"] or 0)

            # 2. Version and Diff counts
            v_row = conn.execute("SELECT COUNT(*) as c FROM document_versions").fetchone()
            total_versions = int(v_row["c"] or 0)

            d_row = conn.execute("SELECT COUNT(*) as c FROM document_diffs").fetchone()
            total_diffs = int(d_row["c"] or 0)

            # 3. Chunks count & files missing chunks
            c_row = conn.execute("SELECT COUNT(*) as c FROM document_chunks").fetchone()
            total_chunks = int(c_row["c"] or 0)

            zero_chunks_cursor = conn.execute(
                """
                SELECT COUNT(*) as c FROM file_records f
                WHERE f.trashed = 0
                  AND (SELECT COUNT(*) FROM document_chunks c WHERE c.file_id = f.id) = 0
                """
            )
            files_with_zero_chunks = int(zero_chunks_cursor.fetchone()["c"] or 0)

            # 4. Project tags distribution
            tag_dist: dict[str, int] = {}
            tag_cursor = conn.execute(
                "SELECT project_tags_json FROM file_records WHERE trashed = 0 AND project_tags_json IS NOT NULL"
            )
            for row in tag_cursor.fetchall():
                if row["project_tags_json"]:
                    try:
                        tags = json.loads(row["project_tags_json"])
                        for t in tags:
                            if t and str(t).strip():
                                tag_clean = str(t).strip()
                                tag_dist[tag_clean] = tag_dist.get(tag_clean, 0) + 1
                    except Exception:
                        pass

            # 5. Sharing status distribution
            sharing_dist: dict[str, int] = {}
            sharing_cursor = conn.execute(
                "SELECT sharing_status, COUNT(*) as c FROM file_records WHERE trashed = 0 GROUP BY sharing_status"
            )
            for row in sharing_cursor.fetchall():
                status = row["sharing_status"] or "unknown"
                sharing_dist[status] = int(row["c"])

            # 6. Recent 5 files
            recent_cursor = conn.execute(
                """
                SELECT id, name, mime_type, modified_time, project_tags_json
                FROM file_records
                WHERE trashed = 0
                ORDER BY modified_time DESC NULLS LAST
                LIMIT 5
                """
            )
            recent_files = []
            for row in recent_cursor.fetchall():
                tags = []
                if row["project_tags_json"]:
                    try:
                        tags = json.loads(row["project_tags_json"])
                    except Exception:
                        pass
                recent_files.append({
                    "file_id": row["id"],
                    "name": row["name"],
                    "type": (
                        "doc"
                        if "document" in (row["mime_type"] or "")
                        else ("sheet" if "spreadsheet" in (row["mime_type"] or "") else "other")
                    ),
                    "modified_time": row["modified_time"],
                    "project_tags": tags,
                })

            return {
                "total_files": total_files,
                "docs_count": docs_count,
                "sheets_count": sheets_count,
                "other_count": other_count,
                "total_versions": total_versions,
                "total_diffs": total_diffs,
                "total_chunks": total_chunks,
                "files_with_zero_chunks": files_with_zero_chunks,
                "project_tags_distribution": tag_dist,
                "sharing_status_distribution": sharing_dist,
                "recent_files": recent_files,
            }

    @staticmethod
    def _row_to_thread_model(row: sqlite3.Row) -> AgentThread:
        """Convert a database row into an AgentThread domain model."""
        created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        updated_at = datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
        message_count = int(row["message_count"]) if "message_count" in row.keys() else 0
        return AgentThread(
            id=row["id"],
            title=row["title"],
            model=row["model"],
            created_at=created_at,
            updated_at=updated_at,
            message_count=message_count,
        )

    @staticmethod
    def _row_to_message_model(row: sqlite3.Row) -> AgentMessage:
        """Convert a database row into an AgentMessage domain model."""
        created_at = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        return AgentMessage(
            id=row["id"],
            thread_id=row["thread_id"],
            role=row["role"],
            content=row["content"],
            trace_json=row["trace_json"],
            citations_json=row["citations_json"],
            model=row["model"],
            latency_ms=float(row["latency_ms"]) if row["latency_ms"] is not None else None,
            created_at=created_at,
        )


def get_crawl_storage(db_path: str | Path | None = None) -> CrawlStorage:
    """Factory helper returning an initialized CrawlStorage instance."""
    return CrawlStorage(db_path=db_path)

