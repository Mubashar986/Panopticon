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

                CREATE INDEX IF NOT EXISTS idx_file_modified_time ON file_records(modified_time);
                CREATE INDEX IF NOT EXISTS idx_file_sharing_status ON file_records(sharing_status);
                CREATE INDEX IF NOT EXISTS idx_file_trashed ON file_records(trashed);
                CREATE INDEX IF NOT EXISTS idx_file_last_seen_at ON file_records(last_seen_at);
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


def get_crawl_storage(db_path: str | Path | None = None) -> CrawlStorage:
    """Factory helper returning an initialized CrawlStorage instance."""
    return CrawlStorage(db_path=db_path)
