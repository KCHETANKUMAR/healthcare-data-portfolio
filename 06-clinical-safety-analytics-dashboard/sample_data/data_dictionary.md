# Synthetic adverse-event report data dictionary

The CSV contains 50 fabricated report rows. No row represents a real person, product, or event report. Counts describe rows in this dataset; they are not incidence rates and do not establish causality or product risk.

| Field | Meaning | Allowed/example values |
|---|---|---|
| `report_id` | Synthetic record identifier; duplicate and blank examples are intentional. | `SYN-001` style text |
| `report_date` | Date associated with the synthetic report row. | ISO date `YYYY-MM-DD` |
| `event_term` | Fictional report's event label. | Short text; sample labels include headache and nausea |
| `seriousness` | Declared row classification; no inference from event text. | `Serious`, `Non-serious` |
| `outcome` | Row's example outcome category. | `Recovered`, `Recovering`, `Not recovered`, `Fatal`, `Unknown` |
| `suspect_product` | Synthetic product label associated with the row; association is not causation. | `DemoCompound-A`, `DemoCompound-B`, `DemoVaccine-C`, `Placebo-Z` |
| `age_group` | Broad fabricated age band, not an exact age. | `18-29`, `30-44`, `45-59`, `60+` |
| `country` | Fictional location label. | `Exampleland`, `Sample Republic`, `Fiction Isles`, `Demo Territory` |
| `report_source` | Fictional reporting source category. | `Fictional participant`, `Fictional clinician`, `Fictional caregiver` |
| `follow_up_received` | Example flag for a follow-up record. | `Yes`, `No` |

## Intentional data-quality examples

The following source data rows (header excluded) intentionally include issues. The dashboard retains these rows and their source values. One row may have more than one issue.

- Row 9 duplicates `SYN-004` from row 4.
- Row 15 has a blank `event_term`.
- Row 18 has a blank `outcome`.
- Row 23 has impossible date `2025-02-30`.
- Row 27 uses unrecognized seriousness value `serious` (lowercase).
- Row 32 uses invalid follow-up flag `Maybe`.
- Row 36 has a blank report ID.
- Row 41 uses unrecognized outcome `Resolved`.
- Row 45 has a blank date.

All remaining data is synthetic and generated solely for interface and test demonstrations.
