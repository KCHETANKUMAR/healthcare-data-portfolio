# Clinical Research Study Dashboard

A beginner-friendly, offline Python command-line tool that summarizes fictional clinical research participant and visit CSV files into a self-contained HTML dashboard. It uses only Python's standard library.

> **Educational simulation only. This dashboard is not a validated clinical trial system and must not be used for medical decisions, participant management, or regulatory reporting.** The bundled data is fictional. Never enter real participant information.

## Purpose and learning objectives

Practice CSV loading, header and date checks, duplicate and cross-file ID checks, descriptive counts, simple HTML/CSS generation, HTML escaping, command-line arguments, and automated tests. The dashboard describes the supplied files; it does not verify clinical correctness or study conduct.

## Features

- Summarizes participant totals by site and study status, and visits by status and site.
- Reports completed and missed visits, overdue scheduled visits, missing fields, duplicate IDs, invalid dates, and unknown participant links.
- Generates responsive, accessible, self-contained HTML with no JavaScript libraries, web server, or network connection.
- Escapes CSV-derived text before adding it to HTML.
- Does not fill missing values or change the source files.

## Technology and requirements

Python 3.10 or later. The project uses only the standard library (`argparse`, `csv`, `datetime`, `html`, `pathlib`, `collections`, and `unittest`). No third-party packages or internet access are needed. `requirements.txt` states this explicitly.

## Files

```text
03-clinical-research-study-dashboard/
├── main.py
├── dashboard.py
├── sample_participants.csv
├── sample_visits.csv
├── requirements.txt
├── README.md
├── .gitignore
└── tests/
    └── test_dashboard.py
```

The sample files contain 20 fictional participant records across four fictional sites and 40 fictional visit records. They include a few deliberate missing values, duplicate IDs, invalid dates, and a visit linked to an unknown participant to demonstrate manual-review warnings.

## Run the sample

From this folder:

```powershell
python main.py
```

The command uses the sample CSVs, uses today's date as the overdue-visit reference date, and writes `dashboard.html` in this folder. Open the file in a normal browser (for example, double-click it or run `Start-Process .\dashboard.html` in PowerShell). The HTML is self-contained and works offline.

For a reproducible reference date:

```powershell
python main.py --as-of 2026-10-15
```

## Use custom CSV files

```powershell
python main.py --participants participants.csv --visits visits.csv --output dashboard.html --as-of 2026-10-15
```

The participant file needs the columns `participant_id`, `site_id`, `enrollment_date`, `study_status`, `age`, and `sex`. The visit file needs `visit_id`, `participant_id`, `visit_name`, `planned_date`, `actual_date`, and `visit_status`. Header omissions, duplicate headers, malformed rows, unreadable files, and invalid reference dates produce helpful errors. Invalid or missing field values that can still be summarized appear as data-quality warnings.

## Interpret the summaries

Visit completion percentage is **completed visit rows divided by all visit rows**. The denominator includes scheduled, missed, and cancelled rows, so this simple percentage is not a protocol-defined compliance measure. Site visit counts use the site listed for the linked participant; unknown participant references appear under “Unknown participant.” Missing site or status categories stay explicitly labeled as missing.

An overdue visit is counted only when it is Scheduled, has a valid ISO `planned_date` earlier than the reference date, and has no `actual_date`. This is a simplified training rule. Actual overdue definitions depend on the study protocol. A missing date is never invented, and an actual date present on a scheduled visit excludes it from this overdue calculation.

Warnings point to supplied values for manual review. Unflagged values are not certified correct, and the dashboard does not diagnose participants, recommend treatment, infer adverse-event causality, or claim regulatory compliance. Its counts describe only the bundled fictional training dataset or the custom files supplied by the user; they are not real study results.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

Tests use temporary directories and the Python standard library only.

## Screenshots

Screenshots can be added later under a `screenshots/` folder. A useful example would show the sample dashboard in a browser. Include fictional data only.
