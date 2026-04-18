# V2 Parity Audit

## Status

Legacy-to-v2 parity is partial. The current v2 covers authentication, basic dataset uploads/imports, periods, user management, dashboard metrics, and a reduced advising workspace. It does not yet reach full legacy parity.

## Completed or Improved In This Pass

- Added adviser-side `Settings` screen with session actions, bulk restore, exclusions, and template preview.
- Added workspace actions for restore latest, recommend, report download, email send, hidden courses, and bypass management.
- Added period activation to the admin UI.
- Fixed workspace state reset so saved selections load back into the form.
- Added backend routes for course catalog, recommendations, clear selections, restore all, bulk restore, exclusions listing, and template preview.
- Separated hidden courses from exclusions in the student payload.
- Stopped restore from generating a new snapshot on every restore.
- Rebuilt the adviser `Insights` page into multi-tab workflows for `All Students`, `Individual Student`, `QAA Sheet`, `Schedule Conflict`, and `Degree Plan`.
- Added backend all-students matrix payloads with semester filtering, co-requisite/concurrent simulation, required/intensive course splits, legend metadata, and course requisites.
- Added adviser-side course offering planner save/restore state using the existing audit log, plus saved impact summary.
- Added individual-student insight email action and richer course metadata display inside `Insights`.

## Critical Gaps Still Remaining

### Missing parity in Insights
- Legacy includes richer `All Students`, `Individual Student`, `QAA Sheet`, and `Schedule Conflict` tools than v2.
- V2 now covers the main tab structure, semester filtering, dynamic course matrix, simulation controls, planner save state, QAA export, conflict export, and degree-plan view.
- Remaining gaps are narrower: the all-students workbook is still not the legacy full-report format, simulation-specific export parity is not done, and some legacy confirmation/workbook details are still simplified.

### Snapshot/session payload parity is still incomplete
- V2 now stores more metadata, but it still does not mirror the full legacy snapshot structure used by `advising_history.py`.
- This is a risk for exact historical replay and export parity.

### Export parity is still incomplete
- V2 now includes QAA workbook export, schedule-conflict CSV export, individual compact report export, and the legacy student workbook route.
- Remaining export gaps are the legacy-style full all-students advising workbook formatting/selection behavior and some sheet-level formatting differences.

### Email parity is still incomplete
- V2 now supports preview and uses active period values, but the output is still simpler than the legacy formatted preview/body behavior.

### Insights planner/degree-plan parity is still incomplete
- Planner save state now exists and persists by major/period.
- Degree-plan data and year/semester grouping now exist in v2.
- Remaining gaps are mostly layout fidelity and some planner-specific downstream summary behavior.

## Reference Mapping

### Legacy Workspace
- `eligibility_view.py:198`
- `eligibility_view.py:430`
- `eligibility_view.py:740`
- `eligibility_view.py:813`

### Legacy Insights
- `full_student_view.py:258`
- `full_student_view.py:327`
- `full_student_view.py:919`
- `full_student_view.py:1216`
- `full_student_view.py:1393`

### Legacy Settings and History
- `pages/settings.py:29`
- `pages/settings.py:104`
- `pages/settings.py:204`
- `pages/settings.py:329`
- `advising_history.py:510`
- `advising_history.py:643`
- `advising_history.py:793`
- `advising_history.py:985`
- `advising_history.py:1111`

### V2 Updated In This Pass
- `v2/frontend/src/pages/adviser/WorkspacePage.tsx`
- `v2/frontend/src/pages/adviser/AdviserSettingsPage.tsx`
- `v2/frontend/src/pages/adviser/InsightsPage.tsx`
- `v2/frontend/src/pages/admin/PeriodsPage.tsx`
- `v2/frontend/src/styles.css`
- `v2/backend/app/api/routes/insights.py`
- `v2/backend/app/services/student_service.py`
- `v2/backend/app/services/insights_service.py`
- `v2/backend/app/api/routes/advising.py`
- `v2/backend/app/api/routes/students.py`
- `v2/backend/app/api/routes/templates.py`
- `v2/backend/app/services/email_service.py`
