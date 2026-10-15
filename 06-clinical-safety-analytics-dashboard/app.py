"""Local, standard-library web dashboard for fictional safety reports."""

from email.parser import BytesParser
from email.policy import default
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlencode, urlparse
import csv
import html
import io
import uuid

from analytics import (DataError, counts_by, export_rows_csv,
                       filter_rows, monthly_counts, overview_metrics, parse_csv)
from data_quality import inspect_quality

BASE_DIR = Path(__file__).resolve().parent
DISCLAIMER = ("Educational pharmacovigilance analytics using synthetic data. Report counts do not establish causality, "
              "incidence, or a validated safety signal. This tool is not for clinical decision-making or regulatory submission.")
MAX_UPLOAD = 2 * 1024 * 1024
SESSIONS = {}


def esc(value):
    return html.escape(str(value), quote=True)


def _bar_section(title, data):
    if not data:
        return "<section><h2>{}</h2><p>No data to summarize.</p></section>".format(esc(title))
    maximum = max(data.values()) or 1
    bars = "".join("<div class='bar-row'><span>{}</span><span class='bar-track'><span class='bar' style='width:{}%'></span></span><strong>{}</strong></div>".format(
        esc(label or "(Missing)"), round(value / maximum * 100), value) for label, value in data.items())
    return "<section><h2>{}</h2>{}</section>".format(esc(title), bars)


def _layout(body, title="Clinical Safety Analytics Dashboard"):
    return """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{}</title><style>
:root{{font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#183243;background:#f2f6f8}}
body{{max-width:1280px;margin:auto;padding:1rem}}header,section,.notice{{background:#fff;border:1px solid #d6e1e7;border-radius:12px;padding:1rem 1.2rem;margin:1rem 0}}
h1,h2{{color:#164d68}}nav a{{margin-right:1.2rem}}.notice{{background:#fff7df;border-color:#edcf73}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:.8rem;margin:1rem 0}}
.card{{background:#e8f2f5;padding:1rem;border-radius:9px}}.card strong{{display:block;font-size:1.45rem;color:#164d68}}label{{display:inline-flex;flex-direction:column;margin:.35rem .65rem .35rem 0;font-weight:600}}
input,select,button{{font:inherit;padding:.5rem;border:1px solid #afc2cc;border-radius:5px}}button{{background:#17617d;color:white;cursor:pointer;border:0}}
.table-wrap{{overflow:auto;max-height:540px;border:1px solid #d6e1e7}}table{{border-collapse:collapse;width:100%;background:white;font-size:.9rem}}th,td{{border-bottom:1px solid #d6e1e7;padding:.55rem;text-align:left;vertical-align:top;min-width:90px}}th{{position:sticky;top:0;background:#e8f2f5}}
.bar-row{{display:grid;grid-template-columns:minmax(130px,230px) minmax(80px,1fr) 38px;gap:.7rem;align-items:center;margin:.45rem 0}}.bar-track{{height:14px;background:#e6eef2;border-radius:8px;overflow:hidden}}.bar{{display:block;height:100%;background:#1680a1;border-radius:8px}}
.issue-row{{background:#fff1ec}}.error{{color:#a12620}}.muted{{color:#546b78}}.actions{{display:flex;gap:.5rem;flex-wrap:wrap}}
@media(max-width:650px){{body{{padding:.5rem}}.bar-row{{grid-template-columns:110px 1fr 28px}}}}
</style></head><body><header><h1>Clinical Safety &amp; Adverse Event Analytics</h1><nav><a href="/">Dashboard</a><a href="/quality">Data-quality report</a><a href="/dictionary">Data dictionary</a></nav></header>{}<footer class="notice"><strong>Educational use only</strong><br>{}</footer><script>
const csvInput=document.querySelector('input[type="file"]');
if(csvInput) csvInput.addEventListener('change',()=>{{const message=document.getElementById('upload-error'); if(csvInput.files.length && csvInput.files[0].size>2097152){{message.textContent='The selected file exceeds the 2 MB upload limit.';csvInput.value='';}}}});
</script></body></html>""".format(esc(title), body, esc(DISCLAIMER))


def _report_table(rows, all_rows, quality_rows):
    if not rows:
        return "<p>No report rows match these filters.</p>"
    issues_by_row = {issue["data_row"] for issue in quality_rows}
    # Row order in a filtered subset follows original import order; use object identity
    # to distinguish duplicate records and retain each source row's issue highlight.
    identities = {id(row) for row in rows}
    visible = []
    for index, row in enumerate(all_rows, start=1):
        if id(row) in identities:
            visible.append((index, row))
    cols = ("report_id", "report_date", "event_term", "seriousness", "outcome", "suspect_product", "age_group", "report_source", "follow_up_received")
    head = "".join("<th>{}</th>".format(esc(col.replace("_", " ").title())) for col in cols)
    body = "".join("<tr data-report-row class='{}'>".format("issue-row" if index in issues_by_row else "") +
                   "".join("<td>{}</td>".format(esc(row.get(col, ""))) for col in cols) + "</tr>" for index, row in visible)
    return "<p>{} rows shown in table. Highlighted rows have quality issues.</p><div class='table-wrap'><table><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>".format(len(rows), head, body)


