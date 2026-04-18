# Full Legacy-to-V2 Parity Matrix

## Status Legend
- `implemented`: clear v2 replacement exists
- `partial`: some behavior exists, but legacy behavior is reduced or incomplete
- `missing`: no meaningful v2 replacement yet
- `intentional divergence`: legacy behavior removed by architecture change

## App Shell And Access
| Legacy module | Purpose | V2 replacement | Status | Notes |
| --- | --- | --- | --- | --- |
| `app.py` | top-level app shell, major switch, nav, period gate, Drive autoload | `v2/frontend/src/App.tsx`, role layouts, admin/adviser routing | partial | Role-based shell exists, but the old period gate and startup orchestration are not fully mirrored. |
| `auth.py` | legacy per-major password gate | `v2/backend/app/api/routes/auth.py`, `v2/backend/app/services/auth_service.py` | intentional divergence | Replaced with real user auth. Legacy major-password behavior is not preserved. |
| `visual_theme.py` | Streamlit theme helpers | `v2/frontend/src/styles.css` | intentional divergence | Replaced by frontend CSS system, not feature parity. |
| `notification_system.py` | Streamlit notifications and feedback widgets | native frontend alerts in multiple pages | partial | Basic alerts exist, but legacy helper variants are not fully rebuilt. |

## Periods And Setup
| Legacy module | Purpose | V2 replacement | Status | Notes |
| --- | --- | --- | --- | --- |
| `advising_period.py` | current period, history, archive, Drive persistence | `v2/backend/app/services/period_service.py`, `v2/backend/app/api/routes/periods.py`, `v2/frontend/src/pages/admin/PeriodsPage.tsx` | partial | Create/list/activate exist. History reconstruction, Drive persistence, and some archive semantics do not. |
| `pages/setup.py` | file uploads, Drive sync, period management | `v2/frontend/src/pages/admin/DatasetsPage.tsx`, `v2/frontend/src/pages/admin/PeriodsPage.tsx`, `v2/frontend/src/pages/admin/ImportsPage.tsx` | partial | Uploads and periods exist. Runtime Drive sync is intentionally removed. |
| `data_upload.py` | legacy upload and Drive sync helper | `v2/backend/app/services/dataset_service.py` | partial | Dataset parsing exists. Legacy Drive-sync semantics do not. |
| `google_drive.py` | live Google Drive runtime storage layer | `v2/backend/app/services/drive_import_service.py`, `v2/backend/app/services/snapshot_export_service.py` | intentional divergence | Used only for migration/import/export paths, not runtime data storage. |

## Dashboard And Home
| Legacy module | Purpose | V2 replacement | Status | Notes |
| --- | --- | --- | --- | --- |
| `pages/home.py` | KPIs, quick actions, graduating soon, recent activity | `v2/frontend/src/pages/adviser/DashboardPage.tsx`, `v2/backend/app/services/insights_service.py` | partial | Metrics exist. Legacy quick-action behavior and some dashboard richness still need checking/porting. |

## Adviser Workspace
| Legacy module | Purpose | V2 replacement | Status | Notes |
| --- | --- | --- | --- | --- |
| `eligibility_utils.py` | core eligibility/requisite logic | reused from legacy inside `v2/backend/app/services/student_service.py` and `v2/backend/app/services/insights_service.py` | implemented | This is one of the stronger parity areas because the logic is reused. |
| `student_search.py` | student picker/search state | `v2/backend/app/api/routes/students.py`, `v2/frontend/src/pages/adviser/WorkspacePage.tsx` | partial | Search exists, but UI behavior is not identical to Streamlit search/select flow. |
| `eligibility_view.py` | full advising workspace | `v2/frontend/src/pages/adviser/WorkspacePage.tsx`, `v2/backend/app/services/student_service.py`, `v2/backend/app/api/routes/advising.py` | partial | Save, restore latest, recommend, email, bypass, hidden courses, selections, and split tables now exist. Legacy show-all pagination and some exact session/autoload behavior still differ. |
| `email_manager.py` | roster loading and email send | `v2/backend/app/services/dataset_service.py`, `v2/backend/app/services/email_service.py` | partial | Email roster and send exist. Legacy output formatting and some roster-management details still differ. |
| `email_templates.py` | template list/descriptions/UI | `v2/backend/app/services/template_service.py`, `v2/frontend/src/pages/admin/TemplatesPage.tsx`, `v2/frontend/src/pages/adviser/AdviserSettingsPage.tsx` | partial | Template save and preview exist. Legacy template metadata/UI richness is reduced. |

