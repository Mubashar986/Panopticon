"""Diagnostic CLI Script to Verify Real Google Drive Authentication.

Usage:
    python scripts/test_drive_auth.py
"""

import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.auth import get_auth_provider
from app.core.auth.exceptions import AuthError
from app.core.config import get_settings
from app.core.logging import setup_logging


def run_auth_diagnostic() -> int:
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    print("\n" + "=" * 80)
    print(f" PANOPTICON AUTHENTICATION DIAGNOSTIC (Mode: {settings.DRIVE_AUTH_MODE})")
    print("=" * 80)

    try:
        provider = get_auth_provider(settings)
        print(f"[*] Active Provider Class : {provider.provider_name}")
        print(f"[*] Configured Scopes     : {', '.join(provider.scopes)}")

        print("\n[*] Acquiring credentials via provider.get_credentials()...")
        creds = provider.get_credentials()

        print("\n[+] SUCCESS! Credentials acquired successfully.")
        print(f"    - Valid?             : {creds.valid}")
        print(f"    - Expired?           : {creds.expired}")
        if hasattr(creds, "token_uri"):
            print(f"    - Token URI          : {creds.token_uri}")

        print("\n[+] Verification Complete: Auth seam is working and ready for Drive crawling.")
        print("=" * 80 + "\n")
        return 0

    except (AuthError, OSError, ValueError) as exc:
        print(f"\n[-] AUTHENTICATION FAILED: {exc}\n", file=sys.stderr)
        print("=" * 80 + "\n", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run_auth_diagnostic())
