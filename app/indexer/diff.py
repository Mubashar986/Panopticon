"""Text Patch Diff Engine utilizing difflib unified diff algorithms and line metrics."""

from __future__ import annotations

import difflib

from app.core.logging import get_logger
from app.indexer.models import DiffResult

logger = get_logger("panopticon.indexer.diff")


class DiffEngine:
    """Computes line-level unified diff patches and change metrics between text snapshots."""

    def __init__(self, context_lines: int = 3) -> None:
        """Initialize DiffEngine with configurable surrounding context lines (default 3).

        Args:
            context_lines: Number of unchanged context lines surrounding each diff hunk.
        """
        self.context_lines = context_lines

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
        # Normalize None to empty strings
        old_str = old_text if old_text is not None else ""
        new_str = new_text if new_text is not None else ""

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

        # Split into lines preserving line endings for unified_diff
        old_lines = old_str.splitlines(keepends=True)
        new_lines = new_str.splitlines(keepends=True)

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
