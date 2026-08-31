"""AI Semantic Change Summarizer using OpenRouter API with Heuristic Rule Fallback."""

from __future__ import annotations

import re
from typing import Protocol

import httpx

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger("panopticon.indexer.summarizer")

DEFAULT_SYSTEM_PROMPT = (
    "You are Panopticon's change summarizer. Summarize what changed in the provided document "
    "diff in exactly one concise, plain-English sentence. Focus on what was added, removed, or "
    "modified. Do not include markdown code fences, greetings, conversational filler, or quotes. "
    "Output only the single summary sentence."
)


class ChangeSummarizer(Protocol):
    """Protocol defining the interface for document difference summarization."""

    def summarize_diff(
        self,
        patch_text: str,
        file_name: str,
        editor: str | None = None,
    ) -> str:
        """Generate a natural language 1-sentence summary of a diff patch.

        Args:
            patch_text: Unified diff patch text.
            file_name: Name of the modified Google Doc / Sheet.
            editor: Email or name of the user who made the edit.

        Returns:
            str: 1-sentence summary description.
        """
        ...


class HeuristicSummarizer:
    """Deterministic, zero-setup local summarizer analyzing diff hunk metrics."""

    def summarize_diff(
        self,
        patch_text: str,
        file_name: str,
        editor: str | None = None,
    ) -> str:
        """Generate a structured statistical summary of the diff patch."""
        if not patch_text or not patch_text.strip():
            return f"No content modifications in '{file_name}'."

        lines = patch_text.splitlines()
        added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
        hunks = sum(1 for line in lines if line.startswith("@@"))

        editor_str = f"{editor} " if editor else ""

        if added > 0 and removed > 0:
            change_desc = f"updated {added + removed} lines (+{added}, -{removed})"
        elif added > 0:
            change_desc = f"added {added} line{'s' if added != 1 else ''}"
        elif removed > 0:
            change_desc = f"removed {removed} line{'s' if removed != 1 else ''}"
        else:
            change_desc = "made minor modifications"

        section_str = f" across {hunks} section{'s' if hunks != 1 else ''}" if hunks > 1 else ""

        return f"{editor_str}modified '{file_name}': {change_desc}{section_str}.".strip()


class OpenRouterSummarizer:
    """Calls OpenRouter API to generate concise semantic change summaries with local fallback."""

    def __init__(
        self,
        api_key: str,
        model: str = "openai/gpt-4o-mini",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 5.0,
        fallback: ChangeSummarizer | None = None,
    ) -> None:
        """Initialize OpenRouterSummarizer.

        Args:
            api_key: OpenRouter API Key (sk-or-...).
            model: OpenRouter model identifier string.
            base_url: OpenRouter API base endpoint.
            timeout_seconds: Maximum HTTP request duration before fallback.
            fallback: Backup summarizer used on error or timeout (defaults to HeuristicSummarizer).
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.fallback = fallback if fallback is not None else HeuristicSummarizer()

    def summarize_diff(
        self,
        patch_text: str,
        file_name: str,
        editor: str | None = None,
    ) -> str:
        """Generate a 1-sentence AI summary via OpenRouter, falling back gracefully on failure."""
        if not self.api_key or not self.api_key.strip():
            return self.fallback.summarize_diff(patch_text, file_name, editor)

        if not patch_text or not patch_text.strip():
            return self.fallback.summarize_diff(patch_text, file_name, editor)

        # Truncate overly long patches to conserve token budget
        truncated_patch = patch_text[:3500]
        if len(patch_text) > 3500:
            truncated_patch += "\n... [diff truncated for length]"

        user_content = (
            f"File: {file_name}\n"
            f"Editor: {editor or 'Unknown'}\n"
            f"Diff Patch:\n{truncated_patch}"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Mubashar986/Panopticon",
            "X-Title": "Panopticon Document Intelligence",
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "max_tokens": 120,
            "temperature": 0.2,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                raw_summary = data["choices"][0]["message"]["content"].strip()
                cleaned = self._clean_summary(raw_summary)
                if cleaned:
                    return cleaned

        except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
            logger.warning("OpenRouter summarization failed (%s). Falling back to heuristic summary.", exc)

        return self.fallback.summarize_diff(patch_text, file_name, editor)

    @staticmethod
    def _clean_summary(text: str) -> str:
        """Sanitize LLM output to ensure a single clean declarative sentence."""
        # Strip <think>...</think> reasoning blocks if present (flags=re.DOTALL)
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        # Strip code blocks or quotes
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        cleaned = cleaned.strip('"\'`')

        # Filter out reasoning/filler lines (e.g. "Here's a thinking process:", "Thinking:")
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        valid_lines: list[str] = []
        for line in lines:
            lower = line.lower()
            if any(lower.startswith(p) for p in ["here's a thinking", "thinking process", "thinking:", "here is a summary", "summary:"]):
                continue
            valid_lines.append(line)

        if not valid_lines:
            return ""

        # Take the best declarative line
        summary = valid_lines[-1] if len(valid_lines) > 1 and len(valid_lines[0]) < 25 else valid_lines[0]
        summary = summary.strip('"\'`* ')
        if not summary.endswith((".", "!", "?")):
            summary += "."

        return summary[:300]


def get_change_summarizer(settings: Settings | None = None) -> ChangeSummarizer:
    """Factory helper returning configured OpenRouterSummarizer or HeuristicSummarizer singleton."""
    cfg = settings if settings is not None else get_settings()

    if cfg.OPENROUTER_API_KEY and cfg.OPENROUTER_API_KEY.strip():
        logger.info("Initializing OpenRouterChangeSummarizer (model=%s)", cfg.OPENROUTER_MODEL)
        return OpenRouterSummarizer(
            api_key=cfg.OPENROUTER_API_KEY,
            model=cfg.OPENROUTER_MODEL,
            base_url=cfg.OPENROUTER_BASE_URL,
        )

    logger.debug("OPENROUTER_API_KEY is unset; using local HeuristicSummarizer.")
    return HeuristicSummarizer()
