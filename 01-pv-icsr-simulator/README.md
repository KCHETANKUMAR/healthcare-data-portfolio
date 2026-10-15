# Pharmacovigilance ICSR Case Processing Simulator

A small, beginner-friendly portfolio project that demonstrates fictional Individual Case Safety Report intake, minimum-criteria review, follow-up tracking, and QC checklist persistence. Built for learning Python, Streamlit, and relational SQLite basics.

> **Educational simulation only. Not for processing real safety reports or regulatory submission.** This is not a validated regulatory system. Sample cases are fictional. Do not enter real patient or safety-report data.

## Features and learning objectives

- Dashboard metrics, searchable case list, filters, and privacy-conscious CSV export.
- Case intake and editing with a preserved source event description and unique `SIM-####` identifiers.
- Four ICSR minimum criteria are met only when each value is explicitly **Yes**. Unknown information is never inferred.
- Linked follow-up records and per-case QC checklist stored in SQLite.
- One-click insertion of three fictional cases; repeated insertion skips existing sample IDs.
- Learn forms, validation, SQL parameters, transactions, foreign keys, and basic automated tests.

## Technology

Python 3.10+, Streamlit, SQLite (`sqlite3`), and Pandas for display/export.

## Folder structure

```text
01-pv-icsr-simulator/
├── app.py
├── database.py
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
└── tests/
    └── test_database.py
```

## Run locally

From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

On macOS/Linux, activate with `source .venv/bin/activate` instead. The app creates `pv_simulator.db` beside `database.py` on first launch. It is ignored by Git.

Run automated tests:

```powershell
python -m unittest discover -s tests -v
```

The only direct runtime dependencies are Streamlit (the interface) and Pandas (case tables and CSV generation). SQLite support comes with Python's standard library; no separate SQLite package is needed.

### Troubleshooting installation

Check the interpreter and pip selected by the active environment:

```powershell
python --version
python -m pip --version
python -m pip config list
```

If installation reports a DNS or connection error, confirm network/DNS access to the configured package index (PyPI by default), then retry once the connection is available:

```powershell
python -m pip install --timeout 20 --retries 2 -r requirements.txt
```

On a managed network, ask its administrator which approved package index or proxy to use. Do not disable TLS/SSL verification or install packages from unknown sources. If `py` says no Python installation is available but `python --version` works, use `python` as shown above.

## Inspect the database

Install [DB Browser for SQLite](https://sqlitebrowser.org/), open this project's `pv_simulator.db`, and use **Browse Data** to inspect `cases`, `follow_ups`, and `qc_checklist`. Close the app before moving or backing up the database.

## Streamlit Community Cloud

1. Create a GitHub repository named `pharma-clinical-mini-projects` and add this folder as `01-pv-icsr-simulator/`.
2. Push the files to GitHub. Do not add `pv_simulator.db`.
3. In Streamlit Community Cloud, create an app from the repository, set the app file to `01-pv-icsr-simulator/app.py`, and deploy.
4. SQLite storage on a hosted app may be ephemeral and is not suitable for operational use. This simulator is educational only.

No deployment has been created for this project.

## Limitations

This project is a teaching aid, not validated software and not a substitute for company procedures, qualified review, or regulatory systems. It does not make clinical or regulatory judgments. Free-text seriousness information is recorded as entered and never guessed. Do not enter real or identifiable information. Cloud filesystem persistence is not guaranteed.

## Screenshots

Screenshots can be added later under a `screenshots/` directory. Capture the running fictional-data dashboard and case detail views, then link them here, for example: `![Dashboard](screenshots/dashboard.png)`.
