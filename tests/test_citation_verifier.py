"""Unit tests for the Citation Verification & Hallucination Guardrail."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.agent.citations import CitationVerifier, VerifiedCitation
from app.agent.engine import AgentStepTrace
from app.indexer.models import DocumentChunk, DocumentDiff, DocumentVersion, DriveFileMetadata
from app.indexer.storage import CrawlStorage


@pytest.fixture
def guard_storage(tmp_path: Path) -> CrawlStorage:
    storage = CrawlStorage(db_path=tmp_path / "citation_guard_test.db")
    doc1 = DriveFileMetadata(
        id="doc_falcon_01",
        name="Project Falcon Technical Specification",
        mime_type="application/vnd.google-apps.document",
        modified_time=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
        created_time=datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc),
        owners=["lead.architect@company.com"],
        last_modifying_user="alice@company.com",
        shared=True,
        sharing_status="domain",
        project_tags=["Falcon", "Security"],
        content_snippet="Falcon technical specification covering OAuth 2.0 PKCE and rate limits.",
        export_status="success",
        web_view_link="https://docs.google.com/document/d/doc_falcon_01/edit",
        size_bytes=15000,
    )
    storage.upsert_files([doc1])

    storage.save_version(
        DocumentVersion(
            id="ver_1",
            file_id="doc_falcon_01",
            version_number=1,
            content_hash="hash_v1",
            modified_time=datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc),
            snapshot_text="Falcon spec v1",
        )
    )
    storage.save_version(
        DocumentVersion(
            id="ver_2",
            file_id="doc_falcon_01",
            version_number=2,
            content_hash="hash_v2",
            modified_time=datetime(2026, 8, 28, 14, 0, tzinfo=timezone.utc),
            snapshot_text="Falcon spec v2",
        )
    )

    diff = DocumentDiff(
        file_id="doc_falcon_01",
        from_version_id="ver_1",
        to_version_id="ver_2",
        lines_added=4,
        lines_removed=1,
        patch_text="--- v1\n+++ v2\n@@ -10,3 +10,6 @@\n-rate_limit = 60\n+rate_limit = 120\n",
        ai_summary="Increased OAuth rate limit from 60 to 120 requests per minute.",
    )
    storage.save_diff(diff)

    chunk = DocumentChunk(
        id="chk_01",
        file_id="doc_falcon_01",
        version_id="ver_2",
        chunk_index=0,
        section_heading="OAuth 2.0 PKCE",
        content_text="[Document: Falcon | Section: OAuth]\nOAuth 2.0 PKCE is strictly enforced for all client apps.",
        char_start=0,
        char_end=100,
    )
    storage.save_chunks([chunk])
    return storage


def test_extract_candidates_from_text_and_trace():
    """Verify regex patterns and trace inspection extract distinct candidate documents."""
    verifier = CitationVerifier()
    raw_answer = (
        "According to [Falcon Spec](https://docs.google.com/document/d/doc_falcon_01/edit), "
        "the auth rules were updated. Also see doc_phoenix_99."
    )
    trace = [
        AgentStepTrace(
            step=1,
            tool_name="search_index",
            arguments={"query": "Falcon"},
            output_summary='{"hits": [{"file_id": "doc_trace_hit", "name": "Trace Document"}]}',
        ),
        AgentStepTrace(
            step=2,
            tool_name="get_document_diff",
            arguments={"file_id": "doc_falcon_01"},
            output_summary='{"diffs": []}',
        ),
    ]

    candidates = verifier.extract_candidates(raw_answer, trace)
    extracted_ids = [c.inferred_id for c in candidates if c.inferred_id]

    assert "doc_falcon_01" in extracted_ids
    assert "doc_phoenix_99" in extracted_ids
    assert "doc_trace_hit" in extracted_ids


def test_verify_real_document_citation(guard_storage: CrawlStorage):
    """Verify authentic document citation is marked verified with real Google Drive URL."""
    verifier = CitationVerifier()
    text = 'As stated in [Project Falcon Technical Specification](https://docs.google.com/document/d/doc_falcon_01/edit), "OAuth 2.0 PKCE" is required.'
    trace = [
        AgentStepTrace(
            step=1,
            tool_name="get_document_diff",
            arguments={"file_id": "doc_falcon_01"},
            output_summary="{}",
        )
    ]

    sanitized_text, citations = verifier.verify_and_sanitize(text, trace, guard_storage)

    assert len(citations) == 1
    cit = citations[0]
    assert cit.file_id == "doc_falcon_01"
    assert cit.document_name == "Project Falcon Technical Specification"
    assert cit.verification_status == "verified"
    assert cit.confidence_score == 1.0
    assert cit.web_view_link == "https://docs.google.com/document/d/doc_falcon_01/edit"
    assert cit.matched_snippet == "OAuth 2.0 PKCE"


def test_hallucination_detection_and_redaction(guard_storage: CrawlStorage):
    """Verify fabricated doc IDs are flagged as hallucinations and fake links redacted."""
    verifier = CitationVerifier()
    text = "Review the architecture in [Secret Memo](https://docs.google.com/document/d/doc_ghost_phantom_99/edit)."
    trace = []

    sanitized_text, citations = verifier.verify_and_sanitize(text, trace, guard_storage)

    assert len(citations) == 1
    cit = citations[0]
    assert cit.file_id == "doc_ghost_phantom_99"
    assert cit.verification_status == "hallucination_flagged"
    assert cit.confidence_score == 0.0

    # Verify link was redacted in markdown
    assert "doc_ghost_phantom_99/edit" not in sanitized_text
    assert "**Secret Memo** *(citation unverified)*" in sanitized_text


def test_url_correction_for_real_document(guard_storage: CrawlStorage):
    """Verify placeholder or broken URLs for real files are replaced by canonical Google Drive URL."""
    verifier = CitationVerifier()
    text = "Found details in [Project Falcon Technical Specification](https://placeholder.invalid/random_link)."
    trace = []

    sanitized_text, citations = verifier.verify_and_sanitize(text, trace, guard_storage)

    assert len(citations) == 1
    assert citations[0].verification_status == "verified"
    assert "https://docs.google.com/document/d/doc_falcon_01/edit" in sanitized_text
    assert "https://placeholder.invalid/random_link" not in sanitized_text


def test_fuzzy_title_matching_resolution(guard_storage: CrawlStorage):
    """Verify slightly modified document title resolves to authentic file record."""
    verifier = CitationVerifier(fuzzy_threshold=0.7)
    text = "Refer to [Falcon Technical Specification](https://docs.google.com/document/d/unknown/edit) for details."
    trace = []

    sanitized_text, citations = verifier.verify_and_sanitize(text, trace, guard_storage)

    assert len(citations) == 1
    assert citations[0].file_id == "doc_falcon_01"
    assert citations[0].verification_status == "verified"
