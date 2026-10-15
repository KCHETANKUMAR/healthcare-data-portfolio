# Clinical Trial Data Quality Checker

A beginner-friendly command-line exercise that scans a **fictional** clinical-trial participant CSV and writes a review report for potential data-quality issues. It uses only Python's standard library and leaves the source file unchanged.

> **Educational simulation only. This tool is not a validated clinical trial system and must not be used to make medical decisions or certify real clinical-trial data.** The included dataset is fictional. Do not use real patient or trial-participant data.

## Purpose and learning objectives

Practice reading CSV files, validating values, reporting row-level findings, writing CSV output, using command-line arguments, and writing tests with `unittest`. Findings are prompts for manual review; they are not proof that the source is wrong.

## Features

- Checks the required CSV header and required values.
- Flags repeated participant IDs, non-numeric or out-of-training-range ages, invalid ISO dates, and consent/adverse-event responses other than Yes or No.
- Checks blood pressure values only when supplied. Non-numeric values and values outside the configured exercise ranges are reported for review.
- Produces a report with one row per finding, including the CSV row number, original value, explanation, and a suggested manual review action. A header-only report is produced when no issues are detected.
- Prints record counts, unique participant IDs, issue counts by type, and records with no detected issues.
- Never fills, edits, or automatically repairs source values. Blank and unknown information is not treated as a negative response.

## Training checks and limitations

The default age range is **18–100**, systolic blood pressure range **70–250**, and diastolic blood pressure range **40–150**. The values are configurable through the `validate_records` and `validate_csv` functions in `validator.py`. The blood pressure ranges are simplified programming-exercise limits, **not clinical decision limits**. An out-of-range result is only a prompt to review the source and configuration; it is not a diagnosis. This tool does not assess eligibility, consent validity, medical significance, protocol compliance, or whether a real dataset is fit for use.

## Requirements

Python 3.10 or later. No third-party packages, internet connection, Pandas, or Streamlit are needed. `requirements.txt` documents that the standard library is sufficient.

## Files

```text
02-clinical-data-quality-checker/
├── main.py                   # CLI and summary
├── validator.py              # CSV reading, checks, and report writing
├── sample_trial_data.csv     # 12 fictional training rows
├── data_quality_report.csv   # generated on run; ignored by Git
├── requirements.txt          # no third-party dependencies
├── README.md
├── .gitignore
└── tests/
    └── test_validator.py
```

## Run the included sample

From this folder:

```powershell
python main.py
```

This validates `sample_trial_data.csv` and writes `data_quality_report.csv` next to the script.

## Check another CSV

```powershell
python main.py --input another_file.csv --output my_report.csv
```

Input CSVs must include the required headers listed in the project goal. Missing headers are reported in the output and also produce a clear terminal warning. Missing input files, unreadable files, malformed CSVs, and unwritable report destinations produce command-line errors.

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Interpret the report

Each output row is one finding. `row_number` counts from the input CSV's first line, so the header is row 1 and the first data record is row 2. Header findings use row 1. `original_value` preserves the supplied value as read; the suggested action asks for manual source review and does not change the data. A count of “records with no detected issues” means only that these programmed checks did not flag those records; it does not confirm them error-free.

The included sample contains 12 fictional rows, including several deliberate training issues and four records intended to produce no findings. The report is regenerated when the sample is run.

## Screenshots

This is a terminal tool, so no browser screenshot applies. To capture its real output locally, run `python main.py` from this folder and use Windows Snipping Tool on the terminal summary. Crop out the prompt and the final report-path line to avoid exposing a local path. If you save the image as `screenshots/cli-summary.png`, add `![CLI summary for fictional training data](screenshots/cli-summary.png)` here. The bundled sample data is fictional; do not show real participant information.
