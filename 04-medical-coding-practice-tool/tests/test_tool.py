import csv
import random
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from datetime import datetime, timezone
from pathlib import Path

from app import PracticeHTTPServer, PracticeHandler, PracticeState, render_entry_card, render_search, server_config
from quiz import (
    build_quiz_export,
    build_quiz_questions,
    next_unanswered_question,
    score_results,
)
from reference_data import (
    REQUIRED_COLUMNS,
    ReferenceDataError,
    load_reference_csv,
    parse_reference_csv,
    search_entries,
)

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data" / "reference_terms.csv"


def entry(term="Term One", definition="Definition one", category="General", code="PRACTICE-001", **extra):
    row = {
        "term": term,
        "definition": definition,
        "category": category,
        "reference_code": code,
        "explanation": "Practice explanation.",
        "source_name": "Fictional Practice Glossary",
        "source_version": "1.0",
    }
    row.update(extra)
    return row


class ReferenceDataTests(unittest.TestCase):
    def test_load_valid_sample_data(self):
        entries, warnings = load_reference_csv(SAMPLE)
        self.assertEqual(len(entries), 8)
        self.assertEqual(entries[0]["reference_code"], "PRACTICE-001")
        self.assertEqual(warnings, [])

    def test_search_by_term_definition_category_and_code(self):
        rows = [entry(), entry("Term Two", "Second unique description", "Other", "PRACTICE-002")]
        self.assertEqual(len(search_entries(rows, "term one")), 1)
        self.assertEqual(len(search_entries(rows, "unique description")), 1)
        self.assertEqual(len(search_entries(rows, "practice-002")), 1)
        self.assertEqual([row["term"] for row in search_entries(rows, category="Other")], ["Term Two"])
        self.assertEqual(search_entries(rows), [])

    def test_csv_import_validation_missing_columns_and_malformed_rows(self):
        good = ",".join(REQUIRED_COLUMNS) + "\n" + "Term,Definition,Category,PRACTICE-9,Explanation,Sample,1\n"
        entries, warnings = parse_reference_csv(good)
        self.assertEqual(entries[0]["term"], "Term")
        self.assertEqual(warnings, [])
        with self.assertRaisesRegex(ReferenceDataError, "missing required columns"):
            parse_reference_csv("term,definition\nTerm,Definition\n")
        with self.assertRaises(ReferenceDataError):
            parse_reference_csv(",".join(REQUIRED_COLUMNS) + "\n" + ",".join(["extra"] * (len(REQUIRED_COLUMNS) + 1)) + "\n")

    def test_duplicate_terms_codes_and_blank_reference_metadata_warn(self):
        rows = [entry(), entry("term one", "Another definition", "Other", "PRACTICE-001")]
        warnings = parse_reference_csv(
            ",".join(REQUIRED_COLUMNS) + "\n" + "\n".join(
                ",".join(row[field] for field in REQUIRED_COLUMNS) for row in rows
            ) + "\n"
        )[1]
        self.assertTrue(any("duplicate term" in warning for warning in warnings))
        self.assertTrue(any("duplicate reference code" in warning for warning in warnings))
        rows[0]["source_name"] = ""
        self.assertTrue(any("source_name" in warning for warning in parse_reference_csv(
            ",".join(REQUIRED_COLUMNS) + "\n" + ",".join(rows[0][field] for field in REQUIRED_COLUMNS) + "\n"
        )[1]))

    def test_html_rendering_escapes_imported_values(self):
        unsafe = entry(term='<img src=x onerror="alert(1)">')
        html = render_entry_card(unsafe)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", html)
        self.assertNotIn(unsafe["term"], html)
        session = {"entries": [unsafe], "dataset_kind": "imported", "dataset_filename": "reference.csv"}
        self.assertNotIn(unsafe["term"], render_search(session, "img"))


