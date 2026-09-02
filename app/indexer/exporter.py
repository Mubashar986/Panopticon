"""Google Drive Document Text Exporter with 10MB Ceiling Circuit Breaker."""

from __future__ import annotations

from typing import Literal

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from pydantic import BaseModel, ConfigDict, Field

from app.core.auth.base import DriveAuthProvider
from app.core.auth.client import build_drive_service
from app.core.logging import get_logger
from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    DriveFileMetadata,
    sanitize_string,
)

logger = get_logger("panopticon.indexer.exporter")

# 10MB Google Drive server-side conversion limit
DEFAULT_MAX_EXPORT_BYTES = 10 * 1024 * 1024
DEFAULT_MAX_SNIPPET_CHARS = 500

ExportStatus = Literal[
    "success",
    "oversized_metadata_only",
    "skipped_unsupported_mime",
    "failed_metadata_only",
]


class ExportResult(BaseModel):
    """Result of attempting to export text from a Google Drive file."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    file_id: str = Field(..., description="Google Drive file ID")
    status: ExportStatus = Field(..., description="Export outcome status")
    content_text: str | None = Field(default=None, description="Full sanitized extracted text if available")
    snippet: str | None = Field(default=None, description="Truncated preview snippet for search indexing")
    size_bytes: int | None = Field(default=None, description="Size of exported byte payload")
    error_message: str | None = Field(default=None, description="Error details if export failed or was truncated")


class ContentExporter:
    """Exports and sanitizes text content from Google Docs and Sheets with 10MB cap handling."""

    def __init__(
        self,
        service: Resource | None = None,
        provider: DriveAuthProvider | None = None,
        max_snippet_chars: int = DEFAULT_MAX_SNIPPET_CHARS,
        max_export_bytes: int = DEFAULT_MAX_EXPORT_BYTES,
    ) -> None:
        """Initialize ContentExporter with injected Google Drive Resource or AuthProvider.

        Args:
            service: Optional pre-built Google Drive v3 Resource.
            provider: Optional DriveAuthProvider instance.
            max_snippet_chars: Maximum character length of generated preview snippets (default 500).
            max_export_bytes: Maximum allowed byte size before tripping circuit breaker (default 10MB).
        """
        if service is not None:
            self._service = service
        else:
            self._service = build_drive_service(provider)

        self.max_snippet_chars = max_snippet_chars
        self.max_export_bytes = max_export_bytes

    @property
    def service(self) -> Resource:
        """Return underlying Google Drive API resource."""
        return self._service

    def get_target_export_mime(self, source_mime: str) -> str | None:
        """Map native Google Workspace MIME types to plain text conversion formats."""
        if source_mime == GOOGLE_DOC_MIME_TYPE:
            return "text/plain"
        elif source_mime == GOOGLE_SHEET_MIME_TYPE:
            return "text/csv"
        return None

    def export_file_content(self, file_id: str, mime_type: str) -> ExportResult:
        """Export text content from a Google Doc or Sheet with 10MB ceiling protection.

        Args:
            file_id: Google Drive file ID.
            mime_type: Google Drive file MIME type.

        Returns:
            ExportResult with status, sanitized text, and bounded search snippet.
        """
        target_mime = self.get_target_export_mime(mime_type)
        if target_mime is None:
            logger.debug(
                "Skipping export for unsupported non-native MIME type: %s (fileId=%s)",
                mime_type,
                file_id,
            )
            return ExportResult(
                file_id=file_id,
                status="skipped_unsupported_mime",
                snippet=None,
            )

        logger.debug("Exporting file %s as %s", file_id, target_mime)

        try:
            request = self._service.files().export_media(
                fileId=file_id,
                mimeType=target_mime,
            )
            raw_bytes: bytes = request.execute(num_retries=3)

            # Handle edge cases where returned payload is str instead of bytes
            if isinstance(raw_bytes, str):
                raw_bytes = raw_bytes.encode("utf-8")

            payload_size = len(raw_bytes)

            # Check if payload exceeded size threshold
            if payload_size > self.max_export_bytes:
                logger.warning(
                    "File %s exceeded max export size (%d bytes > %d bytes); degrading to metadata-only.",
                    file_id,
                    payload_size,
                    self.max_export_bytes,
                )
                return ExportResult(
                    file_id=file_id,
                    status="oversized_metadata_only",
                    snippet="[Oversized file: indexed by metadata only]",
                    size_bytes=payload_size,
                )

            # Decode UTF-8 defensively, replacing corrupt bytes and stripping BOM
            decoded_str = raw_bytes.decode("utf-8", errors="replace").lstrip("\ufeff")
            cleaned_text = sanitize_string(decoded_str) or ""
            if cleaned_text:
                cleaned_text = cleaned_text.lstrip("\ufeff")
            # Collapse raw carriage returns and newlines for clean search snippets
            snippet = " ".join(cleaned_text[: self.max_snippet_chars].split())

            return ExportResult(
                file_id=file_id,
                status="success",
                content_text=cleaned_text,
                snippet=snippet,
                size_bytes=payload_size,
            )

        except HttpError as http_err:
            status_code = http_err.resp.status
            content_str = (
                http_err.content.decode("utf-8", errors="ignore")
                if getattr(http_err, "content", None)
                else ""
            )
            err_lower = f"{http_err._get_reason()} {content_str} {http_err}".lower()

            # Catch 10MB Google export ceiling: 403 exportSizeLimitExceeded or 413 Payload Too Large
            if (
                status_code in (403, 413)
                and ("exportsize" in err_lower or "too large" in err_lower or "limit" in err_lower)
            ) or status_code == 413:
                logger.warning(
                    "Google Drive 10MB export ceiling reached for file %s: %s (graceful fallback)",
                    file_id,
                    content_str or http_err._get_reason(),
                )
                return ExportResult(
                    file_id=file_id,
                    status="oversized_metadata_only",
                    snippet="[Oversized file: indexed by metadata only]",
                    error_message=content_str or http_err._get_reason(),
                )

            logger.error(
                "Google Drive API export error (%d) for file %s: %s",
                status_code,
                file_id,
                err_lower,
            )
            return ExportResult(
                file_id=file_id,
                status="failed_metadata_only",
                error_message=f"Export failed ({status_code}): {http_err._get_reason()}",
            )

        except (TimeoutError, ConnectionResetError, ConnectionError, OSError, ValueError, TypeError) as e:
            logger.warning(
                "Network or processing error exporting content for file %s: %s (graceful fallback)",
                file_id,
                e,
            )
            return ExportResult(
                file_id=file_id,
                status="failed_metadata_only",
                snippet="[Export error: indexed by metadata only]",
                error_message=f"Export error: {e}",
            )

    def export_and_attach(self, metadata: DriveFileMetadata) -> DriveFileMetadata:
        """Export text content and return a new DriveFileMetadata with attached snippet and status.

        Args:
            metadata: Existing DriveFileMetadata record.

        Returns:
            Updated DriveFileMetadata with content_snippet and export_status fields populated.
        """
        result = self.export_file_content(metadata.id, metadata.mime_type)
        return metadata.model_copy(
            update={
                "content_snippet": result.snippet,
                "export_status": result.status,
            }
        )
