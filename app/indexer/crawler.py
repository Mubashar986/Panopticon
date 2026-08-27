"""Google Drive Recursive Multi-Page Crawler with Shared Drive, Permissions & Label Support."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from pydantic import ValidationError

from app.core.auth.base import DriveAuthProvider
from app.core.auth.client import build_drive_service
from app.core.auth.exceptions import (
    AuthError,
    DrivePermissionDeniedError,
    DriveQuotaExceededError,
    DriveRateLimitError,
)
from app.core.logging import get_logger
from app.indexer.labels import LabelExtractor
from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    GOOGLE_SHEET_MIME_TYPE,
    CrawlStats,
    DriveFileMetadata,
)
from app.indexer.permissions import PermissionClassifier

logger = get_logger("panopticon.indexer.crawler")

# Default query targeting only Docs and Sheets and excluding trashed items
DEFAULT_DOCS_SHEETS_QUERY = (
    f"trashed = false and (mimeType = '{GOOGLE_DOC_MIME_TYPE}' or mimeType = '{GOOGLE_SHEET_MIME_TYPE}')"
)

# Explicit field projection to optimize bandwidth and memory
DEFAULT_DRIVE_FIELDS = (
    "nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, "
    "owners, lastModifyingUser, shared, "
    "permissions(id, role, type, emailAddress, domain, displayName, allowFileDiscovery), "
    "webViewLink, iconLink, size, trashed, parents, driveId, labelInfo)"
)


def _handle_http_error(http_err: HttpError) -> None:
    """Map Google API HttpError to typed Panopticon domain exception hierarchy."""
    status = http_err.resp.status
    content_str = (
        http_err.content.decode("utf-8", errors="ignore")
        if getattr(http_err, "content", None)
        else ""
    )
    error_context = f"{http_err._get_reason()} {content_str} {http_err}".lower()

    logger.error("Google Drive API HTTP error %d: %s", status, error_context)

    if status == 429 or "ratelimit" in error_context or "user_rate_limit" in error_context:
        raise DriveRateLimitError(
            f"Google Drive API rate limit reached: {content_str or http_err._get_reason()}"
        ) from http_err
    elif status == 403:
        if "quota" in error_context or "dailylimit" in error_context:
            raise DriveQuotaExceededError(
                f"Google Drive API quota exhausted: {content_str or http_err._get_reason()}"
            ) from http_err
        raise DrivePermissionDeniedError(
            f"Google Drive permission denied: {content_str or http_err._get_reason()}"
        ) from http_err
    raise AuthError(
        f"Google Drive API communication error ({status}): {content_str or http_err._get_reason()}"
    ) from http_err


class DriveCrawler:
    """Multi-page crawler that enumerates Google Docs and Sheets across all accessible drives."""

    def __init__(
        self,
        service: Resource | None = None,
        provider: DriveAuthProvider | None = None,
    ) -> None:
        """Initialize crawler with injected Google Drive Resource or AuthProvider.

        Args:
            service: Optional pre-built Google Drive v3 Resource.
            provider: Optional DriveAuthProvider instance. If neither service nor provider
                     is provided, uses default get_auth_provider().
        """
        if service is not None:
            self._service = service
        else:
            self._service = build_drive_service(provider)

    @property
    def service(self) -> Resource:
        """Return the underlying Google Drive API resource."""
        return self._service

    def crawl_files(
        self,
        query_filter: str | None = None,
        page_size: int = 100,
        max_pages: int | None = None,
        include_labels: list[str] | str | None = None,
    ) -> Iterator[DriveFileMetadata]:
        """Stream sanitized file metadata across all visible drives using cursor pagination.

        Args:
            query_filter: Optional custom Drive search query. If None, defaults to Docs + Sheets.
            page_size: Number of items per page (1 to 1000, default 100).
            max_pages: Optional upper bound on pages to fetch (useful for testing/bounds).
            include_labels: Optional label IDs to request from Google Drive API.

        Yields:
            DriveFileMetadata: Normalized domain object for each discovered file.

        Raises:
            DriveRateLimitError: If API rate limits are encountered.
            DriveQuotaExceededError: If account quota is exhausted.
            DrivePermissionDeniedError: If permissions are insufficient.
            RuntimeError: If cyclic pagination tokens are detected.
            AuthError: On network or communication failures.
        """
        if not 1 <= page_size <= 1000:
            raise ValueError(f"page_size must be between 1 and 1000, got {page_size}")

        query = query_filter if query_filter is not None else DEFAULT_DOCS_SHEETS_QUERY
        page_token: str | None = None
        seen_tokens: set[str] = set()
        pages_fetched = 0

        logger.info(
            "Starting Google Drive crawl (pageSize=%d, query='%s')",
            page_size,
            query,
        )

        while True:
            request_kwargs: dict[str, Any] = {
                "q": query,
                "pageSize": page_size,
                "fields": DEFAULT_DRIVE_FIELDS,
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
                "corpora": "allDrives",
            }
            if include_labels:
                request_kwargs["includeLabels"] = (
                    ",".join(include_labels) if isinstance(include_labels, list) else include_labels
                )
            if page_token is not None:
                request_kwargs["pageToken"] = page_token

            try:
                logger.debug(
                    "Executing files.list request (page=%d, pageToken=%s)",
                    pages_fetched + 1,
                    page_token,
                )
                request = self._service.files().list(**request_kwargs)
                response = request.execute()
            except HttpError as http_err:
                _handle_http_error(http_err)
            except Exception as e:
                logger.error("Unexpected error querying Google Drive API: %s", e)
                raise AuthError(f"Drive API crawl failed: {e}") from e

            pages_fetched += 1
            raw_files: list[dict[str, Any]] = response.get("files", [])
            logger.debug(
                "Fetched page %d with %d items", pages_fetched, len(raw_files)
            )

            for raw_file in raw_files:
                try:
                    labels, project_tags = LabelExtractor.extract_labels(raw_file.get("labelInfo"))
                    raw_perms = raw_file.get("permissions")
                    parsed_perms = PermissionClassifier.parse_permissions(raw_perms)
                    sharing_status = PermissionClassifier.classify_sharing_status(
                        shared=raw_file.get("shared", False),
                        permissions=parsed_perms,
                        drive_id=raw_file.get("driveId"),
                    )

                    metadata = DriveFileMetadata(
                        id=raw_file.get("id", ""),
                        name=raw_file.get("name", "Untitled"),
                        mime_type=raw_file.get("mimeType", "application/octet-stream"),
                        modified_time=raw_file.get("modifiedTime"),
                        created_time=raw_file.get("createdTime"),
                        owners=raw_file.get("owners", []),
                        last_modifying_user=(
                            raw_file.get("lastModifyingUser", {}).get("emailAddress")
                            or raw_file.get("lastModifyingUser", {}).get("displayName")
                        ),
                        shared=raw_file.get("shared", False),
                        web_view_link=raw_file.get("webViewLink"),
                        icon_link=raw_file.get("iconLink"),
                        size_bytes=(
                            int(raw_file["size"]) if raw_file.get("size") else None
                        ),
                        trashed=raw_file.get("trashed", False),
                        parents=raw_file.get("parents", []),
                        drive_id=raw_file.get("driveId"),
                        permissions=parsed_perms,
                        sharing_status=sharing_status,
                        labels=labels,
                        project_tags=project_tags,
                    )
                    yield metadata
                except (ValueError, TypeError, KeyError, ValidationError) as parse_err:
                    logger.warning(
                        "Skipping malformed file entry (id=%s): %s",
                        raw_file.get("id"),
                        parse_err,
                    )

            if max_pages is not None and pages_fetched >= max_pages:
                logger.info("Reached max_pages ceiling (%d); terminating crawl.", max_pages)
                break

            next_page_token: str | None = response.get("nextPageToken")
            if not next_page_token:
                logger.info(
                    "Crawl pagination completed successfully (%d pages fetched).",
                    pages_fetched,
                )
                break

            if next_page_token in seen_tokens:
                logger.error(
                    "Cyclic pagination token detected from Drive API: %s",
                    next_page_token,
                )
                raise RuntimeError(
                    f"Cyclic pagination token detected from Google Drive API: {next_page_token}"
                )

            seen_tokens.add(next_page_token)
            page_token = next_page_token

    def crawl_all(
        self,
        query_filter: str | None = None,
        page_size: int = 100,
        max_pages: int | None = None,
        include_labels: list[str] | str | None = None,
    ) -> list[DriveFileMetadata]:
        """Eagerly fetch and return all discovered file metadata as a list.

        Args:
            query_filter: Optional custom Drive search query.
            page_size: Number of items per page.
            max_pages: Optional maximum number of pages.
            include_labels: Optional label IDs to request.

        Returns:
            list[DriveFileMetadata]: All discovered files.
        """
        return list(
            self.crawl_files(
                query_filter=query_filter,
                page_size=page_size,
                max_pages=max_pages,
                include_labels=include_labels,
            )
        )

    def crawl_with_stats(
        self,
        query_filter: str | None = None,
        page_size: int = 100,
        max_pages: int | None = None,
        include_labels: list[str] | str | None = None,
    ) -> tuple[list[DriveFileMetadata], CrawlStats]:
        """Execute crawl and return both discovered files and detailed execution telemetry.

        Returns:
            tuple[list[DriveFileMetadata], CrawlStats]: Discovered files and crawl metrics.
        """
        start_time = datetime.now(timezone.utc)
        files: list[DriveFileMetadata] = []
        pages_count = 0
        docs_count = 0
        sheets_count = 0
        other_count = 0

        # Run generator
        for item in self.crawl_files(
            query_filter=query_filter,
            page_size=page_size,
            max_pages=max_pages,
            include_labels=include_labels,
        ):
            files.append(item)
            if item.is_doc:
                docs_count += 1
            elif item.is_sheet:
                sheets_count += 1
            else:
                other_count += 1

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Calculate pages from item count / page_size approximation
        pages_count = (len(files) // page_size) + (1 if len(files) % page_size > 0 or not files else 0)

        stats = CrawlStats(
            pages_fetched=pages_count,
            files_discovered=len(files),
            docs_count=docs_count,
            sheets_count=sheets_count,
            other_count=other_count,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
        )

        return files, stats
