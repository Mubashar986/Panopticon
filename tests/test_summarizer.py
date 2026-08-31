"""Unit tests for AI Semantic Change Summarizer (OpenRouter & Heuristic Fallback)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx

from app.core.config import Settings
from app.indexer.summarizer import (
    HeuristicSummarizer,
    OpenRouterSummarizer,
    get_change_summarizer,
)


def test_heuristic_summarizer_empty_diff() -> None:
    """Test heuristic summary on empty or whitespace patch."""
    summarizer = HeuristicSummarizer()
    assert summarizer.summarize_diff("", "Roadmap.gdoc") == "No content modifications in 'Roadmap.gdoc'."
    assert summarizer.summarize_diff("   ", "Roadmap.gdoc") == "No content modifications in 'Roadmap.gdoc'."


def test_heuristic_summarizer_additions_only() -> None:
    """Test heuristic summary for single and multi-line additions."""
    summarizer = HeuristicSummarizer()
    patch_text = (
        "--- v1\n"
        "+++ v2\n"
        "@@ -1,2 +1,4 @@\n"
        " Existing Line\n"
        "+New Line 1\n"
        "+New Line 2\n"
    )
    res = summarizer.summarize_diff(patch_text, "Spec.gdoc", editor="alice@co.com")
    assert "alice@co.com modified 'Spec.gdoc': added 2 lines." == res


def test_heuristic_summarizer_deletions_only() -> None:
    """Test heuristic summary for line deletions."""
    summarizer = HeuristicSummarizer()
    patch_text = (
        "--- v1\n"
        "+++ v2\n"
        "@@ -1,3 +1,2 @@\n"
        " Line 1\n"
        "-Old Deprecated Line\n"
        " Line 3\n"
    )
    res = summarizer.summarize_diff(patch_text, "Budget.gsheet")
    assert "modified 'Budget.gsheet': removed 1 line." == res


def test_heuristic_summarizer_mixed_modifications_multi_hunk() -> None:
    """Test heuristic summary for updates across multiple sections."""
    summarizer = HeuristicSummarizer()
    patch_text = (
        "--- v1\n"
        "+++ v2\n"
        "@@ -1,2 +1,2 @@\n"
        "-Title v1\n"
        "+Title v2\n"
        "@@ -20,2 +20,3 @@\n"
        " Body line\n"
        "+Appendix line\n"
    )
    res = summarizer.summarize_diff(patch_text, "Architecture.gdoc", editor="bob@co.com")
    assert "bob@co.com modified 'Architecture.gdoc': updated 3 lines (+2, -1) across 2 sections." == res


def test_openrouter_summarizer_success() -> None:
    """Test OpenRouterSummarizer making successful API call."""
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Alice added the OAuth 2.0 PKCE authentication flow and updated the rate limits."
                }
            }
        ]
    }

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
        summarizer = OpenRouterSummarizer(api_key="sk-or-test-key-123")
        patch_text = "@@ -1,2 +1,3 @@\n-old\n+new line 1\n+new line 2"

        result = summarizer.summarize_diff(patch_text, "Auth.gdoc", editor="alice@co.com")

        assert result == "Alice added the OAuth 2.0 PKCE authentication flow and updated the rate limits."
        assert mock_post.called
        kwargs = mock_post.call_args[1]
        assert kwargs["json"]["model"] == "openai/gpt-4o-mini"
        assert "Authorization" in kwargs["headers"]
        assert kwargs["headers"]["Authorization"] == "Bearer sk-or-test-key-123"


def test_openrouter_summarizer_empty_key_fallback() -> None:
    """Test that missing API key falls back to HeuristicSummarizer without HTTP call."""
    with patch("httpx.Client.post") as mock_post:
        summarizer = OpenRouterSummarizer(api_key="")
        patch_text = "@@ -1 +1,2 @@\n Line 1\n+Line 2"

        result = summarizer.summarize_diff(patch_text, "Notes.gdoc")

        assert not mock_post.called
        assert "added 1 line" in result


def test_openrouter_summarizer_http_error_fallback() -> None:
    """Test that HTTP errors (e.g. 401, 429, 500) trigger graceful fallback without raising."""
    with patch("httpx.Client.post", side_effect=httpx.HTTPStatusError("429 Too Many Requests", request=MagicMock(), response=MagicMock())):
        summarizer = OpenRouterSummarizer(api_key="sk-or-test-key-123")
        patch_text = "@@ -1 +1,2 @@\n Line 1\n+Line 2"

        result = summarizer.summarize_diff(patch_text, "Notes.gdoc", editor="charlie@co.com")

        assert "charlie@co.com modified 'Notes.gdoc': added 1 line." == result


def test_openrouter_summarizer_timeout_fallback() -> None:
    """Test that network timeout triggers graceful fallback."""
    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Read timed out")):
        summarizer = OpenRouterSummarizer(api_key="sk-or-test-key-123")
        patch_text = "@@ -1,2 +1 @@\n-Line 1\n Line 2"

        result = summarizer.summarize_diff(patch_text, "Notes.gdoc")

        assert "modified 'Notes.gdoc': removed 1 line." == result


def test_openrouter_clean_summary_formatting() -> None:
    """Test response sanitization stripping markdown code blocks and quotes."""
    summarizer = OpenRouterSummarizer(api_key="test")
    raw_markdown = '```markdown\n"Sarah upgraded the encryption cipher from AES-128 to AES-256."\n```'
    cleaned = summarizer._clean_summary(raw_markdown)
    assert cleaned == "Sarah upgraded the encryption cipher from AES-128 to AES-256."


def test_get_change_summarizer_factory() -> None:
    """Test get_change_summarizer factory behavior based on configuration settings."""
    # 1. No key -> HeuristicSummarizer
    s1 = get_change_summarizer(Settings(OPENROUTER_API_KEY=""))
    assert isinstance(s1, HeuristicSummarizer)

    # 2. With key -> OpenRouterSummarizer
    s2 = get_change_summarizer(Settings(OPENROUTER_API_KEY="sk-or-valid-key"))
    assert isinstance(s2, OpenRouterSummarizer)
    assert s2.api_key == "sk-or-valid-key"
