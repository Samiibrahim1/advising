# Architecture Guide — PU Academic Advising V2

## 1. What This System Does

This is a **university academic advising tool** for Phoenicia University. It helps advisers guide students through course selection each semester and tracks academic progress across their degree. There are two types of users:

- **Admins** set up the system: create majors, manage users, upload course data, configure email templates, run backups.
- **Advisers** do the advising: search for a student, review their eligibility, select courses, send an email summary.

The system supports four academic programs (majors): **PBHL**, **SPTH-New**, **SPTH-Old**, and **NURS**. Each major has its own course list, progress reports, and advising periods.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (SPA)                    │
│  React 19 + TypeScript + Vite + React Query          │
│  Port 5173 (dev) / Static (prod Render)              │
└──────────────────────┬──────────────────────────────┘
                       │ HTTPS (JSON)
                       ▼
┌─────────────────────────────────────────────────────┐
│                  Backend (API)                       │
│  FastAPI + SQLAlchemy + Pydantic                     │
│  Port 8000 (dev) / Render Web Service (prod)         │
├──────────────────────┬──────────────────────────────┤
│  Service Layer       │  Legacy Bridge               │
│  (all business logic)│  (eligibility_utils.py,      │
│                      │   reporting.py at repo root)  │
└──────────┬───────────┴──────────────────────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌──────────┐
│   DB    │  │ Storage  │
│ Neon PG │  │ R2 / FS  │
│(SQLite  │  │          │
│  local) │  │          │
└─────────┘  └──────────┘
```

---

## 3. Frontend

**Location:** `v2/frontend/`  
**Stack:** React 19, TypeScript (strict), Vite 7, React Router 7, TanStack React Query 5

### Routing Structure

```
/login              → LoginPage (email + password form)
/                   → HubPage (app launcher — links to admin, adviser, progress)

/admin              → AdminLayout (sidebar + outlet)
  /admin/overview   → AdminOverviewPage (stats cards)
  /admin/users      → UsersPage (CRUD user management)
  /admin/majors     → MajorsPage (CRUD majors + SMTP config)
  /admin/templates  → TemplatesPage (email template editor)
  /admin/periods    → PeriodsPage (view/create advising periods)
  /admin/datasets   → DatasetsPage (upload/activate datasets)
  /admin/backups    → BackupsPage (trigger/restore backups)
  /admin/audit      → AuditPage (event log viewer)
  /admin/imports    → ImportsPage (legacy/Google Drive import)

/adviser/:majorCode → AdviserLayout + MajorProvider
  /dashboard        → DashboardPage (metrics cards + charts)
  /workspace        → WorkspacePage (student search → advise → email)
  /insights         → InsightsPage (multi-student grid, QAA, conflicts)
  /settings         → AdviserSettingsPage (period/session management)

/progress/:majorCode → ProgressLayout + MajorProvider
  /upload           → UploadPage (upload progress report + course config)
  /configure        → ConfigurePage (equivalents + assignment types)
  /reports          → ReportsPage (progress report viewer)
  /students         → StudentProgressPage (per-student assignments)
