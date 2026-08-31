"""Unit tests for Text Patch DiffEngine."""

from __future__ import annotations

from app.indexer.diff import DiffEngine, get_diff_engine
from app.indexer.models import DiffResult


def test_diff_engine_identical_text() -> None:
    """Test that comparing identical text returns has_changes=False with zero metrics."""
    engine = get_diff_engine()
    text = "Line 1\nLine 2\nLine 3\n"
    res = engine.compute_diff(text, text)

    assert isinstance(res, DiffResult)
    assert not res.has_changes
    assert res.patch_text == ""
    assert res.lines_added == 0
    assert res.lines_removed == 0
    assert res.hunks_count == 0


def test_diff_engine_single_line_addition() -> None:
    """Test detecting a single appended line."""
    engine = DiffEngine()
    old = "Line 1\nLine 2\n"
    new = "Line 1\nLine 2\nLine 3\n"

    res = engine.compute_diff(old, new, from_label="v1", to_label="v2")

    assert res.has_changes
    assert res.lines_added == 1
    assert res.lines_removed == 0
    assert res.hunks_count == 1
    assert "--- v1" in res.patch_text
    assert "+++ v2" in res.patch_text
    assert "+Line 3" in res.patch_text


def test_diff_engine_single_line_deletion() -> None:
    """Test detecting a single deleted line."""
    engine = DiffEngine()
    old = "Line 1\nLine 2\nLine 3\n"
    new = "Line 1\nLine 3\n"

    res = engine.compute_diff(old, new)

    assert res.has_changes
    assert res.lines_added == 0
    assert res.lines_removed == 1
    assert res.hunks_count == 1
    assert "-Line 2" in res.patch_text


def test_diff_engine_multiline_modification() -> None:
    """Test multiple lines changed across different paragraphs."""
    engine = DiffEngine(context_lines=2)
    old = "Title\n\nIntro line 1\nIntro line 2\n\nBody line 1\nBody line 2\n"
    new = "Title\n\nIntro line 1 edited\nIntro line 2\n\nBody line 1\nBody line 2 modified\nNew section line\n"

    res = engine.compute_diff(old, new)

    assert res.has_changes
    assert res.lines_added == 3
    assert res.lines_removed == 2
    assert "-Intro line 1" in res.patch_text
    assert "+Intro line 1 edited" in res.patch_text
    assert "-Body line 2" in res.patch_text
    assert "+Body line 2 modified" in res.patch_text
    assert "+New section line" in res.patch_text


def test_diff_engine_empty_and_none_inputs() -> None:
    """Test edge cases with None and empty string inputs."""
    engine = DiffEngine()

    # Both None
    r1 = engine.compute_diff(None, None)
    assert not r1.has_changes

    # Old None, New text
    r2 = engine.compute_diff(None, "Brand new document\n")
    assert r2.has_changes
    assert r2.lines_added == 1
    assert r2.lines_removed == 0
    assert "+Brand new document" in r2.patch_text

    # Old text, New None (Total deletion)
    r3 = engine.compute_diff("Old doc text\n", None)
    assert r3.has_changes
    assert r3.lines_added == 0
    assert r3.lines_removed == 1
    assert "-Old doc text" in r3.patch_text


def test_diff_engine_crlf_normalization() -> None:
    """Test that Windows CRLF vs LF differences are normalized cleanly."""
    engine = DiffEngine()
    unix_text = "Line 1\nLine 2\nLine 3\n"
    win_text = "Line 1\r\nLine 2\r\nLine 3\r\n"

    res = engine.compute_diff(unix_text, win_text)
    assert not res.has_changes
    assert res.lines_added == 0
    assert res.lines_removed == 0


def test_diff_engine_no_trailing_newline() -> None:
    """Test text inputs without trailing newlines."""
    engine = DiffEngine()
    old = "Line 1"
    new = "Line 1\nLine 2"

    res = engine.compute_diff(old, new)
    assert res.has_changes
    assert res.lines_added == 1
    assert res.lines_removed == 0
    assert "+Line 2" in res.patch_text
