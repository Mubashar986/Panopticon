"""Text Patch Diff Engine utilizing difflib unified diff algorithms and line metrics."""

from __future__ import annotations

import difflib
import re

from app.core.logging import get_logger
from app.indexer.models import DiffResult

logger = get_logger("panopticon.indexer.diff")

# Regex to detect sentence boundaries followed by a capital letter or quote
_SENTENCE_BOUNDARY_REGEX = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")


def segment_diff_lines(text: str, max_line_len: int = 160) -> list[str]:
    """Segment raw text into diffable lines with prose sentence boundary splitting.

    Splits dense unwrapped Google Docs paragraphs on sentence boundaries to prevent
    monolithic diff hunks where a 1-word edit replaces an entire multi-sentence paragraph.
    Tabular CSV lines (containing multiple commas or tabs) are preserved intact.
    """
    raw_lines = text.splitlines(keepends=False)
    segmented: list[str] = []

    for line in raw_lines:
        line_clean = line.strip()
        if not line_clean:
            segmented.append("\n")
            continue

        # Preserve structured tabular data (CSV / TSV / Markdown tables) if no sentence boundaries exist
        is_tabular = ("\t" in line or line.startswith("|") or (line.count(",") >= 2 and not bool(_SENTENCE_BOUNDARY_REGEX.search(line_clean))))
        if is_tabular:
            segmented.append(line + "\n")
            continue

        # If prose line is long, break on sentence boundaries
        if len(line_clean) > max_line_len:
            sentences = _SENTENCE_BOUNDARY_REGEX.split(line_clean)
            for s in sentences:
                s_strip = s.strip()
                if s_strip:
                    segmented.append(s_strip + "\n")
        else:
            segmented.append(line_clean + "\n")

    return segmented


class DiffEngine:
    """Computes line-level unified diff patches and change metrics between text snapshots."""

    def __init__(self, context_lines: int = 3, max_prose_line_len: int = 160) -> None:
        """Initialize DiffEngine with configurable surrounding context lines (default 3).

        Args:
            context_lines: Number of unchanged context lines surrounding each diff hunk.
            max_prose_line_len: Max character length before prose paragraph is split by sentence.
        """
        self.context_lines = context_lines
        self.max_prose_line_len = max_prose_line_len

    def compute_diff(
        self,
        old_text: str | None,
        new_text: str | None,
        from_label: str = "before",
        to_label: str = "after",
    ) -> DiffResult:
        """Compute standard Git-style unified diff and extract change metrics.

        Args:
            old_text: Prior text snapshot.
            new_text: New text snapshot.
            from_label: Label for origin snapshot header (default 'before').
            to_label: Label for target snapshot header (default 'after').

        Returns:
            DiffResult: Structured outcome with patch text, lines_added, lines_removed, hunks_count.
        """
        # Normalize None to empty strings and strip UTF-8 BOM
        old_str = (old_text if old_text is not None else "").lstrip("\ufeff")
        new_str = (new_text if new_text is not None else "").lstrip("\ufeff")

        # Normalize line endings to avoid CRLF vs LF false diffs
        old_str = old_str.replace("\r\n", "\n").replace("\r", "\n")
        new_str = new_str.replace("\r\n", "\n").replace("\r", "\n")

        # Short-circuit exact match
        if old_str == new_str:
            return DiffResult(
                has_changes=False,
                patch_text="",
                lines_added=0,
                lines_removed=0,
                hunks_count=0,
            )

        # Split into lines preserving line endings and segmenting dense prose paragraphs
        old_lines = segment_diff_lines(old_str, max_line_len=self.max_prose_line_len)
        new_lines = segment_diff_lines(new_str, max_line_len=self.max_prose_line_len)

        # Ensure last line ends with newline for clean unified diff calculation if non-empty
        if old_lines and not old_lines[-1].endswith("\n"):
            old_lines[-1] += "\n"
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"

        diff_gen = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=from_label,
            tofile=to_label,
            n=self.context_lines,
        )

        diff_lines = list(diff_gen)
        if not diff_lines:
            return DiffResult(
                has_changes=False,
                patch_text="",
                lines_added=0,
                lines_removed=0,
                hunks_count=0,
            )

        lines_added = 0
        lines_removed = 0
        hunks_count = 0

        for line in diff_lines:
            if line.startswith("@@"):
                hunks_count += 1
            elif line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1

        patch_text = "".join(diff_lines).strip()

        logger.debug(
            "Computed diff (%d hunks, +%d lines, -%d lines)",
            hunks_count,
            lines_added,
            lines_removed,
        )

        return DiffResult(
            has_changes=True,
            patch_text=patch_text,
            lines_added=lines_added,
            lines_removed=lines_removed,
            hunks_count=hunks_count,
        )


def get_diff_engine(context_lines: int = 3) -> DiffEngine:
    """Factory helper returning a configured DiffEngine instance."""
    return DiffEngine(context_lines=context_lines)
