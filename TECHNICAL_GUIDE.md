# Advising V2 — Technical Reference
### Complete engineering documentation for replication, extension, and production deployment

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Repository Layout](#2-repository-layout)
3. [Technology Stack](#3-technology-stack)
4. [Backend Architecture](#4-backend-architecture)
   - 4.1 [Entry Point & Middleware](#41-entry-point--middleware)
   - 4.2 [Configuration & Environment](#42-configuration--environment)
   - 4.3 [Database Layer](#43-database-layer)
   - 4.4 [ORM Models](#44-orm-models)
   - 4.5 [Authentication & Authorization](#45-authentication--authorization)
   - 4.6 [API Router & Routes](#46-api-router--routes)
   - 4.7 [Service Layer](#47-service-layer)
   - 4.8 [Shared Legacy Modules](#48-shared-legacy-modules)
   - 4.9 [Storage Abstraction](#49-storage-abstraction)
5. [Frontend Architecture](#5-frontend-architecture)
   - 5.1 [App Shell & Routing](#51-app-shell--routing)
   - 5.2 [State Management](#52-state-management)
   - 5.3 [API Client & Hooks](#53-api-client--hooks)
   - 5.4 [Admin Pages](#54-admin-pages)
   - 5.5 [Adviser Pages](#55-adviser-pages)
   - 5.6 [Workspace Components](#56-workspace-components)
6. [Data Models & Schema](#6-data-models--schema)
7. [Core Business Logic](#7-core-business-logic)
   - 7.1 [Eligibility Engine](#71-eligibility-engine)
   - 7.2 [Dataset Ingestion](#72-dataset-ingestion)
   - 7.3 [Insights & Analytics](#73-insights--analytics)
   - 7.4 [Email System](#74-email-system)
   - 7.5 [Backup & Import](#75-backup--import)
8. [API Endpoint Reference](#8-api-endpoint-reference)
9. [Environment Variables](#9-environment-variables)
10. [Local Development Setup](#10-local-development-setup)
11. [Production Deployment Notes](#11-production-deployment-notes)
12. [Parity Status & Known Gaps](#12-parity-status--known-gaps)

---

## 1. System Overview

Advising V2 is a full-stack, role-gated academic advising dashboard. It replaces a legacy Streamlit monolith with a decoupled REST API backend (FastAPI) and a React SPA frontend.

**Key concerns:**
- Per-major dataset management (Excel upload → parse → store)
- Real-time prerequisite eligibility computation per student
- Advising session recording (advised / optional / repeat course selections)
- Analytical insights across cohorts
- Excel report generation
- SMTP email delivery with template rendering
- Legacy data migration

The eligibility engine and Excel reporting logic (`eligibility_utils.py`, `reporting.py`) are **shared with the legacy app** — they live in the workspace root and are imported by `sys.path` manipulation inside the backend services.

---

## 2. Repository Layout

```
v2/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app factory
│   │   ├── db.py                 # SQLAlchemy engine + session factory
│   │   ├── api/
│   │   │   ├── deps.py           # FastAPI dependency injectors (auth, DB, access)
│   │   │   ├── router.py         # Root APIRouter — mounts all route modules
│   │   │   └── routes/           # One file per domain
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── majors.py
│   │   │       ├── datasets.py
│   │   │       ├── periods.py
│   │   │       ├── students.py
│   │   │       ├── advising.py
│   │   │       ├── insights.py
│   │   │       ├── reports.py
│   │   │       ├── emails.py
│   │   │       ├── templates.py
│   │   │       ├── backups.py
│   │   │       ├── imports.py
│   │   │       ├── audit_events.py
│   │   │       └── health.py
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic Settings from .env
│   │   │   ├── roles.py          # ADMIN / ADVISER constants
│   │   │   └── security.py       # JWT encode/decode, password hashing
│   │   ├── models/
│   │   │   ├── __init__.py       # Re-exports all ORM classes
│   │   │   └── entities.py       # All SQLAlchemy mapped classes
│   │   ├── schemas/              # Pydantic request/response models
│   │   │   ├── advising.py
│   │   │   ├── admin.py
│   │   │   ├── auth.py
│   │   │   ├── common.py
│   │   │   └── insights.py
│   │   └── services/             # Business logic (no HTTP concerns)
│   │       ├── auth_service.py
│   │       ├── audit.py
│   │       ├── backup_job.py
│   │       ├── bootstrap.py
│   │       ├── dataset_service.py
│   │       ├── drive_import_service.py
│   │       ├── email_service.py
│   │       ├── import_service.py
│   │       ├── insights_service.py
│   │       ├── period_service.py
│   │       ├── snapshot_export_service.py
│   │       ├── storage.py
│   │       ├── student_service.py
│   │       └── template_service.py
│   ├── requirements.txt
│   ├── .python-version           # Python 3.12
│   └── advising_v2.db            # SQLite dev database (gitignored in prod)
├── frontend/
│   ├── src/
│   │   ├── main.tsx              # React root mount
│   │   ├── App.tsx               # Routes + role guards
│   │   ├── styles.css            # Global CSS (design tokens + utility classes)
│   │   ├── lib/
│   │   │   ├── api.ts            # Type definitions + apiFetch utility
│   │   │   ├── hooks.ts          # React Query hooks
│   │   │   └── MajorContext.tsx  # React context for the active major
│   │   ├── components/
│   │   │   ├── AppFrame.tsx      # Shell layout (nav + outlet)
│   │   │   ├── StatCard.tsx      # Metric display card
│   │   │   ├── Tooltip.tsx       # Hover tooltip
│   │   │   └── workspace/
│   │   │       ├── CourseSelectionBuilder.tsx
│   │   │       ├── EligibilityTables.tsx
│   │   │       ├── ExceptionManagement.tsx
│   │   │       └── StudentProfileHeader.tsx
│   │   └── pages/
│   │       ├── LoginPage.tsx
│   │       ├── admin/
│   │       │   ├── AdminOverviewPage.tsx
│   │       │   ├── AuditLogPage.tsx
│   │       │   ├── BackupsPage.tsx
│   │       │   ├── DatasetsPage.tsx
│   │       │   ├── ImportsPage.tsx
│   │       │   ├── PeriodsPage.tsx
│   │       │   ├── TemplatesPage.tsx
│   │       │   └── UsersPage.tsx
│   │       └── adviser/
│   │           ├── DashboardPage.tsx
│   │           ├── WorkspacePage.tsx
│   │           ├── InsightsPage.tsx
│   │           └── AdviserSettingsPage.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── PARITY_AUDIT.md
├── FULL_PARITY_MATRIX.md
├── LAY_TERMS_GUIDE.md            # (this repo's plain-language guide)
└── README.md
```

---

## 3. Technology Stack

### Backend
| Concern | Library / Version |
|---|---|
| Web framework | FastAPI 0.116 |
| ASGI server | uvicorn[standard] 0.35 |
| ORM | SQLAlchemy 2.0 (future=True) |
| DB drivers | psycopg3 (Postgres) + sqlite built-in |
| Settings | pydantic-settings 2.10 |
| Auth / JWT | python-jose[cryptography] 3.5 |
| Password hashing | passlib[bcrypt] (scheme: pbkdf2_sha256) |
| Data parsing | pandas 2.2, numpy 1.26, openpyxl 3.1 |
| Object storage | boto3 1.39 (S3-compatible Cloudflare R2) |
| HTTP client | httpx 0.28 |
| Google Drive | google-api-python-client 2.159, google-auth 2.38 |
| Testing | pytest 8.4 |

### Frontend
| Concern | Library / Version |
|---|---|
| Framework | React 19 |
| Language | TypeScript 5.8 |
| Build tool | Vite 7 |
| Routing | react-router-dom 7 |
| Data fetching | @tanstack/react-query 5 |

### Infrastructure (optional / production)
| Concern | Service |
|---|---|
| Database | Neon (serverless PostgreSQL) |
| File storage | Cloudflare R2 |
| Email | Microsoft Office 365 SMTP (`smtp.office365.com:587`) |
| Google Drive import | Google Drive API v3 |

---

## 4. Backend Architecture

### 4.1 Entry Point & Middleware

**`app/main.py`**

```python
app = FastAPI(title=settings.app_name)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, ...)
app.include_router(api_router, prefix='/api')

@app.on_event('startup')
def on_startup():
    Base.metadata.create_all(bind=engine)   # DDL auto-create
    seed_defaults(session)                   # Insert default majors/users/templates
```

All routes live under `/api`. CORS origins are configurable via `CORS_ORIGINS` env var (comma-separated).

The startup hook runs `CREATE TABLE IF NOT EXISTS` for all mapped tables and seeds default data (4 majors, 2 users, 2 email templates). This is idempotent — safe to re-run on every startup.

---

### 4.2 Configuration & Environment

**`app/core/config.py`** — `pydantic-settings` `BaseSettings` class, cached with `@lru_cache`.

All settings have defaults (database falls back to SQLite, JWT secret defaults to `'change-me'`).

| Env Var | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///./advising_v2.db` |
| `JWT_SECRET` | HMAC secret for JWT signing | `change-me` (must override) |
| `JWT_EXPIRY_MINUTES` | Token TTL | `480` (8 hours) |
| `CORS_ORIGINS` | Allowed frontend origins | localhost:5173 + 5174 |
| `R2_ACCOUNT_ID` | Cloudflare account ID | None |
| `R2_ACCESS_KEY_ID` | R2 access key | None |
| `R2_SECRET_ACCESS_KEY` | R2 secret key | None |
| `R2_BUCKET` | R2 bucket name | None |
| `R2_PUBLIC_BASE_URL` | Public URL prefix for R2 assets | None |
| `LOCAL_STORAGE_PATH` | Local file storage root | `./local-storage` |
| `LEGACY_IMPORTS_PATH` | Path to legacy app root | `../../` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | None |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | None |
| `GOOGLE_REFRESH_TOKEN` | Google Drive refresh token | None |
| `GOOGLE_FOLDER_ID` | Google Drive folder to import from | None |

---

### 4.3 Database Layer

**`app/db.py`**

```python
engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True, ...)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
class Base(DeclarativeBase): pass
```

- SQLite: `check_same_thread=False` connect arg is added automatically.
- PostgreSQL (Neon): No extra connect args; `pool_pre_ping=True` handles connection recycling.
- Sessions are injected per-request via `get_db()` dependency (yielded, always closed in finally).

---

### 4.4 ORM Models

All models are defined in **`app/models/entities.py`** and re-exported from `app/models/__init__.py`.

All tables inherit `TimestampMixin` (auto `created_at`, `updated_at` via `func.now()`).

| Table | Purpose |
|---|---|
| `users` | Staff accounts (admin or adviser). `password_hash` uses pbkdf2_sha256. |
| `majors` | Academic programs (PBHL, SPTH-New, etc.). Stores per-major SMTP credentials (`smtp_email`, `smtp_password`). |
| `user_major_access` | M2M join table — which advisers can access which majors |
| `upload_batches` | Audit record of every file upload |
| `dataset_versions` | Parsed dataset payloads stored as JSON in `parsed_payload` column. One active version per `(major_id, dataset_type)` at a time. |
| `advising_periods` | Semester + year + advisor scoped to a major. Only one `is_active=True` per major. Snapshots three dataset version FKs: `progress_version_id` (progress_report), `progress_dataset_version_id` (progress), `config_version_id` (course_config). |
| `student_selections` | Current advised/optional/repeat course lists per `(major, period, student)`. Unique per that triple. |
| `session_snapshots` | Immutable point-in-time snapshots of selections, created on every save. |
| `course_exclusions` | Courses excluded from a specific student's view (multi-student bulk operation). |
| `hidden_courses` | Courses hidden for a single student (per-student hide). |
| `bypasses` | Prerequisite override grants per `(major, student, course)`. |
| `email_roster_entries` | Student ID → email mapping, populated when an email roster file is uploaded. |
| `email_templates` | Configurable subject/body templates with Jinja-style format variables. |
| `export_artifacts` | Metadata about generated exports (storage key + filename). |
| `backup_runs` | History of backup jobs. |
| `audit_events` | Append-only log: `actor_user_id`, `event_type`, `entity_type`, `entity_id`, `payload` JSON. |
| `equivalent_courses` | Course alias mappings for Academic Progress — unique on `(major_id, alias_code)`. |
| `assignment_types` | Named assignment labels per major (e.g., "Internship") — unique on `(major_id, label)`. |
| `progress_assignments` | Per-student assignment records linking a student to a course via an assignment type — unique on `(major_id, student_id, assignment_type)`. |

Progress ORM models are defined in **`app/models/progress_models.py`**.

**Dataset version lifecycle**: on every upload, all previous versions for that `(major_id, dataset_type)` are marked `is_active=False`, and the new version is inserted with `is_active=True`. Only the active version is used for queries.

---

### 4.5 Authentication & Authorization

**JWT flow** (`app/core/security.py`):
- Passwords hashed with `passlib` using `pbkdf2_sha256`.
- JWT signed with HS256 using `JWT_SECRET`. Payload: `{ sub: user_id, role: role, iat, exp }`.
- Tokens stored in `localStorage` on the frontend (`advising_v2_token`).
- Token TTL defaults to 480 minutes (8 hours).

**Dependency injection** (`app/api/deps.py`):
- `get_db()` — yields a `SessionLocal` session.
- `get_current_user()` — extracts Bearer token, decodes JWT, loads `User` from DB.
- `require_staff()` — asserts role is `admin` or `adviser`.
- `require_admin()` — asserts role is `admin` only.
- `ensure_major_access(major_code, db, user)` — if role is `admin`, always passes. If `adviser`, checks `user_major_access` table.

---

### 4.6 API Router & Routes

**`app/api/router.py`** — mounts all sub-routers under `/api`.

| Route Module | Prefix | Auth |
|---|---|---|
| `health` | `/health` | None |
| `auth` | `/auth` | None (login) / Bearer (me) |
| `users` | `/users` | Admin |
| `majors` | `/majors` | Staff |
| `datasets` | `/datasets` | Staff / Admin |
| `periods` | `/periods` | Staff |
| `students` | `/students` | Staff |
| `advising` | `/advising` | Staff |
| `insights` | `/insights` | Staff |
| `reports` | `/reports` | Staff |
| `emails` | `/emails` | Staff |
| `templates` | `/templates` | Staff |
| `backups` | `/backups` | Admin |
| `imports` | `/imports` | Admin |
| `audit_events` | `/audit-events` | Admin |
| `progress` | `/progress` | Staff / Admin |

---

### 4.7 Service Layer

Services contain all business logic. Route handlers call services and do nothing else (no direct DB queries in routes). Key services:

#### `dataset_service.py`
- `upload_dataset(session, *, major_code, dataset_type, filename, content, user_id)` — parses file (Excel/CSV), checksums content, stores in StorageService, deactivates old versions, inserts new `DatasetVersion`. Supported types: `courses`, `progress`, `advising_selections`, `email_roster`, `progress_report`, `course_config`.
- `load_progress_excel(content)` — specialized parser that merges "Required Courses" and "Intensive Courses" sheets from the progress Excel into one DataFrame, aligning numeric columns.
- `dataset_dataframe(session, major_code, dataset_type)` — retrieves the active dataset and deserializes `parsed_payload.records` back to a DataFrame.
- `get_active_dataset(session, major_code, dataset_type)` — returns the active `DatasetVersion` row.

#### `student_service.py`
- `search_students(session, major_code, query)` — filters progress DataFrame by name/ID, computes standings.
- `student_eligibility(session, major_code, student_id)` — main eligibility computation. Loads courses + progress DFs, calls into `eligibility_utils` for each course, assembles `StudentEligibilityResponse`. Each `EligibilityCourse` includes `credits` (float) and `suggested_semester` (string) sourced from the courses dataset. Loads selection, bypasses, hidden courses, excluded courses from DB.
- `save_selection(session, *, major_code, period_code, student_id, student_name, payload, user_id, create_snapshot=True)` — upserts `StudentSelection`, optionally creates `SessionSnapshot`.
- `recommended_courses(session, major_code, student_id)` — returns eligible, non-completed, offered courses sorted by suggested semester.
- `export_student_report(session, major_code, student_id)` — generates an Excel workbook (calls `apply_excel_formatting` from legacy `reporting.py`).
- `set_bypass / remove_bypass` — CRUD on `Bypass` table.
- `replace_hidden_courses / replace_exclusions` — replaces hidden/excluded course lists atomically.

#### `period_service.py`
- `create_period(session, *, major_code, semester, year, advisor_name)` — deactivates all other periods for the major, creates a new active one. Captures the currently active `progress_report`, `progress`, and `course_config` dataset version IDs so they can be restored later.
- `activate_period(session, period_code)` — restores all three snapshotted datasets (`progress_report`, `progress`, `course_config`) to the versions that were active when the period was created. This ensures switching back to an older period loads the correct historical student data and course configuration.
- `archive_period / delete_period` — lifecycle management.
- `current_period(session, major_code)` — returns the active `AdvisingPeriod` or None.
- Period code format: `{major}-{semester}-{year}-{advisor-slug}` (e.g., `pbhl-spring-2026-dr-smith`).

#### `insights_service.py`
- `dashboard_metrics(session, major_code)` — counts total students in progress DF, counts `StudentSelection` records with non-empty `advised` lists, computes progress %, finds graduating-soon unadvised students. Now also computes `credit_distribution`: a 4-bucket histogram `[≤18, 19–36, 37–72, 73+]` of remaining credits per unique student ID, returned as `list[{label, count}]` in `DashboardMetrics`.
- `all_students_view(session, major_code, simulated_courses, semester_filter)` — for every student in the progress DF, runs eligibility for every course. Returns a matrix structure.
- `course_offering_recommendations(session, major_code, graduation_threshold, min_eligible_students)` — scores each course by: eligible student count, graduating student count (remaining ≤ threshold), cascading eligibility (students who would become eligible for other courses if this one is offered), and bottleneck score.
- `qaa_sheet(session, major_code, graduating_threshold)` — filters students near graduation, returns per-student course status breakdowns.
- `schedule_conflicts(session, major_code, ...)` — clusters students by shared eligible courses to find scheduling conflict risks.
- `degree_plan_view(session, major_code, student_id)` — groups courses by suggested semester for a single student.
- Excel export functions: `build_all_advised_report`, `build_individual_report`, `build_qaa_report`, `build_schedule_conflicts_report`.

#### `email_service.py`
- `build_student_email(session, *, major_code, student_id, template_key)` — fetches student's selection and eligibility, renders template variables, returns preview dict.
- `send_student_email(session, *, major_code, student_id, template_key, adviser_email)` — loads SMTP credentials from the Major record, calls `build_student_email`, adds CC header for the adviser, sends via Office 365.

#### `auth_service.py`
- `authenticate_user(session, email, password)` — looks up active user by email, calls `verify_password`.

#### `import_service.py`
- `import_legacy_snapshot(session, *, major_code, import_root, user_id)` — reads legacy folder structure, calls `upload_dataset` for courses/progress/email_roster, calls `_upsert_periods` and `_apply_session_records` from `drive_import_service.py` to migrate historical data.

#### `progress_processing.py`
Pure-Python port of the legacy `archive/course_mapping/` processing engine. No Streamlit imports. Key functions:
- `read_progress_report(content, filename)` → DataFrame with columns `[ID, NAME, Course, Grade, Year, Semester]`.
- `read_course_config(content, filename)` → structured dict with `target_courses`, `intensive_courses`, `target_rules`, `intensive_rules`. Validates no overlapping date ranges and no course appearing in both required and intensive.
- `process_progress_report(df, target_courses, intensive_courses, ...)` → `(req_df, int_df, extra_df, extra_list)` — pivots long-format rows into per-student pivot tables.
- `calculate_credits(row, courses_dict)` → `{completed, registered, remaining, total}`.
- `calculate_gpa_for_rows(df, courses_dict)` → `{student_id: gpa}`.
- `cell_color(value)`, `extract_primary_grade(value)`, `semester_to_ordinal()`, `determine_course_value()` — helpers for display and GPA calculation.

#### `progress_service.py`
Orchestration layer for the Academic Progress feature:
- `upload_progress_report(session, *, major_code, filename, content, user_id)` → delegates to `upload_dataset` with type `progress_report`.
- `preview_progress_upload(session, major_code, content)` → parses incoming bytes with `read_progress_report` (no DB write), loads the current active dataset, and returns `{new_students, removed_students, grade_changes, total_students}` diff summary.
- `upload_course_config(session, *, major_code, filename, content, user_id)` → delegates to `upload_dataset` with type `course_config`.
- `get_data_status(session, major_code)` → `DataStatus` — reports whether both files are uploaded and their metadata.
- `generate_report(session, major_code, show_all_grades, page, page_size, search)` → `ReportResponse` — loads both datasets, applies aliases from `equivalent_courses`, runs `process_progress_report`, paginates, applies per-student assignments.
- `push_progress_to_advising(session, major_code, user_id)` → generates collapsed c/cr/nc Excel, stores it as `progress` dataset, and links the new version to the currently active advising period's `progress_dataset_version_id`.
- `export_report_excel(session, major_code, show_all_grades)` → `bytes` — two-sheet XLSX (Required + Intensive) with color-coded cells using `openpyxl`.
- `list_equivalents / replace_equivalents` — bulk-replace `equivalent_courses` for a major.
- `list_assignment_types / create_assignment_type / delete_assignment_type` — CRUD on `assignment_types`.
- `list_assignments / upsert_assignment / delete_assignment / reset_all_assignments` — CRUD on `progress_assignments`.

#### `backup_job.py`
- `run_backup(triggered_by)` — calls `pg_dump` via subprocess, gzips output, writes to storage with key `backups/{timestamp}/database.sql.gz`, records `BackupRun`.

#### `bootstrap.py`
- `seed_defaults(session)` — idempotent seed of: 4 default majors, admin + adviser users, default email templates, major access grants for all users.

#### `storage.py` — `StorageService`
- **Two backends**: if R2 credentials are configured → lazy-imports boto3 and uses S3 client pointed at Cloudflare R2 endpoint (`https://{account_id}.r2.cloudflarestorage.com`). Otherwise → writes to `LOCAL_STORAGE_PATH` on disk. boto3 is only imported when R2 is configured, saving ~50 MB of RAM on deployments that use local storage only.
- Methods: `put_bytes(key, content)`, `get_bytes(key)`, `public_url(key)`.
- `get_bytes(key)` raises `FileNotFoundError` when the requested file does not exist (both R2 `NoSuchKey` and local missing-file cases). Callers must handle this — e.g. the dataset download route returns HTTP 404 with a re-upload prompt.
- Storage key conventions: `datasets/{major_code}/{type}/{checksum}-{filename}`, `backups/{timestamp}/database.sql.gz`, `legacy-imports/{major_code}/{filename}`.
- **Ephemeral storage warning**: on platforms with ephemeral filesystems (e.g. Render free tier), locally-stored files are lost on every deploy. The actual parsed data survives in the database (`DatasetVersion.parsed_payload`), but the raw uploaded files will not be downloadable after a restart unless R2 is configured.

---

### 4.8 Shared Legacy Modules

The backend imports two modules from the workspace root (the legacy Streamlit app):

**`eligibility_utils.py`** (root):  
Used in `student_service.py` and `insights_service.py`. Key functions:
- `check_eligibility(student_row, course_code, advised_list, courses_df, ...)` → `(status_str, justification_str)`
- `check_course_completed(student_row, course_code)` → `bool`
- `check_course_registered(student_row, course_code)` → `bool`
- `get_mutual_concurrent_pairs(courses_df)` → `dict[str, list[str]]`
- `get_student_standing(total_credits)` → `str` (Freshman/Sophomore/Junior/Senior)
- `build_requisites_str(row)` → human-readable prerequisites string
- `parse_requirements()`

**`reporting.py`** (root):  
Used in `insights_service.py` for Excel workbook generation:
- `apply_excel_formatting(wb)`
- `apply_full_report_formatting(wb)`
- `apply_individual_compact_formatting(wb)`
- `add_summary_sheet(wb, ...)`

These are injected via `sys.path.insert(0, ROOT_DIR)` inside each service file. `ROOT_DIR` resolves to 4 levels up from `app/services/`, i.e., the workspace root.

---

### 4.9 Storage Abstraction

`StorageService` is instantiated fresh per call (no singleton). It auto-detects R2 vs local mode at construction time based on whether all four R2 env vars are present. When R2 is not configured, boto3 is never imported.

In R2 mode, content-type is guessed from filename via `mimetypes.guess_type`. Public URL is `R2_PUBLIC_BASE_URL/{key}`.

In local mode, files are written under `LOCAL_STORAGE_PATH/{key}` with directories created on demand. Public URL returns the absolute local path.

#### Error Handling

The global exception handler (`main.py`) catches any unhandled exception and returns a JSON 500 response with explicit CORS headers, ensuring cross-origin clients always receive a usable error response even if middleware fails to add headers.

---

## 5. Frontend Architecture

### 5.1 App Shell & Routing

**`App.tsx`** — root component. Checks `localStorage` for `advising_v2_token`. If present, calls `/auth/me` to validate. Routes to `/admin/**` or `/adviser/**` based on `user.role`.

`RequireRole` guard redirects to the appropriate root if role doesn't match.

Two layout components (`AdminLayout`, `AdviserLayout`) render `AppFrame` with role-appropriate nav items. `AdviserLayout` wraps content with `MajorProvider`.

Route tree:
```
/               → redirect to /admin or /hub
/hub            → HubPage (requires adviser role) — app chooser card
/admin          → AdminLayout (requires admin role)
  index         → AdminOverviewPage
  /datasets     → DatasetsPage
  /periods      → PeriodsPage
  /users        → UsersPage
  /templates    → TemplatesPage
  /backups      → BackupsPage
  /audit        → AuditLogPage
  /progress     → AdminProgressPage (wrapped with MajorProvider)
/adviser        → AdviserLayout (requires adviser role)
  index         → DashboardPage
  /workspace    → WorkspacePage
  /insights     → InsightsPage
  /settings     → AdviserSettingsPage
/progress       → ProgressLayout (requires adviser role, wraps MajorProvider)
  index         → redirect to /progress/upload
  /upload       → UploadPage
  /configure    → ConfigurePage
  /reports      → ReportsPage
  /students     → StudentProgressPage
```

---

### 5.2 State Management

- **Server state**: React Query (`@tanstack/react-query`). All API data is cached with query keys.
- **Active major**: React Context (`MajorContext.tsx`). Stores `majorCode` string + `setMajorCode` + `allowedMajors` list. Initializes from the user's `major_codes` array, defaulting to the first allowed major.
- **Local UI state**: `useState` in individual page components.
- **Query invalidation**: After mutations (save selection, add bypass, etc.), `queryClient.invalidateQueries()` is called with relevant query keys to trigger refetch.

---

### 5.3 API Client & Hooks

**`lib/api.ts`**:  
- `API_BASE_URL` — from `VITE_API_BASE_URL` env var, falls back to `http://localhost:8000`.
- `apiFetch<T>(path, init?)` — wraps `fetch`, prepends `API_BASE_URL + '/api'`, attaches `Authorization: Bearer {token}` header from `localStorage`, throws on non-OK responses.
- All TypeScript types for API responses are defined here.

**`lib/hooks.ts`**:  
Thin wrappers around `useQuery`:
- `useCurrentUser()` — `GET /auth/me`
- `useMajors()` — `GET /majors`
- `useDashboard(majorCode)` — `GET /insights/{major}/dashboard`
- `useStudents(majorCode, query)` — `GET /students/{major}/search?query=...`
- `useStudentEligibility(majorCode, studentId)` — `GET /students/{major}/{id}`
- `useCourseCatalog(majorCode)` — `GET /students/{major}/catalog`
- `useDatasetVersions(majorCode)` — `GET /datasets/{major}`
- `usePeriods(majorCode)` — `GET /periods/{major}`
- `useTemplates(majorCode?)` — `GET /templates?major_code=...`
- `useUsers()` — `GET /users`
- `useBackups()` — `GET /backups`
- `useSessions(majorCode, periodCode?, studentId?)` — `GET /advising/sessions/{major}`
- `useExclusions(majorCode)` — `GET /advising/exclusions/{major}`
- `useAuditLog(eventType?)` — `GET /audit-events`
- `useProgressStatus(majorCode)` — `GET /progress/{major}/status`
- `useProgressEquivalents(majorCode)` — `GET /progress/{major}/equivalents`
- `useProgressAssignmentTypes(majorCode)` — `GET /progress/{major}/assignment-types`
- `useProgressAssignments(majorCode)` — `GET /progress/{major}/assignments`
- `useProgressReport(majorCode, page, pageSize, showAllGrades, search)` — `GET /progress/{major}/report` in page components using `authedFetch` (a local wrapper around `fetch`) then calling `queryClient.invalidateQueries`.

---

### 5.4 Admin Pages

| Page | Key functionality |
|---|---|
| `AdminOverviewPage` | Stats: majors count, users count, backup count |
| `DatasetsPage` | List dataset versions per major; upload new via `multipart/form-data`; activate/deactivate versions; download active file; download blank template |
| `PeriodsPage` | List, create, activate, archive, delete advising periods per major |
| `UsersPage` | List, create, toggle active, reset password for staff users; manage major access |
| `TemplatesPage` | CRUD email templates; preview rendered output for a student |
| `BackupsPage` | List backup runs; trigger new backup |
| `AuditLogPage` | Paginated audit event log with event type filter |
| `ImportsPage` | Trigger legacy snapshot import by major code |
| `AdminProgressPage` | Progress management for a selected major: data status, assignment types overview, full assignments table, reset-all danger action |

---

### 5.5 Adviser Pages

#### `DashboardPage`
- Major selector dropdown.
- 4 stat cards: Total Students, Advised, Not Advised, Progress %.
- "Graduating Soon (Not Advised)" table with deep-link to workspace (`?student_id=...&major=...`).
- "Recent Activity" feed from session snapshots.

#### `WorkspacePage`
The most complex page. Contains:
- Major selector + student combobox search (debounced, dropdown)
- Tab bar: Schedule, Academic, Exceptions, Degree Plan, History
- **Schedule tab**: `CourseSelectionBuilder` (course grid cards) + `StudentProfileHeader` (actions)
- **Academic tab**: `EligibilityTables` (required + intensive course tables)
- **Exceptions tab**: `ExceptionManagement` (bypass CRUD)
- **Degree Plan tab**: Visual semester-by-semester grouping
- **History tab**: Session snapshots for the student with restore actions
- Save, Email, Report download actions
- Handles `?major=` and `?student_id=` URL params for deep-linking from Dashboard

State loaded into `formState: { advised[], optional[], repeat[], note }`. Saved via `POST /advising/selection`.

#### `InsightsPage`
Multi-tab insights:
- **All Students tab**: Dynamic matrix table (students × courses), semester filter, remaining credits filter, simulated course controls, required/intensive column toggles, legend.
- **QAA tab**: Graduating students detail view, configurable credit threshold.
- **Conflicts tab**: Schedule conflict groups, configurable group count/min students.
- **Planner tab**: Course offering recommendations with priority scoring, save/restore planner state, impact summary for selected courses.

Each tab has an Excel export button that calls the corresponding `/reports/` endpoint.

#### `AdviserSettingsPage`
- Session management tools (clear period selections, bulk restore from history, clear individual student from current period)
- Exclusions management (add/remove global course exclusions for sets of students)

---

### 5.7 Academic Progress Pages

Located at `v2/frontend/src/pages/progress/`. All pages run inside `ProgressLayout` which provides a `MajorProvider` and an `AppFrame` with Home / Upload / Configure / Reports / Students nav.

#### `HubPage`
App chooser shown to advisers at `/hub`. Two cards: "Student Advising" (→ `/adviser`) and "Academic Progress" (→ `/progress`). Acts as the post-login landing page for advisers.

#### `UploadPage`
- Drag-and-drop upload zones for Progress Report and Course Config files.
- Status banner cards showing current dataset state (student count, required/intensive counts, upload date).
- Per-upload error/success feedback.

#### `ConfigurePage`
Two panels:
- **EquivalentsPanel**: editable table of `alias_code → canonical_code` pairs; saves with a single PUT call.
- **AssignmentTypesPanel**: list of type labels with add-new input and delete with confirmation.

#### `ReportsPage`
- Paginated pivot table (50 rows/page) with color-coded grade cells.
- Search box (deferred-query), show-all-grades toggle, Export XLSX button.
- Required section + Intensive section + extra courses tag list below table.

#### `StudentProgressPage`
- Sidebar list of all students (searchable, links via `?id=` URL param).
- Detail panel: credit summary cards, per-course grade table with color coding, assignment inputs per type.
- Supports deep-link via `?id=` query param.

---

### 5.6 Workspace Components

#### `CourseSelectionBuilder`
- Receives `eligibility[]`, `formState`, `onChange`, `onSave` props.
- **Stacked layout**: full-width course pool on top, full-width selections row below (4-column grid: Advised | Optional | Repeat | Advisor Note). Responsive — collapses to 2-col at 1100px, 1-col at 640px.
- **Search/filter bar** at the top of the course pool — instant client-side filter by course code or title.
- **Show not offered toggle**: checkbox next to the search bar. When enabled, courses not offered this semester appear greyed out with an "○ Not offered" label and no action buttons. Off by default.
- **Semester grouping**: courses are grouped by `suggested_semester` (from the courses dataset) into collapsible sections with course count badges. Courses without a suggested semester appear in an "Other" group.
- Renders course cards in a grid. Main courses and intensive courses are in separate sections.
- Each card shows status dot (green=eligible, grey=ineligible, yellow=registered, dark grey=completed, light grey=not offered), title, and action buttons (Advise / Optional / Repeat).
- **Status background colors**: cards have tinted backgrounds — green for completed, yellow for registered, grey for ineligible/not-offered, white for eligible.
- **Prerequisites inline**: ineligible course cards show requisite text (Prereq/Conc/Coreq) directly below the "Not eligible" label.
- Running credit bar: `advisedCredits / remainingCredits` with percentage.
- **Credit breakdown**: per-category display (Advised / Optional / Repeat credits) below the progress bar.
- **Credit load warnings**: orange warning when total advised credits exceed 18 (heavy load), red warning when exceeding remaining credits.
- Undo stack (up to 20 states) stored in `useRef`.

#### `EligibilityTables`
- Renders two tables (Required Courses, Intensive Courses) showing status pill, action, and justification for each course.

#### `ExceptionManagement`
- Bypass creation form (course selector + note textarea).
- Active bypasses list with delete button.

#### `StudentProfileHeader`
- Flat row: identity (name, ID), stats (standing, remaining credits, active period, completed count, registered count, eligible count), action buttons (Recommend, Download Report, Email, View Preview).
- **Course counters**: computed from the `eligibility[]` prop — shows how many courses are completed, registered, and eligible at a glance.
- **Recommend preview**: clicking "Recommend" shows a preview modal listing the recommended courses with titles and credit values. The adviser can Accept (apply to advised list) or Cancel.
- Email preview loads via `GET /templates/preview?...` and renders inline.
- **Tab persistence**: switching between students no longer resets the active tab — the last-viewed tab (Schedule Builder, Academic Record, Degree Plan, Bypass, History) is preserved across student switches within the session.

---

## 6. Data Models & Schema

### Status Codes (eligibility_service internal)
```
'completed'       → 'c'
'registered'      → 'r'
'advised'         → 'a'
'advised_repeat'  → 'ar'
'optional'        → 'o'
'bypass'          → 'b'
'eligible'        → 'na'
'not_eligible'    → 'ne'
```

### Dataset Types
| Type | Source | Key Columns / Structure |
|---|---|---|
| `courses` | Excel (1 sheet) | Course Code, Course Title, Credits, Type, Prerequisites, Corequisites, Suggested Semester |
| `progress` | Excel (1-2 sheets: Required + Intensive) | ID, NAME, per-course status columns, # of Credits Completed, # Registered, # Remaining |
| `advising_selections` | Excel or CSV | Historical selections — used for bulk restore |
| `email_roster` | CSV, Excel, or JSON | Student ID → Email mapping |
| `progress_report` | Excel/CSV | Long-format rows: ID, NAME, Course, Grade, Year, Semester. Parsed by `read_progress_report()`. Stored as `{records: [...rows]}`. |
| `course_config` | Excel/CSV | Target + intensive course rules with optional date ranges. Parsed by `read_course_config()`. Stored as `{records: [config_dict]}` (single-element list). |

### Period Code Format
`{major_code_lower}-{semester_lower}-{year}-{advisor_name_slug}`  
Example: `pbhl-spring-2026-dr-smith`

---

## 7. Core Business Logic

### 7.1 Eligibility Engine

Eligibility is computed in `student_service.py::student_eligibility()` by calling `eligibility_utils.check_eligibility()` for every non-hidden, non-excluded course in the courses DataFrame.

Each course returns either:
- `'Eligible'` — all prerequisite/corequisite conditions met
- `'Eligible (Bypass)'` — bypass exists in DB
- `'Not Eligible: {reason}'` — with reason string

The service also:
- Marks courses as `completed` or `registered` via `check_course_completed` / `check_course_registered`
- Builds `action` field by combining eligibility + existing selection state (e.g., advised, optional, repeat, completed, registered, bypass, not eligible)
- Computes `advised_credits`, `optional_credits`, `repeat_credits` by summing credit values from course DF

The `mutual_concurrent_pairs` pre-computation identifies pairs of courses that are each other's corequisites — important for course-offering recommendations.

---

### 7.2 Dataset Ingestion

On upload (`dataset_service.upload_dataset`):

1. Validate `dataset_type` is one of the four supported types.
2. Call `_parse_dataset(dataset_type, file_bytes, filename)` → returns `(records: list[dict], metadata: dict)`.
3. For `progress` type, call `load_progress_excel` which handles the two-sheet merge (`Required Courses` + `Intensive Courses`) by outer-joining on `[ID, NAME]` and de-duplicating numeric summary columns.
4. SHA-256 hash the raw bytes for the `checksum` field and deduplication.
5. Store raw bytes in `StorageService` under key `datasets/{major}/{type}/{checksum}-{filename}`.
6. Deactivate all existing versions for this `(major_id, dataset_type)`.
7. Insert new `DatasetVersion` with `parsed_payload={"records": records}` and `is_active=True`.
8. For `email_roster` type only, also upsert `EmailRosterEntry` rows.
9. Commit.

Retrieval (`dataset_dataframe`): load `parsed_payload["records"]` from the active version and reconstruct a DataFrame via `pd.DataFrame(records)`.

---

### 7.3 Insights & Analytics

#### Dashboard Metrics
```
total_students     = len(progress_df)
advised_students   = count of StudentSelection rows with len(advised) > 0
not_advised        = total - advised
progress_percent   = (advised / total) * 100
graduating_soon    = students where remaining_credits <= 36 AND not in advised set
recent_activity    = last 10 SessionSnapshot rows ordered by created_at desc
```

#### All Students View
For each student in the progress DF, and each course in the courses DF:
- Run `_status_code(student_row, student_id, course_code, ...)` — returns one of the status codes.
- Return a matrix: `{ rows: [{student_id, name, remaining_credits, courses: {code: status_code}}], required_courses: [], intensive_courses: [], course_metadata: {} }`
- Semester filtering narrows which courses appear in columns.
- Simulated courses: treated as already advised for all students during the status calculation (simulation mode).

#### Course Offering Planner
Scoring formula per course:
- `currently_eligible` — count of students with status `'na'` (eligible) for this course
- `graduating_students` — subset of above where `remaining_credits <= graduation_threshold`
- `cascading_eligible` — count of additional students who would become eligible for other courses if this course were offered
- `bottleneck_score` — `graduating_students * 2 + currently_eligible + cascading_eligible * 0.5`
- `priority_score` — `bottleneck_score` (used for sorting)

Saved planner state is stored in `audit_events` table with `event_type='planner.save'` and `entity_type='major'`, payload containing `{selected_courses, graduation_threshold, min_eligible_students}`. The latest such event is retrieved as the current state.

---

### 7.4 Email System

**Delivery**: `smtplib.SMTP('smtp.office365.com', 587)` with `starttls()`. Login uses **per-major** SMTP credentials stored on the `majors` table (`smtp_email`, `smtp_password`). Global `.env` SMTP variables are no longer used.

**CC**: The logged-in adviser's email (from their `users.email`) is added as a CC header on every outgoing email.

**Template rendering**: Python `str.format()` with keyword args. Variables: `{student_name}`, `{major}`, `{semester}`, `{year}`, `{advisor_name}`.

**Body construction**: template body + advised courses list + optional courses list + repeat courses list + note.

**Email roster lookup**: `EmailRosterEntry` table, matched on `(major_id, student_id)`.

If per-major SMTP credentials are not configured, `send_student_email` returns `{success: False, message: 'SMTP credentials not configured for {major}'}` rather than raising.

---

### 7.5 Backup & Import

**Backup**: Calls `pg_dump {DATABASE_URL}` as a subprocess, captures stdout, compresses with gzip, writes to `backups/{timestamp}/database.sql.gz` in storage, records `BackupRun`. Note: only works with PostgreSQL (`pg_dump`). Will fail silently or raise on SQLite.

**Legacy import** (`import_service.import_legacy_snapshot`):
1. Resolves `{import_root}/{major_code}/` directory.
2. Reads and uploads `courses.xlsx`, `progress.xlsx`, `email_roster.json`.
3. Reads `current_period.json` and `advising_period_history.json` → calls `_upsert_periods`.
4. Reads `course_exclusions.json` → calls `_import_hidden_courses`.
5. Reads `sessions/advising_session_*.json` + `sessions/advising_index.json` → calls `_apply_session_records` to recreate `SessionSnapshot` and `StudentSelection` rows.
6. Records a `BackupRun` with manifest of what was imported.

---

## 8. API Endpoint Reference

### Auth
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/login` | None | Email + password → JWT token |
| GET | `/api/auth/me` | Bearer | Current user + major_codes |

### Majors
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/majors` | Staff | List all active majors (includes `smtp_email`, `smtp_configured` — never exposes password) |
| PUT | `/api/majors/{code}` | Admin | Update major name, SMTP email, SMTP password |
| GET | `/api/majors/{code}/smtp-password` | Admin | Reveal stored SMTP password for a major |

### Datasets
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/datasets/{major_code}` | Staff | List all dataset versions |
| GET | `/api/datasets/templates/{dataset_type}` | Staff | Download blank XLSX template |
| GET | `/api/datasets/{major_code}/{dataset_type}/download` | Staff | Download active file |
| POST | `/api/datasets/{major_code}` | Staff | Upload new dataset file (multipart) |
| POST | `/api/datasets/{version_id}/activate` | Admin | Activate a specific version |
| DELETE | `/api/datasets/{version_id}` | Admin | Delete inactive version |

### Periods
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/periods/{major_code}` | Staff | List periods |
| POST | `/api/periods/{major_code}` | Admin | Create period |
| POST | `/api/periods/{major_code}/{period_code}/activate` | Admin | Activate period |
| POST | `/api/periods/{major_code}/{period_code}/archive` | Admin | Archive period |
| DELETE | `/api/periods/{major_code}/{period_code}` | Admin | Delete period |

### Students
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/students/{major_code}/search?query=` | Staff | Search students in progress DF |
| GET | `/api/students/{major_code}/catalog` | Staff | All courses in catalog |
| GET | `/api/students/{major_code}/{student_id}` | Staff | Full eligibility payload |

### Advising
| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/advising/selection` | Staff | Save advised/optional/repeat lists |
| GET | `/api/advising/sessions/{major_code}` | Staff | List session snapshots |
| POST | `/api/advising/sessions/{major}/{period}/{student}/restore` | Staff | Restore latest snapshot |
| POST | `/api/advising/sessions/{major}/snapshot/{id}/restore` | Staff | Restore specific snapshot |
| POST | `/api/advising/sessions/restore-all` | Staff | Restore all sessions from a period |
| POST | `/api/advising/sessions/bulk-restore` | Staff | Restore sessions for student subset |
| DELETE | `/api/advising/selection/{major}/{period}` | Staff | Clear all selections for period |
| GET | `/api/advising/recommendations/{major}/{student}` | Staff | Recommended courses |
| POST | `/api/advising/bypasses` | Staff | Set bypass |
| DELETE | `/api/advising/bypasses/{major}/{student}/{course}` | Staff | Remove bypass |
| POST | `/api/advising/hidden-courses` | Staff | Replace hidden courses list |
| POST | `/api/advising/exclusions` | Staff | Replace exclusions for students |
| GET | `/api/advising/exclusions/{major_code}` | Staff | List all exclusions |

### Insights
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/insights/{major}/dashboard` | Staff | Dashboard metrics |
| GET | `/api/insights/{major}/all-students` | Staff | Full student matrix |
| GET | `/api/insights/{major}/individual/{student_id}` | Staff | Individual student insight view |
| GET | `/api/insights/{major}/course-planner` | Staff | Course offering recommendations |
| GET | `/api/insights/{major}/course-planner-state` | Staff | Saved planner selection |
| POST | `/api/insights/{major}/course-planner-state` | Staff | Save planner selection |
| GET | `/api/insights/{major}/qaa` | Staff | QAA sheet data |
| GET | `/api/insights/{major}/schedule-conflicts` | Staff | Schedule conflict analysis |
| GET | `/api/insights/{major}/degree-plan/{student_id}` | Staff | Degree plan grouped by semester |

### Reports (Excel Downloads)
| Method | Path | Description |
|---|---|---|
| GET | `/api/reports/{major}/student/{student_id}` | Individual student workbook |
| GET | `/api/reports/{major}/individual/{student_id}` | Individual compact format |
| GET | `/api/reports/{major}/all-advised` | All advised students workbook |
| GET | `/api/reports/{major}/qaa` | QAA report workbook |
| GET | `/api/reports/{major}/schedule-conflicts` | Schedule conflicts CSV |

### Academic Progress
| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/progress/{major_code}/status` | Staff | Dataset upload status for this major |
| POST | `/api/progress/{major_code}/upload/progress-report/preview` | Staff | Parse file and return diff summary (no save): `{new_students, removed_students, grade_changes, total_students}` |
| POST | `/api/progress/{major_code}/upload/progress-report` | Admin | Upload progress report file |
| POST | `/api/progress/{major_code}/upload/course-config` | Admin | Upload course configuration file |
| GET | `/api/progress/{major_code}/report` | Staff | Paginated pivot report (`?page&page_size&show_all_grades&search`) |
| GET | `/api/progress/{major_code}/report/export` | Staff | Download full report as XLSX |
| GET | `/api/progress/{major_code}/equivalents` | Staff | List course alias→canonical mappings |
| PUT | `/api/progress/{major_code}/equivalents` | Admin | Replace all equivalents (bulk) |
| GET | `/api/progress/{major_code}/assignment-types` | Staff | List assignment type labels |
| POST | `/api/progress/{major_code}/assignment-types` | Admin | Create assignment type |
| DELETE | `/api/progress/{major_code}/assignment-types/{id}` | Admin | Delete assignment type |
| GET | `/api/progress/{major_code}/assignments` | Staff | List all student assignments |
| PUT | `/api/progress/{major_code}/assignments` | Staff | Upsert one student assignment |
| DELETE | `/api/progress/{major_code}/assignments/one` | Staff | Delete one student assignment |
| DELETE | `/api/progress/{major_code}/assignments` | Admin | Reset all assignments for major |

### Users, Templates, Emails, Backups, Imports, Audit — follow similar CRUD patterns.

---

## 9. Environment Variables

Create `v2/backend/.env`:

```dotenv
# Required for production
DATABASE_URL=postgresql+psycopg://user:password@host/dbname
JWT_SECRET=your-random-256-bit-secret

# CORS — set to your frontend URL
CORS_ORIGINS=https://yourdomain.com

# Cloudflare R2 (leave blank to use local storage)
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=
R2_PUBLIC_BASE_URL=

# Optional
JWT_EXPIRY_MINUTES=480
LOCAL_STORAGE_PATH=./local-storage
LEGACY_IMPORTS_PATH=../../
```

Create `v2/frontend/.env`:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
# or for production:
VITE_API_BASE_URL=https://api.yourdomain.com
```

---

## 10. Local Development Setup

```bash
# Backend
cd v2/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional: copy .env.example to .env and fill in secrets
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd v2/frontend
npm install
npm run dev  # starts at http://localhost:5173
```

**Default seeded credentials** (created by `bootstrap.py` on first startup):
- Admin: `admin@example.com` / `admin1234`
- Adviser: `adviser@example.com` / `adviser1234`

**Recommendation**: change these immediately in production by updating via the Users API.

The app auto-creates all database tables (`Base.metadata.create_all`) on startup — no migration tool is needed for initial setup. For schema evolution, you will need to either drop and recreate (dev only) or write manual ALTER TABLE migrations.

---

## 11. Production Deployment Notes

### Backend
- Use `gunicorn -k uvicorn.workers.UvicornWorker app.main:app` or `uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Set `DATABASE_URL` to a managed PostgreSQL instance (e.g., Neon).
- Set `JWT_SECRET` to a cryptographically random string (run: `python -c "import secrets; print(secrets.token_hex(32))"`).
- Configure `CORS_ORIGINS` to your frontend's public URL only.
- Enable HTTPS via a reverse proxy (nginx, Caddy, etc.) — JWT tokens are transmitted in headers and must be protected in transit.
- The `backup_job.py` requires `pg_dump` to be on `PATH` — it will fail on SQLite. Schedule backups with a cron job or systemd timer calling `python -m app.services.backup_job`.

### Frontend
- Build with `npm run build` → produces `dist/` folder.
- Serve as static files behind the same reverse proxy, or deploy to Vercel/Netlify.
- Set `VITE_API_BASE_URL` at build time to the backend's public URL.

### Security Checklist
- [ ] Change all default passwords before first use.
- [ ] Set a strong `JWT_SECRET` (minimum 256-bit random hex).
- [ ] Restrict `CORS_ORIGINS` to production frontend URL only.
- [ ] Enable HTTPS in front of both backend and frontend.
- [ ] Ensure `R2_SECRET_ACCESS_KEY` and `SMTP_PASSWORD` are never committed to source control.
- [ ] Rotate `pg_dump` credentials if the backup storage is shared.

---

## 12. Parity Status & Known Gaps

The V2 rebuild is **partially complete**. See `PARITY_AUDIT.md` for a detailed gap list. Key remaining gaps as of the last audit:

1. **All-students workbook export** — V2 exports are simplified relative to the legacy formatting in `full_student_view.py`.
2. **Session snapshot payload** — V2 stores a reduced snapshot structure vs the full legacy `advising_history.py` format; exact historical replay is not guaranteed.
3. **Email body formatting** — V2 email body is plainer than the legacy formatted preview.
4. **Simulation-specific exports** — "simulated" all-students state is not exportable in the same format as legacy.
5. **Degree plan layout fidelity** — Data is present but visual grouping differs from legacy.
6. **Planner summary details** — Some downstream cascade/period summary data shown in legacy planner is not reproduced.

The eligibility computation itself is **fully parity** — it calls the same `eligibility_utils.py` functions as the legacy Streamlit app.
