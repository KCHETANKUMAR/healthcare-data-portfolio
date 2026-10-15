import tempfile
import unittest
from pathlib import Path

import database


def case(case_id="SIM-1000", yes="Yes"):
    return dict(case_id=case_id, patient_identifiable=yes, reporter_identifiable=yes,
                product_identified=yes, reaction_reported=yes,
                event_description="Fictional source description", patient_age="",
                patient_sex="Unknown", product_name="TrainingMed", onset_date="",
                received_date="2026-01-01", seriousness="Unknown", outcome="Unknown",
                source_notes="", fictional=1)


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "test.db"
        database.initialize_database(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_initialization_and_case_round_trip(self):
        database.create_case(case(), self.path)
        self.assertEqual(database.get_case("SIM-1000", self.path)["event_description"], "Fictional source description")
        self.assertTrue(self.path.exists())

    def test_minimum_criteria_requires_four_explicit_yes(self):
        self.assertTrue(database.meets_minimum(case()))
        self.assertFalse(database.meets_minimum(case(yes="Unknown")))

    def test_followup_persists(self):
        database.create_case(case(), self.path)
        fid = database.add_follow_up("SIM-1000", dict(missing_field="Onset", question="When did it start?", date_raised="2026-01-02"), self.path)
        database.update_follow_up(fid, dict(missing_field="Onset", question="When did it start?", date_raised="2026-01-02", response_received="2026-01-03", response_notes="No response", status="Answered"), self.path)
        self.assertEqual(database.get_follow_ups("SIM-1000", self.path)[0]["status"], "Answered")

    def test_qc_persists(self):
        database.create_case(case(), self.path)
        database.save_qc("SIM-1000", {"source_transcribed": True, "final_review": True}, self.path)
        self.assertEqual(database.get_qc("SIM-1000", self.path)["final_review"], 1)

    def test_sample_data_is_idempotent_and_third_case_fails_criteria(self):
        self.assertEqual(database.insert_sample_data(self.path), 3)
        self.assertEqual(database.insert_sample_data(self.path), 0)
        self.assertEqual(len(database.get_cases(self.path)), 3)
        self.assertEqual(database.get_case("SIM-0003", self.path)["validation_status"], "Does not yet meet minimum criteria")


if __name__ == "__main__":
    unittest.main()
