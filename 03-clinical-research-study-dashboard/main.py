"""Generate an offline HTML dashboard from fictional study CSV files."""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from pathlib import Path

from dashboard import (
    DashboardInputError,
    PARTICIPANT_FIELDS,
    VISIT_FIELDS,
    analyze_data,
    load_csv,
    write_dashboard,
)

PROJECT_DIR = Path(__file__).resolve().parent


def _reference_date(value: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid ISO date in YYYY-MM-DD format") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("must use exact ISO YYYY-MM-DD format")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a self-contained dashboard from fictional study CSV files.")
    parser.add_argument("--participants", default=str(PROJECT_DIR / "sample_participants.csv"), help="Participant CSV path")
    parser.add_argument("--visits", default=str(PROJECT_DIR / "sample_visits.csv"), help="Visit CSV path")
    parser.add_argument("--output", default=str(PROJECT_DIR / "dashboard.html"), help="Output HTML path")
    parser.add_argument("--as-of", type=_reference_date, default=date.today(), help="Reference date YYYY-MM-DD for overdue visit counts (default: today)")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        participants = load_csv(args.participants, PARTICIPANT_FIELDS)
        visits = load_csv(args.visits, VISIT_FIELDS)
        summary = analyze_data(participants, visits, as_of=args.as_of)
        write_dashboard(summary, args.output)
    except FileNotFoundError as exc:
        parser.error(f"input file not found: {exc.filename}")
    except (PermissionError, OSError) as exc:
        parser.error(f"could not read an input file or write the dashboard: {exc}")
    except (UnicodeError, csv.Error, DashboardInputError) as exc:
        parser.error(str(exc))

    print("Clinical Research Study Dashboard - educational simulation")
    print(f"Participants: {summary['participant_count']}")
    print(f"Visit records: {summary['visit_count']}")
    print(f"Completed visits: {summary['completed_visits']}")
    print(f"Overdue scheduled visits: {len(summary['overdue_visits'])}")
    print(f"Data-quality warnings: {len(summary['warnings'])}")
    print(f"Dashboard written to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
