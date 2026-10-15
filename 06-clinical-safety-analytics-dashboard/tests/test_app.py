import csv
import http.client
import io
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

import app
from analytics import parse_csv


class DashboardAppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.DashboardHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        result = response.status, response.getheaders(), response.read()
        conn.close()
        return result

    def test_home_shows_metrics_and_disclaimer(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Educational pharmacovigilance analytics using synthetic data", body)
        self.assertIn(b"Unique report IDs", body)
        self.assertTrue(any(k.lower() == "set-cookie" for k, _ in headers))

    def test_filter_affects_dashboard_and_export(self):
        _, headers, _ = self.request("GET", "/")
        cookie = next(value.split(";", 1)[0] for key, value in headers if key.lower() == "set-cookie")
        status, _, page = self.request("GET", "/?suspect_product=DemoCompound-A", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertIn(b"DemoCompound-A", page)
        status, headers, body = self.request("GET", "/export/reports.csv?suspect_product=DemoCompound-A", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertTrue(any(k.lower() == "content-type" and "text/csv" in v for k, v in headers))
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
        self.assertTrue(rows)
        self.assertTrue(all(row["suspect_product"] == "DemoCompound-A" for row in rows))

    def test_quality_export_is_separate_and_has_issues(self):
        status, headers, body = self.request("GET", "/export/issues.csv")
        self.assertEqual(status, 200)
        self.assertTrue(any("synthetic-data-quality-issues.csv" in v for k, v in headers if k.lower() == "content-disposition"))
        rows = list(csv.DictReader(io.StringIO(body.decode("utf-8"))))
        self.assertTrue(any(row["issue_type"] == "Duplicate report ID" for row in rows))

    def test_invalid_filter_returns_helpful_error(self):
        status, _, body = self.request("GET", "/?start_date=bad")
        self.assertEqual(status, 400)
        self.assertIn(b"YYYY-MM-DD", body)

    def test_malformed_upload_is_rejected_without_replacing_session(self):
        _, headers, _ = self.request("GET", "/")
        cookie = next(value.split(";", 1)[0] for key, value in headers if key.lower() == "set-cookie")
        boundary = "----test-boundary"
        payload = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"bad.csv\"\r\n"
                   f"Content-Type: text/csv\r\n\r\nreport_id,event_term\r\nX,Headache\r\n--{boundary}--\r\n").encode()
        status, _, body = self.request("POST", "/import", payload, {"Cookie": cookie, "Content-Type": f"multipart/form-data; boundary={boundary}"})
        self.assertEqual(status, 400)
        self.assertIn(b"Missing required columns", body)
        self.assertEqual(len(app.SESSIONS[cookie.split("=", 1)[1]]), 50)

    def test_unknown_path_is_404(self):
        status, _, _ = self.request("GET", "/unknown")
        self.assertEqual(status, 404)

    def test_empty_dashboard_and_untrusted_values_render_safely(self):
        empty = app.render_dashboard([], {}, "")
        self.assertIn("No report rows match", empty)
        sample = Path(__file__).resolve().parents[1] / "sample_data" / "adverse_event_reports.csv"
        rows = parse_csv(sample.read_bytes())[:1]
        rows[0]["event_term"] = "<script>alert(1)</script>"
        rendered = app.render_dashboard(rows, {}, "")
        self.assertNotIn("<script>alert", rendered)
        self.assertIn("&lt;script&gt;", rendered)


if __name__ == "__main__":
    unittest.main()
