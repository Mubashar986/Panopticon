"""Live test script for OpenRouter Summarizer."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.indexer.summarizer import OpenRouterSummarizer, get_change_summarizer


def test_live_call() -> None:
    settings = get_settings()
    print(f"[*] Testing Model: {settings.OPENROUTER_MODEL}")
    print(f"[*] API Key:       {settings.OPENROUTER_API_KEY[:10]}...{settings.OPENROUTER_API_KEY[-6:]}")

    summarizer = get_change_summarizer()

    patch_sample = (
        "--- v1\n"
        "+++ v2\n"
        "@@ -5,2 +5,4 @@\n"
        " Security Policy:\n"
        "-Password auth only\n"
        "+OAuth 2.0 PKCE authentication enabled\n"
        "+Enforce Multi-Factor Authentication for all admins\n"
    )

    print("\n[*] Sending diff to OpenRouter...")
    summary = summarizer.summarize_diff(
        patch_text=patch_sample,
        file_name="Security_Policy.gdoc",
        editor="alex.security@company.com",
    )

    print(f"\n[+] Generated Semantic AI Summary:\n    \"{summary}\"\n")


if __name__ == "__main__":
    test_live_call()
