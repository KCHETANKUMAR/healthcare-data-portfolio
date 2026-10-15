import csv
import io
import json
import unittest

from screening import (DOES_NOT_MEET, MEETS, REVIEW, ScreeningError, load_config,
                      parse_participant_csv, report_csv, screen_participant)


BASE = {"study_name": "Practice study", "criteria": [
    {"name": "Age", "type": "inclusion", "field": "age", "operator": "between", "expected": [18, 65], "explanation": "Within sample age range."},
    {"name": "BMI", "type": "inclusion", "field": "bmi", "operator": "between", "expected": [18.5, 32], "explanation": "Within sample BMI range."},
    {"name": "Consent", "type": "inclusion", "field": "consent_status", "operator": "==", "expected": "Yes", "explanation": "Sample consent flag."},
    {"name": "Smoking", "type": "exclusion", "field": "smoking_status", "operator": "==", "expected": "Current", "explanation": "Sample exclusion flag."},
]}


def person(**updates):
    value = {"participant_id": "DEMO-1", "age": "18", "bmi": "18.5", "consent_status": "Yes", "smoking_status": "Never", "medical_history_flag": "No"}
    value.update(updates)
    return value


class ScreeningTests(unittest.TestCase):
    def test_valid_config_and_participant_meet(self):
        config = load_config(json.dumps(BASE))
        result = screen_participant(person(), config)
        self.assertEqual(result["status"], MEETS)
        self.assertEqual([x["outcome"] for x in result["criteria"]], ["MET", "MET", "MET", "NOT MET"])

    def test_age_and_bmi_boundaries_are_inclusive(self):
        self.assertEqual(screen_participant(person(age="65", bmi="32"), BASE)["status"], MEETS)

    def test_inclusion_not_met_disqualifies(self):
        self.assertEqual(screen_participant(person(age="17"), BASE)["status"], DOES_NOT_MEET)

    def test_exclusion_met_disqualifies(self):
        result = screen_participant(person(smoking_status="Current"), BASE)
        self.assertEqual(result["status"], DOES_NOT_MEET)
        self.assertEqual(result["criteria"][-1]["outcome"], "MET")

    def test_exclusion_not_met_does_not_disqualify(self):
        self.assertEqual(screen_participant(person(smoking_status="Former"), BASE)["status"], MEETS)

    def test_missing_value_is_unknown(self):
        result = screen_participant(person(age=""), BASE)
        self.assertEqual(result["criteria"][0]["outcome"], "UNKNOWN")
        self.assertEqual(result["status"], REVIEW)

    def test_invalid_numeric_value_is_unknown(self):
        result = screen_participant(person(bmi="n/a"), BASE)
        self.assertEqual(result["criteria"][1]["outcome"], "UNKNOWN")
        self.assertEqual(result["status"], REVIEW)

    def test_multiple_criteria_report_unknown_and_disqualifier(self):
        result = screen_participant(person(age="", smoking_status="Current"), BASE)
        self.assertEqual(result["status"], DOES_NOT_MEET)
        self.assertTrue(result["requires_review"])

    def test_invalid_json_and_empty_criteria_rejected(self):
        with self.assertRaises(ScreeningError): load_config("{")
        invalid = {"study_name": "x", "criteria": []}
        with self.assertRaises(ScreeningError): load_config(invalid)

    def test_unsupported_operator_rejected(self):
        config = json.loads(json.dumps(BASE)); config["criteria"][0]["operator"] = "eval"
        with self.assertRaisesRegex(ScreeningError, "unsupported operator"): load_config(config)

    def test_unknown_field_rejected(self):
        config = json.loads(json.dumps(BASE)); config["criteria"][0]["field"] = "diagnosis"
        with self.assertRaisesRegex(ScreeningError, "unknown field"): load_config(config)

    def test_malformed_threshold_rejected(self):
        config = json.loads(json.dumps(BASE)); config["criteria"][0]["expected"] = [65, 18]
        with self.assertRaises(ScreeningError): load_config(config)

    def test_csv_headers_and_duplicate_ids(self):
        headers = "participant_id,age,bmi,smoking_status,medical_history_flag,consent_status\n"
        with self.assertRaisesRegex(ScreeningError, "missing required columns"):
            parse_participant_csv("participant_id,age\nA,20\n")
        with self.assertRaisesRegex(ScreeningError, "Duplicate participant ID"):
            parse_participant_csv(headers + "A,20,21,Never,No,Yes\nA,21,22,Never,No,Yes\n")

    def test_csv_invalid_numeric_is_preserved_as_warning(self):
        data = "participant_id,age,bmi,smoking_status,medical_history_flag,consent_status\nA,twenty,22,Never,No,Yes\n"
        row = parse_participant_csv(data)[0]
        self.assertEqual(row["age"], "twenty")
        self.assertTrue(row["data_warnings"])
        self.assertEqual(screen_participant(row, BASE)["criteria"][0]["outcome"], "UNKNOWN")

    def test_csv_malformed_row_rejected(self):
        data = "participant_id,age,bmi,smoking_status,medical_history_flag,consent_status\nA,20,21,Never,No,Yes,extra\n"
        with self.assertRaisesRegex(ScreeningError, "more values"):
            parse_participant_csv(data)
        short_data = "participant_id,age,bmi,smoking_status,medical_history_flag,consent_status\nA,20,21\n"
        with self.assertRaisesRegex(ScreeningError, "fewer values"):
            parse_participant_csv(short_data)

    def test_report_csv_contains_criterion_results(self):
        text = report_csv([screen_participant(person(), BASE)])
        rows = list(csv.DictReader(io.StringIO(text)))
        self.assertEqual(len(rows), len(BASE["criteria"]))
        self.assertEqual(rows[0]["overall_status"], MEETS)
        self.assertEqual(rows[0]["outcome"], "MET")

    def test_malicious_html_like_values_remain_plain_data(self):
        result = screen_participant(person(participant_id="<script>alert(1)</script>", smoking_status="<b>Current</b>"), BASE)
        self.assertIn("<script>", result["participant_id"])
        self.assertEqual(result["criteria"][-1]["outcome"], "NOT MET")


if __name__ == "__main__":
    unittest.main()
