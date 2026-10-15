# Project 05: Clinical Trial Eligibility Screener

A beginner-friendly, local web application for learning how a fictional study's inclusion and exclusion criteria can be checked against participant records. It uses Python's standard library, a built-in HTTP server, and configurable JSON criteria. No third-party packages, internet access, external APIs, or paid services are needed.

> **Educational simulation using configurable sample criteria. Results are not medical advice, do not establish clinical-trial eligibility, and must not be used for actual recruitment or clinical decisions.**

All included participants and study rules are fictional. This tool does not replace a protocol, investigator judgment, or clinical review and produces no diagnosis. For demonstrations, use fictional data or data you are authorized to use and have properly de-identified. Do not enter identifiable patient information.

## Requirements and launch

- Python 3.9 or later (tested with Python 3.11).
- No dependency installation is required; `requirements.txt` documents that there are no third-party packages.

From this folder, run:

```powershell
python app.py
```

Open <http://127.0.0.1:8000> in a browser. Press `Ctrl+C` in the terminal to stop the server. The server binds to localhost only and keeps imported participants and configuration in browser-session memory; restarting the process clears that session state.

## Features

- Overview, editable fictional study configuration, participant import, screening results, and report pages.
- Load included fictional sample participants or import a CSV.
- View every criterion's name, type, field, operator, expected value, observed value, result, and explanation.
- Filter the report by overall status and download criterion-level CSV.
- Server-side validation, escaped HTML output, duplicate-ID checks, upload-size limit, and helpful input errors.

## Participant CSV

Required headers are `participant_id`, `age`, `bmi`, `smoking_status`, `medical_history_flag`, and `consent_status`. The `notes` column is optional. Keep values as text exactly as recorded. Blank values and invalid numeric values remain unassessable and produce `UNKNOWN` when a configured criterion uses them.

```csv
participant_id,age,bmi,smoking_status,medical_history_flag,consent_status,notes
DEMO-101,34,24.2,Never,No,Yes,Fictional demonstration row
```

CSV structure and duplicate participant IDs are checked on import. Extra fields in a row, missing required headers, empty IDs, and unsupported file types are rejected. Invalid numeric values are preserved and shown as `UNKNOWN`; they are not silently corrected.

## Study configuration

The application starts with [`study_config.json`](study_config.json). Edit JSON in the **Study configuration** page, or edit this file before starting the app. Configuration must include a study name and at least one criterion. Each criterion has a unique `name`, `type` (`inclusion` or `exclusion`), supported `field`, supported `operator`, `expected` value, and a plain-language `explanation`.

Example:

```json
{
  "study_name": "Fictional Practice Study",
  "criteria": [
    {
      "name": "Age range",
      "type": "inclusion",
      "field": "age",
      "operator": "between",
      "expected": [18, 65],
      "explanation": "Age is within the configured example range."
    }
  ]
}
```

Supported fields: `age`, `bmi`, `participant_id`, `smoking_status`, `medical_history_flag`, and `consent_status`. (The available criterion fields are explicitly listed in `screening.py`; fields not supported there are rejected.) Numeric fields support `>=`, `<=`, `>`, `<`, `==`, and `between` with two ordered numeric bounds. Text fields support `==`, `!=`, `in`, `not_in`, and `contains`. The condition describes the condition being checked: a matched inclusion is `MET` (favorable), while a matched exclusion is `MET` (disqualifying). Use clear criterion names/explanations and only fictional example thresholds. The app validates field/operator compatibility, expected values, and criterion structure before saving. Invalid configurations are not applied.

Configuration changes and imported records live in the current browser session; edit the JSON file for a durable local starting configuration. Never treat example rules as universal eligibility standards.

## Interpreting outcomes

- **MET**: the condition expressed by that criterion matches the observed value.
- **NOT MET**: the criterion's condition does not match the observed value.
- **UNKNOWN**: required information is blank, invalid, or cannot be assessed.
- **MEETS CONFIGURED CRITERIA**: all configured criteria were assessable; no failed inclusion or met exclusion disqualified the record.
- **DOES NOT MEET CONFIGURED CRITERIA**: an inclusion criterion was `NOT MET` or an exclusion criterion was `MET`.
- **REQUIRES REVIEW**: there is no known disqualifying result, but at least one criterion is `UNKNOWN`.

When a record has both a disqualifying result and unknown criteria, the overall status is does not meet while the unknown criteria remain visibly flagged for review. These are mechanical outcomes against the saved fictional configuration, not clinical decisions.

## Tests

Run from this project directory:

```powershell
python -m unittest discover -s tests -v
```

The tests use `unittest` and cover criteria/configuration validation, numeric boundaries, unknown and disqualifying results, CSV import validation, report export, HTML safety, and local HTTP responses.

## Project structure

```text
app.py                 Local HTTP interface
screening.py           Configuration, CSV, screening, and report functions
study_config.json      Fictional sample criteria
sample_data/           Fictional participant CSV
tests/                 Standard-library unit and HTTP smoke tests
requirements.txt       Notes that no external dependencies are needed
```

## Limitations

This is a small local learning exercise, not a validated, secure, multi-user, or regulatory system. It has no authentication, audit trail, database, protocol management, access controls, or clinical review workflow. Session state is in memory and disappears when the server restarts. The demo uses a fixed localhost port (8000). Do not use it for actual recruitment, clinical decisions, or real patient data.
