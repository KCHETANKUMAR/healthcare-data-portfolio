"""CSV loading, duplicate warnings, and lookup helpers for practice terms."""

from __future__ import annotations

import csv
from collections import Counter
from io import StringIO
from pathlib import Path
from typing import Iterable, Mapping

REQUIRED_COLUMNS = (
    "term", "definition", "category", "reference_code", "explanation", "source_name", "source_version"
)


class ReferenceDataError(ValueError):
    """Raised when a reference CSV is structurally invalid."""


def parse_reference_csv(text: str) -> tuple[list[dict[str, str]], list[str]]:
    """Parse CSV text without creating or inferring any reference values."""
    reader = csv.DictReader(StringIO(text, newline=""), strict=True)
    headers = list(reader.fieldnames or [])
    if not headers:
        raise ReferenceDataError("CSV is empty or has no header row.")
    if len(set(headers)) != len(headers):
        repeated = sorted({name for name in headers if headers.count(name) > 1})
        raise ReferenceDataError("CSV has duplicate column names: " + ", ".join(repeated))
    missing = [name for name in REQUIRED_COLUMNS if name not in headers]
    if missing:
        raise ReferenceDataError("CSV is missing required columns: " + ", ".join(missing))

    entries: list[dict[str, str]] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ReferenceDataError(f"CSV row {row_number} has more values than the header.")
        entries.append({key: (value if value is not None else "") for key, value in row.items()})
    return entries, find_duplicate_warnings(entries)


def load_reference_csv(path: str | Path) -> tuple[list[dict[str, str]], list[str]]:
    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ReferenceDataError(f"{source} is not valid UTF-8 text.") from exc
    try:
        return parse_reference_csv(text)
    except csv.Error as exc:
        raise ReferenceDataError(f"Malformed CSV: {exc}") from exc


def find_duplicate_warnings(entries: Iterable[Mapping[str, str]]) -> list[str]:
    """Report duplicate term names and supplied reference codes by row."""
    rows = list(entries)
    term_counts = Counter((row.get("term", "").strip().casefold()) for row in rows if row.get("term", "").strip())
    code_counts = Counter((row.get("reference_code", "").strip().casefold()) for row in rows if row.get("reference_code", "").strip())
    warnings: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        term = row.get("term", "").strip()
        code = row.get("reference_code", "").strip()
        if term and term_counts[term.casefold()] > 1:
            warnings.append(f"Row {row_number}: duplicate term '{term}'.")
        if code and code_counts[code.casefold()] > 1:
            warnings.append(f"Row {row_number}: duplicate reference code '{code}'.")
        for field in ("term", "definition", "reference_code", "explanation", "source_name", "source_version"):
            if not row.get(field, "").strip():
                warnings.append(f"Row {row_number}: '{field}' is blank; no value was supplied or inferred.")
    return warnings


def search_entries(
    entries: Iterable[Mapping[str, str]],
    query: str = "",
    category: str = "All categories",
) -> list[dict[str, str]]:
    """Search term, definition, category, or reference code, with category filter."""
    needle = query.strip().casefold()
    selected_category = category.strip()
    if not needle and selected_category.casefold() == "all categories":
        return []
    results = []
    for original in entries:
        row = dict(original)
        if selected_category.casefold() != "all categories" and row.get("category", "").casefold() != selected_category.casefold():
            continue
        haystack = " ".join(row.get(field, "") for field in ("term", "definition", "category", "reference_code")).casefold()
        if not needle or needle in haystack:
            results.append(row)
    return results


def categories(entries: Iterable[Mapping[str, str]]) -> list[str]:
    return sorted({row.get("category", "").strip() for row in entries if row.get("category", "").strip()}, key=str.casefold)
