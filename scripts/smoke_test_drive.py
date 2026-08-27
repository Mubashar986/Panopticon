"""Smoke Test: Query and List Files via Google Drive API Authentication Provider.

Usage:
    python scripts/smoke_test_drive.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Bootstrap project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.auth import build_drive_service, get_auth_provider
from app.core.auth.exceptions import AuthError
from app.core.config import get_settings
from app.core.logging import setup_logging


def format_mime_type(mime_type: str) -> str:
    """Format Google and generic MIME types for compact table display."""
    mapping = {
        "application/vnd.google-apps.document": "Google Doc",
        "application/vnd.google-apps.spreadsheet": "Google Sheet",
        "application/vnd.google-apps.presentation": "Google Slide",
        "application/vnd.google-apps.folder": "Folder",
        "application/vnd.google-apps.form": "Google Form",
        "application/pdf": "PDF Document",
    }
    return mapping.get(mime_type, mime_type.split("/")[-1].upper())


def format_timestamp(iso_str: str | None) -> str:
    """Format ISO timestamp into human-readable local string."""
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_str[:16]


def run_smoke_test(page_size: int = 50) -> int:
    """Execute live Google Drive API files.list query and render diagnostic report."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    print("\n" + "=" * 90)
    print(f" PANOPTICON DRIVE API SMOKE TEST (Task 1.3 - Mode: {settings.DRIVE_AUTH_MODE})")
    print("=" * 90)

    try:
        provider = get_auth_provider(settings)
        print(f"[*] Provider in use : {provider.provider_name}")
        print("[*] Requesting Drive v3 Service client...")

        service = build_drive_service(provider)
        print("[+] Drive v3 client successfully initialized.")

        print(f"\n[*] Querying first {page_size} files from Google Drive...")
        response: dict[str, Any] = (
            service.files()
            .list(
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, size)",
                includeItemsFromAllDrives=True,
                supportsAllDrives=True,
            )
            .execute()
        )

        files = response.get("files", [])
        if not files:
            print("\n[!] No files found in your Google Drive (Drive appears empty).")
            print("=" * 90 + "\n")
            return 0

        print(f"\n[+] Successfully retrieved {len(files)} files:\n")
        header = f"{'#':<3} | {'FILE NAME':<35} | {'TYPE':<14} | {'MODIFIED':<16} | {'FILE ID'}"
        print(header)
        print("-" * len(header) + "-" * 15)

        for idx, item in enumerate(files, start=1):
            name = item.get("name", "Untitled")
            if len(name) > 33:
                name = name[:30] + "..."
            mime = format_mime_type(item.get("mimeType", "unknown"))
            modified = format_timestamp(item.get("modifiedTime"))
            file_id = item.get("id", "N/A")
            print(f"{idx:<3} | {name:<35} | {mime:<14} | {modified:<16} | {file_id}")

        print("\n" + "=" * 90)
        print("[+] SUCCESS: Smoke test verified! Auth provider is ready for indexing in Epic 2.")
        print("=" * 90 + "\n")
        return 0

    except (AuthError, OSError, ValueError) as err:
        print(f"\n[-] SMOKE TEST FAILED: {err}\n", file=sys.stderr)
        print("=" * 90 + "\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run_smoke_test())
