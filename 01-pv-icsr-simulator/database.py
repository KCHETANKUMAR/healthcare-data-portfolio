"""SQLite storage for the educational PV ICSR simulator."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

DEFAULT_DB = Path(__file__).with_name("pv_simulator.db")
YES_NO_UNKNOWN = ("Yes", "No", "Unknown")
CASE_FIELDS = ("patient_identifiable", "reporter_identifiable", "product_identified", "reaction_reported")


class ClosingConnection(sqlite3.Connection):
    """Connection context manager that also closes its handle on exit."""
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()


def connect(db_path: str | Path = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def meets_minimum(case: dict[str, Any] | sqlite3.Row) -> bool:
    return all(case[field] == "Yes" for field in CASE_FIELDS)


def initialize_database(db_path: str | Path = DEFAULT_DB) -> None:
    with connect(db_path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL UNIQUE,
            patient_identifiable TEXT NOT NULL CHECK(patient_identifiable IN ('Yes','No','Unknown')),
            reporter_identifiable TEXT NOT NULL CHECK(reporter_identifiable IN ('Yes','No','Unknown')),
            product_identified TEXT NOT NULL CHECK(product_identified IN ('Yes','No','Unknown')),
            reaction_reported TEXT NOT NULL CHECK(reaction_reported IN ('Yes','No','Unknown')),
            event_description TEXT NOT NULL,
            patient_age TEXT, patient_sex TEXT, product_name TEXT,
            onset_date TEXT, received_date TEXT NOT NULL,
            seriousness TEXT NOT NULL DEFAULT '', outcome TEXT NOT NULL DEFAULT '', source_notes TEXT NOT NULL DEFAULT '',
            validation_status TEXT NOT NULL CHECK(validation_status IN ('Meets minimum criteria','Does not yet meet minimum criteria')),
            follow_up_needed INTEGER NOT NULL CHECK(follow_up_needed IN (0,1)),
            fictional INTEGER NOT NULL DEFAULT 0 CHECK(fictional IN (0,1)),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS follow_ups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL REFERENCES cases(case_id) ON DELETE CASCADE,
            missing_field TEXT NOT NULL, question TEXT NOT NULL, date_raised TEXT NOT NULL,
            response_received TEXT, response_notes TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL CHECK(status IN ('Open','Answered','Closed')) DEFAULT 'Open',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS qc_checklist (
            case_id TEXT PRIMARY KEY REFERENCES cases(case_id) ON DELETE CASCADE,
            source_transcribed INTEGER NOT NULL DEFAULT 0 CHECK(source_transcribed IN (0,1)),
            description_preserved INTEGER NOT NULL DEFAULT 0 CHECK(description_preserved IN (0,1)),
            criteria_reviewed INTEGER NOT NULL DEFAULT 0 CHECK(criteria_reviewed IN (0,1)),
            facts_distinguished INTEGER NOT NULL DEFAULT 0 CHECK(facts_distinguished IN (0,1)),
            seriousness_checked INTEGER NOT NULL DEFAULT 0 CHECK(seriousness_checked IN (0,1)),
            followup_reviewed INTEGER NOT NULL DEFAULT 0 CHECK(followup_reviewed IN (0,1)),
            dates_checked INTEGER NOT NULL DEFAULT 0 CHECK(dates_checked IN (0,1)),
            final_review INTEGER NOT NULL DEFAULT 0 CHECK(final_review IN (0,1)),
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """)