## Sessions And History
| Legacy module | Purpose | V2 replacement | Status | Notes |
| --- | --- | --- | --- | --- |
| `advising_history.py` | save payloads, autosave, restore, bulk restore, local cache, index, panels | `v2/backend/app/services/student_service.py`, `v2/backend/app/api/routes/advising.py`, `v2/frontend/src/pages/adviser/AdviserSettingsPage.tsx` | partial | Restore latest, restore all, bulk restore, session listing, and snapshot save exist. Full payload fidelity, autosave/local cache behavior, and history panel parity are still incomplete. |
| `course_exclusions.py` | per-student exclusion persistence | `v2/backend/app/services/student_service.py`, `v2/frontend/src/pages/adviser/AdviserSettingsPage.tsx` | partial | Exclusions exist. Legacy Drive/local bucket sync does not. |

## Insights, Reporting, Planner, Degree Plan
| Legacy module | Purpose | V2 replacement | Status | Notes |
| --- | --- | --- | --- | --- |
| `pages/insights.py` | insights shell | `v2/frontend/src/pages/adviser/InsightsPage.tsx` | partial | Shell exists, but only a reduced subset is exposed. |
| `full_student_view.py` | all students, individual student, QAA, schedule conflict | `v2/frontend/src/pages/adviser/InsightsPage.tsx`, `v2/backend/app/services/insights_service.py` | missing | This is the largest remaining parity hole. |
| `course_offering_planner.py` | planner UI, thresholds, save offerings | `v2/backend/app/services/insights_service.py` | partial | Planner scoring exists. Planner UI controls and saved-state workflow do not. |
| `degree_plan_view.py` | degree-plan visualization | none | missing | No real v2 degree-plan view yet. |
| `graduation_projection.py` | projected graduation helper | none | missing | No direct v2 equivalent is wired into UI or API. |
| `reporting.py` | workbook formatting, summary sheets, compact/full formats | `v2/backend/app/services/student_service.py` with `apply_excel_formatting` | partial | Basic per-student workbook formatting exists. Full report family parity is not there. |

## Settings And Admin Workflows
| Legacy module | Purpose | V2 replacement | Status | Notes |
| --- | --- | --- | --- | --- |
| `pages/settings.py` | sessions, exclusions, sync, email templates | `v2/frontend/src/pages/adviser/AdviserSettingsPage.tsx`, `v2/frontend/src/pages/admin/TemplatesPage.tsx` | partial | Sessions, exclusions, and template preview are now present. Sync/cache tab is intentionally removed because runtime Drive is gone. |
| `pages/workspace.py` | shell around eligibility view | `v2/frontend/src/pages/adviser/WorkspacePage.tsx` | implemented | Straight replacement. |
| `pages/home.py` | dashboard shell | `v2/frontend/src/pages/adviser/DashboardPage.tsx` | partial | See dashboard notes above. |
| `pages/setup.py` | setup shell | admin dataset/period/import pages | partial | Split across multiple admin pages. |

## Legacy-Only Utility Or Test Files
| Legacy module | Purpose | V2 replacement | Status | Notes |
| --- | --- | --- | --- | --- |
| `get_refresh_token.py` | manual Google token helper | none | intentional divergence | Migration/runtime model changed. |
| `tests/test_advising_period.py` | legacy test file | `v2/backend/tests/*` | partial | v2 has tests, but parity-coverage is still far smaller than needed. |

## Highest-Risk Missing Features
1. `full_student_view.py` parity.
2. `degree_plan_view.py` parity.
3. `graduation_projection.py` parity.
4. Full `advising_history.py` snapshot fidelity and autosave/cache semantics.
5. Full export family parity from `reporting.py` and `full_student_view.py`.

## Current Best Reference Files
- Legacy workspace: `eligibility_view.py`
- Legacy insights: `full_student_view.py`
- Legacy history: `advising_history.py`
- V2 workspace: `v2/frontend/src/pages/adviser/WorkspacePage.tsx`
- V2 settings: `v2/frontend/src/pages/adviser/AdviserSettingsPage.tsx`
- V2 student/session backend: `v2/backend/app/services/student_service.py`
- V2 insights backend: `v2/backend/app/services/insights_service.py`
