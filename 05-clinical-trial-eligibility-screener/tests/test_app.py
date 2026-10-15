import http.client
import threading
import unittest
from http.server import ThreadingHTTPServer

import app
from screening import screen_participant
from test_screening import BASE, person


class AppSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), app.ScreenerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        payload = response.read()
        result = response.status, response.getheaders(), payload
        connection.close()
        return result

    def test_home_serves_disclaimer(self):
        status, headers, body = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"not medical advice", body)
        self.assertTrue(any(k.lower() == "set-cookie" for k, _ in headers))

    def test_config_page_escapes_json_textarea(self):
        _, _, body = self.request("GET", "/config")
        self.assertIn(b"Study configuration", body)
        self.assertIn(b"&quot;study_name&quot;", body)
        self.assertNotIn(b"<script>alert", body)

    def test_imported_html_like_values_are_escaped_in_results(self):
        result = screen_participant(person(participant_id="<script>alert(1)</script>", smoking_status="<b>Current</b>"), BASE)
        rendered = app.render_result(result)
        self.assertNotIn("<script>alert", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertIn("&lt;b&gt;Current&lt;/b&gt;", rendered)

    def test_report_without_screening_is_helpful_error(self):
        status, _, body = self.request("GET", "/report.csv")
        self.assertEqual(status, 400)
        self.assertIn(b"Screen participants first", body)

    def test_unknown_route_post_is_handled_as_input_error(self):
        status, _, body = self.request("POST", "/bad", "", {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 400)
        self.assertIn(b"Unknown action", body)

    def test_sample_screen_report_workflow(self):
        status, headers, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        cookie = next(value.split(";", 1)[0] for key, value in headers if key.lower() == "set-cookie")
        status, headers, _ = self.request("POST", "/sample", "", {"Cookie": cookie, "Content-Length": "0"})
        self.assertEqual(status, 303)
        status, _, _ = self.request("POST", "/screen", "", {"Cookie": cookie, "Content-Length": "0"})
        self.assertEqual(status, 303)
        status, headers, report = self.request("GET", "/report.csv", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertTrue(any(k.lower() == "content-type" and "text/csv" in v for k, v in headers))
        self.assertIn(b"criterion_name", report)
        self.assertIn(b"DEMO-001", report)
        self.assertIn(b"REQUIRES REVIEW", report)


if __name__ == "__main__":
    unittest.main()
