"""Validation helpers for fictional clinical-trial CSV training data.

The checks in this module are programming exercises. They do not assess
clinical significance or certify the quality of real clinical-trial data.
"""

from __future__ import annotations

import csv
import math
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REQUIRED_FIELDS = (
    "participant_id",
    "site_id",
    "age",
    "sex",
    "informed_consent",
    "visit_date",
    "systolic_bp",
    "diastolic_bp",
    "adverse_event_reported",
)

# BP fields may be blank, but if supplied they must be numeric. These limits
# are intentionally configurable training ranges, not clinical limits.
REQUIRED_VALUE_FIELDS = (
    "participant_id",
    "site_id",
    "age",
    "sex",
    "informed_consent",
    "visit_date",
    "adverse_event_reported",
)
REPORT_FIELDS = (
    "row_number",
    "participant_id",
    "field_name",
    "issue_type",
    "original_value",
    "explanation",
    "suggested_manual_review_action",
)


def _issue(
    row_number: int,
    participant_id: str,
    field_name: str,
    issue_type: str,
    original_value: str,
    explanation: str,
    action: str,
) -> dict[str, object]:
    return {
        "row_number": row_number,
        "participant_id": participant_id,
        "field_name": field_name,
        "issue_type": issue_type,
        "original_value": original_value,
        "explanation": explanation,
        "suggested_manual_review_action": action,
    }


def read_csv(input_path: str | Path) -> tuple[list[dict[str, str | None]], list[str]]:
    """Read a UTF-8 CSV without changing any source values."""
    records: list[dict[str, str | None]] = []
    with Path(input_path).open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, strict=True)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            records.append(dict(row))
    return records, fieldnames


