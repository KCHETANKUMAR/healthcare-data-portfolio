"""Local, standard-library web interface for terminology practice."""

from __future__ import annotations

import argparse
import csv
import html
import random
import secrets
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default as email_policy
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from quiz import build_quiz_export, build_quiz_questions, next_unanswered_question, score_results
from reference_data import (
    ReferenceDataError,
    categories,
    load_reference_csv,
    parse_reference_csv,
    search_entries,
)

PROJECT_DIR = Path(__file__).resolve().parent
SAMPLE_DATA = PROJECT_DIR / "sample_data" / "reference_terms.csv"
MAX_UPLOAD_BYTES = 2 * 1024 * 1024


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_entry_card(entry: dict[str, str], *, reveal: bool = True) -> str:
    """Render an entry with imported values escaped for safe HTML display."""
    code = entry.get("reference_code", "").strip()
    code_text = code if code else "No reference code supplied"
    definition = entry.get("definition", "").strip() or "No definition supplied"
    explanation = entry.get("explanation", "").strip() or "No explanation supplied"
    source_name = entry.get("source_name", "").strip() or "Not provided in the imported row"
    source_version = entry.get("source_version", "").strip() or "Not provided in the imported row"
    details = ""
    if reveal:
        details = (
            f'<p><strong>Definition:</strong> {escape(definition)}</p>'
            f'<p><strong>Reference entry:</strong> {escape(code_text)} · {escape(entry.get("category", ""))}</p>'
            f'<p><strong>Explanation:</strong> {escape(explanation)}</p>'
            f'<p class="source"><strong>Source:</strong> {escape(source_name)} · <strong>Version:</strong> {escape(source_version)}</p>'
        )
    return (
        '<article class="entry-card">'
        f'<h3>{escape(entry.get("term", "").strip() or "Term not supplied")}</h3>'
        f'<p class="category">{escape(entry.get("category", "").strip() or "Category not supplied")}</p>'
        + details + '</article>'
    )


def _warning_list(warnings: list[str]) -> str:
    if not warnings:
        return '<p class="success">No duplicate or blank-field warnings found in this CSV.</p>'
    return '<ul class="warning-list">' + "".join(f"<li>{escape(warning)}</li>" for warning in warnings) + "</ul>"


