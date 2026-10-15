"""Small reusable quiz helpers and safe CSV result export."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timezone
from io import StringIO
from typing import Iterable, Mapping

EXPORT_FIELDS = (
    "Timestamp", "Question", "Selected answer", "Expected answer", "Result", "Score percentage", "Explanation"
)


def next_unanswered_question(questions: Iterable[Mapping[str, object]], seen: set[str]) -> Mapping[str, object] | None:
    """Return the first unused question, or None after a full quiz round."""
    return next((question for question in questions if str(question.get("question_id", "")) not in seen), None)


def build_quiz_questions(entries: Iterable[Mapping[str, str]], *, minimum_options: int = 3,
                         rng: random.Random | None = None) -> list[dict[str, object]]:
    """Create nonrepeating definition and reference-code questions.

    A valid multiple-choice question requires at least ``minimum_options``
    distinct choices including its correct answer.
    """
    if minimum_options < 2:
        raise ValueError("A multiple-choice question needs at least two options.")
    rows = [dict(row) for row in entries]
    unique_rows = []
    seen_terms = set()
    for row in rows:
        term_key = row.get("term", "").strip().casefold()
        if term_key and term_key not in seen_terms:
            seen_terms.add(term_key)
            unique_rows.append(row)

    randomizer = rng or random.Random()
    questions: list[dict[str, object]] = []
    for target in unique_rows:
        term = target.get("term", "").strip()
        for kind, field, prompt in (
            ("definition", "definition", f"Which definition best matches the term: {term}?"),
            ("reference_code", "reference_code", f"Which nonofficial practice identifier is paired with: {term}?"),
        ):
            expected = target.get(field, "").strip()
            if not expected:
                continue
            candidates = list(dict.fromkeys(
                row.get(field, "").strip() for row in unique_rows
                if row.get(field, "").strip() and row.get(field, "").strip() != expected
            ))
            if len(candidates) < minimum_options - 1:
                continue
            options = [expected, *randomizer.sample(candidates, minimum_options - 1)]
            randomizer.shuffle(options)
            questions.append({
                "question_id": f"{len(questions) + 1:04d}-{kind}",
                "kind": kind,
                "prompt": prompt,
                "options": options,
                "expected_answer": expected,
                "explanation": target.get("explanation", ""),
                "term": term,
            })
    randomizer.shuffle(questions)
    return questions


def score_results(results: Iterable[Mapping[str, object]]) -> dict[str, float | int]:
    rows = list(results)
    correct = sum(1 for row in rows if bool(row.get("correct")))
    answered = len(rows)
    return {"answered": answered, "correct": correct, "percentage": (correct / answered * 100) if answered else 0.0}


def build_quiz_export(results: Iterable[Mapping[str, object]], now: datetime | None = None) -> tuple[str, str]:
    """Return a safe, fixed-pattern filename and CSV text including session summary."""
    rows = list(results)
    timestamp = now or datetime.now(timezone.utc)
    score = score_results(rows)
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({
            "Timestamp": row.get("timestamp", ""),
            "Question": row.get("question", ""),
            "Selected answer": row.get("selected_answer", ""),
            "Expected answer": row.get("expected_answer", ""),
            "Result": "Correct" if row.get("correct") else "Incorrect",
            "Score percentage": f"{float(row.get('score_percentage', 0)):.1f}%",
            "Explanation": row.get("explanation", ""),
        })
    writer.writerow({
        "Timestamp": timestamp.astimezone(timezone.utc).isoformat(timespec="seconds"),
        "Question": "SESSION SUMMARY",
        "Result": f"{score['correct']} correct of {score['answered']} answered",
        "Score percentage": f"{score['percentage']:.1f}%",
    })
    filename = "quiz-results-" + timestamp.astimezone(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".csv"
    return filename, output.getvalue()