def validate_records(
    records: Sequence[Mapping[str | None, str | list[str] | None]],
    fieldnames: Sequence[str],
    *,
    age_range: tuple[float, float] = (18, 100),
    systolic_range: tuple[float, float] = (70, 250),
    diastolic_range: tuple[float, float] = (40, 150),
) -> dict[str, object]:
    """Return findings and row counts; the supplied records are never edited."""
    if age_range[0] > age_range[1] or systolic_range[0] > systolic_range[1] or diastolic_range[0] > diastolic_range[1]:
        raise ValueError("Each configured minimum must be less than or equal to its maximum.")

    issues: list[dict[str, object]] = []
    present_headers = set(fieldnames)
    missing_headers = [field for field in REQUIRED_FIELDS if field not in present_headers]
    for field in missing_headers:
        issues.append(_issue(
            1, "", field, "missing_header", "",
            f"Required column '{field}' is missing from the CSV header.",
            "Review the source file header and confirm the correct column name before changing the file.",
        ))

    normalized_ids = [
        str(row.get("participant_id") or "").strip()
        for row in records
        if str(row.get("participant_id") or "").strip()
    ]
    id_counts = Counter(normalized_ids)
    row_issue_counts: Counter[int] = Counter()

    for index, row in enumerate(records):
        row_number = index + 2  # CSV row one is the header.
        raw_id_value = row.get("participant_id")
        participant_id = str(raw_id_value or "").strip()
        row_findings: list[dict[str, object]] = []

        for field in REQUIRED_VALUE_FIELDS:
            raw_value = row.get(field)
            if raw_value is None or not str(raw_value).strip():
                row_findings.append(_issue(
                    row_number, participant_id, field, "missing_required_value", "" if raw_value is None else str(raw_value),
                    f"Required value for '{field}' is blank.",
                    "Check the source record and resolve the value with an authorized reviewer; do not infer it.",
                ))

        if participant_id and id_counts[participant_id] > 1:
            row_findings.append(_issue(
                row_number, participant_id, "participant_id", "duplicate_participant_id", str(raw_id_value),
                "This participant ID occurs more than once in the file.",
                "Compare the source records and confirm whether the repeated ID is expected or a data-entry issue.",
            ))

        age_value = str(row.get("age") or "").strip()
        if age_value:
            try:
                age = float(age_value)
                if not math.isfinite(age):
                    raise ValueError
            except ValueError:
                row_findings.append(_issue(
                    row_number, participant_id, "age", "age_not_numeric", str(row.get("age") or ""),
                    "Age must be a finite numeric value for this training check.",
                    "Check the source value and confirm the appropriate representation; do not replace it automatically.",
                ))
            else:
                if not age_range[0] <= age <= age_range[1]:
                    row_findings.append(_issue(
                        row_number, participant_id, "age", "age_out_of_training_range", str(row.get("age") or ""),
                        f"Age is outside the configured training range of {age_range[0]:g}–{age_range[1]:g}.",
                        "Review the source value and the exercise's configured range; this flag is not a clinical judgment.",
                    ))

        visit_date = str(row.get("visit_date") or "").strip()
        if visit_date:
            try:
                parsed_date = date.fromisoformat(visit_date)
                if parsed_date.isoformat() != visit_date:
                    raise ValueError
            except ValueError:
                row_findings.append(_issue(
                    row_number, participant_id, "visit_date", "invalid_date", str(row.get("visit_date") or ""),
                    "Visit date must be a valid calendar date in ISO YYYY-MM-DD format.",
                    "Check the source date and confirm its intended format; do not guess or correct it automatically.",
                ))

        for field, allowed in (("informed_consent", {"Yes", "No"}), ("adverse_event_reported", {"Yes", "No"})):
            raw_value = row.get(field)
            value = str(raw_value or "").strip()
            if value and value not in allowed:
                row_findings.append(_issue(
                    row_number, participant_id, field, "invalid_response", str(raw_value),
                    f"'{field}' must be recorded as Yes or No; the supplied value is not one of those options.",
                    "Review the source record and confirm the response; do not interpret blank or unknown values as No.",
                ))

        for field, limits in (("systolic_bp", systolic_range), ("diastolic_bp", diastolic_range)):
            raw_value = row.get(field)
            value = str(raw_value or "").strip()
            if not value:
                continue
            try:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError
            except ValueError:
                row_findings.append(_issue(
                    row_number, participant_id, field, "blood_pressure_not_numeric", str(raw_value),
                    f"'{field}' must be numeric when a value is provided.",
                    "Check the source entry and confirm the intended value; do not convert it automatically.",
                ))
            else:
                if not limits[0] <= number <= limits[1]:
                    row_findings.append(_issue(
                        row_number, participant_id, field, "blood_pressure_out_of_training_range", str(raw_value),
                        f"Value is outside the configurable training range of {limits[0]:g}–{limits[1]:g}; this is a review flag, not a diagnosis.",
                        "Manually check the source and the exercise range. Do not interpret this flag as a clinical diagnosis.",
                    ))

        issues.extend(row_findings)
        if row_findings:
            row_issue_counts[row_number] += len(row_findings)

    unique_ids = len(set(normalized_ids))
    return {
        "records_checked": len(records),
        "unique_participant_ids": unique_ids,
        "issues": issues,
        "missing_headers": missing_headers,
        "records_without_detected_issues": len(records) - len(row_issue_counts),
    }


def validate_csv(
    input_path: str | Path,
    *,
    age_range: tuple[float, float] = (18, 100),
    systolic_range: tuple[float, float] = (70, 250),
    diastolic_range: tuple[float, float] = (40, 150),
) -> dict[str, object]:
    records, fieldnames = read_csv(input_path)
    result = validate_records(
        records,
        fieldnames,
        age_range=age_range,
        systolic_range=systolic_range,
        diastolic_range=diastolic_range,
    )
    result["input_path"] = str(input_path)
    return result


def write_report(issues: Iterable[Mapping[str, object]], output_path: str | Path) -> None:
    """Write findings, including a header-only CSV when there are no issues."""
    with Path(output_path).open("w", encoding="utf-8", newline="") as report_file:
        writer = csv.DictWriter(report_file, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(issues)
