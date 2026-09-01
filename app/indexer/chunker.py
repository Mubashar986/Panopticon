"""Semantic sliding-window text chunker for document retrieval."""

from __future__ import annotations

import hashlib
import re

from app.indexer.models import DocumentChunk


class TextChunker:
    """Slices plain text documents into overlapping contextual passages with metadata anchors."""

    def __init__(self, chunk_size: int = 1500, overlap: int = 200) -> None:
        """Initialize chunker with size and overlap constraints.

        Args:
            chunk_size: Target maximum character length of each chunk before metadata prefix.
            overlap: Number of characters to preserve from the previous chunk.
        """
        if overlap >= chunk_size:
            raise ValueError(f"Overlap ({overlap}) must be strictly less than chunk_size ({chunk_size})")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_document(
        self,
        content_text: str,
        file_id: str,
        file_name: str,
        version_id: str | None = None,
    ) -> list[DocumentChunk]:
        """Split a document into structured, contextual chunks.

        Args:
            content_text: Full plain text extracted from Google Doc/Sheet.
            file_id: Unique Google Drive file identifier.
            file_name: Human-readable document title.
            version_id: Optional DocumentVersion identifier this text corresponds to.

        Returns:
            list[DocumentChunk]: Ordered sequence of chunks with metadata anchors.
        """
        if not content_text or not content_text.strip():
            return []

        clean_text = content_text.strip()
        headings = self._extract_headings(clean_text)

        # Split text into paragraphs/sections while preserving character offsets
        paragraphs = self._split_paragraphs(clean_text)
        if not paragraphs:
            return []

        chunks: list[DocumentChunk] = []
        current_paras: list[tuple[str, int, int]] = []  # (text, start_offset, end_offset)
        current_len = 0
        chunk_idx = 0

        for para_text, p_start, p_end in paragraphs:
            current_paras.append((para_text, p_start, p_end))
            current_len += len(para_text) + 2  # account for \n\n

            if current_len >= self.chunk_size:
                chunk = self._create_chunk(
                    paragraphs=current_paras,
                    file_id=file_id,
                    file_name=file_name,
                    version_id=version_id,
                    chunk_index=chunk_idx,
                    headings=headings,
                )
                chunks.append(chunk)
                chunk_idx += 1

                # Calculate overlap retention
                current_paras = self._calculate_overlap(current_paras)
                current_len = sum(len(p[0]) + 2 for p in current_paras)

        # Process any remaining text in buffer
        if current_paras:
            # If remaining paras exactly duplicate the previous chunk, skip
            if not chunks or (current_paras[0][1] != chunks[-1].char_start or current_paras[-1][2] != chunks[-1].char_end):
                chunk = self._create_chunk(
                    paragraphs=current_paras,
                    file_id=file_id,
                    file_name=file_name,
                    version_id=version_id,
                    chunk_index=chunk_idx,
                    headings=headings,
                )
                chunks.append(chunk)

        return chunks

    def _split_paragraphs(self, text: str) -> list[tuple[str, int, int]]:
        """Split text into paragraph spans with start and end offsets."""
        paragraphs: list[tuple[str, int, int]] = []
        for match in re.finditer(r"[^\n]+(?:\n[^\n]+)*", text):
            p_text = match.group().strip()
            if p_text:
                paragraphs.append((p_text, match.start(), match.end()))
        return paragraphs

    def _extract_headings(self, text: str) -> list[tuple[int, str]]:
        """Extract markdown headings (#) and all-caps section titles with character offsets."""
        headings: list[tuple[int, str]] = []
        # Match markdown headings e.g. # Heading, ## Section
        for m in re.finditer(r"^(#{1,6})\s+(.+)$", text, flags=re.MULTILINE):
            headings.append((m.start(), m.group(2).strip()))

        # Match all-caps section headers e.g. "SECTION 1: OVERVIEW" or "ARCHITECTURE SPECIFICATION"
        for m in re.finditer(r"^[A-Z0-9\s:_\-]{4,60}$", text, flags=re.MULTILINE):
            line = m.group().strip()
            # Must contain letters and not be entirely digits
            if any(c.isalpha() for c in line) and len(line.split()) <= 8:
                headings.append((m.start(), line))

        headings.sort(key=lambda x: x[0])
        return headings

    def _get_active_heading(self, char_offset: int, headings: list[tuple[int, str]]) -> str | None:
        """Find the nearest section heading that precedes the given character offset."""
        active: str | None = None
        for offset, title in headings:
            if offset <= char_offset:
                active = title
            else:
                break
        return active

    def _calculate_overlap(
        self, paragraphs: list[tuple[str, int, int]]
    ) -> list[tuple[str, int, int]]:
        """Retain the trailing paragraphs that fit within the overlap character budget."""
        retained: list[tuple[str, int, int]] = []
        retained_len = 0

        for p_text, p_start, p_end in reversed(paragraphs):
            if retained_len + len(p_text) <= self.overlap or not retained:
                retained.insert(0, (p_text, p_start, p_end))
                retained_len += len(p_text)
            else:
                break

        return retained

    def _create_chunk(
        self,
        paragraphs: list[tuple[str, int, int]],
        file_id: str,
        file_name: str,
        version_id: str | None,
        chunk_index: int,
        headings: list[tuple[int, str]],
    ) -> DocumentChunk:
        """Construct a DocumentChunk model with context header stamp."""
        raw_body = "\n\n".join(p[0] for p in paragraphs)
        char_start = paragraphs[0][1]
        char_end = paragraphs[-1][2]

        section_heading = self._get_active_heading(char_start, headings)

        # Context Anchor Stamp
        heading_display = section_heading if section_heading else "General"
        header_prefix = f"[Document: {file_name} | Section: {heading_display}]\n\n"
        full_content = f"{header_prefix}{raw_body}"

        # Deterministic unique chunk ID
        seed = f"{file_id}_{chunk_index}_{char_start}_{char_end}"
        chunk_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        chunk_id = f"chk_{chunk_hash}"

        word_count = len(full_content.split())

        return DocumentChunk(
            id=chunk_id,
            file_id=file_id,
            version_id=version_id,
            chunk_index=chunk_index,
            section_heading=section_heading,
            content_text=full_content,
            char_start=char_start,
            char_end=char_end,
            word_count=word_count,
            embedding=None,
        )
