"""Google Drive Access Control List (ACL) Parsing and Sharing Status Classification."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.indexer.models import DrivePermission, SharingStatus

logger = get_logger("panopticon.indexer.permissions")


class PermissionClassifier:
    """Classifies Google Drive file visibility and sharing status from ACL entries."""

    @staticmethod
    def parse_permissions(
        raw_permissions: list[dict[str, Any]] | None,
    ) -> list[DrivePermission]:
        """Convert raw Google Drive permissions dict list into validated DrivePermission objects.

        Args:
            raw_permissions: Raw JSON array of permission objects from files.list response.

        Returns:
            list[DrivePermission]: Normalized immutable permission objects.
        """
        if not raw_permissions or not isinstance(raw_permissions, list):
            return []

        parsed: list[DrivePermission] = []
        for raw in raw_permissions:
            if not isinstance(raw, dict):
                continue
            try:
                perm = DrivePermission(
                    id=str(raw.get("id", "")),
                    role=str(raw.get("role", "reader")),
                    type=str(raw.get("type", "user")),
                    email_address=raw.get("emailAddress"),
                    domain=raw.get("domain"),
                    display_name=raw.get("displayName"),
                    allow_file_discovery=raw.get("allowFileDiscovery"),
                )
                parsed.append(perm)
            except (ValueError, TypeError, KeyError) as parse_err:
                logger.warning(
                    "Skipping malformed permission entry: %s (%s)",
                    raw,
                    parse_err,
                )

        return parsed

    @classmethod
    def classify_sharing_status(
        cls,
        shared: bool = False,
        permissions: list[DrivePermission] | list[dict[str, Any]] | None = None,
        drive_id: str | None = None,
    ) -> SharingStatus:
        """Compute the deterministic 4-tier sharing status for a file.

        Hierarchy rule:
        1. 'anyone': If any permission principal has type == 'anyone' (Public Web Link).
        2. 'domain': If any permission principal has type == 'domain' (Org-Wide).
        3. 'shared': If shared=True, drive_id is present (Shared Drive), or multiple users/groups are present.
        4. 'private': If only the single creator/owner has access.

        Args:
            shared: Google Drive boolean shared flag.
            permissions: List of DrivePermission models or raw permission dicts.
            drive_id: ID of parent Shared Drive if applicable.

        Returns:
            SharingStatus: One of 'anyone', 'domain', 'shared', 'private'.
        """
        # If raw dicts passed, normalize first
        parsed_perms: list[DrivePermission]
        if permissions and len(permissions) > 0 and isinstance(permissions[0], dict):
            parsed_perms = cls.parse_permissions(permissions)  # type: ignore[arg-type]
        elif permissions:
            parsed_perms = permissions  # type: ignore[assignment]
        else:
            parsed_perms = []

        # 1. Broadest exposure: Anyone with the link or searchable on the web
        for p in parsed_perms:
            if p.type == "anyone":
                return "anyone"

        # 2. Company / Domain-wide exposure
        for p in parsed_perms:
            if p.type == "domain":
                return "domain"

        # 3. Shared Drive membership (all items in a Shared Drive are shared)
        if drive_id is not None and str(drive_id).strip() != "":
            return "shared"

        # 4. Explicit shared flag from Drive metadata
        if shared:
            return "shared"

        # 5. Multi-principal permissions (e.g. reader or writer beyond owner)
        non_owner_count = sum(1 for p in parsed_perms if p.role != "owner")
        if non_owner_count > 0 or len(parsed_perms) > 1:
            return "shared"

        return "private"