```

### Data Flow

All server state is managed by **React Query**. There is no Redux or Zustand.

1. Components call `useQuery` or `useMutation` hooks with `apiFetch()` calls.
2. `apiFetch()` (in `lib/api.ts`) prepends `/api`, attaches the Bearer token from `localStorage`, and throws on non-2xx.
3. After mutations, `queryClient.invalidateQueries()` triggers refetches.
4. Auth token stored in `localStorage` as `advising_v2_token`.

### Key Components

| Component | File | Purpose |
|-----------|------|---------|
| `StudentProfileHeader` | `components/workspace/` | Shows student info + email button |
| `CourseSelectionBuilder` | `components/workspace/` | Drag courses between eligible/advised/optional/repeat |
| `EligibilityTables` | `components/workspace/` | Course tables with status badges |
| `ExceptionManagement` | `components/workspace/` | Bypasses + hidden courses + exclusions |

---

## 4. Backend

**Location:** `v2/backend/`  
**Stack:** FastAPI, SQLAlchemy 2.0 (mapped columns), Pydantic v2, Python 3.11

### Directory Layout

```
app/
├── main.py              # App creation, startup migrations, CORS, exception handler
├── db.py                # Engine + SessionLocal + DeclarativeBase
├── core/
│   ├── config.py        # Pydantic Settings (env vars)
│   ├── roles.py         # ADMIN, ADVISER constants
│   └── security.py      # Password hashing (PBKDF2), JWT encode/decode
├── models/
│   ├── entities.py      # All ORM models (User, Major, DatasetVersion, etc.)
│   └── progress_models.py  # EquivalentCourse, AssignmentType, ProgressAssignment
├── schemas/
│   ├── admin.py         # User, Major, Period, Dataset, Template, Backup schemas
│   ├── auth.py          # Login, Token, CurrentUser
│   ├── common.py        # ORMModel base, MessageResponse
│   ├── insights.py      # Dashboard, CourseOffering, Planner schemas
│   ├── progress.py      # Progress report, assignment schemas
│   └── advising.py      # Student, Eligibility, Selection, Session schemas
├── api/
│   ├── deps.py          # Auth dependencies (get_current_user, require_admin, ensure_major_access)
│   ├── router.py        # Aggregates all sub-routers under /api
│   └── routes/          # 16 route modules (health, auth, users, majors, ...)
└── services/            # Business logic layer (no raw DB queries in routes)
    ├── auth_service.py
    ├── audit.py
    ├── bootstrap.py     # Seeds default data on first startup
    ├── storage.py       # R2 or local filesystem abstraction
    ├── dataset_service.py
    ├── period_service.py
    ├── template_service.py
    ├── student_service.py
    ├── email_service.py
    ├── insights_service.py
    ├── progress_service.py
    ├── progress_processing.py
    ├── backup_job.py
    ├── drive_import_service.py
    ├── import_service.py
    └── snapshot_export_service.py
```

### Request Lifecycle

```
HTTP Request
  → CORS Middleware
  → FastAPI Router (prefix /api)
  → Route handler (in routes/)
    → Auth dependency (get_current_user → JWT decode → User lookup)
    → Major access check (ensure_major_access)
    → Service function call (all business logic here)
      → ORM queries via SQLAlchemy Session
      → Legacy bridge calls (eligibility_utils, reporting)
      → Storage operations (R2 or local)
    → Pydantic schema serialization
  → JSON Response
