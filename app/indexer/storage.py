"""SQLite Local Storage Repository for Crawl State and File Metadata."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.indexer.models import (
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

                CREATE INDEX IF NOT EXISTS idx_file_modified_time ON file_records(modified_time);
                CREATE INDEX IF NOT EXISTS idx_file_sharing_status ON file_records(sharing_status);
                CREATE INDEX IF NOT EXISTS idx_file_trashed ON file_records(trashed);
                CREATE INDEX IF NOT EXISTS idx_file_last_seen_at ON file_records(last_seen_at);

                CREATE INDEX IF NOT EXISTS idx_versions_file_id ON document_versions(file_id);
                CREATE INDEX IF NOT EXISTS idx_versions_file_version ON document_versions(file_id, version_number DESC);
                CREATE INDEX IF NOT EXISTS idx_versions_content_hash ON document_versions(content_hash);
                CREATE INDEX IF NOT EXISTS idx_diffs_file_id ON document_diffs(file_id);
                CREATE INDEX IF NOT EXISTS idx_diffs_versions ON document_diffs(from_version_id, to_version_id);
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


def get_crawl_storage(db_path: str | Path | None = None) -> CrawlStorage:
    """Factory helper returning an initialized CrawlStorage instance."""
    return CrawlStorage(db_path=db_path)

