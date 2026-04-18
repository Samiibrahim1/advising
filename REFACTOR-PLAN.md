# Refactor Plan — 30-Day Sprint Plan

## Top 10 Issues

| # | Severity | File | Line(s) | Description |
|---|----------|------|---------|-------------|
| 1 | **CRITICAL** | `services/storage.py` | 43–44 | **Path traversal in local storage.** `put_bytes(key)` writes to `self.local_root / key` with no sanitization. A crafted key like `../../etc/cron.d/evil` escapes the storage root. Same issue in `get_bytes()`. |
| 2 | **CRITICAL** | `services/backup_job.py` | 145–168 | **Restore overwrites production DB with no safeguard.** `restore_backup()` directly pipes into `psql` or overwrites the SQLite file. No confirmation, no pre-restore backup, no dry-run. A mis-click deletes all current data. |
| 3 | **CRITICAL** | `frontend/src/pages/LoginPage.tsx` | 8–9 | **Hardcoded credentials in source code.** Login form ships with `admin@example.com` / `admin1234` pre-filled. These are the real default seeded credentials. Visible in browser source in production. |
| 4 | **HIGH** | `services/bootstrap.py` | 46–53 | **Default users with weak known passwords.** Seeds `admin@example.com:admin1234` and `adviser@example.com:adviser1234` on every fresh deploy. No forced password change, no env-var override. |
| 5 | **HIGH** | `schemas/admin.py` | 13 | **No password complexity validation.** `UserCreateRequest.password` is an unbounded `str`. Accepts empty strings, single characters, or dictionary words. Same for `UserUpdateRequest.new_password`. |
| 6 | **HIGH** | `api/routes/datasets.py` | 153–169 | **No upload size limit.** `upload_dataset_route()` reads the entire `UploadFile` into memory with no cap. A 2GB upload will OOM the server. FastAPI has no default body limit. |
| 7 | **HIGH** | `api/deps.py` | 28–39 | **No login rate limiting.** `get_current_user()` and the login endpoint have no throttle. An attacker can brute-force credentials at full speed with no lockout. |
| 8 | **MEDIUM** | `services/email_service.py` (template rendering) | 200–207 | **String format injection in email templates.** `template.subject_template.format(...)` and `body_template.format(...)` use Python `str.format()`. A malicious template key like `{student_name.__class__}` could leak internal state. |
| 9 | **MEDIUM** | `api/routes/majors.py` | (SMTP password route) | **SMTP password stored and returned in plaintext.** `GET /majors/{code}/smtp-password` returns the raw password. It's stored unencrypted in the `majors` table. |
| 10 | **MEDIUM** | `main.py` | 46–82 | **Startup migrations use raw SQL strings with no error handling.** Column migrations use `text()` with `ALTER TABLE` without try/except. On PostgreSQL, if a column already exists (race condition on multi-instance deploy), the startup crashes. The `existing_cols` check only runs once; a second concurrent worker may try to add the same column. |

---

## 30-Day Sprint Plan

### Week 1: Security Hardening (Issues #1–#5)

**Goal:** Close all critical and high-severity security holes.

| Day | Task | Issue | Risk |
|-----|------|-------|------|
| 1 | **Fix path traversal in StorageService.** Validate that resolved path stays within `local_root`. Reject keys containing `..` or starting with `/`. | #1 | Low — only affects local storage path, R2 keys are safe |
| 1 | **Remove hardcoded credentials from LoginPage.** Change `useState('')` for both email and password. Remove the pre-filled demo values. | #3 | Low — cosmetic change |
| 2 | **Add pre-restore backup to `restore_backup()`.** Before overwriting, call `run_backup(triggered_by='pre-restore-safety')` and store reference. Log the safety backup ID. | #2 | Medium — must test with both SQLite and PostgreSQL |
| 3 | **Add password complexity validation.** Add `@field_validator('password')` to `UserCreateRequest` enforcing min 8 chars, at least 1 digit, at least 1 letter. Same for `new_password` in `UserUpdateRequest`. | #5 | Low — only affects new/changed passwords |
| 3 | **Make default seed passwords configurable.** Read `DEFAULT_ADMIN_PASSWORD` and `DEFAULT_ADVISER_PASSWORD` from env vars in `bootstrap.py`. Fall back to current values only if `APP_ENV=development`. | #4 | Low — backward-compatible |
| 4 | **Add upload file size limit.** Reject uploads > 50MB in `upload_dataset_route()` by checking `file.size` or reading with a capped buffer. Return 413 if exceeded. | #6 | Low — straightforward guard |
| 5 | **Add login rate limiting.** Use `slowapi` or a simple in-memory counter in `auth.py` to limit login attempts to 5 per minute per IP. Return 429 on excess. | #7 | Medium — needs testing under load, consider Redis for multi-worker |