def render_dashboard(all_rows, filters, search, notice=""):
    filtered = filter_rows(all_rows, filters)
    if search:
        filtered = filter_rows(filtered, search=search)
    metrics = overview_metrics(filtered)
    all_issues = inspect_quality(all_rows)
    issue_rows = {issue["data_row"] for issue in all_issues}
    filtered_issue_count = sum(1 for idx, row in enumerate(all_rows, 1) if id(row) in {id(r) for r in filtered} and idx in issue_rows)
    cards = [("Filtered report rows", metrics["total_rows"]), ("Unique report IDs", metrics["unique_report_ids"]),
             ("Serious rows", metrics["serious_rows"]), ("Rows missing required fields", metrics["rows_with_missing_required_fields"]),
             ("Quality issues, entire dataset", len(all_issues)), ("Issues among filtered rows", filtered_issue_count)]
    card_html = "".join("<div class='card'><span>{}</span><strong>{}</strong></div>".format(esc(label), value) for label, value in cards)
    fields = ("event_term", "seriousness", "outcome", "suspect_product", "age_group")
    options = []
    for field in fields:
        choices = sorted({row.get(field, "") for row in all_rows}, key=str.casefold)
        selected = filters.get(field, "")
        options.append("<label>{}<select name='{}'><option value=''>All values</option>{}</select></label>".format(
            esc(field.replace("_", " ").title()), field,
            "".join("<option value='{}' {}>{}</option>".format(esc("__MISSING__" if not v else v), "selected" if (filters.get(field) == "__MISSING__" if not v else v == selected) else "", esc(v or "(Missing)")) for v in choices)))
    filters_form = "<form method='get' action='/'><label>From date<input type='date' name='start_date' value='{}'></label><label>To date<input type='date' name='end_date' value='{}'></label><label>Search report data<input type='search' name='search' value='{}'></label>{}<p><button>Apply filters</button> <a href='/'>Clear filters</a></p></form>".format(
        esc(filters.get("start_date", "")), esc(filters.get("end_date", "")), esc(search), "".join(options))
    counts = {field: counts_by(filtered, field) for field in fields + ("report_source",)}
    months = monthly_counts(filtered)
    q = urlencode({key: value for key, value in {**filters, "search": search}.items() if value})
    suffix = "?" + q if q else ""
    issue_link = "<p><a href='/quality'>View {} total-dataset data-quality issues</a></p>".format(len(all_issues))
    search_note = "<p class='muted'>Date, category, and text search filters affect metrics, breakdowns, trends, the report table, and filtered report export. The data-quality report always covers the full loaded dataset.</p>"
    body = "{}{}<section><h2>Dataset</h2><p>{} rows loaded. All imported rows remain in the dataset; duplicates and missing values are not discarded.</p><form method='post' action='/import' enctype='multipart/form-data'><label>Import replacement CSV<input type='file' name='file' accept='.csv,text/csv' required></label><button>Validate and import</button><p id='upload-error' class='error' role='status'></p></form><div class='actions'><a href='/export/reports.csv{}'>Export filtered report CSV</a> · <a href='/export/issues.csv'>Export full data-quality CSV</a></div></section><section><h2>Interactive filters</h2>{}</section><section><h2>Report table</h2>{}{}</section>{}{}".format(
        "<p class='notice'>{}</p>".format(esc(notice)) if notice else "",
        "<div class='cards'>{}</div>".format(card_html), len(all_rows), suffix, filters_form,
        search_note, _report_table(filtered, all_rows, all_issues), issue_link,
        "".join(_bar_section(title, counts[field]) for field, title in [("event_term", "Counts by event term"), ("seriousness", "Counts by seriousness"), ("outcome", "Counts by outcome"), ("suspect_product", "Counts by suspect product"), ("age_group", "Counts by age group"), ("report_source", "Counts by reporting source")]) + _bar_section("Monthly report rows (valid report dates)", months))
    return _layout(body)


