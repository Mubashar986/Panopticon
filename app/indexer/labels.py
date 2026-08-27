"""Google Drive Workspace Labels Query Formulation and Tag Extraction."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.indexer.models import (
    DriveLabel,
    DriveLabelField,
    sanitize_string,
)

logger = get_logger("panopticon.indexer.labels")


def build_label_query(
    label_id: str,
    field_id: str | None = None,
    value: str | None = None,
) -> str:
    """Construct a valid Google Drive API v3 search query for Google Drive Labels.

    Syntax rules:
        - Label presence: 'labels/LABEL_ID' in labels
        - Specific field value: labels/LABEL_ID.FIELD_ID = 'VALUE'

    Args:
        label_id: The unique Google Drive Label ID (e.g. 'lbl_12345').
        field_id: Optional field ID within the label (e.g. 'fld_project_name').
        value: Optional target value to match against the field.

    Returns:
        Formatted query string ready for Google Drive API files.list(q=...).
    """
    clean_label = sanitize_string(label_id) or label_id

    if field_id and value is not None:
        clean_field = sanitize_string(field_id) or field_id
        # Escape single quotes within the value string
        escaped_value = value.replace("'", "\\'")
        clean_value = sanitize_string(escaped_value) or escaped_value
        return f"labels/{clean_label}.{clean_field} = '{clean_value}'"

    # Default to label presence check
    return f"'labels/{clean_label}' in labels"


class LabelExtractor:
    """Defensive extractor for Google Drive API labelInfo response structures."""

    @staticmethod
    def extract_labels(
        raw_label_info: dict[str, Any] | None,
    ) -> tuple[list[DriveLabel], list[str]]:
        """Safely parse raw Google Drive labelInfo JSON into normalized domain models.

        Args:
            raw_label_info: Raw 'labelInfo' dictionary from Google Drive API files.list or files.get.

        Returns:
            tuple[list[DriveLabel], list[str]]:
                - List of normalized DriveLabel domain objects.
                - Flat list of project tags / label values extracted across text and selection fields.
        """
        if not raw_label_info or not isinstance(raw_label_info, dict):
            return [], []

        raw_labels_list = raw_label_info.get("labels")
        if not raw_labels_list or not isinstance(raw_labels_list, list):
            return [], []

        normalized_labels: list[DriveLabel] = []
        collected_tags: list[str] = []

        for raw_label in raw_labels_list:
            if not isinstance(raw_label, dict):
                continue

            label_id = raw_label.get("id", "")
            if not label_id:
                continue

            revision_id = raw_label.get("revisionId")
            raw_fields_map = raw_label.get("fields", {})
            fields_dict: dict[str, DriveLabelField] = {}

            if isinstance(raw_fields_map, dict):
                for f_id, f_data in raw_fields_map.items():
                    if not isinstance(f_data, dict):
                        continue

                    value_type = f_data.get("valueType", "text")
                    extracted_values: list[str] = []

                    # 1. Parse text fields
                    if "text" in f_data:
                        raw_text = f_data["text"]
                        if isinstance(raw_text, list):
                            for t in raw_text:
                                s = sanitize_string(t) if isinstance(t, str) else None
                                if s:
                                    extracted_values.append(s)
                        elif isinstance(raw_text, str):
                            s = sanitize_string(raw_text)
                            if s:
                                extracted_values.append(s)

                    # 2. Parse selection fields (dropdown / choice options)
                    elif "selection" in f_data:
                        raw_sel = f_data["selection"]
                        if isinstance(raw_sel, list):
                            for sel in raw_sel:
                                if isinstance(sel, str):
                                    s = sanitize_string(sel)
                                    if s:
                                        extracted_values.append(s)
                                elif isinstance(sel, dict):
                                    s = sanitize_string(sel.get("displayName") or sel.get("id"))
                                    if s:
                                        extracted_values.append(s)
                        elif isinstance(raw_sel, str):
                            s = sanitize_string(raw_sel)
                            if s:
                                extracted_values.append(s)

                    # 3. Parse user fields (email addresses / display names)
                    elif "user" in f_data:
                        raw_users = f_data["user"]
                        if isinstance(raw_users, list):
                            for u in raw_users:
                                if isinstance(u, dict):
                                    s = sanitize_string(u.get("emailAddress") or u.get("displayName"))
                                    if s:
                                        extracted_values.append(s)
                                elif isinstance(u, str):
                                    s = sanitize_string(u)
                                    if s:
                                        extracted_values.append(s)

                    # 4. Parse integer / numeric fields
                    elif "integer" in f_data:
                        raw_int = f_data["integer"]
                        if isinstance(raw_int, list):
                            for n in raw_int:
                                extracted_values.append(str(n))
                        elif raw_int is not None:
                            extracted_values.append(str(raw_int))

                    # 5. Parse dateString fields
                    elif "dateString" in f_data:
                        raw_date = f_data["dateString"]
                        if isinstance(raw_date, list):
                            for d in raw_date:
                                s = sanitize_string(d) if isinstance(d, str) else None
                                if s:
                                    extracted_values.append(s)
                        elif isinstance(raw_date, str):
                            s = sanitize_string(raw_date)
                            if s:
                                extracted_values.append(s)

                    primary_display = extracted_values[0] if extracted_values else None

                    fields_dict[f_id] = DriveLabelField(
                        id=f_id,
                        field_type=value_type,
                        values=extracted_values,
                        display_value=primary_display,
                    )

                    # Aggregate text and selection values into project tags
                    if value_type in ("text", "selection"):
                        for val in extracted_values:
                            if val not in collected_tags:
                                collected_tags.append(val)

            normalized_labels.append(
                DriveLabel(
                    id=label_id,
                    revision_id=revision_id,
                    fields=fields_dict,
                )
            )

        return normalized_labels, collected_tags
