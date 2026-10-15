"""Validation and screening logic for the educational eligibility screener."""

import csv
import io
import json
import math


FIELDS = {
    "participant_id": "text",
    "age": "number",
    "bmi": "number",
    "smoking_status": "text",
    "medical_history_flag": "text",
    "consent_status": "text",
}
REQUIRED_CSV_HEADERS = set(FIELDS)
OUTCOMES = {"MET", "NOT MET", "UNKNOWN"}
MEETS = "MEETS CONFIGURED CRITERIA"
DOES_NOT_MEET = "DOES NOT MEET CONFIGURED CRITERIA"
REVIEW = "REQUIRES REVIEW"


class ScreeningError(ValueError):
    """Raised when a study configuration or participant file is invalid."""


def load_config(source):
    """Parse JSON configuration text or return a configuration dictionary."""
    try:
        config = json.loads(source) if isinstance(source, str) else source
    except (json.JSONDecodeError, TypeError) as exc:
        raise ScreeningError(f"Configuration is not valid JSON: {exc}") from exc
    validate_config(config)
    return config


def validate_config(config):
    if not isinstance(config, dict) or not isinstance(config.get("study_name"), str) or not config["study_name"].strip():
        raise ScreeningError("Configuration must include a non-empty study_name.")
    criteria = config.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        raise ScreeningError("Configuration must include a non-empty criteria list.")
    names = set()
    for index, criterion in enumerate(criteria, start=1):
        where = f"Criterion {index}"
        if not isinstance(criterion, dict):
            raise ScreeningError(f"{where} must be an object.")
        for key in ("name", "type", "field", "operator", "expected", "explanation"):
            if key not in criterion:
                raise ScreeningError(f"{where} is missing {key!r}.")
        name = criterion["name"]
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ScreeningError(f"{where} needs a unique, non-empty name.")
        names.add(name)
        if criterion["type"] not in ("inclusion", "exclusion"):
            raise ScreeningError(f"{where} type must be inclusion or exclusion.")
        if not isinstance(criterion["explanation"], str) or not criterion["explanation"].strip():
            raise ScreeningError(f"{where} explanation must be non-empty text.")
        field = criterion["field"]
        if field not in FIELDS:
            raise ScreeningError(f"{where} uses unknown field {field!r}.")
        operator = criterion["operator"]
        allowed = {"number": {">=", "<=", ">", "<", "==", "between"},
                   "text": {"==", "!=", "in", "not_in", "contains"}}[FIELDS[field]]
        if operator not in allowed:
            raise ScreeningError(f"{where} uses unsupported operator {operator!r} for {field}.")
        expected = criterion["expected"]
        if operator == "between":
            if (not isinstance(expected, list) or len(expected) != 2 or
                    any(not _finite_number(v) for v in expected) or float(expected[0]) > float(expected[1])):
                raise ScreeningError(f"{where} expected value for between must be two ordered numbers.")
        elif FIELDS[field] == "number":
            if not _finite_number(expected):
                raise ScreeningError(f"{where} expected value must be a finite number.")
        elif operator in {"in", "not_in"}:
            if not isinstance(expected, list) or not expected or any(not isinstance(v, str) for v in expected):
                raise ScreeningError(f"{where} expected value must be a non-empty list of strings.")
        elif not isinstance(expected, str) or not expected:
            raise ScreeningError(f"{where} expected value must be non-empty text.")
    return True


