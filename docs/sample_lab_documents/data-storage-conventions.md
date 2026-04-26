# Data Storage and Naming Conventions

This is the canonical guide for where data lives in our lab and how to name
files, samples, and experiment records. Following these conventions makes
your work reproducible and rescuable when someone else needs to pick it up.
Owner: Hannah Liu (liu@example.lab).

## Where things go

| What | Where | Notes |
|------|-------|-------|
| Raw instrument data | `/lab-storage/raw/<instrument>/<YYYY>/<YYYY-MM-DD>/` | Read-only after upload. Auto-mirrored nightly to cold storage. |
| Processed data | `/lab-storage/processed/<project>/<your-initials>/` | You own it. Keep your scratch work here. |
| Analysis notebooks | GitHub repo `lab-org/analyses`, one branch per project | PR into `main` when results are presentation-ready. |
| Lab notebook entries | Benchling, project-scoped | Mirror to PDF for any entry that's referenced in a paper. |
| Manuscripts and figures | Google Drive shared folder "Lab — Manuscripts" | Lock to read-only once submitted. |

Personal laptops are not a valid storage location for any data that's part
of a project. If it's not in `/lab-storage` or in the right Google Drive
folder, it does not exist as far as the lab is concerned.

## File naming convention

`<YYYY-MM-DD>_<initials>_<short-description>_<rep>.<ext>`

Examples:
- `2026-04-25_pm_microscope-calibration_run1.tif`
- `2026-04-25_pm_microscope-calibration_run2.tif`
- `2026-04-26_hl_western-blot_anti-actin.png`

Use lowercase, hyphens between words, underscores between fields. No spaces.
No special characters. The date format is ISO-8601 (year first) so files
sort chronologically.

## Sample naming convention

`<project>-<construct>-<replicate>-<date>`

Example: `cellpaint-egfp-r3-20260425`. Sample IDs flow into Benchling, the
plate maps, and the analysis notebooks — pick one and stick with it for the
whole experiment.

## Retention expectations

- Raw data: kept indefinitely. Auto-tiered to cold storage after 12 months.
- Processed data: kept for 5 years past project close-out, then reviewed.
- Notebook entries: kept indefinitely. Required for any data cited in a
  paper.
- Personal scratch: cleaned up annually. If you're leaving, archive your
  active work into the project's processed folder.

## What to do if you broke a convention

Tell Hannah Liu in the `#lab-data` Slack channel, then fix it. We do not
audit retroactively — the goal is consistency going forward, not blame for
old files. If you inherited a project that doesn't follow these
conventions, you are not responsible for re-naming the historical work,
but new files you produce should follow the rules.
