"""Command-line entry point for the clinical data quality training checker."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from validator import validate_csv, write_report

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT_DIR / "sample_trial_data.csv"
DEFAULT_OUTPUT = PROJECT_DIR / "data_quality_report.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check a fictional clinical-trial CSV for training data-quality issues."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input CSV path (default: sample_trial_data.csv)")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Issue report CSV path (default: data_quality_report.csv)")
    return parser


def print_summary(result: dict[str, object], output_path: str | Path) -> None:
    issues = result["issues"]
    assert isinstance(issues, list)
    print("Clinical Trial Data Quality Checker - educational simulation")
    print(f"Records checked: {result['records_checked']}")
    print(f"Unique participant IDs: {result['unique_participant_ids']}")
    print(f"Total issues found: {len(issues)}")
    print(f"Records with no detected issues: {result['records_without_detected_issues']}")
    print("Issue counts by type:")
    counts = Counter(str(issue["issue_type"]) for issue in issues)
    if counts:
        for issue_type in sorted(counts):
            print(f"  {issue_type}: {counts[issue_type]}")
    else:
        print("  No detected issues.")
    print(f"Report written to: {output_path}")
    print("No source values were changed or automatically repaired.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_path = Path(args.input)
    output_path = Path(args.output)
    if input_path.resolve() == output_path.resolve():
        parser.error("--output must be different from --input; source data is never overwritten")

    try:
        result = validate_csv(input_path)
        write_report(result["issues"], output_path)
    except FileNotFoundError:
        parser.error(f"input file not found: {input_path}")
    except (PermissionError, OSError) as exc:
        parser.error(f"could not read input or write report: {exc}")
    except (UnicodeError, csv.Error) as exc:
        parser.error(f"could not read CSV data: {exc}")

    missing_headers = result["missing_headers"]
    if missing_headers:
        print("Missing required CSV headers: " + ", ".join(missing_headers), file=sys.stderr)
        print(f"Header findings were written to: {output_path}", file=sys.stderr)
    print_summary(result, output_path)
    return 1 if missing_headers else 0


if __name__ == "__main__":
    raise SystemExit(main())
