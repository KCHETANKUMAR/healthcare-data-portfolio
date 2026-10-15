import unittest
from pathlib import Path

from analytics import parse_csv
from data_quality import inspect_quality


class QualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "sample_data" / "adverse_event_reports.csv"
        cls.rows = parse_csv(path.read_bytes())
        cls.issues = inspect_quality(cls.rows)

    def test_sample_reports_all_documented_issue_types(self):
        types = {issue["issue_type"] for issue in self.issues}
        self.assertIn("Duplicate report ID", types)
        self.assertIn("Missing report ID", types)
        self.assertIn("Missing required field", types)
        self.assertIn("Invalid date", types)
        self.assertIn("Unrecognized seriousness", types)
        self.assertIn("Unrecognized outcome", types)
        self.assertIn("Invalid follow-up value", types)

    def test_duplicate_id_issue_is_attached_to_both_rows(self):
        duplicates = [item for item in self.issues if item["issue_type"] == "Duplicate report ID"]
        self.assertEqual(len(duplicates), 2)
        self.assertEqual({item["report_id"] for item in duplicates}, {"SYN-004"})

    def test_missing_and_invalid_fields_identify_source_row_and_value(self):
        invalid_date = next(item for item in self.issues if item["issue_type"] == "Invalid date")
        self.assertEqual(invalid_date["original_value"], "2025-02-30")
        self.assertGreater(invalid_date["data_row"], 0)
        invalid_category = next(item for item in self.issues if item["issue_type"] == "Unrecognized seriousness")
        self.assertEqual(invalid_category["original_value"], "serious")

    def test_quality_does_not_modify_source_values(self):
        row = self.rows[26]
        before = dict(row)
        inspect_quality([row])
        self.assertEqual(row, before)

    def test_empty_dataset_has_no_issues(self):
        self.assertEqual(inspect_quality([]), [])


if __name__ == "__main__":
    unittest.main()
