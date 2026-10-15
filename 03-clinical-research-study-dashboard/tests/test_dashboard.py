import csv
import tempfile
import unittest
from collections import Counter
from datetime import date
from pathlib import Path

from dashboard import (
    DashboardInputError,
    PARTICIPANT_FIELDS,
    VISIT_FIELDS,
    analyze_data,
    load_csv,
    render_dashboard,
    write_dashboard,
)


def participant(pid="P001", **updates):
    row = {
        "participant_id": pid,
        "site_id": "SITE-A",
        "enrollment_date": "2026-01-01",
        "study_status": "Enrolled",
        "age": "35",
        "sex": "Female",
    }
    row.update(updates)
    return row


def visit(visit_id="V001", pid="P001", **updates):
    row = {
        "visit_id": visit_id,
        "participant_id": pid,
        "visit_name": "Screening",
        "planned_date": "2026-01-05",
        "actual_date": "2026-01-05",
        "visit_status": "Completed",
    }
    row.update(updates)
    return row


class DashboardTests(unittest.TestCase):
    def test_loading_valid_csv_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "participants.csv"
            with path.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=PARTICIPANT_FIELDS)
                writer.writeheader()
                writer.writerow(participant())
            self.assertEqual(load_csv(path, PARTICIPANT_FIELDS), [participant()])

    def test_missing_required_headers_raise_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("participant_id,site_id\nP001,SITE-A\n", encoding="utf-8")
            with self.assertRaisesRegex(DashboardInputError, "missing required CSV headers"):
                load_csv(path, PARTICIPANT_FIELDS)

    def test_missing_values_are_counted_and_warned(self):
        row = participant(age="", sex="")
        result = analyze_data(
            [row],
            [visit(actual_date="", visit_status="Scheduled")],
            as_of=date(2026, 2, 1),
        )
        missing = [warning for warning in result["warnings"] if warning["warning_type"] == "missing_value"]
        self.assertEqual(result["participant_missing_fields"], 2)
        self.assertEqual(result["visit_missing_fields"], 0)
        self.assertEqual({warning["field"] for warning in missing}, {"age", "sex"})

    def test_duplicate_participant_ids_flag_each_row(self):
        result = analyze_data([participant(), participant()], [], as_of=date(2026, 1, 1))
        duplicates = [warning for warning in result["warnings"] if warning["warning_type"] == "duplicate_id"]
        self.assertEqual([warning["row_number"] for warning in duplicates], [2, 3])

    def test_duplicate_visit_ids_flag_each_row(self):
        result = analyze_data([participant()], [visit(), visit()], as_of=date(2026, 1, 1))
        duplicates = [warning for warning in result["warnings"] if warning["warning_type"] == "duplicate_id"]
        self.assertEqual(len(duplicates), 2)
        self.assertTrue(all(warning["dataset"] == "visits" for warning in duplicates))

    def test_invalid_dates_are_reported(self):
        result = analyze_data(
            [participant(enrollment_date="2026-02-30")],
            [visit(planned_date="2026-02-30")],
            as_of=date(2026, 3, 1),
        )
        invalid = [warning for warning in result["warnings"] if warning["warning_type"] == "invalid_date"]
        self.assertEqual({warning["field"] for warning in invalid}, {"enrollment_date", "planned_date"})

    def test_unknown_participant_visit_is_reported(self):
        result = analyze_data([participant()], [visit(pid="P999")], as_of=date(2026, 1, 1))
        unknown = [warning for warning in result["warnings"] if warning["warning_type"] == "unknown_participant"]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0]["value"], "P999")

    def test_counts_by_site_and_status(self):
        participants = [participant("P001", study_status="Enrolled"), participant("P002", site_id="SITE-B", study_status="Completed")]
        visits = [visit("V001", "P001", visit_status="Completed"), visit("V002", "P002", visit_status="Missed")]
        result = analyze_data(participants, visits, as_of=date(2026, 1, 1))
        self.assertEqual(result["participant_by_site"], Counter({"SITE-A": 1, "SITE-B": 1}))
        self.assertEqual(result["participant_by_status"], Counter({"Enrolled": 1, "Completed": 1}))
        self.assertEqual(result["visits_by_status"], Counter({"Completed": 1, "Missed": 1}))
        self.assertEqual(result["visits_by_site_status"][("SITE-B", "Missed")], 1)

    def test_overdue_visit_rule_with_fixed_reference_date(self):
        participants = [participant()]
        visits = [
            visit("V001", visit_status="Scheduled", planned_date="2026-01-01", actual_date=""),
            visit("V002", visit_status="Scheduled", planned_date="2026-02-01", actual_date=""),
            visit("V003", visit_status="Scheduled", planned_date="2026-01-01", actual_date="2026-01-02"),
            visit("V004", visit_status="Completed", planned_date="2026-01-01", actual_date="2026-01-02"),
            visit("V005", visit_status="Scheduled", planned_date="2026-02-30", actual_date=""),
        ]
        result = analyze_data(participants, visits, as_of=date(2026, 2, 1))
        self.assertEqual([item["visit_id"] for item in result["overdue_visits"]], ["V001"])

    def test_completion_percentage_denominator_is_all_visit_rows(self):
        result = analyze_data(
            [participant()],
            [visit("V001", visit_status="Completed"), visit("V002", visit_status="Scheduled", actual_date="")],
            as_of=date(2026, 1, 1),
        )
        self.assertEqual(result["completion_percentage"], 50.0)
        self.assertEqual(result["completion_denominator"], 2)

    def test_html_escapes_untrusted_csv_values(self):
        malicious = '<script>alert("x")</script>'
        result = analyze_data([participant(site_id=malicious)], [visit()], as_of=date(2026, 1, 1))
        html = render_dashboard(result, generated_on=date(2026, 1, 2))
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;", html)
        self.assertNotIn(malicious, html)

    def test_successful_html_generation(self):
        result = analyze_data([participant()], [visit()], as_of=date(2026, 1, 10))
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "dashboard.html"
            write_dashboard(result, output, generated_on=date(2026, 1, 11))
            document = output.read_text(encoding="utf-8")
            self.assertTrue(document.startswith("<!doctype html>"))
            self.assertIn("Overdue scheduled visits", document)
            self.assertIn("Data-quality warnings", document)
            self.assertIn("Participant records", document)


if __name__ == "__main__":
    unittest.main()
