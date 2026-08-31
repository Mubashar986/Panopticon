"""Benchmark candidate OpenRouter models on live document diffs."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.indexer.summarizer import OpenRouterSummarizer


def run_benchmark() -> None:
    s = get_settings()
    patch = (
        "--- v1\n"
        "+++ v2\n"
        "@@ -10,3 +10,4 @@\n"
        "-Password auth only\n"
        "+OAuth 2.0 PKCE authentication enabled\n"
        "+Enforce Multi-Factor Authentication for all admins\n"
    )

    test_models = [
        "google/gemini-2.0-flash-lite-preview-02-05:free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "deepseek/deepseek-chat",
        "openai/gpt-4o-mini",
        "nvidia/nemotron-3.5-lightning:free",
    ]

    print("=================================================================")
    print("  OPENROUTER CHANGE SUMMARIZATION BENCHMARK")
    print("=================================================================\n")

    for m in test_models:
        summarizer = OpenRouterSummarizer(api_key=s.OPENROUTER_API_KEY, model=m)
        out = summarizer.summarize_diff(patch, "Security_Policy.gdoc", editor="alex@co.com")
        print(f"[*] Model:  {m}")
        print(f"    Result: \"{out}\"\n")


if __name__ == "__main__":
    run_benchmark()