def render_page(session: dict[str, object], content: str, *, title: str = "Medical Terminology Practice Tool") -> str:
    dataset_kind = str(session.get("dataset_kind", "sample"))
    if dataset_kind == "sample":
        dataset_notice = "Fictional sample practice entries with nonofficial practice identifiers. Not an official or verified coding reference."
    else:
        name = escape(session.get("dataset_filename", "user CSV"))
        dataset_notice = f"Imported file: {name}. Its source has not been independently verified; check permissions and provenance."
    notice = str(session.pop("notice", "") or "")
    notice_html = f'<p class="notice">{escape(notice)}</p>' if notice else ""
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><style>
:root{{--ink:#163344;--muted:#536b78;--teal:#0b6b67;--deep:#104052;--line:#d5e1e6;--paper:#f2f7f8;--white:#fff;--amber:#fff5dc;--amber-ink:#653c00;}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
header{{background:var(--deep);color:white;padding:1.4rem max(1rem,calc((100vw - 1000px)/2))}}header h1{{margin:0;font-size:clamp(1.5rem,4vw,2.2rem)}}
nav{{display:flex;flex-wrap:wrap;gap:.55rem;margin-top:1rem}}nav a{{color:white;text-decoration:none;border:1px solid #a8c6d0;padding:.4rem .7rem;border-radius:7px}}nav a:hover,nav a:focus{{background:#20596c}}
main{{max-width:1000px;margin:1.2rem auto;padding:0 1rem 2rem}}.disclaimer{{padding:.85rem 1rem;background:var(--amber);color:var(--amber-ink);border-left:5px solid #d18b00;border-radius:7px;font-weight:700;margin-bottom:1rem}}
.dataset{{color:var(--muted);font-size:.92rem;margin:.5rem 0 1rem}}.panel,.entry-card{{background:var(--white);border:1px solid var(--line);border-radius:11px;padding:1rem 1.1rem;margin:.9rem 0;box-shadow:0 2px 7px #1737470c}}h2{{margin:.2rem 0 .7rem;font-size:1.35rem}}h3{{margin:.1rem 0 .25rem}}.category,.source,.muted{{color:var(--muted)}}
label{{display:block;font-weight:650;margin:.55rem 0 .2rem}}input[type=text],select,input[type=file]{{width:100%;max-width:620px;padding:.65rem;border:1px solid #8098a3;border-radius:6px;background:white;color:var(--ink);font:inherit}}button,.button{{display:inline-block;margin:.7rem .35rem .1rem 0;padding:.62rem .9rem;border:0;border-radius:7px;background:var(--teal);color:white;font:inherit;font-weight:700;text-decoration:none;cursor:pointer}}button:hover,.button:hover{{background:#084f4b}}.secondary{{background:#355d70}}.notice{{padding:.7rem .9rem;border-radius:7px;background:#e5f3f1;color:#104f4b}}.success{{color:#14532d;background:#effbf2;padding:.7rem;border-radius:7px}}.warning-list{{padding-left:1.4rem}}.warning-list li{{margin:.35rem 0}}
.entry-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:.8rem}}.entry-card p{{margin:.45rem 0}}.stats{{display:flex;flex-wrap:wrap;gap:.65rem}}.stat{{background:#e8f2f4;border-radius:8px;padding:.7rem 1rem;min-width:135px}}.stat strong{{display:block;font-size:1.35rem;color:var(--deep)}}.choice{{display:flex;align-items:flex-start;gap:.55rem;padding:.6rem;border:1px solid var(--line);border-radius:7px;margin:.45rem 0;font-weight:400}}.choice input{{margin-top:.38rem}}.correct{{border-left:5px solid #17803d;padding:.7rem;background:#effbf2}}.incorrect{{border-left:5px solid #b45309;padding:.7rem;background:#fff7ed}}footer{{max-width:1000px;margin:0 auto;padding:0 1rem 1.5rem;color:var(--muted);font-size:.9rem}}
@media(max-width:560px){{header{{padding:1rem}}main{{margin-top:.8rem}}.panel,.entry-card{{padding:.85rem}}nav a{{font-size:.92rem}}}}
</style></head><body><header><h1>Medical Terminology &amp; Coding Practice Tool</h1><nav aria-label="Main navigation"><a href="/">Home</a><a href="/search">Search</a><a href="/flashcards">Flashcards</a><a href="/quiz">Quiz</a><a href="/import">Reference Import</a></nav></header>
<main><p class="disclaimer">Educational practice only. This tool does not provide clinically validated diagnoses, official code assignments, billing advice, or regulatory guidance.</p>
<p class="dataset">{dataset_notice}</p>{notice_html}{content}</main>
<footer>Use only terminology data you are entitled to use. Imported reference files are displayed as supplied and are not independently verified.</footer></body></html>'''


def render_search(session: dict[str, object], query: str = "", category: str = "All categories") -> str:
    entries = session["entries"]
    assert isinstance(entries, list)
    cats = categories(entries)
    options = '<option value="All categories">All categories</option>' + "".join(
        f'<option value="{escape(cat)}"{" selected" if cat.casefold() == category.casefold() else ""}>{escape(cat)}</option>'
        for cat in cats
    )
    matches = search_entries(entries, query, category)
    if not query.strip() and category == "All categories":
        results_html = '<p class="muted">Enter a search term or choose a category to browse.</p>'
    elif matches:
        results_html = '<div class="entry-grid">' + "".join(render_entry_card(entry) for entry in matches) + '</div>'
    else:
        results_html = '<p class="muted">No entries matched. Try a different spelling or category.</p>'
    body = f'''<section class="panel"><h2>Search the reference</h2><form method="get" action="/search">
<label for="q">Search term, definition, category, or reference code</label><input id="q" name="q" type="text" maxlength="200" value="{escape(query)}">
<label for="category">Category filter</label><select id="category" name="category">{options}</select><button type="submit">Search</button></form></section>
<section><h2>Results ({len(matches)})</h2>{results_html}</section>'''
    return render_page(session, body, title="Search · Medical Terminology Practice Tool")


def render_flashcard(session: dict[str, object], index: int = 0, reveal: bool = False) -> str:
    entries = session["entries"]
    order = session["flash_order"]
    assert isinstance(entries, list) and isinstance(order, list)
    if not entries:
        body = '<section class="panel"><h2>No terms available</h2><p>Import a CSV containing practice entries to use flashcards.</p></section>'
    else:
        index = index % len(order)
        entry = entries[order[index]]
        actions = f'<p class="muted">Card {index + 1} of {len(order)}</p>'
        if reveal:
            actions += render_entry_card(entry)
        else:
            actions += f'<article class="entry-card"><h3>{escape(entry.get("term", "") or "Term not supplied")}</h3><p class="category">{escape(entry.get("category", "") or "Category not supplied")}</p><p>Think of the definition, then reveal the entry.</p></article>'
        actions += f'<a class="button" href="/flashcards?index={index}&amp;reveal=1">Reveal definition and reference</a>' if not reveal else ""
        actions += f'<a class="button secondary" href="/flashcards?index={(index + 1) % len(order)}">Next card</a>'
        actions += '<a class="button secondary" href="/flashcards?shuffle=1">Shuffle cards</a>'
        body = '<section class="panel"><h2>Flashcards</h2>' + actions + '</section>'
    return render_page(session, body, title="Flashcards · Medical Terminology Practice Tool")


def render_quiz(session: dict[str, object]) -> str:
    questions = session["quiz_questions"]
    seen = session["quiz_seen"]
    results = session["quiz_results"]
    assert isinstance(questions, list) and isinstance(seen, set) and isinstance(results, list)
    score = score_results(results)
    stats = f'''<div class="stats"><div class="stat">Questions answered<strong>{score['answered']}</strong></div><div class="stat">Correct answers<strong>{score['correct']}</strong></div><div class="stat">Score<strong>{score['percentage']:.1f}%</strong></div></div>'''
    last_html = ""
    last = session.pop("last_result", None)
    if isinstance(last, dict):
        style = "correct" if last["correct"] else "incorrect"
        result_text = "Correct" if last["correct"] else "Not quite"
        last_html = f'<div class="{style}"><strong>{result_text}.</strong> Expected answer: {escape(last["expected_answer"])}<br>{escape(last["explanation"] or "No explanation was supplied in the reference row.")}</div>'

    current = next_unanswered_question(questions, seen)
    if not questions:
        quiz_html = '<p class="muted">There are not enough distinct terms or answer choices to make a valid three-option multiple-choice quiz. Import a larger reference dataset.</p>'
    elif current is None:
        quiz_html = '<p class="success">All available questions have been used in this quiz session. Reset the quiz to start a new round.</p><form method="post" action="/quiz"><input type="hidden" name="action" value="reset"><button class="secondary" type="submit">Reset quiz</button></form>'
    else:
        options = "".join(
            f'<label class="choice"><input type="radio" name="answer" value="{index}" required><span>{escape(option)}</span></label>'
            for index, option in enumerate(current["options"])
        )
        quiz_html = f'''<section class="panel"><p class="muted">Question {len(seen) + 1} of {len(questions)}</p><h2>{escape(current['prompt'])}</h2>
<form method="post" action="/quiz"><input type="hidden" name="action" value="answer"><input type="hidden" name="question_id" value="{escape(current['question_id'])}">{options}<button type="submit">Submit answer</button></form></section>'''
    body = f'<section class="panel"><h2>Quiz</h2>{stats}{last_html}</section>{quiz_html}<p><a class="button secondary" href="/export.csv">Download session results CSV</a></p>'
    return render_page(session, body, title="Quiz · Medical Terminology Practice Tool")


def render_import(session: dict[str, object]) -> str:
    body = '''<section class="panel"><h2>Import a reference CSV</h2>
<p>Required columns: <code>term,definition,category,reference_code,explanation,source_name,source_version</code>.</p>
<p>Imported rows replace the practice data for this browser session only. Duplicate terms/codes and blank reference/source fields are shown as warnings. No missing values are invented.</p>
<form method="post" action="/import" enctype="multipart/form-data"><label for="reference_file">Choose CSV file</label>
<input id="reference_file" type="file" name="reference_file" accept=".csv,text/csv" required><button type="submit">Validate and import</button></form></section>'''
    warnings = session.pop("import_warnings", [])
    if warnings:
        body += '<section class="panel"><h2>Import warnings</h2>' + _warning_list(warnings) + '</section>'
    entries = session.get("entries", [])
    body += f'<p class="muted">Current session dataset: {len(entries)} rows.</p>'
    return render_page(session, body, title="Reference Import · Medical Terminology Practice Tool")


def render_home(session: dict[str, object]) -> str:
    entries = session["entries"]
    body = f'''<section class="panel"><h2>Practice workspace</h2><p>This local tool supports terminology lookup, flashcards, multiple-choice practice, and CSV reference imports.</p>
<div class="stats"><div class="stat">Reference entries<strong>{len(entries)}</strong></div><div class="stat">Quiz questions<strong>{len(session['quiz_questions'])}</strong></div></div></section>
<section class="panel"><h2>Quick search</h2><form method="get" action="/search"><label for="q">Term, definition, category, or reference code</label><input id="q" name="q" type="text" maxlength="200"><button type="submit">Search</button></form></section>
<section class="panel"><h2>Start learning</h2><p><a class="button" href="/flashcards">Open flashcards</a><a class="button" href="/quiz">Start quiz</a><a class="button secondary" href="/import">Import reference CSV</a></p></section>'''
    return render_page(session, body, title="Home · Medical Terminology Practice Tool")


class PracticeState:
    def __init__(self, sample_path: Path = SAMPLE_DATA):
        self.sample_entries, self.sample_warnings = load_reference_csv(sample_path)
        self.sessions: dict[str, dict[str, object]] = {}

    def new_session(self) -> dict[str, object]:
        entries = [dict(row) for row in self.sample_entries]
        return {
            "entries": entries,
            "dataset_kind": "sample",
            "dataset_filename": "Fictional Practice Glossary",
            "import_warnings": list(self.sample_warnings),
            "flash_order": list(range(len(entries))),
            "quiz_questions": build_quiz_questions(entries),
            "quiz_seen": set(),
            "quiz_results": [],
            "notice": "",
        }


def _single(form: dict[str, list[str]], key: str, limit: int = 1000) -> str:
    values = form.get(key, [""])
    value = values[0] if values else ""
    if len(value) > limit:
        raise ValueError(f"The {key} value is too long.")
    return value


def _uploaded_csv(content_type: str, body: bytes) -> tuple[str, bytes]:
    try:
        content_type_bytes = content_type.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError("Invalid upload content type.") from exc
    message_bytes = b"Content-Type: " + content_type_bytes + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    message = BytesParser(policy=email_policy).parsebytes(message_bytes)
    if not message.is_multipart():
        raise ValueError("Please upload a CSV file using the file picker.")
    for part in message.iter_parts():
        if part.get_content_disposition() == "form-data" and part.get_param("name", header="content-disposition") == "reference_file":
            filename = part.get_filename() or "uploaded-reference.csv"
            filename = filename.replace("\\", "/").split("/")[-1][:120]
            payload = part.get_payload(decode=True) or b""
            return filename, payload
    raise ValueError("No reference_file upload was included in the form.")


class PracticeHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, handler_class, state: PracticeState):
        self.state = state
        super().__init__(address, handler_class)


class PracticeHandler(BaseHTTPRequestHandler):
    server: PracticeHTTPServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args) -> None:
        # Keep the beginner's terminal readable and avoid logging query values.
        return

    def _session(self) -> tuple[str, dict[str, object], bool]:
        cookies = SimpleCookie(self.headers.get("Cookie", ""))
        cookie = cookies.get("practice_session")
        session_id = cookie.value if cookie else ""
        session = self.server.state.sessions.get(session_id)
        if session is None:
            session_id = secrets.token_urlsafe(24)
            session = self.server.state.new_session()
            self.server.state.sessions[session_id] = session
            return session_id, session, True
        return session_id, session, False

    def _send(self, status: int, body: bytes = b"", content_type: str = "text/html; charset=utf-8",
              session_id: str = "", new_cookie: bool = False, extra_headers: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self' 'unsafe-inline'; form-action 'self'; base-uri 'none'; object-src 'none'")
        if new_cookie:
            self.send_header("Set-Cookie", f"practice_session={session_id}; HttpOnly; SameSite=Lax; Path=/")
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _page(self, session_id: str, session: dict[str, object], is_new: bool, body: str, status: int = 200) -> None:
        self._send(status, render_page(session, body).encode("utf-8"), session_id=session_id, new_cookie=is_new)

    def _redirect(self, path: str, session_id: str, is_new: bool) -> None:
        self._send(303, session_id=session_id, new_cookie=is_new, extra_headers={"Location": path})

    def do_GET(self) -> None:
        session_id, session, is_new = self._session()
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query, keep_blank_values=True)
        try:
            if parsed.path == "/":
                self._page(session_id, session, is_new, render_home(session))
            elif parsed.path == "/search":
                query = _single(params, "q", 200)
                category = _single(params, "category", 100)
                if category and category != "All categories" and category not in categories(session["entries"]):
                    raise ValueError("Choose a category from the available list.")
                self._send(200, render_search(session, query, category or "All categories").encode("utf-8"), session_id=session_id, new_cookie=is_new)
            elif parsed.path == "/flashcards":
                if _single(params, "shuffle", 2) == "1":
                    random.shuffle(session["flash_order"])
                    self._redirect("/flashcards", session_id, is_new)
                    return
                raw_index = _single(params, "index", 12) or "0"
                if not raw_index.isdecimal():
                    raw_index = "0"
                reveal = _single(params, "reveal", 2) == "1"
                self._send(200, render_flashcard(session, int(raw_index), reveal).encode("utf-8"), session_id=session_id, new_cookie=is_new)
            elif parsed.path == "/quiz":
                if _single(params, "reset", 2) == "1":
                    session["quiz_seen"] = set()
                    session["quiz_results"] = []
                    session.pop("last_result", None)
                    session["notice"] = "Quiz session reset."
                    self._redirect("/quiz", session_id, is_new)
                    return
                self._send(200, render_quiz(session).encode("utf-8"), session_id=session_id, new_cookie=is_new)
            elif parsed.path == "/import":
                self._send(200, render_import(session).encode("utf-8"), session_id=session_id, new_cookie=is_new)
            elif parsed.path == "/export.csv":
                filename, csv_text = build_quiz_export(session["quiz_results"])
                self._send(200, csv_text.encode("utf-8"), "text/csv; charset=utf-8", session_id, is_new,
                           {"Content-Disposition": f'attachment; filename="{filename}"'})
            else:
                self._page(session_id, session, is_new, '<section class="panel"><h2>Page not found</h2><p>Use the navigation links to continue.</p></section>', 404)
        except ValueError as exc:
            body = f'<section class="panel"><h2>Invalid input</h2><p>{escape(exc)}</p></section>'
            self._page(session_id, session, is_new, body, 400)

    def do_POST(self) -> None:
        session_id, session, is_new = self._session()
        parsed = urlparse(self.path)
        try:
            raw_length = self.headers.get("Content-Length", "0")
            if not raw_length.isdecimal():
                raise ValueError("Invalid request length.")
            length = int(raw_length)
            if length > MAX_UPLOAD_BYTES:
                raise ValueError("Request is larger than the 2 MB upload limit.")
            body = self.rfile.read(length)
            if parsed.path == "/quiz":
                self._handle_quiz_post(session_id, session, is_new, body)
            elif parsed.path == "/import":
                self._handle_import_post(session_id, session, is_new, body)
            else:
                self._page(session_id, session, is_new, '<section class="panel"><h2>Page not found</h2></section>', 404)
        except (ValueError, UnicodeError) as exc:
            self._page(session_id, session, is_new, f'<section class="panel"><h2>Could not process request</h2><p>{escape(exc)}</p></section>', 400)

    def _handle_quiz_post(self, session_id: str, session: dict[str, object], is_new: bool, body: bytes) -> None:
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/x-www-form-urlencoded"):
            raise ValueError("Quiz answers must be submitted using the quiz form.")
        form = parse_qs(body.decode("utf-8", errors="strict"), keep_blank_values=True)
        action = _single(form, "action", 20)
        if action == "reset":
            session["quiz_seen"] = set()
            session["quiz_results"] = []
            session.pop("last_result", None)
            session["notice"] = "Quiz session reset."
            self._redirect("/quiz", session_id, is_new)
            return
        if action != "answer":
            raise ValueError("Select a valid quiz action.")
        question_id = _single(form, "question_id", 100)
        questions = session["quiz_questions"]
        seen = session["quiz_seen"]
        current = next_unanswered_question(questions, seen)
        if current is None or current["question_id"] != question_id:
            raise ValueError("That question is no longer current. Load the quiz and answer the displayed question.")
        answer_index = _single(form, "answer", 3)
        if not answer_index.isdecimal() or int(answer_index) >= len(current["options"]):
            raise ValueError("Choose one of the listed answer options.")
        selected = current["options"][int(answer_index)]
        correct = selected == current["expected_answer"]
        results = session["quiz_results"]
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        result = {
            "timestamp": timestamp,
            "question": current["prompt"],
            "selected_answer": selected,
            "expected_answer": current["expected_answer"],
            "correct": correct,
            "explanation": current["explanation"],
        }
        session["quiz_seen"].add(question_id)
        results.append(result)
        score = score_results(results)
        result["score_percentage"] = score["percentage"]
        session["last_result"] = result
        self._redirect("/quiz", session_id, is_new)

    def _handle_import_post(self, session_id: str, session: dict[str, object], is_new: bool, body: bytes) -> None:
        filename, payload = _uploaded_csv(self.headers.get("Content-Type", ""), body)
        if len(payload) > MAX_UPLOAD_BYTES:
            raise ValueError("Uploaded file is larger than the 2 MB limit.")
        try:
            csv_text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError("CSV must use UTF-8 text encoding.") from exc
        try:
            entries, warnings = parse_reference_csv(csv_text)
        except (ReferenceDataError, csv.Error) as exc:
            raise ValueError(str(exc)) from exc
        session["entries"] = entries
        session["dataset_kind"] = "imported"
        session["dataset_filename"] = filename
        session["import_warnings"] = warnings
        session["flash_order"] = list(range(len(entries)))
        session["quiz_questions"] = build_quiz_questions(entries)
        session["quiz_seen"] = set()
        session["quiz_results"] = []
        session.pop("last_result", None)
        session["notice"] = f"Imported {len(entries)} row(s) from {filename}. Source details are displayed as supplied and were not independently verified."
        self._redirect("/import", session_id, is_new)


def create_server(port: int = 8000, state: PracticeState | None = None) -> PracticeHTTPServer:
    return PracticeHTTPServer(("127.0.0.1", port), PracticeHandler, state or PracticeState())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Start the offline terminology practice web app.")
    parser.add_argument("--port", type=int, default=8000, help="Local port to use (default: 8000)")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        server = create_server(args.port)
    except OSError as exc:
        parser.error(f"could not start local server on port {args.port}: {exc}")
    print(f"Serving locally at http://127.0.0.1:{server.server_port}/")
    print("Press Ctrl+C to stop. Educational practice only; imported references are not independently verified.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local practice server.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
