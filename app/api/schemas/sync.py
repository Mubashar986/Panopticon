"""Pydantic schemas and response contracts for background Drive sync and re-indexing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SyncPhase = Literal[
    "idle",
    "crawling",
    "exporting",
    "updating_sqlite",
    "indexing_meilisearch",
    "failed",
]

SyncMode = Literal["incremental", "full_refresh", "reindex"]


class SyncTriggerRequest(BaseModel):
    """Payload to configure a background Drive sync job."""

    model_config = ConfigDict(frozen=True)

    full_refresh: bool = Field(
        default=False,
        description="If True, ignores existing watermark and performs a full re-crawl of Google Drive",
    )
    export_content: bool = Field(
        default=True,
        description="If True, downloads text content snippets for Docs and Sheets (10MB cap safe)",
    )
    page_size: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Google Drive API pagination page size",
    )


class SyncTriggerResponse(BaseModel):
    """Response returned immediately when a sync job is accepted."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="started", description="Status string: 'started'")
    message: str = Field(..., description="Human-readable description of the launched background job")
    job_id: str = Field(..., description="Unique job execution identifier")
    sync_mode: SyncMode = Field(..., description="Active sync mode: 'incremental', 'full_refresh', or 'reindex'")
    started_at: str = Field(..., description="ISO 8601 timestamp when the background worker started")


class SyncStats(BaseModel):
    """Metrics and file counts from a completed synchronization run."""

    model_config = ConfigDict(frozen=True)

    sync_mode: str = Field(default="incremental", description="Sync strategy executed")
    added: int = Field(default=0, description="Newly discovered files indexed")
    updated: int = Field(default=0, description="Modified files re-indexed")
    deleted: int = Field(default=0, description="Deleted or inaccessible files purged")
    unchanged: int = Field(default=0, description="Unmodified files skipped")
    total_stored: int = Field(default=0, description="Total active files tracked in local SQLite")
    total_indexed: int = Field(default=0, description="Total searchable files stored in Meilisearch")
    duration_seconds: float = Field(default=0.0, description="Total job execution time in seconds")


class SyncStatusResponse(BaseModel):
    """Live progress and status of the background synchronization subsystem."""

    model_config = ConfigDict(frozen=True)

    is_syncing: bool = Field(..., description="True if a background sync job is currently running")
    job_id: str | None = Field(default=None, description="Active job ID if currently syncing")
    sync_mode: SyncMode | None = Field(default=None, description="Active or last executed sync mode")
    current_phase: SyncPhase = Field(default="idle", description="Current step in the sync pipeline")
    progress_message: str = Field(default="Ready", description="Human-readable progress description")
    started_at: str | None = Field(default=None, description="Start timestamp of the active job")
    duration_seconds: float | None = Field(default=None, description="Elapsed or total job runtime")
    last_sync_time: str | None = Field(
        default=None, description="ISO 8601 watermark timestamp of last successful Drive sync"
    )
    last_sync_stats: SyncStats | None = Field(
        default=None, description="Statistics from the most recent completed sync run"
    )
    last_error: str | None = Field(
        default=None, description="Error message if the previous sync run failed"
    )


class ReindexResponse(BaseModel):
    """Response returned when a local search re-indexing job is triggered."""

    model_config = ConfigDict(frozen=True)

    status: str = Field(default="started", description="Status string: 'started'")
    message: str = Field(..., description="Description of the re-indexing job")
    job_id: str = Field(..., description="Unique job identifier")
    started_at: str = Field(..., description="Start timestamp")