### Week 2: Data Safety & Email Fixes (Issues #8–#10)

**Goal:** Fix remaining medium-severity issues and improve data safety.

| Day | Task | Issue | Risk |
|-----|------|-------|------|
| 6 | **Sanitize email template rendering.** Replace `str.format()` with a safe templating approach: use `string.Template.safe_substitute()` or a whitelist of allowed placeholders. | #8 | Medium — must not break existing templates |
| 7 | **Encrypt SMTP password at rest.** Use Fernet symmetric encryption (key from env var) to encrypt `smtp_password` before storing and decrypt on read. Migrate existing plaintext values on startup. | #9 | High — breaking change, needs migration. Flag only if risky. |
| 8 | **Make startup migrations idempotent.** Wrap each `ALTER TABLE` in try/except and catch "column already exists" errors. Add logging instead of crashing. | #10 | Low — defensive programming |
| 9 | **Add soft-delete for periods and majors.** Instead of hard delete, set `archived_at` timestamp. Add `is_archived` filter to all queries. Keep hard delete as admin-only "purge" option. | Beyond top 10 | Medium — schema change |
| 10 | **Add audit logging for restore operations.** Log a `backup.restored` event before and after restore. Include backup ID, triggered_by, and result. | #2 related | Low |

### Week 3: Performance & Caching

**Goal:** Address the O(S×C) performance bottleneck and add caching.

| Day | Task | Risk |
|-----|------|------|
| 11–12 | **Cache eligibility results.** Add a per-request or short-TTL (30s) cache for `student_eligibility()` results keyed by `(major_code, student_id, dataset_version_id)`. Use `cachetools.TTLCache` or similar. | Medium — cache invalidation on selection save |
| 13 | **Paginate all-students view.** Add `page` + `page_size` params to `GET /insights/{major}/all-students`. Process only requested page server-side. | Medium — frontend must handle pagination |
| 14 | **Add debounced student search.** Frontend: 300ms debounce on search input. Backend: limit search results to 25 by default. | Low |
| 15 | **Stream Excel exports.** Use `openpyxl` write-only mode and `StreamingResponse` for report exports instead of building full workbook in memory. | Medium — API contract unchanged |

### Week 4: Testing & Cleanup

**Goal:** Add test coverage for critical paths and clean up tech debt.

| Day | Task | Risk |
|-----|------|------|
| 16–17 | **Add backend integration tests.** Cover: login flow, dataset upload, period create/activate/restore, student eligibility, email send. Use `TestClient` + SQLite in-memory. Target: 15 tests covering all critical paths. | Low |
| 18 | **Add frontend component tests.** Cover: LoginPage, WorkspacePage save/email flow, InsightsPage data display. Use Vitest + React Testing Library. Target: 10 tests. | Low |
| 19 | **Extract WorkspacePage into sub-components.** Split the 700+ line file into: `StudentSearch`, `CourseBuilder`, `SessionHistory`, `EmailPanel`. | Low — pure refactor, no behavior change |
| 20 | **Remove dead code and consolidate imports.** Clean up unused imports, remove commented-out code, consolidate duplicate type definitions between frontend and backend. | Low |

---

## Success Metrics

| Metric | Before | After Week 4 |
|--------|--------|--------------|
| Critical security issues | 3 | 0 |
| High severity issues | 4 | 0 |
| Backend test count | 0 | 15+ |
| Frontend test count | 0 | 10+ |
| Max upload size enforcement | None | 50 MB |
| Login rate limiting | None | 5/min/IP |
| Password minimum complexity | None | 8 chars, mixed |

---

## Out of Scope (Future)

These are real issues but don't fit in a 30-day window:

- **Token refresh / rotation** — Currently tokens live 8 hours with no refresh. Implement refresh tokens when adding session management.
- **Full HTML email** — Currently plain-text only. Add mjml or Jinja2 HTML templates when design team provides mockups.
- **Backup encryption at rest** — Requires KMS integration. Plan for when moving to production-grade backup strategy.
- **Audit log archival** — Table grows unbounded. Add partitioning or time-based archival when audit volume exceeds 100K rows.
- **WebSocket for real-time updates** — Polling works for current user count (<50 concurrent). Revisit at scale.
