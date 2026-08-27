"""Unit tests for Google Drive Workspace Labels Query Formulation and Tag Extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.indexer.crawler import DriveCrawler
from app.indexer.labels import (
    DriveLabel,
    DriveLabelField,
    LabelExtractor,
    build_label_query,
)
from app.indexer.models import (
    GOOGLE_DOC_MIME_TYPE,
    DriveFileMetadata,
)


def test_build_label_query_presence() -> None:
    """Test building query for label presence."""
    query = build_label_query(label_id="lbl_project_tracker")
    assert query == "'labels/lbl_project_tracker' in labels"


def test_build_label_query_field_value() -> None:
    """Test building query for specific label field equality."""
    query = build_label_query(
        label_id="lbl_project",
        field_id="fld_name",
        value="Project Falcon",
    )
    assert query == "labels/lbl_project.fld_name = 'Project Falcon'"


def test_build_label_query_escapes_quotes() -> None:
    """Test escaping single quotes in label query values."""
    query = build_label_query(
        label_id="lbl_client",
        field_id="fld_company",
        value="O'Reilly Media",
    )
    assert query == "labels/lbl_client.fld_company = 'O\\'Reilly Media'"


def test_label_extractor_empty_or_none() -> None:
    """Test LabelExtractor returns empty lists on None, empty dict, or non-dict inputs."""
    assert LabelExtractor.extract_labels(None) == ([], [])
    assert LabelExtractor.extract_labels({}) == ([], [])
    assert LabelExtractor.extract_labels({"labels": []}) == ([], [])
    assert LabelExtractor.extract_labels({"otherKey": 123}) == ([], [])


def test_label_extractor_text_and_selection_fields() -> None:
    """Test extracting text and selection dropdown label fields."""
    raw_label_info = {
        "labels": [
            {
                "id": "lbl_project_governance",
                "revisionId": "rev_001",
                "fields": {
                    "fld_project_name": {
                        "id": "fld_project_name",
                        "valueType": "text",
                        "text": ["Project Falcon\x00"],
                    },
                    "fld_status": {
                        "id": "fld_status",
                        "valueType": "selection",
                        "selection": [
                            {"id": "opt_active", "displayName": "Active"},
                        ],
                    },
                },
            }
        ]
    }

    labels, project_tags = LabelExtractor.extract_labels(raw_label_info)

    assert len(labels) == 1
    label = labels[0]
    assert label.id == "lbl_project_governance"
    assert label.revision_id == "rev_001"
    assert len(label.fields) == 2

    # Check text field
    name_field = label.fields["fld_project_name"]
    assert name_field.field_type == "text"
    assert name_field.values == ["Project Falcon"]
    assert name_field.display_value == "Project Falcon"

    # Check selection field
    status_field = label.fields["fld_status"]
    assert status_field.field_type == "selection"
    assert status_field.values == ["Active"]
    assert status_field.display_value == "Active"

    # Check aggregated project tags
    assert "Project Falcon" in project_tags
    assert "Active" in project_tags


def test_label_extractor_user_and_integer_fields() -> None:
    """Test extracting user emails and integer fields."""
    raw_label_info = {
        "labels": [
            {
                "id": "lbl_metadata",
                "fields": {
                    "fld_owner": {
                        "id": "fld_owner",
                        "valueType": "user",
                        "user": [{"emailAddress": "lead@company.com"}],
                    },
                    "fld_priority": {
                        "id": "fld_priority",
                        "valueType": "integer",
                        "integer": [1],
                    },
                    "fld_target_date": {
                        "id": "fld_target_date",
                        "valueType": "dateString",
                        "dateString": ["2026-12-31"],
                    },
                },
            }
        ]
    }

    labels, _ = LabelExtractor.extract_labels(raw_label_info)
    assert len(labels) == 1
    fields = labels[0].fields

    assert fields["fld_owner"].values == ["lead@company.com"]
    assert fields["fld_priority"].values == ["1"]
    assert fields["fld_target_date"].values == ["2026-12-31"]


def test_drive_label_helper_methods() -> None:
    """Test DriveLabel helper lookup methods."""
    field = DriveLabelField(
        id="fld_dept",
        field_type="text",
        values=["Engineering", "Platform"],
        display_value="Engineering",
    )
    label = DriveLabel(id="lbl_org", fields={"fld_dept": field})

    assert label.get_field_values("fld_dept") == ["Engineering", "Platform"]
    assert label.get_field_display("fld_dept") == "Engineering"
    assert label.get_field_values("non_existent") == []
    assert label.get_field_display("non_existent") is None


def test_drive_file_metadata_has_project_tag() -> None:
    """Test DriveFileMetadata has_project_tag case-insensitive matching."""
    meta = DriveFileMetadata(
        id="file_1",
        name="Architecture Doc",
        mime_type=GOOGLE_DOC_MIME_TYPE,
        project_tags=["Project Falcon", "Q3 Milestone"],
    )

    assert meta.has_project_tag("Project Falcon") is True
    assert meta.has_project_tag("project falcon") is True
    assert meta.has_project_tag("PROJECT FALCON") is True
    assert meta.has_project_tag("q3 milestone") is True
    assert meta.has_project_tag("Project Orion") is False


def test_crawler_with_labels_integration() -> None:
    """Test DriveCrawler extracting labelInfo and passing include_labels."""
    mock_service = MagicMock()
    mock_req = MagicMock()
    mock_service.files().list.return_value = mock_req

    mock_req.execute.return_value = {
        "files": [
            {
                "id": "doc_tagged",
                "name": "Governed Falcon Doc",
                "mimeType": GOOGLE_DOC_MIME_TYPE,
                "labelInfo": {
                    "labels": [
                        {
                            "id": "lbl_project",
                            "fields": {
                                "fld_name": {
                                    "id": "fld_name",
                                    "valueType": "text",
                                    "text": ["Falcon"],
                                }
                            },
                        }
                    ]
                },
            },
            {
                "id": "doc_untagged",
                "name": "Random Notes",
                "mimeType": GOOGLE_DOC_MIME_TYPE,
            },
        ],
        "nextPageToken": None,
    }

    crawler = DriveCrawler(service=mock_service)
    results = crawler.crawl_all(include_labels=["lbl_project"])

    assert len(results) == 2

    # Tagged file
    tagged = results[0]
    assert tagged.id == "doc_tagged"
    assert len(tagged.labels) == 1
    assert tagged.project_tags == ["Falcon"]
    assert tagged.has_project_tag("Falcon") is True

    # Untagged file
    untagged = results[1]
    assert untagged.id == "doc_untagged"
    assert untagged.labels == []
    assert untagged.project_tags == []
    assert untagged.has_project_tag("Falcon") is False

    # Check that includeLabels was passed in query
    kwargs = mock_service.files().list.call_args[1]
    assert kwargs["includeLabels"] == "lbl_project"
    assert "labelInfo" in kwargs["fields"]
