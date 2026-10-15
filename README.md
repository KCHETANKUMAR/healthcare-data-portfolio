# Pharmaceutical & Clinical Research Mini-Projects

A portfolio of six independent educational projects exploring pharmacovigilance, clinical research, clinical data management, medical terminology, and descriptive safety analytics. Each project has its own source, sample data, tests, and setup instructions.

> **Educational use only.** These projects are learning exercises that use fictional data. They are not validated medical, clinical, safety-report processing, or regulatory systems. Never enter real patient information or use these projects for clinical care, operational decisions, or regulatory submissions.

## Project index

| Project | Topic | Technologies | Screenshot |
|---|---|---|---|
| [Project 01: PV ICSR Case Processing Simulator](01-pv-icsr-simulator/) | Pharmacovigilance, case intake, follow-up, and QC workflow | Python, Streamlit, Pandas, SQLite | — |
| [Project 02: Clinical Trial Data Quality Checker](02-clinical-data-quality-checker/) | Clinical research CSV validation and issue reporting | Python standard library, CSV, unittest | — |
| [Project 03: Clinical Research Study Dashboard](03-clinical-research-study-dashboard/) | Offline summaries of fictional participant and visit data | Python standard library, CSV, HTML/CSS | [Dashboard](03-clinical-research-study-dashboard/screenshots/dashboard.png) |
| [Project 04: Medical Terminology & Coding Practice Tool](04-medical-coding-practice-tool/) | Terminology search, flashcards, quizzes, and reference CSV practice | Python standard library, HTTP, CSV, HTML/CSS | [Live demo](https://medical-terminology-practice-tool.onrender.com) · [Screenshot](04-medical-coding-practice-tool/screenshots/practice-tool.png) |
| [Project 05: Clinical Trial Eligibility Screener](05-clinical-trial-eligibility-screener/) | Educational screening against configurable fictional study criteria | Python standard library, HTTP, JSON, CSV | [Screening report](05-clinical-trial-eligibility-screener/screenshots/screening-report.png) |
| [Project 06: Clinical Safety & Adverse Event Analytics Dashboard](06-clinical-safety-analytics-dashboard/) | Descriptive analysis and quality checks for synthetic safety report rows | Python standard library, HTTP, CSV, HTML/CSS | [Dashboard](06-clinical-safety-analytics-dashboard/screenshots/dashboard.png) |


## Getting started

Projects are independent; use Python 3.9+ or 3.10+ as stated in each project README. Project 01 needs the dependencies in its `requirements.txt`; Projects 02–06 use the Python standard library. From the master folder, launch an individual project with:

```powershell
cd 01-pv-icsr-simulator; python -m pip install -r requirements.txt; streamlit run app.py
```

For Projects 02–06, change into that project's folder and follow its README. The usual entry points are `python main.py` for Projects 02 and 03, and `python app.py` for Projects 04–06. Project-specific options and test commands are documented in each [project README](01-pv-icsr-simulator/README.md), [Project 02](02-clinical-data-quality-checker/README.md), [Project 03](03-clinical-research-study-dashboard/README.md), [Project 04](04-medical-coding-practice-tool/README.md), [Project 05](05-clinical-trial-eligibility-screener/README.md), and [Project 06](06-clinical-safety-analytics-dashboard/README.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the folder structure and documentation expectations for future projects.

## License

This portfolio is distributed under the MIT License; see [LICENSE](LICENSE). Individual projects may include their own license files. Project 01 also includes an MIT License.
