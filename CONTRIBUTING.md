# Adding a future project

Keep each mini-project small, self-contained, and clearly labeled as an educational exercise.

## Folder and files

Create the next numbered folder at the repository root, for example `02-short-project-name/`. Include only files needed to understand and run that project. A typical structure is:

```text
02-short-project-name/
├── README.md
├── requirements.txt       # when the project uses Python packages
├── src/                   # optional source folder
└── tests/                 # when automated checks are useful
```

Follow the existing Project 01 layout when a flat structure is simpler. Keep project dependencies and setup instructions local to the project so projects remain independent.

## README checklist

Explain the purpose, learning objectives, features, tools, folder structure, setup, run and test commands, and known limitations. State what has and has not been implemented. Label planned work as planned. Do not claim deployment, validation, or capabilities that have not been verified.

## Data and safety

- Use fictional or synthetic data only. Never add patient records, confidential materials, credentials, tokens, or personal secrets.
- Make it clear that projects are not validated medical, clinical, pharmacovigilance, or regulatory systems.
- Do not imply real case-processing experience or suitability for clinical or regulatory use.
- Exclude virtual environments, databases, caches, generated files, and local secrets from commits.

## Before adding a project

Run the checks documented by that project, review its `.gitignore`, inspect the files intended for commit, and update the root project index. Do not add generated databases, `.venv`, caches, or build outputs.