def create_case(data: dict[str, Any], db_path: str | Path = DEFAULT_DB) -> str:
    values = dict(data)
    values["validation_status"] = "Meets minimum criteria" if meets_minimum(values) else "Does not yet meet minimum criteria"
    values["follow_up_needed"] = int(not meets_minimum(values))
    fields = ["case_id", *CASE_FIELDS, "event_description", "patient_age", "patient_sex", "product_name", "onset_date", "received_date", "seriousness", "outcome", "source_notes", "validation_status", "follow_up_needed", "fictional"]
    with connect(db_path) as conn:
        conn.execute(f"INSERT INTO cases ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [values.get(f, 0 if f == "fictional" else "") for f in fields])
        conn.execute("INSERT INTO qc_checklist(case_id) VALUES (?)", (values["case_id"],))
    return values["case_id"]


def get_cases(db_path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM cases ORDER BY id DESC")]


def get_case(case_id: str, db_path: str | Path = DEFAULT_DB) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()
        return dict(row) if row else None


def update_case(case_id: str, data: dict[str, Any], db_path: str | Path = DEFAULT_DB) -> None:
    values = dict(data)
    values["validation_status"] = "Meets minimum criteria" if meets_minimum(values) else "Does not yet meet minimum criteria"
    values["follow_up_needed"] = int(not meets_minimum(values))
    fields = [*CASE_FIELDS, "event_description", "patient_age", "patient_sex", "product_name", "onset_date", "received_date", "seriousness", "outcome", "source_notes", "validation_status", "follow_up_needed"]
    with connect(db_path) as conn:
        conn.execute(f"UPDATE cases SET {','.join(f'{f}=?' for f in fields)}, updated_at=CURRENT_TIMESTAMP WHERE case_id=?", [values.get(f, "") for f in fields] + [case_id])


def add_follow_up(case_id: str, data: dict[str, Any], db_path: str | Path = DEFAULT_DB) -> int:
    with connect(db_path) as conn:
        cur = conn.execute("INSERT INTO follow_ups(case_id,missing_field,question,date_raised,response_received,response_notes,status) VALUES (?,?,?,?,?,?,?)", (case_id, data["missing_field"], data["question"], data["date_raised"], data.get("response_received") or None, data.get("response_notes", ""), data.get("status", "Open")))
        return int(cur.lastrowid)


def get_follow_ups(case_id: str, db_path: str | Path = DEFAULT_DB) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM follow_ups WHERE case_id=? ORDER BY id", (case_id,))]


def update_follow_up(follow_up_id: int, data: dict[str, Any], db_path: str | Path = DEFAULT_DB) -> None:
    with connect(db_path) as conn:
        conn.execute("UPDATE follow_ups SET missing_field=?,question=?,date_raised=?,response_received=?,response_notes=?,status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (data["missing_field"], data["question"], data["date_raised"], data.get("response_received") or None, data.get("response_notes", ""), data["status"], follow_up_id))


QC_FIELDS = ("source_transcribed", "description_preserved", "criteria_reviewed", "facts_distinguished", "seriousness_checked", "followup_reviewed", "dates_checked", "final_review")


def get_qc(case_id: str, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM qc_checklist WHERE case_id=?", (case_id,)).fetchone()
        return dict(row) if row else {}


def save_qc(case_id: str, data: dict[str, Any], db_path: str | Path = DEFAULT_DB) -> None:
    with connect(db_path) as conn:
        conn.execute(f"INSERT INTO qc_checklist(case_id,{','.join(QC_FIELDS)}) VALUES ({','.join('?' for _ in range(len(QC_FIELDS)+1))}) ON CONFLICT(case_id) DO UPDATE SET {','.join(f'{f}=excluded.{f}' for f in QC_FIELDS)}, updated_at=CURRENT_TIMESTAMP", [case_id, *[int(bool(data.get(f, False))) for f in QC_FIELDS]])


def insert_sample_data(db_path: str | Path = DEFAULT_DB) -> int:
    samples = [
        dict(case_id="SIM-0001", patient_identifiable="Yes", reporter_identifiable="Yes", product_identified="Yes", reaction_reported="Yes", event_description="Reporter described a headache after use of MedA.", patient_age="", patient_sex="Unknown", product_name="MedA", onset_date="", received_date="2026-01-10", seriousness="Not reported", outcome="Recovered", source_notes="Fictional training case; optional details omitted.", fictional=1),
        dict(case_id="SIM-0002", patient_identifiable="Yes", reporter_identifiable="Yes", product_identified="Yes", reaction_reported="Yes", event_description="Consumer reported a skin rash after use of MedB.", patient_age="", patient_sex="Unknown", product_name="MedB", onset_date="", received_date="2026-02-15", seriousness="Not reported", outcome="Unknown", source_notes="Fictional training case; onset and recovery details unknown.", fictional=1),
        dict(case_id="SIM-0003", patient_identifiable="No", reporter_identifiable="No", product_identified="No", reaction_reported="Yes", event_description="Someone felt dizzy after taking medicine.", patient_age="", patient_sex="Unknown", product_name="", onset_date="", received_date="2026-03-20", seriousness="Not reported", outcome="Unknown", source_notes="Fictional training case; patient, reporter, and product identification missing.", fictional=1),
    ]
    added = 0
    with connect(db_path) as conn:
        for s in samples:
            if conn.execute("SELECT 1 FROM cases WHERE case_id=?", (s["case_id"],)).fetchone():
                continue
            s["validation_status"] = "Meets minimum criteria" if meets_minimum(s) else "Does not yet meet minimum criteria"
            s["follow_up_needed"] = int(not meets_minimum(s))
            fields = ["case_id", *CASE_FIELDS, "event_description", "patient_age", "patient_sex", "product_name", "onset_date", "received_date", "seriousness", "outcome", "source_notes", "validation_status", "follow_up_needed", "fictional"]
            conn.execute(f"INSERT INTO cases ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})", [s.get(f, "") for f in fields])
            conn.execute("INSERT INTO qc_checklist(case_id) VALUES (?)", (s["case_id"],))
            added += 1
    return added