class DeploymentAndHTTPTests(unittest.TestCase):
    def test_server_config_local_render_and_invalid_ports(self):
        self.assertEqual(server_config({}), ("127.0.0.1", 8000))
        self.assertEqual(server_config({"PORT": "9001"}), ("127.0.0.1", 9001))
        self.assertEqual(server_config({"PORT": "10000", "RENDER": "true"}), ("0.0.0.0", 10000))
        for port in ("zero", "0", "65536"):
            with self.assertRaises(ValueError):
                server_config({"PORT": port})

    def test_pages_csrf_session_isolation_import_quiz_export_and_secure_cookie(self):
        server = PracticeHTTPServer(("127.0.0.1", 0), PracticeHandler, PracticeState())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        conn = HTTPConnection("127.0.0.1", server.server_port)
        try:
            conn.request("GET", "/")
            response = conn.getresponse()
            home = response.read().decode()
            cookie = response.getheader("Set-Cookie").split(";", 1)[0]
            self.assertEqual(response.status, 200)
            self.assertIn("Educational practice only", home)
            for path in ("/search", "/flashcards", "/quiz", "/import", "/export.csv"):
                conn.request("GET", path, headers={"Cookie": cookie})
                page = conn.getresponse()
                self.assertEqual(page.status, 200, path)
                payload = page.read()
                if path in ("/quiz", "/import"):
                    self.assertIn(b'name="csrf_token"', payload)

            # A cross-site style form without a token is rejected.
            conn.request("POST", "/quiz", body="action=reset", headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"})
            rejected = conn.getresponse()
            self.assertEqual(rejected.status, 400)
            rejected.read()

            # A valid quiz answer is accepted and appears in the same session's CSV.
            session_id = cookie.split("=", 1)[1]
            session = server.state.sessions[session_id]
            question = session["quiz_questions"][0]
            token = session["csrf_token"]
            body = f"csrf_token={token}&action=answer&question_id={question['question_id']}&answer=0"
            conn.request("POST", "/quiz", body=body, headers={"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"})
            answered = conn.getresponse()
            self.assertEqual(answered.status, 303)
            answered.read()
            self.assertEqual(len(session["quiz_results"]), 1)
            conn.request("GET", "/export.csv", headers={"Cookie": cookie})
            exported = conn.getresponse()
            csv_text = exported.read().decode()
            self.assertIn("SESSION SUMMARY", csv_text)

            # HTTPS termination proxy flag adds Secure only to the newly-issued cookie.
            conn.request("GET", "/", headers={"X-Forwarded-Proto": "https"})
            secure_response = conn.getresponse()
            secure_response.read()
            self.assertIn("; Secure", secure_response.getheader("Set-Cookie"))

            # Import validation is enforced through the HTTP handler and requires the session token.
            boundary = "----PracticeBoundary"
            upload = (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"csrf_token\"\r\n\r\n{token}\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"reference_file\"; filename=\"practice.csv\"\r\n"
                "Content-Type: text/csv\r\n\r\nterm,definition\r\nMissing columns,Nope\r\n"
                f"--{boundary}--\r\n"
            )
            conn.request("POST", "/import", body=upload, headers={"Cookie": cookie, "Content-Type": f"multipart/form-data; boundary={boundary}"})
            invalid_import = conn.getresponse()
            self.assertEqual(invalid_import.status, 400)
            self.assertIn(b"missing required columns", invalid_import.read())

            headers = "term,definition,category,reference_code,explanation,source_name,source_version"
            data = headers + "\nPrivate test term,Definition,General,PRACTICE-TEST,Practice only,Fictional,1"
            upload = (
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"csrf_token\"\r\n\r\n{token}\r\n"
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"reference_file\"; filename=\"practice.csv\"\r\n"
                f"Content-Type: text/csv\r\n\r\n{data}\r\n--{boundary}--\r\n"
            )
            conn.request("POST", "/import", body=upload, headers={"Cookie": cookie, "Content-Type": f"multipart/form-data; boundary={boundary}"})
            imported = conn.getresponse()
            self.assertEqual(imported.status, 303)
            imported.read()
            self.assertEqual(session["dataset_kind"], "imported")

            # A second visitor gets a separate sample session and no imported state/results.
            conn.request("GET", "/import")
            other = conn.getresponse()
            other_cookie = other.getheader("Set-Cookie").split(";", 1)[0]
            other.read()
            other_session = server.state.sessions[other_cookie.split("=", 1)[1]]
            self.assertEqual(other_session["dataset_kind"], "sample")
            self.assertEqual(other_session["quiz_results"], [])
        finally:
            conn.close()
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class QuizTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            entry("Term One", "Definition one", "A", "PRACTICE-001"),
            entry("Term Two", "Definition two", "B", "PRACTICE-002"),
            entry("Term Three", "Definition three", "C", "PRACTICE-003"),
            entry("Term Four", "Definition four", "D", "PRACTICE-004"),
        ]

    def test_quiz_questions_include_varied_question_types_and_do_not_repeat(self):
        questions = build_quiz_questions(self.rows, rng=random.Random(3))
        self.assertIn("definition", {question["kind"] for question in questions})
        self.assertIn("reference_code", {question["kind"] for question in questions})
        seen = set()
        first = next_unanswered_question(questions, seen)
        self.assertIsNotNone(first)
        seen.add(first["question_id"])
        second = next_unanswered_question(questions, seen)
        self.assertNotEqual(first["question_id"], second["question_id"])
        seen.update(question["question_id"] for question in questions)
        self.assertIsNone(next_unanswered_question(questions, seen))

    def test_insufficient_options_are_handled(self):
        questions = build_quiz_questions(self.rows[:2], rng=random.Random(1))
        self.assertEqual(questions, [])

    def test_quiz_scoring(self):
        results = [{"correct": True}, {"correct": False}, {"correct": True}]
        score = score_results(results)
        self.assertEqual((score["answered"], score["correct"]), (3, 2))
        self.assertAlmostEqual(score["percentage"], 200 / 3)
        self.assertEqual(score_results([]), {"answered": 0, "correct": 0, "percentage": 0.0})

    def test_quiz_results_export_has_answers_timestamp_and_summary(self):
        rows = [{
            "timestamp": "2026-01-02T03:04:05+00:00",
            "question": "Which definition matches Term One?",
            "selected_answer": "Definition one",
            "expected_answer": "Definition one",
            "correct": True,
            "score_percentage": 100,
            "explanation": "Review the reference explanation.",
        }]
        filename, csv_text = build_quiz_export(rows, datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc))
        data = list(csv.DictReader(csv_text.splitlines()))
        self.assertEqual(filename, "quiz-results-20260102-030405.csv")
        self.assertEqual(data[0]["Selected answer"], "Definition one")
        self.assertEqual(data[0]["Expected answer"], "Definition one")
        self.assertEqual(data[-1]["Question"], "SESSION SUMMARY")
        self.assertEqual(data[-1]["Score percentage"], "100.0%")

    def test_export_neutralizes_spreadsheet_formulas_in_imported_text(self):
        _, csv_text = build_quiz_export([{
            "question": '=HYPERLINK("https://example.invalid")',
            "selected_answer": " +SUM(1,1)",
            "expected_answer": "@malicious",
            "explanation": "-1+1",
        }])
        self.assertIn("'=HYPERLINK", csv_text)
        self.assertIn("' +SUM", csv_text)
        self.assertIn("'@malicious", csv_text)


if __name__ == "__main__":
    unittest.main()
