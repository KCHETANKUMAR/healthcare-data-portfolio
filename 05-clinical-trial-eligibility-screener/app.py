"""Local standard-library web interface for fictional eligibility practice."""

from email.parser import BytesParser
from email.policy import default
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import html
import json
import uuid

from screening import (DOES_NOT_MEET, MEETS, REVIEW, ScreeningError, load_config,
                      parse_participant_csv, report_csv, screen_participants)

BASE_DIR = Path(__file__).resolve().parent
DISCLAIMER = ("Educational simulation using configurable sample criteria. Results are not medical advice, "
              "do not establish clinical-trial eligibility, and must not be used for actual recruitment or clinical decisions.")
MAX_UPLOAD = 2 * 1024 * 1024
STATES = {}


def esc(value):
    return html.escape(str(value), quote=True)


def page(title, body):
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{}</title>
<style>
body{{font:16px system-ui,sans-serif;max-width:1080px;margin:2rem auto;padding:0 1rem;color:#172b3a;background:#f5f8fa}}
header,section,.notice{{background:white;border:1px solid #d9e2e8;border-radius:12px;padding:1.2rem;margin:1rem 0}}
nav a{{margin-right:1rem}}h1,h2{{color:#123f5a}}textarea{{width:100%;min-height:390px;font:14px ui-monospace,monospace}}
input,button,select{{font:inherit;padding:.55rem;margin:.25rem 0}}button{{background:#145c78;color:white;border:0;border-radius:6px;cursor:pointer}}
table{{border-collapse:collapse;width:100%;background:white}}th,td{{border:1px solid #d9e2e8;padding:.55rem;text-align:left;vertical-align:top}}.cards{{display:flex;gap:1rem;flex-wrap:wrap}}.card{{padding:1rem;background:#e9f2f6;border-radius:8px;min-width:145px}}.MET{{color:#176b3a}}.NOT\ MET{{color:#a32a24}}.UNKNOWN{{color:#9a5a00}}.error{{color:#a32a24}}
</style></head><body><header><h1>Clinical Trial Eligibility Screener</h1><nav><a href="/">Overview</a><a href="/config">Study configuration</a><a href="/participants">Participant data</a><a href="/results">Screening report</a></nav></header>{}<footer class="notice"><strong>Educational use only</strong><br>{}</footer><script>
const csvInput = document.querySelector('input[type="file"]');
if (csvInput) csvInput.addEventListener('change', () => {{
  const message = document.getElementById('upload-error');
  if (csvInput.files.length && csvInput.files[0].size > 2097152) {{
    message.textContent = 'The selected file exceeds the 2 MB upload limit.';
    csvInput.value = '';
  }} else if (message) {{ message.textContent = ''; }}
}});
</script></body></html>""".format(esc(title), body, esc(DISCLAIMER))


def render_result(result):
    rows = "".join("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
        esc(c["name"]), esc(c["type"]), esc(c["observed"] or "(blank)"), esc(c["expected"]),
        esc(c["outcome"]), esc(c["explanation"])) for c in result["criteria"])
    return ("<section><h3>Participant {}</h3><p><strong>Status: {}</strong> — {}</p>"
            "{}<table><thead><tr><th>Criterion</th><th>Type</th><th>Observed</th><th>Expected</th><th>Outcome</th><th>Explanation</th></tr></thead><tbody>{}</tbody></table></section>").format(
                esc(result["participant_id"]), esc(result["status"]), esc(result["reason"]),
                "<p class='error'>Unknown criteria remain flagged for review.</p>" if result["requires_review"] else "", rows)


class ScreenerHandler(BaseHTTPRequestHandler):
    server_version = "EducationalScreener/1.0"

    def log_message(self, fmt, *args):
        print("[local server] " + fmt % args)

    def _state(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        sid = cookie.get("screener_session")
        if not sid or sid.value not in STATES:
            key = uuid.uuid4().hex
            STATES[key] = {"config": load_config((BASE_DIR / "study_config.json").read_text(encoding="utf-8")),
                           "participants": [], "results": []}
            return key, STATES[key], True
        return sid.value, STATES[sid.value], False

    def _send(self, content, status=200, content_type="text/html; charset=utf-8", cookie=None):
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", f"screener_session={cookie}; HttpOnly; SameSite=Lax; Path=/")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        size = int(self.headers.get("Content-Length", "0"))
        if size > MAX_UPLOAD:
            raise ScreeningError("Request is too large. Upload limit is 2 MB.")
        return self.rfile.read(size)

    def _form(self):
        raw = self._body()
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            message = BytesParser(policy=default).parsebytes(
                b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + raw)
            values = {}
            for part in message.iter_parts():
                key = part.get_param("name", header="content-disposition")
                values[key] = {"filename": part.get_filename(), "data": part.get_payload(decode=True) or b""}
            return values
        return {key: entries[-1] for key, entries in parse_qs(raw.decode("utf-8"), keep_blank_values=True).items()}

    def do_GET(self):
        sid, state, new_cookie = self._state()
        route = urlparse(self.path).path
        if route == "/report.csv":
            if not state["results"]:
                return self._send("No screening report is available yet. Screen participants first.", 400, "text/plain; charset=utf-8", sid if new_cookie else None)
            return self._send(report_csv(state["results"]), content_type="text/csv; charset=utf-8", cookie=sid if new_cookie else None)
        if route == "/config":
            body = "<section><h2>Study configuration</h2><p>Edit the fictional study JSON. The server validates every field, operator, and threshold before saving.</p><form method='post' action='/config'><textarea name='config'>{}</textarea><br><button>Validate and save configuration</button></form></section>".format(esc(json.dumps(state["config"], indent=2)))
        elif route == "/participants":
            warnings = ["{}: {}".format(p["participant_id"], warning) for p in state["participants"] for warning in p.get("data_warnings", [])]
            warning_html = "<p><strong>Data warnings:</strong></p><ul>{}</ul>".format("".join("<li>{}</li>".format(esc(w)) for w in warnings)) if warnings else ""
            loaded = "<p>Loaded {} participant rows.</p>{}".format(len(state["participants"]), warning_html) if state["participants"] else "<p>No participants loaded.</p>"
            body = "<section><h2>Participant data</h2><p>Included examples are fictional. CSV needs participant_id, age, bmi, smoking_status, medical_history_flag, consent_status. Notes are optional.</p><form method='post' action='/sample'><button>Load fictional sample participants</button></form><form method='post' action='/upload' enctype='multipart/form-data'><label>Import CSV <input type='file' name='file' accept='.csv,text/csv' required></label><button>Import participants</button><p id='upload-error' class='error' role='status'></p></form>{}<form method='post' action='/screen'><button {}>Screen loaded participants</button></form></section>".format(loaded, "" if state["participants"] else "disabled")
        elif route == "/results":
            counts = {MEETS: 0, DOES_NOT_MEET: 0, REVIEW: 0}
            for result in state["results"]: counts[result["status"]] += 1
            cards = "".join("<div class='card'><strong>{}</strong><br>{}</div>".format(esc(label), count) for label, count in [("Total screened", len(state["results"])), *counts.items()])
            filter_form = "<form method='get' action='/results'><label>Filter status <select name='status'><option value=''>All statuses</option>{}</select></label><button>Apply</button></form>".format("".join("<option {}>{}</option>".format("selected" if self._query("status") == x else "", esc(x)) for x in counts))
            chosen = self._query("status")
            visible = [r for r in state["results"] if not chosen or r["status"] == chosen]
            body = "<section><h2>Screening report</h2>{}<p><a href='/report.csv'>Download criterion-level CSV</a></p>{}</section>".format("<div class='cards'>{}</div>".format(cards), filter_form + ("".join(render_result(r) for r in visible) if visible else "<p>No results match this filter. Screen loaded participants to view details.</p>"))
        else:
            body = "<section><h2>Overview</h2><p>Practice transparent screening against criteria configured for a fictional study. This tool does not determine real eligibility.</p><ul><li>Review or edit the study criteria.</li><li>Load fictional sample participants or import a permitted CSV.</li><li>Screen records and inspect criterion-level MET, NOT MET, or UNKNOWN outcomes.</li></ul><p><a href='/participants'>Load participant data</a> · <a href='/config'>Review configuration</a></p></section>"
        notice = self._query("notice")
        if notice:
            body = "<section class='notice'>{}</section>".format(esc(notice)) + body
        self._send(page(route.strip("/").title() or "Overview", body), cookie=sid if new_cookie else None)

    def _query(self, key):
        return parse_qs(urlparse(self.path).query).get(key, [""])[0]

    def do_POST(self):
        sid, state, new_cookie = self._state()
        try:
            form = self._form()
            route = urlparse(self.path).path
            if route == "/config":
                config = load_config(form.get("config", ""))
                state["config"] = config
                state["results"] = []
                message = "Configuration validated and saved for this browser session."
            elif route == "/sample":
                state["participants"] = parse_participant_csv((BASE_DIR / "sample_data" / "participants.csv").read_bytes())
                state["results"] = []
                message = "Loaded {} fictional sample participants.".format(len(state["participants"]))
            elif route == "/upload":
                upload = form.get("file")
                if not isinstance(upload, dict) or not upload.get("filename") or not upload.get("data"):
                    raise ScreeningError("Choose a non-empty CSV file to import.")
                if Path(upload["filename"]).suffix.casefold() != ".csv":
                    raise ScreeningError("Choose a file with the .csv extension.")
                state["participants"] = parse_participant_csv(upload["data"])
                state["results"] = []
                message = "Imported {} participant rows. Numeric errors remain UNKNOWN during screening.".format(len(state["participants"]))
            elif route == "/screen":
                if not state["participants"]: raise ScreeningError("Load sample participants or import a CSV first.")
                state["results"] = screen_participants(state["participants"], state["config"])
                self._redirect("/results", sid, "Screened {} fictional participant records.".format(len(state["results"])))
                return
            else:
                raise ScreeningError("Unknown action.")
            self._redirect("/participants" if route != "/config" else "/config", sid, message)
        except (ScreeningError, UnicodeDecodeError, ValueError) as exc:
            self._send(page("Input error", "<section><h2 class='error'>Could not complete that action</h2><p>{}</p><p><a href='/'>Return to overview</a></p></section>".format(esc(exc))), 400, cookie=sid if new_cookie else None)
        except Exception:
            self._send(page("Server error", "<section><h2 class='error'>Server error</h2><p>The request could not be completed. Check the input and try again.</p></section>"), 500, cookie=sid if new_cookie else None)

    def _redirect(self, path, sid, message):
        from urllib.parse import quote
        self.send_response(303)
        self.send_header("Location", path + "?notice=" + quote(message, safe=""))
        self.send_header("Set-Cookie", f"screener_session={sid}; HttpOnly; SameSite=Lax; Path=/")
        self.end_headers()


def main():
    host, port = "127.0.0.1", 8000
    server = ThreadingHTTPServer((host, port), ScreenerHandler)
    print(f"Open http://{host}:{port} in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping local screener.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
