# Medical Terminology & Coding Practice Tool

A small, beginner-friendly local web application for looking up terminology, reviewing flashcards, taking a multiple-choice quiz, and importing a reference CSV. It runs with Python's standard library and does not need internet access.

> **Educational practice only.** This tool does not provide clinically validated diagnoses, official code assignments, billing advice, or regulatory guidance. The bundled identifiers and mappings are fictional, nonofficial practice examples. Imported references are displayed as supplied and are not independently verified.

## Why this is useful for a beginner portfolio

The project demonstrates practical Python skills with CSV parsing, validation, search, quiz scoring, session state, HTML escaping, a local HTTP server, and CSV export, while clearly separating practice material from authoritative coding systems.

## Features

- Search entries by term, definition, category, or reference code, with a category filter.
- Review one flashcard at a time, reveal its definition/reference entry, advance, and shuffle.
- Take a multiple-choice quiz with both term-to-definition and term-to-practice-identifier questions. Questions do not repeat in a round; scoring is shown as the learner answers.
- Import a reference CSV through the local interface. Required columns are checked; duplicate terms/codes and blank reference/source fields generate warnings.
- Download quiz answers and a session summary as a CSV with a fixed, safe filename pattern.
- Imported values are HTML-escaped. The local server validates form fields and uploads and is bound to `127.0.0.1` only.

## Requirements

Python 3.10 or later. No third-party packages, internet access, cloud account, external API, or web server installation is needed. `requirements.txt` states that Python's standard library is sufficient.

## Launch locally

From this project folder, run:

```powershell
python app.py
```

Open the printed address, normally `http://127.0.0.1:8000/`, in your browser. Stop the server with **Ctrl+C**. To choose another local port, use `python app.py --port 8080`.

## Sample reference data

The built-in sample is `sample_data/reference_terms.csv`. Its identifiers (`PRACTICE-001`, etc.) are **nonofficial practice identifiers** and do not represent ICD, SNOMED CT, CPT, or any other official code system. Definitions and explanations are simplified demonstrations, not verified clinical references.

Expected CSV columns and example row:

```csv
term,definition,category,reference_code,explanation,source_name,source_version
Example term,A short practice definition,General terminology,PRACTICE-101,Practice explanation only,Instructor-provided dataset,1.0
```

Use **Reference Import** in the application to select a CSV file. The uploaded rows replace the sample reference only in that browser session while the server process is running; the tool does not write or alter the uploaded file. Source name and version appear as supplied. Blank source details remain blank and are identified as missing; nothing is filled in automatically. Duplicate names and codes are retained and reported for review. You are responsible for checking the source, version, license, and permissions for any external dataset you import. Do not import proprietary data unless you are entitled to use it.

## Quiz results

Use **Download session results CSV** in Quiz mode. The download contains a timestamp, each question, selected and expected answers, correctness, score percentage, explanations, and a final session summary. The download filename uses a fixed `quiz-results-YYYYMMDD-HHMMSS.csv` pattern. Quiz results and imported data are held in server memory for the session; they are not stored in a database and are cleared when the server stops.

## Tests

Run the standard-library unit tests from this folder:

```powershell
python -m unittest discover -s tests -v
```

## Project structure

```text
04-medical-coding-practice-tool/
├── app.py                         # local HTTP server and web interface
├── reference_data.py               # CSV validation, duplicate warnings, search
├── quiz.py                         # question generation, scoring, CSV export
├── sample_data/
│   └── reference_terms.csv         # fictional practice examples
├── requirements.txt                # no third-party dependencies
├── README.md
├── .gitignore
└── tests/
    └── test_tool.py
```

## Limitations and safe use

This is a learning tool, not a clinical or coding reference. It does not validate diagnoses, assign official codes, support billing, provide regulatory guidance, or replace qualified review. Even imported data with source metadata is not independently verified by this application. No real patient data should be entered. The application binds to the local computer, and imported references and quiz results remain in memory only for the current run/session.
