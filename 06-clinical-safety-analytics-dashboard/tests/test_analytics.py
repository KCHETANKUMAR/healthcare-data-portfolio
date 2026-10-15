import csv
import io
import unittest
from pathlib import Path

from analytics import (DataError, counts_by, export_rows_csv, filter_rows,
                       monthly_counts, overview_metrics, parse_csv)

BASE = Path(__file__).resolve().parents[1]


class AnalyticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = parse_csv((BASE / "sample_data" / "adverse_event_reports.csv").read_bytes())

    def test_sample_loads_fifty_rows(self):
        self.assertEqual(len(self.rows), 50)

    def test_row_and_unique_id_metrics_are_distinct(self):
        metrics = overview_metrics(self.rows)
        self.assertEqual(metrics["total_rows"], 50)
        self.assertEqual(metrics["unique_report_ids"], 48)

    def test_seriousness_and_outcome_breakdowns(self):
        serious = counts_by(self.rows, "seriousness")
        outcomes = counts_by(self.rows, "outcome")
        self.assertEqual(serious["Serious"], 12)
        self.assertIn("(Missing)", outcomes)
        self.assertIn("Resolved", outcomes)

    def test_monthly_grouping_ignores_invalid_and_missing_dates(self):
        result = monthly_counts(self.rows)
        self.assertTrue(result)
        self.assertEqual(sum(result.values()), 48)
        self.assertEqual(list(result), sorted(result))

    def test_date_range_and_categories_filter(self):
        result = filter_rows(self.rows, {"start_date": "2025-01-01", "end_date": "2025-01-31", "seriousness": "Serious"})
        self.assertTrue(result)
        self.assertTrue(all(r["seriousness"] == "Serious" and "2025-01" in r["report_date"] for r in result))

    def test_search_filters_case_insensitively(self):
        result = filter_rows(self.rows, search="democompound-a")
        self.assertTrue(result)
        self.assertTrue(all("DemoCompound-A" in row["suspect_product"] for row in result))

    def test_missing_category_can_be_selected(self):
        result = filter_rows(self.rows, {"event_term": "__MISSING__"})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event_term"], "")

    def test_invalid_date_filter_and_reversed_range_rejected(self):
        with self.assertRaises(DataError): filter_rows(self.rows, {"start_date": "not-date"})
        with self.assertRaises(DataError): filter_rows(self.rows, {"start_date": "2025-02-01", "end_date": "2025-01-01"})

    def test_csv_schema_missing_duplicate_and_short_rows(self):
        with self.assertRaisesRegex(DataError, "Missing required columns"):
            parse_csv("report_id,event_term\nA,Headache\n")
        with self.assertRaisesRegex(DataError, "duplicate column"):
            parse_csv("report_id,report_id\nA,B\n")
        with self.assertRaisesRegex(DataError, "fewer values"):
            parse_csv("report_id,report_date,event_term,seriousness,outcome,suspect_product,age_group,country,report_source,follow_up_received\nA,2025-01-01\n")
        with self.assertRaisesRegex(DataError, "Malformed CSV"):
            parse_csv('report_id,report_date,event_term,seriousness,outcome,suspect_product,age_group,country,report_source,follow_up_received\n"unterminated,2025-01-01,x,x,x,x,x,x,x,x\n')

    def test_empty_dataset_behaviors_and_export(self):
        self.assertEqual(overview_metrics([])["total_rows"], 0)
        self.assertEqual(monthly_counts([]), {})
        self.assertEqual(filter_rows([], {}), [])
        parsed = list(csv.DictReader(io.StringIO(export_rows_csv([]))))
        self.assertEqual(parsed, [])

    def test_filtered_csv_export_contains_only_filtered_rows(self):
        filtered = filter_rows(self.rows, {"suspect_product": "DemoCompound-A"})
        exported = list(csv.DictReader(io.StringIO(export_rows_csv(filtered))))
        self.assertTrue(exported)
        self.assertTrue(all(row["suspect_product"] == "DemoCompound-A" for row in exported))


if __name__ == "__main__":
    unittest.main()