def _issues_csv(issues):
    output = io.StringIO(newline="")
    fields = ["data_row", "report_id", "field", "issue_type", "explanation", "original_value"]
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(issues)
    return output.getvalue()


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "SyntheticSafetyDashboard/1.0"

    def log_message(self, fmt, *args):
        print("[local server] " + fmt % args)

    def _session(self):
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        token = cookie.get("safety_session")
        if token and token.value in SESSIONS:
            return token.value, SESSIONS[token.value], False
        token_id = uuid.uuid4().hex
        sample = parse_csv((BASE_DIR / "sample_data" / "adverse_event_reports.csv").read_bytes())
        SESSIONS[token_id] = sample
        return token_id, sample, True

    def _send(self, content, status=200, content_type="text/html; charset=utf-8", cookie=None, filename=None):
        data = content.encode("utf-8") if isinstance(content, str) else content
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'none'")
        if cookie:
            self.send_header("Set-Cookie", f"safety_session={cookie}; HttpOnly; SameSite=Lax; Path=/")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, message, status=400, cookie=None):
        self._send(_layout("<section><h2 class='error'>Request could not be completed</h2><p>{}</p><p><a href='/'>Back to dashboard</a></p></section>".format(esc(message)), "Input error"), status, cookie=cookie)

    def _filters(self):
        query = parse_qs(urlparse(self.path).query)
        return {key: query.get(key, [""])[0] for key in ("start_date", "end_date", "event_term", "seriousness", "outcome", "suspect_product", "age_group")}, query.get("search", [""])[0]

    def do_GET(self):
        token, rows, new_cookie = self._session()
        route = urlparse(self.path).path
        try:
            if route == "/export/reports.csv":
                filters, search = self._filters()
                filtered = filter_rows(rows, filters, search)
                return self._send(export_rows_csv(filtered), content_type="text/csv; charset=utf-8", cookie=token if new_cookie else None, filename="filtered-synthetic-reports.csv")
            if route == "/export/issues.csv":
                return self._send(_issues_csv(inspect_quality(rows)), content_type="text/csv; charset=utf-8", cookie=token if new_cookie else None, filename="synthetic-data-quality-issues.csv")
            if route == "/dictionary":
                content = (BASE_DIR / "sample_data" / "data_dictionary.md").read_text(encoding="utf-8")
                body = "<section><h2>Data dictionary</h2><pre>{}</pre></section>".format(esc(content))
                return self._send(_layout(body, "Data dictionary"), cookie=token if new_cookie else None)
            issues = inspect_quality(rows)
            if route == "/quality":
                body = "<section><h2>Data-quality report</h2><p>Quality issues below cover the full loaded dataset, even when dashboard filters are active. Source values are preserved.</p><p>{} issues found. <a href='/export/issues.csv'>Download issue CSV</a></p>{}</section>".format(len(issues), _quality_table(issues))
                return self._send(_layout(body, "Data-quality report"), cookie=token if new_cookie else None)
            if route != "/":
                return self._send_error("That page was not found.", 404, token if new_cookie else None)
            filters, search = self._filters()
            notice = parse_qs(urlparse(self.path).query).get("notice", [""])[0]
            page = render_dashboard(rows, filters, search, notice=notice)
            return self._send(page, cookie=token if new_cookie else None)
        except DataError as exc:
            return self._send_error(str(exc), 400, token if new_cookie else None)
        except (OSError, csv.Error) as exc:
            return self._send_error(f"Could not read or export data: {exc}", 500, token if new_cookie else None)

    def do_POST(self):
        token, rows, new_cookie = self._session()
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > MAX_UPLOAD:
                raise DataError("Upload limit is 2 MB.")
            if urlparse(self.path).path != "/import":
                return self._send_error("Unknown action.", 404, token if new_cookie else None)
            content_type = self.headers.get("Content-Type", "")
            if not content_type.startswith("multipart/form-data"):
                raise DataError("Choose a CSV file using the import form.")
            message = BytesParser(policy=default).parsebytes(b"Content-Type: " + content_type.encode("ascii") + b"\r\nMIME-Version: 1.0\r\n\r\n" + self.rfile.read(length))
            uploads = [part for part in message.iter_parts() if part.get_param("name", header="content-disposition") == "file"]
            if not uploads or not uploads[0].get_filename():
                raise DataError("Select a CSV file to import.")
            if Path(uploads[0].get_filename()).suffix.casefold() != ".csv":
                raise DataError("The selected file must have a .csv extension.")
            imported = parse_csv(uploads[0].get_payload(decode=True) or b"")
            SESSIONS[token] = imported
            self.send_response(303)
            self.send_header("Location", "/?notice=" + quote(f"Imported {len(imported)} rows. Source rows with issues remain included."))
            self.send_header("Set-Cookie", f"safety_session={token}; HttpOnly; SameSite=Lax; Path=/")
            self.end_headers()
        except DataError as exc:
            self._send_error(str(exc), 400, token if new_cookie else None)
        except (OSError, UnicodeError, ValueError) as exc:
            self._send_error(f"Import failed: {exc}", 400, token if new_cookie else None)


def _quality_table(issues):
    if not issues:
        return "<p>No detected issues.</p>"
    head = "".join("<th>{}</th>".format(esc(k.replace("_", " ").title())) for k in ("data_row", "report_id", "field", "issue_type", "explanation", "original_value"))
    body = "".join("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(*[esc(issue.get(k, "")) for k in ("data_row", "report_id", "field", "issue_type", "explanation", "original_value")]) for issue in issues)
    return "<div class='table-wrap'><table><thead><tr>{}</tr></thead><tbody>{}</tbody></table></div>".format(head, body)


def main():
    host, port = "127.0.0.1", 8000
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"Dashboard ready at http://{host}:{port}. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping dashboard.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