def _finite_number(value):
    if isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def parse_participant_csv(content):
    """Validate a CSV string and return participant rows without repairing data."""
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ScreeningError("CSV must be encoded as UTF-8.") from exc
    try:
        reader = csv.DictReader(io.StringIO(content, newline=""))
        headers = reader.fieldnames
    except (csv.Error, TypeError) as exc:
        raise ScreeningError(f"Could not read CSV: {exc}") from exc
    if not headers:
        raise ScreeningError("CSV is empty or has no header row.")
    if len(headers) != len(set(headers)):
        raise ScreeningError("CSV contains duplicate column headers.")
    missing = REQUIRED_CSV_HEADERS - set(headers)
    if missing:
        raise ScreeningError("CSV is missing required columns: " + ", ".join(sorted(missing)))
    participants, seen = [], set()
    for line, row in enumerate(reader, start=2):
        if None in row:
            raise ScreeningError(f"CSV row {line} has more values than the header.")
        if any(value is None for value in row.values()):
            raise ScreeningError(f"CSV row {line} has fewer values than the header; check for missing delimiters/columns.")
        if not any((value or "").strip() for value in row.values()):
            continue
        participant_id = (row.get("participant_id") or "").strip()
        if not participant_id:
            raise ScreeningError(f"CSV row {line} is missing participant_id.")
        if participant_id in seen:
            raise ScreeningError(f"Duplicate participant ID {participant_id!r} on row {line}.")
        seen.add(participant_id)
        participant = {field: (row.get(field) or "").strip() for field in FIELDS}
        participant["notes"] = (row.get("notes") or "").strip()
        participant["data_warnings"] = []
        for field in ("age", "bmi"):
            value = participant[field]
            if value and not _finite_number(value):
                participant["data_warnings"].append(f"{field} is not a valid finite number")
        participants.append(participant)
    if not participants:
        raise ScreeningError("CSV contains no participant rows.")
    return participants


def _evaluate(condition, actual, expected):
    op = condition["operator"]
    if op == ">=": return actual >= float(expected)
    if op == "<=": return actual <= float(expected)
    if op == ">": return actual > float(expected)
    if op == "<": return actual < float(expected)
    if op == "==": return actual == (float(expected) if isinstance(actual, float) else expected)
    if op == "!=": return actual != expected
    if op == "between": return float(expected[0]) <= actual <= float(expected[1])
    if op == "in": return actual in expected
    if op == "not_in": return actual not in expected
    if op == "contains": return expected.casefold() in actual.casefold()
    raise ScreeningError(f"Unsupported operator {op!r}.")


def screen_participant(participant, config):
    validate_config(config)
    results = []
    for criterion in config["criteria"]:
        field = criterion["field"]
        raw = participant.get(field)
        observed = "" if raw is None else str(raw)
        outcome = "UNKNOWN"
        if isinstance(raw, str) and raw.strip():
            try:
                actual = float(raw) if FIELDS[field] == "number" else raw.strip()
                if FIELDS[field] == "number" and not math.isfinite(actual):
                    raise ValueError
                outcome = "MET" if _evaluate(criterion, actual, criterion["expected"]) else "NOT MET"
            except (TypeError, ValueError, OverflowError):
                outcome = "UNKNOWN"
        results.append({**criterion, "observed": observed, "outcome": outcome})
    disqualified = any((r["type"] == "inclusion" and r["outcome"] == "NOT MET") or
                       (r["type"] == "exclusion" and r["outcome"] == "MET") for r in results)
    unknown = any(r["outcome"] == "UNKNOWN" for r in results)
    status = DOES_NOT_MEET if disqualified else REVIEW if unknown else MEETS
    reason = ("At least one configured criterion disqualifies this fictional participant." if disqualified else
              "At least one criterion could not be assessed; manual review is needed." if unknown else
              "All configured criteria were assessable and none disqualified the participant.")
    return {"participant_id": str(participant.get("participant_id", "")), "status": status,
            "requires_review": unknown, "reason": reason, "criteria": results}


def screen_participants(participants, config):
    validate_config(config)
    return [screen_participant(person, config) for person in participants]


def report_csv(results):
    """Return criterion-level report CSV text suitable for a download."""
    output = io.StringIO(newline="")
    fields = ["participant_id", "overall_status", "criterion_name", "criterion_type", "field",
              "operator", "expected", "observed", "outcome", "explanation"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for result in results:
        for criterion in result["criteria"]:
            writer.writerow({"participant_id": result["participant_id"], "overall_status": result["status"],
                             "criterion_name": criterion["name"], "criterion_type": criterion["type"],
                             "field": criterion["field"], "operator": criterion["operator"],
                             "expected": json.dumps(criterion["expected"], ensure_ascii=False),
                             "observed": criterion["observed"], "outcome": criterion["outcome"],
                             "explanation": criterion["explanation"]})
    return output.getvalue()
