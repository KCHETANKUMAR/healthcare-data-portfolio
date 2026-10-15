import csv
import io
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from main import main
from validator import REPORT_FIELDS, REQUIRED_FIELDS, validate_csv, validate_records, write_report


def valid_record(participant_id="T001"):
    return {
        "participant_id": participant_id,
        "site_id": "SITE-01",
        "age": "34",
        "sex": "Female",
        "informed_consent": "Yes",
        "visit_date": "2025-04-15",
        "systolic_bp": "120",
        "diastolic_bp": "80",
        "adverse_event_reported": "No",
    }


def validate_one(record):
    return validate_records([record], REQUIRED_FIELDS)


class ValidatorTests(unittest.TestCase):
    def test_valid_record_has_no_issues(self):
        result = validate_one(valid_record())
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["records_without_detected_issues"], 1)

    def test_missing_required_value_detected_with_csv_row_number(self):
        record = valid_record()
        record["site_id"] = ""
        issues = validate_one(record)["issues"]
        finding = next(issue for issue in issues if issue["issue_type"] == "missing_required_value")
        self.assertEqual((finding["row_number"], finding["field_name"]), (2, "site_id"))

    def test_duplicate_ids_flag_each_repeated_record(self):
        result = validate_records([valid_record("DUP"), valid_record("DUP")], REQUIRED_FIELDS)
        duplicates = [issue for issue in result["issues"] if issue["issue_type"] == "duplicate_participant_id"]
        self.assertEqual([issue["row_number"] for issue in duplicates], [2, 3])
        self.assertEqual(result["unique_participant_ids"], 1)

    def test_invalid_date_detected(self):
        record = valid_record()
        record["visit_date"] = "2025-02-30"
        self.assertIn("invalid_date", {issue["issue_type"] for issue in validate_one(record)["issues"]})

    def test_non_numeric_and_out_of_range_age_detected(self):
        for age, expected in (("adult", "age_not_numeric"), ("17", "age_out_of_training_range")):
            with self.subTest(age=age):
                record = valid_record()
                record["age"] = age
                self.assertIn(expected, {issue["issue_type"] for issue in validate_one(record)["issues"]})

    def test_invalid_consent_and_adverse_event_values_detected(self):
        record = valid_record()
        record["informed_consent"] = "Pending"
        record["adverse_event_reported"] = "Maybe"
        issues = validate_one(record)["issues"]
        self.assertEqual(sum(issue["issue_type"] == "invalid_response" for issue in issues), 2)

    def test_out_of_range_blood_pressure_flagged_for_review(self):
        record = valid_record()
        record["systolic_bp"] = "251"
        record["diastolic_bp"] = "151"
        issues = validate_one(record)["issues"]
        bp_issues = [issue for issue in issues if issue["issue_type"] == "blood_pressure_out_of_training_range"]
        self.assertEqual({issue["field_name"] for issue in bp_issues}, {"systolic_bp", "diastolic_bp"})
        self.assertTrue(all("not a diagnosis" in issue["explanation"] for issue in bp_issues))

    def test_missing_required_header_reported(self):
        headers = [field for field in REQUIRED_FIELDS if field != "site_id"]
        result = validate_records([valid_record()], headers)
        finding = next(issue for issue in result["issues"] if issue["issue_type"] == "missing_header")
        self.assertEqual((finding["row_number"], finding["field_name"]), (1, "site_id"))

    def test_empty_report_still_has_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.csv"
            write_report([], path)
            with path.open("r", encoding="utf-8", newline="") as report_file:
                rows = list(csv.reader(report_file))
            self.assertEqual(rows, [list(REPORT_FIELDS)])

    def test_csv_validation_does_not_mutate_source_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            record = valid_record()
            record["age"] = "17"
            with path.open("w", encoding="utf-8", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=REQUIRED_FIELDS)
                writer.writeheader()
                writer.writerow(record)
            result = validate_csv(path)
            self.assertEqual(record["age"], "17")
            self.assertEqual(result["issues"][0]["original_value"], "17")

    def test_cli_refuses_to_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.csv"
            original = "participant_id,age\nP001,17\n"
            path.write_text(original, encoding="utf-8")
            error_output = io.StringIO()
            with redirect_stderr(error_output), self.assertRaises(SystemExit) as raised:
                main(["--input", str(path), "--output", str(path)])
            self.assertEqual(raised.exception.code, 2)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
