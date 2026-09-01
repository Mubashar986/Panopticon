"""Citation verification and zero-hallucination guardrail subsystem."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from app.agent.engine import AgentStepTrace
from app.core.logging import get_logger
from app.indexer.models import DriveFileMetadata
from app.indexer.storage import CrawlStorage

logger = get_logger("panopticon.agent.citations")


class VerifiedCitation(BaseModel):
    """Authoritatively validated document citation."""

    model_config = ConfigDict(frozen=True)

    file_id: str = Field(..., description="Google Drive unique file ID")
    document_name: str = Field(..., description="Canonical document title")
    web_view_link: str = Field(..., description="Authoritative Google Drive URL")
    mime_type: str = Field(default="application/vnd.google-apps.document", description="Document MIME type")
    matched_snippet: str | None = Field(default=None, description="Verified quote or excerpt from source text")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Groundedness confidence score")
    verification_status: Literal["verified", "unverified", "hallucination_flagged"] = Field(
        default="verified", description="Grounding validation status"
    )


class CitationCandidate(NamedTuple):
    """Raw reference extracted from LLM text or execution trace."""

    raw_text: str
    inferred_id: str | None
    inferred_title: str | None
    inferred_url: str | None


class CitationVerifier:
    """Deterministic validation guardrail checking LLM citations against SQLite state."""

    # Regex patterns for citation discovery
    MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
    FILE_ID_PATTERN = re.compile(r"\b(doc_[a-zA-Z0-9_\-]+)\b")
    GDRIVE_URL_ID_PATTERN = re.compile(r"docs\.google\.com/(?:document|spreadsheets)/d/([a-zA-Z0-9_\-]+)")
    QUOTED_TEXT_PATTERN = re.compile(r'"([^"]{5,100})"')

    def __init__(self, fuzzy_threshold: float = 0.8) -> None:
        self.fuzzy_threshold = fuzzy_threshold

    def extract_candidates(
        self, text: str, trace: list[AgentStepTrace] | None = None
    ) -> list[CitationCandidate]:
        """Extract candidate document references from synthesized text and execution trace."""
        candidates: list[CitationCandidate] = []
        seen_identifiers: set[str] = set()

        # 1. Extract markdown links: [Title](URL)
        for match in self.MARKDOWN_LINK_PATTERN.finditer(text):
            title, url = match.group(1).strip(), match.group(2).strip()
            inferred_id = None
            url_match = self.GDRIVE_URL_ID_PATTERN.search(url)
            if url_match:
                inferred_id = url_match.group(1)
            elif "doc_" in url:
                id_sub = self.FILE_ID_PATTERN.search(url)
                if id_sub:
                    inferred_id = id_sub.group(1)

            ident = inferred_id or url or title
            if ident not in seen_identifiers:
                seen_identifiers.add(ident)
                candidates.append(
                    CitationCandidate(
                        raw_text=match.group(0),
                        inferred_id=inferred_id,
                        inferred_title=title,
                        inferred_url=url,
                    )
                )

        # 2. Extract raw file IDs in text (e.g. "doc_falcon_01")
        for match in self.FILE_ID_PATTERN.finditer(text):
            raw_id = match.group(1)
            if raw_id not in seen_identifiers:
                seen_identifiers.add(raw_id)
                candidates.append(
                    CitationCandidate(
                        raw_text=raw_id,
                        inferred_id=raw_id,
                        inferred_title=None,
                        inferred_url=None,
                    )
                )

        # 3. Extract files touched in the execution trace
        if trace:
            for step in trace:
                file_id = step.arguments.get("file_id")
                if file_id and str(file_id) not in seen_identifiers:
                    seen_identifiers.add(str(file_id))
                    candidates.append(
                        CitationCandidate(
                            raw_text=f"trace_step_{step.step}",
                            inferred_id=str(file_id),
                            inferred_title=None,
                            inferred_url=None,
                        )
                    )
                # Also check hits returned in tool output summary
                try:
                    out_data = json.loads(step.output_summary)
                    hits = out_data.get("hits", [])
                    for h in hits:
                        fid = h.get("file_id")
                        fname = h.get("name")
                        if fid and fid not in seen_identifiers:
                            seen_identifiers.add(fid)
                            candidates.append(
                                CitationCandidate(
                                    raw_text=f"trace_hit_{fid}",
                                    inferred_id=fid,
                                    inferred_title=fname,
                                    inferred_url=None,
                                )
                            )
                except Exception:
                    pass

        return candidates

    def verify_and_sanitize(
        self,
        text: str,
        trace: list[AgentStepTrace],
        storage: CrawlStorage,
    ) -> tuple[str, list[VerifiedCitation]]:
        """Verify citations against authoritative storage, sanitize markdown, and return verified list.

        Returns:
            tuple[str, list[VerifiedCitation]]: (Sanitized markdown answer, list of verified citations).
        """
        candidates = self.extract_candidates(text, trace)
        verified_citations: list[VerifiedCitation] = []
        citations_by_id: dict[str, VerifiedCitation] = {}
        sanitized_text = text

        # Cache known files from storage for title matching
        all_stored_files = storage.list_files(limit=100)

        # Extract any quotes from synthesized text for grounding checks
        quoted_phrases = [m.group(1).strip() for m in self.QUOTED_TEXT_PATTERN.finditer(text)]

        # Trace file IDs observed during tool execution
        trace_file_ids = set()
        for t in trace:
            if t.arguments.get("file_id"):
                trace_file_ids.add(str(t.arguments["file_id"]))

        for candidate in candidates:
            resolved_file: DriveFileMetadata | None = None
            is_hallucination = False

            # A. Attempt direct lookup by inferred ID
            if candidate.inferred_id:
                resolved_file = storage.get_file(candidate.inferred_id)

            # B. If ID not found or missing, attempt title matching
            if not resolved_file and candidate.inferred_title:
                resolved_file = self._match_by_title(candidate.inferred_title, all_stored_files)

            # C. Handle Resolution Result
            if resolved_file:
                # Document is authentic!
                file_id = resolved_file.id
                if file_id in citations_by_id:
                    continue  # Already processed

                # Grounding & quote match check
                matched_snippet, quote_verified = self._check_grounding(
                    resolved_file.id, quoted_phrases, storage
                )

                confidence = 1.0 if quote_verified else (0.9 if file_id in trace_file_ids else 0.75)

                citation = VerifiedCitation(
                    file_id=resolved_file.id,
                    document_name=resolved_file.name,
                    web_view_link=resolved_file.web_view_link
                    or f"https://docs.google.com/document/d/{resolved_file.id}/edit",
                    mime_type=resolved_file.mime_type,
                    matched_snippet=matched_snippet,
                    confidence_score=confidence,
                    verification_status="verified",
                )
                citations_by_id[file_id] = citation
                verified_citations.append(citation)

                # Sanitize Markdown: If the LLM used a broken or placeholder URL, fix it with canonical link
                if candidate.inferred_url and candidate.inferred_url != citation.web_view_link:
                    old_link_md = f"[{candidate.inferred_title}]({candidate.inferred_url})"
                    new_link_md = f"[{citation.document_name}]({citation.web_view_link})"
                    sanitized_text = sanitized_text.replace(old_link_md, new_link_md)

            elif candidate.inferred_id and candidate.inferred_id.startswith("doc_"):
                # Fabricated doc ID that does NOT exist in SQLite!
                is_hallucination = True
                flagged_citation = VerifiedCitation(
                    file_id=candidate.inferred_id,
                    document_name=candidate.inferred_title or f"Unverified ({candidate.inferred_id})",
                    web_view_link="",
                    mime_type="application/octet-stream",
                    matched_snippet=None,
                    confidence_score=0.0,
                    verification_status="hallucination_flagged",
                )
                verified_citations.append(flagged_citation)

                # Redact hallucinated link in markdown
                if candidate.inferred_url:
                    broken_md = f"[{candidate.inferred_title}]({candidate.inferred_url})"
                    redacted_md = f"**{candidate.inferred_title}** *(citation unverified)*"
                    sanitized_text = sanitized_text.replace(broken_md, redacted_md)

        logger.info(
            "Citation verification completed: %d total citations (%d verified, %d flagged)",
            len(verified_citations),
            len([c for c in verified_citations if c.verification_status == "verified"]),
            len([c for c in verified_citations if c.verification_status == "hallucination_flagged"]),
        )
        return sanitized_text, verified_citations

    def _match_by_title(
        self, candidate_title: str, stored_files: list[DriveFileMetadata]
    ) -> DriveFileMetadata | None:
        """Resolve a candidate title to a stored document using exact or fuzzy matching."""
        cand_clean = candidate_title.strip().lower()
        if not cand_clean:
            return None

        # 1. Exact case-insensitive match
        for f in stored_files:
            if f.name.strip().lower() == cand_clean:
                return f

        # 2. Substring containment
        for f in stored_files:
            fname_clean = f.name.strip().lower()
            if cand_clean in fname_clean or fname_clean in cand_clean:
                return f

        # 3. Fuzzy ratio match
        best_file: DriveFileMetadata | None = None
        best_ratio = 0.0
        for f in stored_files:
            ratio = SequenceMatcher(None, cand_clean, f.name.strip().lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_file = f

        if best_ratio >= self.fuzzy_threshold and best_file is not None:
            return best_file

        return None

    def _check_grounding(
        self,
        file_id: str,
        quoted_phrases: list[str],
        storage: CrawlStorage,
    ) -> tuple[str | None, bool]:
        """Check if any quoted text appears in the document's versions, diffs, or chunks."""
        if not quoted_phrases:
            return None, False

        # Check diff patches
        diffs = storage.get_diffs(file_id)
        for d in diffs:
            for phrase in quoted_phrases:
                p_lower = phrase.lower()
                if (d.patch_text and p_lower in d.patch_text.lower()) or (
                    d.ai_summary and p_lower in d.ai_summary.lower()
                ):
                    return phrase, True

        # Check document chunks
        chunks = storage.get_chunks_for_file(file_id)
        for c in chunks:
            for phrase in quoted_phrases:
                if phrase.lower() in c.content_text.lower():
                    return phrase, True

        # Return first quote with false if ungrounded
        return quoted_phrases[0] if quoted_phrases else None, False