```

### Authentication Flow

1. User POSTs email+password to `/api/auth/login`.
2. `auth_service.authenticate_user()` verifies password hash (PBKDF2_SHA256).
3. Server issues a JWT (HS256) with `sub=user_id`, expires in 480 minutes.
4. Frontend stores token in `localStorage`, sends as `Authorization: Bearer <token>` header.
5. `get_current_user()` dependency decodes JWT, fetches User from DB on every request.
6. `ensure_major_access()` checks UserMajorAccess table (admins bypass this check).

---

## 5. Database

### Development: SQLite (file: `advising_v2.db`)
### Production: Neon PostgreSQL

### Key Tables (23 total)

| Table | Purpose |
|-------|---------|
| `users` | Accounts (email, password_hash, role) |
| `majors` | Academic programs (PBHL, SPTH-New, etc.) + SMTP config |
| `user_major_access` | Which users can access which majors |
| `upload_batches` | Log of every file upload |
| `dataset_versions` | Versioned datasets (courses, progress, email_roster, etc.) |
| `advising_periods` | Semester periods with snapshot pointers to dataset versions |
| `student_selections` | Advised/optional/repeat course picks per student |
| `session_snapshots` | Point-in-time snapshots of advising sessions |
| `course_exclusions` | Courses excluded for specific students |
| `hidden_courses` | Courses hidden from a student's view |
| `bypasses` | Prerequisite override records |
| `email_roster_entries` | Student email addresses |
| `email_templates` | Configurable email templates with variable placeholders |
| `export_artifacts` | Tracks exported files |
| `backup_runs` | Backup metadata and storage keys |
| `audit_events` | Full audit trail of all significant actions |
| `equivalent_courses` | Course alias mappings (progress tracking) |
| `assignment_types` | Elective slot categories (S.C.E, F.E.C, etc.) |
| `progress_assignments` | Per-student elective slot assignments |

### Dataset Versioning & Period Snapshots

Datasets are versioned. Only one version per type per major is "active" at a time.

When an advising period is **created**, it captures snapshot pointers to the currently active:
- `progress_version_id` → progress_report dataset
- `progress_dataset_version_id` → progress dataset
- `config_version_id` → course_config dataset

When a period is **activated** (switched to), those snapshots are restored — the pointed-to dataset versions are re-activated, so the user sees the data as it was when the period was created.

When a new dataset is **uploaded**, the active period's snapshot pointer is updated to track the latest version.

---

## 6. Legacy Bridge

The **eligibility engine** lives at the workspace root (not in `v2/`):
- `eligibility_utils.py` — Core prerequisite/corequisite checking, course eligibility calculations
- `reporting.py` — Excel report generation helpers

The V2 backend imports these via `sys.path` manipulation in `dataset_service.py`. The `_find_legacy_root()` function walks up the directory tree looking for `eligibility_utils.py`.

This is a **shared dependency** — the same files are used by the V1 Streamlit app. Changes to these files affect both versions.

---

## 7. Storage

**Production:** Cloudflare R2 (S3-compatible object storage)  
**Development:** Local filesystem (`./local-storage/`)

The `StorageService` class abstracts this. It auto-detects R2 credentials and falls back to local disk.

Storage keys follow the pattern: `datasets/{major_code}/{dataset_type}/{checksum}-{filename}`

---

## 8. Email Transport

Email sends go through a priority chain:

1. **Brevo API** (HTTPS to `api.brevo.com`) — Primary. Sends from verified university address `cph@pu.edu.lb`.
2. **Microsoft Graph API** (HTTPS to `graph.microsoft.com`) — Code ready, needs Azure AD credentials.
3. **Direct SMTP** (port 587 to Office 365) — Works locally but **blocked by Render** in production.

The `send_student_email()` function in `email_service.py` tries each transport in order and returns on the first success.

---

## 9. Startup Behavior

On startup (`main.py → on_startup()`):
1. Create all database tables (SQLAlchemy `create_all`)
2. Run column migrations (add missing columns to `advising_periods` and `majors` tables)
3. Seed default data (4 majors, 2 users, 2 email templates)
4. Backfill NULL snapshot columns on existing periods
5. Fix PostgreSQL sequence numbers (safety net after data migrations)

---

## 10. Data Flow: Advising a Student

```
1. Adviser opens WorkspacePage
2. Types student ID → GET /students/{major}/search
3. Selects student → GET /students/{major}/{student_id}
   → student_service.student_eligibility()
   → Loads courses dataset, progress dataset, exclusions, bypasses, hidden courses
   → Calls legacy eligibility_utils to check prerequisites
   → Returns full eligibility + current selections
4. Adviser drags courses → CourseSelectionBuilder
5. Clicks Save → POST /advising/selection
   → Saves StudentSelection rows + creates SessionSnapshot
6. Clicks Send Email → POST /emails/{major}/{student_id}
   → Builds email from template + selection data
   → Sends via Brevo (or fallback transport)
```

---

## 11. Data Flow: Academic Progress

```
1. Admin uploads progress report (Excel) → POST /progress/{major}/upload/progress-report
   → progress_processing.read_progress_report() parses wide/long format
   → Stored as DatasetVersion with parsed_payload
2. Admin uploads course config (Excel) → POST /progress/{major}/upload/course-config
   → progress_processing.read_course_config() parses target/intensive courses
3. Admin clicks "Push to Advising" → POST /progress/{major}/push-to-advising
   → Computes credits, GPA, remaining courses from progress + config
   → Updates progress dataset used by advising eligibility engine
4. Adviser views progress → GET /progress/{major}/report
   → progress_service.generate_report() joins progress + config
   → Returns paginated student rows with course grades and colors
```
