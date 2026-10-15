"""Transparent checks that report source data without modifying it."""

from collections import Counter

from analytics import VALID_FOLLOW_UP, VALID_OUTCOMES, VALID_SERIOUSNESS, parse_date

REQUIRED_FIELDS = ("report_id", "report_date", "event_term", "seriousness", "outcome",
                   "suspect_product", "age_group", "country", "report_source", "follow_up_received")


def inspect_quality(rows):
    issues = []
    id_counts = Counter(row.get("report_id", "").strip() for row in rows if row.get("report_id", "").strip())
    for index, row in enumerate(rows, start=1):
        identifier = row.get("report_id", "").strip() or f"(blank ID; data row {index})"

        def add(field, issue_type, explanation):
            issues.append({"data_row": index, "report_id": identifier, "field": field,
                           "issue_type": issue_type, "explanation": explanation,
                           "original_value": row.get(field, "")})

        if not row.get("report_id", "").strip():
            add("report_id", "Missing report ID", "A report identifier is required; the source value is blank.")
        elif id_counts[row["report_id"].strip()] > 1:
            add("report_id", "Duplicate report ID", "This identifier occurs in more than one source row; no rows were removed.")
        for field in REQUIRED_FIELDS:
            if not row.get(field, "").strip() and field != "report_id":
                add(field, "Missing required field", "The required source value is blank.")
        if row.get("report_date", "").strip() and parse_date(row["report_date"]) is None:
            add("report_date", "Invalid date", "Expected a valid calendar date formatted YYYY-MM-DD.")
        if row.get("seriousness", "").strip() and row["seriousness"] not in VALID_SERIOUSNESS:
            add("seriousness", "Unrecognized seriousness", "Value must exactly match a documented category; source value is preserved.")
        if row.get("outcome", "").strip() and row["outcome"] not in VALID_OUTCOMES:
            add("outcome", "Unrecognized outcome", "Value must exactly match a documented category; source value is preserved.")
        if row.get("follow_up_received", "").strip() and row["follow_up_received"] not in VALID_FOLLOW_UP:
            add("follow_up_received", "Invalid follow-up value", "Value must be Yes or No; source value is preserved.")
    return issues
