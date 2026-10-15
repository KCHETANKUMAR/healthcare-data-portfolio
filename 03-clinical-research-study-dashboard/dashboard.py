"""Load, summarize, and render fictional clinical research study data."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Iterable, Mapping

PARTICIPANT_FIELDS = (
    "participant_id", "site_id", "enrollment_date", "study_status", "age", "sex"
)
VISIT_FIELDS = (
    "visit_id", "participant_id", "visit_name", "planned_date", "actual_date", "visit_status"
)
PARTICIPANT_STATUSES = {"Screening", "Enrolled", "Completed", "Withdrawn"}
VISIT_STATUSES = {"Scheduled", "Completed", "Missed", "Cancelled"}


class DashboardInputError(ValueError):
    """Raised when an input CSV cannot be used with this dashboard."""


def load_csv(path: str | Path, required_headers: Iterable[str]) -> list[dict[str, str]]:
    """Read a UTF-8 CSV, preserving cell values and rejecting invalid headers."""
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file, strict=True)
        headers = list(reader.fieldnames or [])
        if not headers:
            raise DashboardInputError(f"{source} is empty or has no CSV header row.")
        repeated_headers = sorted({header for header in headers if headers.count(header) > 1})
        if repeated_headers:
            raise DashboardInputError(f"{source} has duplicate CSV headers: {', '.join(repeated_headers)}")
        missing = [header for header in required_headers if header not in headers]
        if missing:
            raise DashboardInputError(f"{source} is missing required CSV headers: {', '.join(missing)}")
        rows: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            if None in row:
                raise DashboardInputError(f"{source} has more values than headers on CSV row {line_number}.")
            rows.append({key: value if value is not None else "" for key, value in row.items()})
    return rows


def _value(row: Mapping[str, str], field: str) -> str:
    return str(row.get(field, "") or "").strip()


def _parse_iso_date(raw: str) -> date | None:
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == raw else None


def _warning(dataset: str, row_number: int, record_id: str, field: str,
             warning_type: str, value: str, message: str) -> dict[str, object]:
    return {
        "dataset": dataset,
        "row_number": row_number,
        "record_id": record_id,
        "field": field,
        "warning_type": warning_type,
        "value": value,
        "message": message,
    }


def analyze_data(
    participants: list[dict[str, str]],
    visits: list[dict[str, str]],
    as_of: date | None = None,
) -> dict[str, object]:
    """Calculate descriptive counts and manual-review warnings.

    Completion percentage uses all visit rows as its denominator:
    completed visit rows / total visit rows. It is a descriptive dataset
    summary, not a protocol-defined compliance measure.
    """
    reference_date = as_of or date.today()
    warnings: list[dict[str, object]] = []
    participant_ids = [_value(row, "participant_id") for row in participants]
    participant_counts = Counter(participant_ids)
    for index, row in enumerate(participants, start=2):
        participant_id = _value(row, "participant_id")
        for field in PARTICIPANT_FIELDS:
            value = _value(row, field)
            if not value:
                warnings.append(_warning(
                    "participants", index, participant_id, field, "missing_value", value,
                    f"Participant field '{field}' is blank; review the source record if applicable.",
                ))
        if participant_id and participant_counts[participant_id] > 1:
            warnings.append(_warning(
                "participants", index, participant_id, "participant_id", "duplicate_id", participant_id,
                "Participant ID appears more than once; confirm the source records manually.",
            ))
        raw_date = _value(row, "enrollment_date")
        if raw_date and _parse_iso_date(raw_date) is None:
            warnings.append(_warning(
                "participants", index, participant_id, "enrollment_date", "invalid_date", raw_date,
                "Enrollment date is not a valid ISO YYYY-MM-DD calendar date.",
            ))
        status = _value(row, "study_status")
        if status and status not in PARTICIPANT_STATUSES:
            warnings.append(_warning(
                "participants", index, participant_id, "study_status", "unexpected_status", status,
                "Study status is outside the sample's expected categories; review the source and study definitions.",
            ))

    known_ids = {participant_id for participant_id in participant_ids if participant_id}
    participant_by_id: dict[str, dict[str, str]] = {}
    for row in participants:
        pid = _value(row, "participant_id")
        if pid and pid not in participant_by_id:
            participant_by_id[pid] = row

    visit_ids = [_value(row, "visit_id") for row in visits]
    visit_counts = Counter(visit_ids)
    overdue_visits: list[dict[str, str]] = []
    for index, row in enumerate(visits, start=2):
        visit_id = _value(row, "visit_id")
        participant_id = _value(row, "participant_id")
        status = _value(row, "visit_status")
        planned_raw = _value(row, "planned_date")
        actual_raw = _value(row, "actual_date")
        for field in VISIT_FIELDS:
            value = _value(row, field)
            # Actual dates are not expected for visits that are not completed.
            if not value and not (field == "actual_date" and status in {"Scheduled", "Missed", "Cancelled"}):
                warnings.append(_warning(
                    "visits", index, visit_id, field, "missing_value", value,
                    f"Visit field '{field}' is blank; review the source record if applicable.",
                ))
        if visit_id and visit_counts[visit_id] > 1:
            warnings.append(_warning(
                "visits", index, visit_id, "visit_id", "duplicate_id", visit_id,
                "Visit ID appears more than once; confirm the source records manually.",
            ))
        if participant_id and participant_id not in known_ids:
            warnings.append(_warning(
                "visits", index, visit_id, "participant_id", "unknown_participant", participant_id,
                "Visit refers to a participant ID that is not present in the participant file.",
            ))
        if status and status not in VISIT_STATUSES:
            warnings.append(_warning(
                "visits", index, visit_id, "visit_status", "unexpected_status", status,
                "Visit status is outside the sample's expected categories; review the source and study definitions.",
            ))
        for field, raw in (("planned_date", planned_raw), ("actual_date", actual_raw)):
            if raw and _parse_iso_date(raw) is None:
                warnings.append(_warning(
                    "visits", index, visit_id, field, "invalid_date", raw,
                    f"{field.replace('_', ' ').capitalize()} is not a valid ISO YYYY-MM-DD calendar date.",
                ))

        planned = _parse_iso_date(planned_raw)
        if status == "Scheduled" and planned is not None and planned < reference_date and not actual_raw:
            participant = participant_by_id.get(participant_id, {})
            overdue_visits.append({
                "visit_id": visit_id,
                "participant_id": participant_id,
                "site_id": _value(participant, "site_id") or "(Missing site)",
                "visit_name": _value(row, "visit_name"),
                "planned_date": planned_raw,
            })

    participant_by_site = Counter(_value(row, "site_id") or "(Missing site)" for row in participants)
    participant_by_status = Counter(_value(row, "study_status") or "(Missing status)" for row in participants)
    visits_by_status = Counter(_value(row, "visit_status") or "(Missing status)" for row in visits)
    visits_by_site_status: Counter[tuple[str, str]] = Counter()
    for row in visits:
        pid = _value(row, "participant_id")
        participant = participant_by_id.get(pid)
        site = _value(participant, "site_id") if participant else "(Unknown participant)"
        visits_by_site_status[(site or "(Missing site)", _value(row, "visit_status") or "(Missing status)")] += 1

    completed = visits_by_status["Completed"]
    visit_total = len(visits)
    completion_pct = (completed / visit_total * 100) if visit_total else 0.0
    participant_missing = sum(1 for warning in warnings if warning["dataset"] == "participants" and warning["warning_type"] == "missing_value")
    visit_missing = sum(1 for warning in warnings if warning["dataset"] == "visits" and warning["warning_type"] == "missing_value")

    return {
        "reference_date": reference_date,
        "participants": participants,
        "visits": visits,
        "participant_count": len(participants),
        "visit_count": visit_total,
        "completed_visits": completed,
        "missed_visits": visits_by_status["Missed"],
        "overdue_visits": overdue_visits,
        "participant_by_site": participant_by_site,
        "participant_by_status": participant_by_status,
        "visits_by_status": visits_by_status,
        "visits_by_site_status": visits_by_site_status,
        "completion_percentage": completion_pct,
        "completion_denominator": visit_total,
        "participant_missing_fields": participant_missing,
        "visit_missing_fields": visit_missing,
        "warnings": warnings,
    }


def _e(value: object) -> str:
    """HTML-escape every value sourced from CSV or rendered as text."""
    return escape(str(value), quote=True)


def _bar_table(title: str, counts: Mapping[str, int]) -> str:
    if not counts:
        return '<p class="muted">No records.</p>'
    maximum = max(counts.values()) or 1
    rows = []
    for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())):
        width = count / maximum * 100
        rows.append(
            f'<div class="bar-row"><span class="bar-label">{_e(label)}</span>'
            f'<span class="bar-track" role="img" aria-label="{_e(label)}: {count}">'
            f'<span class="bar-fill" style="width:{width:.1f}%"></span></span>'
            f'<strong class="bar-count">{count}</strong></div>'
        )
    return f'<div class="bar-list" aria-label="{_e(title)}">{"".join(rows)}</div>'


def _overdue_table(rows: list[dict[str, str]]) -> str:
    if not rows:
        return '<p class="empty-state">No overdue scheduled visits detected for this reference date.</p>'
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(row[key])}</td>" for key in ("visit_id", "participant_id", "site_id", "visit_name", "planned_date")) + "</tr>"
        for row in rows
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Visit ID</th><th>Participant ID</th>'
        '<th>Site</th><th>Visit</th><th>Planned date</th></tr></thead><tbody>' + body + '</tbody></table></div>'
    )


def _warnings_table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return '<p class="empty-state">No data-quality warnings detected by these checks.</p>'
    body = "".join(
        "<tr>" + "".join(f"<td>{_e(row[key])}</td>" for key in ("dataset", "row_number", "record_id", "field", "warning_type", "value", "message")) + "</tr>"
        for row in rows
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Dataset</th><th>CSV row</th><th>Record ID</th>'
        '<th>Field</th><th>Warning</th><th>Supplied value</th><th>Manual review note</th></tr></thead><tbody>'
        + body + '</tbody></table></div>'
    )


def render_dashboard(summary: Mapping[str, object], generated_on: date | None = None) -> str:
    """Render a self-contained, script-free and responsive HTML dashboard."""
    generated = generated_on or date.today()
    participants = summary["participants"]
    visits = summary["visits"]
    overdue = summary["overdue_visits"]
    warnings = summary["warnings"]
    participant_sites = summary["participant_by_site"]
    participant_statuses = summary["participant_by_status"]
    visit_statuses = summary["visits_by_status"]
    visits_by_site_status = summary["visits_by_site_status"]
    assert isinstance(participants, list) and isinstance(visits, list)
    assert isinstance(overdue, list) and isinstance(warnings, list)
    assert isinstance(participant_sites, Counter) and isinstance(participant_statuses, Counter)
    assert isinstance(visit_statuses, Counter) and isinstance(visits_by_site_status, Counter)

    site_status_html = "".join(
        f"<tr><td>{_e(site)}</td><td>{_e(status)}</td><td>{count}</td></tr>"
        for (site, status), count in sorted(visits_by_site_status.items())
    ) or '<tr><td colspan="3">No visits.</td></tr>'
    completion = float(summary["completion_percentage"])
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Offline educational dashboard for fictional clinical research study data">
  <title>Clinical Research Study Dashboard</title>
  <style>
    :root {{ color-scheme: light; --ink:#152a3a; --muted:#526579; --line:#d4dee7; --blue:#155e75; --teal:#0f766e; --paper:#f3f7fa; --white:#fff; --warn:#7c2d12; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; background:var(--paper); color:var(--ink); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
    header {{ background:#12344a; color:white; padding:2rem max(1rem,calc((100vw - 1180px)/2)); }}
    h1 {{ margin:0 0 .4rem; font-size:clamp(1.7rem,4vw,2.5rem); line-height:1.15; }} header p {{ margin:.5rem 0 0; max-width:850px; }}
    .disclaimer {{ margin-top:1rem; padding:.8rem 1rem; border-left:5px solid #fbbf24; border-radius:4px; background:#fff8e1; color:#422006; font-weight:700; }}
    main {{ max-width:1180px; margin:1.5rem auto; padding:0 1rem 2rem; }} .meta {{ color:var(--muted); display:flex; flex-wrap:wrap; gap:.5rem 1.5rem; margin:.75rem 0 1.25rem; }}
    .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:1rem; }} .card,.panel {{ background:var(--white); border:1px solid var(--line); border-radius:12px; box-shadow:0 2px 8px #18354a0b; }}
    .card {{ padding:1rem 1.1rem; }} .card h2 {{ margin:0; font-size:.92rem; color:var(--muted); font-weight:650; }} .metric {{ display:block; margin-top:.2rem; font-size:2rem; font-weight:750; color:var(--blue); }}
    .panel {{ padding:1.1rem; margin-top:1rem; }} h2.section {{ margin:0 0 .85rem; font-size:1.25rem; }} h3 {{ font-size:1rem; }} .grid-2 {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr)); gap:1rem; }}
    .bar-list {{ display:grid; gap:.65rem; }} .bar-row {{ display:grid; grid-template-columns:minmax(90px,1fr) minmax(90px,2fr) 2.5rem; gap:.7rem; align-items:center; }} .bar-label {{ overflow-wrap:anywhere; }} .bar-track {{ height:13px; background:#e5edf2; border-radius:20px; overflow:hidden; }} .bar-fill {{ display:block; height:100%; background:var(--teal); border-radius:20px; }} .bar-count {{ text-align:right; }}
    .table-wrap {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; font-size:.92rem; }} th,td {{ text-align:left; vertical-align:top; border-bottom:1px solid var(--line); padding:.65rem .55rem; overflow-wrap:anywhere; }} th {{ background:#eaf1f5; color:#18384d; }} .empty-state {{ color:#14532d; background:#ecfdf5; border-radius:8px; padding:.8rem; }} .muted {{ color:var(--muted); }}
    .note {{ color:var(--muted); font-size:.93rem; }} footer {{ max-width:1180px; padding:1rem; margin:0 auto 1rem; color:var(--muted); font-size:.88rem; }}
    @media(max-width:560px) {{ header {{ padding:1.3rem 1rem; }} main {{ margin-top:1rem; }} .bar-row {{ grid-template-columns:1fr 2fr 2rem; gap:.45rem; font-size:.9rem; }} .panel {{ padding:.8rem; }} }}
  </style>
</head>
<body>
  <header>
    <h1>Clinical Research Study Dashboard</h1>
    <p>Descriptive summaries of the supplied fictional participant and visit files.</p>
    <div class="disclaimer">Educational simulation only. This dashboard is not a validated clinical trial system and must not be used for medical decisions, participant management, or regulatory reporting.</div>
  </header>
  <main>
    <div class="meta"><span>Reference date: <strong>{_e(summary['reference_date'])}</strong></span><span>Report generated: <strong>{_e(generated)}</strong></span><span>Source rows: fictional training data</span></div>
    <section class="cards" aria-label="Study summary">
      <article class="card"><h2>Participant records</h2><span class="metric">{int(summary['participant_count'])}</span></article>
      <article class="card"><h2>Completed visits</h2><span class="metric">{int(summary['completed_visits'])}</span></article>
      <article class="card"><h2>Missed visits</h2><span class="metric">{int(summary['missed_visits'])}</span></article>
      <article class="card"><h2>Overdue scheduled visits</h2><span class="metric">{len(overdue)}</span></article>
      <article class="card"><h2>Data-quality warnings</h2><span class="metric">{len(warnings)}</span></article>
    </section>
    <div class="grid-2">
      <section class="panel"><h2 class="section">Participants by site</h2>{_bar_table('Participants by site', participant_sites)}</section>
      <section class="panel"><h2 class="section">Participants by study status</h2>{_bar_table('Participants by study status', participant_statuses)}</section>
      <section class="panel"><h2 class="section">Visits by status</h2>{_bar_table('Visits by status', visit_statuses)}</section>
      <section class="panel"><h2 class="section">Visit completion</h2><p><strong>{completion:.1f}%</strong> ({int(summary['completed_visits'])} completed / {int(summary['completion_denominator'])} total visit records).</p><p class="note">Denominator: every row in the supplied visit file, including scheduled, missed, and cancelled visits. This is a simple descriptive percentage, not a protocol-defined completion measure.</p></section>
    </div>
    <section class="panel"><h2 class="section">Visit counts by site and status</h2><div class="table-wrap"><table><thead><tr><th>Site</th><th>Status</th><th>Visit records</th></tr></thead><tbody>{site_status_html}</tbody></table></div></section>
    <section class="panel"><h2 class="section">Overdue scheduled visits</h2><p class="note">Simplified training rule: Scheduled, valid planned date before the reference date, and no actual date. Actual study definitions depend on the study protocol.</p>{_overdue_table(overdue)}</section>
    <section class="panel"><h2 class="section">Data-quality warnings for manual review</h2><p class="note">Missing fields counted: participant file {int(summary['participant_missing_fields'])}; visit file {int(summary['visit_missing_fields'])}. Missing actual dates for Scheduled, Missed, or Cancelled visits are not counted as missing because no completed visit date is expected by this exercise.</p>{_warnings_table(warnings)}</section>
    <section class="panel"><h2 class="section">Data summary and interpretation</h2><p>The summaries describe only the supplied fictional dataset. They are not evidence of actual study performance, participant status, or site performance. Warnings identify records for human review and do not certify that unflagged values are correct.</p><p class="note">No missing values were filled and no source records were modified. No clinical interpretation, treatment recommendation, causality assessment, or regulatory compliance conclusion is made.</p><p>Loaded {len(participants)} participant rows and {len(visits)} visit rows. Completion denominator: {int(summary['completion_denominator'])} visit rows.</p></section>
  </main>
  <footer>Offline, self-contained HTML. No scripts, external libraries, web server, or network access required.</footer>
</body>
</html>
'''


def write_dashboard(summary: Mapping[str, object], output_path: str | Path,
                    generated_on: date | None = None) -> None:
    html_document = render_dashboard(summary, generated_on=generated_on)
    Path(output_path).write_text(html_document, encoding="utf-8")
