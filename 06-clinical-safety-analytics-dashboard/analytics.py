"""CSV loading, filtering, and descriptive summaries for synthetic reports."""

import csv
import io
from collections import Counter
from datetime import date

REQUIRED_COLUMNS = [
    "report_id", "report_date", "event_term", "seriousness", "outcome",
    "suspect_product", "age_group", "country", "report_source", "follow_up_received",
]
VALID_SERIOUSNESS = {"Serious", "Non-serious"}
VALID_OUTCOMES = {"Recovered", "Recovering", "Not recovered", "Fatal", "Unknown"}
VALID_FOLLOW_UP = {"Yes", "No"}


class DataError(ValueError):
    """Raised for an invalid CSV structure or filter parameter."""


def parse_csv(content):
    """Parse and validate CSV structure; keep every original row and value."""
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise DataError("CSV must use UTF-8 text encoding.") from exc
    try:
        reader = csv.reader(io.StringIO(content, newline=""), strict=True)
        headers = next(reader, None)
    except (csv.Error, TypeError) as exc:
        raise DataError(f"Could not read CSV: {exc}") from exc
    if not headers:
        raise DataError("CSV is empty or has no header row.")
    if len(headers) != len(set(headers)):
        raise DataError("CSV contains duplicate column headers.")
    missing = [name for name in REQUIRED_COLUMNS if name not in headers]
    if missing:
        raise DataError("Missing required columns: " + ", ".join(missing))
    rows = []
    try:
        for values in reader:
            row_number = reader.line_num
            if not values:
                continue
            if len(values) > len(headers):
                raise DataError(f"Row {row_number} has more values than the header.")
            if len(values) < len(headers):
                raise DataError(f"Row {row_number} has fewer values than the header.")
            if not any(value.strip() for value in values):
                continue
            rows.append(dict(zip(headers, values)))
    except csv.Error as exc:
        raise DataError(f"Malformed CSV near line {reader.line_num}: {exc}") from exc
    return rows


def parse_date(value):
    try:
        return date.fromisoformat((value or "").strip())
    except (TypeError, ValueError):
        return None


def filter_rows(rows, filters=None, search=""):
    filters = filters or {}
    start, end = filters.get("start_date", ""), filters.get("end_date", "")
    parsed_start, parsed_end = (parse_date(start) if start else None), (parse_date(end) if end else None)
    if start and not parsed_start:
        raise DataError("Start date must use YYYY-MM-DD.")
    if end and not parsed_end:
        raise DataError("End date must use YYYY-MM-DD.")
    if parsed_start and parsed_end and parsed_start > parsed_end:
        raise DataError("Start date must not be after end date.")
    categorical = ("event_term", "seriousness", "outcome", "suspect_product", "age_group")
    result = []
    needle = (search or "").strip().casefold()
    for row in rows:
        day = parse_date(row.get("report_date"))
        if parsed_start and (not day or day < parsed_start):
            continue
        if parsed_end and (not day or day > parsed_end):
            continue
        category_mismatch = False
        for field in categorical:
            selected = filters.get(field, "")
            value = row.get(field, "")
            if selected == "__MISSING__":
                if value.strip():
                    category_mismatch = True
                    break
            elif selected and value != selected:
                category_mismatch = True
                break
        if category_mismatch:
            continue
        if needle and not any(needle in str(value).casefold() for value in row.values()):
            continue
        result.append(row)
    return result


def counts_by(rows, field):
    counts = Counter(row.get(field, "") or "(Missing)" for row in rows)
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())))


def monthly_counts(rows):
    counts = Counter()
    for row in rows:
        day = parse_date(row.get("report_date"))
        if day:
            counts[day.strftime("%Y-%m")] += 1
    return dict(sorted(counts.items()))


def overview_metrics(rows):
    ids = {row.get("report_id", "").strip() for row in rows if row.get("report_id", "").strip()}
    required = REQUIRED_COLUMNS
    missing_rows = sum(any(not row.get(field, "").strip() for field in required) for row in rows)
    return {
        "total_rows": len(rows),
        "unique_report_ids": len(ids),
        "serious_rows": sum(row.get("seriousness") == "Serious" for row in rows),
        "rows_with_missing_required_fields": missing_rows,
    }


def export_rows_csv(rows):
    output = io.StringIO(newline="")
    fields = list(rows[0]) if rows else REQUIRED_COLUMNS
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()
