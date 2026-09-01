"""Unit tests for semantic text chunker."""

import pytest

from app.indexer.chunker import TextChunker
from app.indexer.models import DocumentChunk


def test_chunker_initialization_validation():
    """Verify ValueError is raised if overlap >= chunk_size."""
    with pytest.raises(ValueError, match="Overlap"):
        TextChunker(chunk_size=500, overlap=500)

    with pytest.raises(ValueError, match="Overlap"):
        TextChunker(chunk_size=500, overlap=600)

    chunker = TextChunker(chunk_size=1000, overlap=200)
    assert chunker.chunk_size == 1000
    assert chunker.overlap == 200


def test_chunk_empty_document():
    """Verify empty or whitespace-only documents return an empty list."""
    chunker = TextChunker()
    assert chunker.chunk_document("", "doc_1", "Empty Doc") == []
    assert chunker.chunk_document("   \n\n  \t ", "doc_1", "Empty Doc") == []


def test_chunk_small_document():
    """Verify documents smaller than chunk_size result in a single chunk."""
    chunker = TextChunker(chunk_size=1500, overlap=200)
    text = "This is a brief specification document.\n\nIt covers the core architecture."
    chunks = chunker.chunk_document(text, "doc_small", "Small Doc", version_id="ver_01")

    assert len(chunks) == 1
    chunk = chunks[0]
    assert isinstance(chunk, DocumentChunk)
    assert chunk.file_id == "doc_small"
    assert chunk.version_id == "ver_01"
    assert chunk.chunk_index == 0
    assert "[Document: Small Doc | Section: General]" in chunk.content_text
    assert "This is a brief specification document." in chunk.content_text
    assert chunk.char_start == 0
    assert chunk.char_end == len(text)
    assert chunk.word_count > 0
    assert chunk.id.startswith("chk_")


def test_chunk_with_markdown_headings():
    """Verify markdown headings (# and ##) are detected and propagated to chunk metadata."""
    chunker = TextChunker(chunk_size=120, overlap=30)
    text = (
        "# System Overview\n\n"
        "Panopticon indexes Google Workspace documents.\n\n"
        "## Authentication Architecture\n\n"
        "OAuth 2.0 PKCE is used for authenticating desktop and web clients.\n\n"
        "## Deployment Model\n\n"
        "FastAPI is deployed locally with Meilisearch running on port 7700."
    )
    chunks = chunker.chunk_document(text, "doc_headings", "Architecture Spec")
    assert len(chunks) >= 2

    # First chunk should have System Overview or Authentication Architecture
    assert any("Overview" in (c.section_heading or "") for c in chunks)
    assert any("Authentication" in (c.section_heading or "") for c in chunks)


def test_chunk_sliding_window_overlap():
    """Verify that consecutive chunks preserve overlapping text."""
    chunker = TextChunker(chunk_size=250, overlap=80)
    paragraphs = [
        f"Paragraph {i}: This is detailed content explaining subsystem component {i} in depth with technical specifications."
        for i in range(1, 10)
    ]
    text = "\n\n".join(paragraphs)

    chunks = chunker.chunk_document(text, "doc_overlap", "Overlap Test Doc")
    assert len(chunks) > 1

    # Verify sequential indices
    for idx, chunk in enumerate(chunks):
        assert chunk.chunk_index == idx
        assert chunk.file_id == "doc_overlap"
        assert chunk.char_start < chunk.char_end

    # Check that text from the end of chunk 0 appears in chunk 1
    chunk_0_text = chunks[0].content_text
    chunk_1_text = chunks[1].content_text

    # Extract some words from chunk 0
    words_chunk_0 = set(chunk_0_text.split()[-10:])
    words_chunk_1 = set(chunk_1_text.split()[:25])
    # Should have non-empty intersection due to overlap
    assert len(words_chunk_0.intersection(words_chunk_1)) > 0


def test_chunk_all_caps_section_headings():
    """Verify all-caps lines are detected as section headings."""
    chunker = TextChunker(chunk_size=400, overlap=50)
    text = (
        "SECURITY POLICIES\n\n"
        "All credentials must be stored in encrypted vaults.\n\n"
        "INCIDENT RESPONSE PROTOCOL\n\n"
        "Contact the SRE on-call engineer immediately upon severity 1 alerts."
    )
    chunks = chunker.chunk_document(text, "doc_caps", "Security Guide")
    assert len(chunks) >= 1
    assert any(c.section_heading == "SECURITY POLICIES" for c in chunks)
