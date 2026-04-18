# Changes Log — Codebase Audit Fixes

All changes made during the security audit on 2026-03-28. Every fix targets a specific issue from REFACTOR-PLAN.md.

---

## Fix 1: Path Traversal in StorageService (Issue #1 — CRITICAL)

**File:** `v2/backend/app/services/storage.py`

**Problem:** `put_bytes(key)` and `get_bytes(key)` used `self.local_root / key` with no validation. A crafted key like `../../etc/passwd` would escape the storage root directory.

**Fix:**
- Resolved `local_root` to an absolute path on init (`.resolve()`)
- Added `_safe_local_path(key)` method that resolves the full path and checks it starts with `local_root`
- Replaced all raw `self.local_root / key` usages with `self._safe_local_path(key)` in `put_bytes()`, `get_bytes()`, and `public_url()`
- Raises `ValueError` if path escapes root

**Verified:** Smoke test confirms `../../etc/passwd` is correctly rejected.

---

## Fix 2: Pre-Restore Safety Backup (Issue #2 — CRITICAL)

**File:** `v2/backend/app/services/backup_job.py`

**Problem:** `restore_backup()` immediately overwrote the production database with no safety net. A mistaken restore would permanently lose all current data.

**Fix:**
- Added `run_backup(triggered_by='pre-restore-safety')` call before the actual restore
- The safety backup is logged with the target backup ID for traceability
- If the safety backup fails (e.g., storage issue), a warning is logged but restore proceeds — this avoids a chicken-and-egg problem where a broken DB prevents both backup and restore

**Risk note:** The restore still executes destructively (by design). The safety backup means the previous state is always recoverable by restoring the safety backup.

---

## Fix 3: Hardcoded Credentials in Login Form (Issue #3 — CRITICAL)

**File:** `v2/frontend/src/pages/LoginPage.tsx`

**Problem:** Login form was pre-filled with `admin@example.com` / `admin1234` — the actual default seeded credentials. These were visible in the production bundle's source.

**Fix:**
- Changed `useState('admin@example.com')` → `useState('')`
- Changed `useState('admin1234')` → `useState('')`

**Note:** The default seeded credentials in `bootstrap.py` (Issue #4) still exist. That's flagged for Week 1 of the refactor plan — it requires an env-var approach and falls outside "safe fix without changing core functionality."

---

## Fix 4: Password Complexity Validation (Issue #5 — HIGH)

**File:** `v2/backend/app/schemas/admin.py`

**Problem:** `UserCreateRequest.password` and `UserUpdateRequest.new_password` accepted any string, including empty strings and single characters.

**Fix:**
- Added `_validate_password_strength()` function enforcing: min 8 characters, at least 1 digit, at least 1 letter
- Added `@field_validator('password')` to `UserCreateRequest`
- Added `@field_validator('new_password')` to `UserUpdateRequest` (only validates when non-null and non-empty)
- Returns clear Pydantic validation errors (e.g., "Password must be at least 8 characters")

**Verified:** Smoke test confirms `'short'` is rejected and `'GoodPass1'` is accepted.

---

## Fix 5: Upload File Size Limit (Issue #6 — HIGH)

**File:** `v2/backend/app/api/routes/datasets.py`

**Problem:** `upload_dataset_route()` read the entire upload into memory with no cap. A malicious or accidental 2GB upload could crash the server.

**Fix:**
- Added `_MAX_UPLOAD_BYTES = 50 * 1024 * 1024` (50 MB)
- Upload handler reads file content first, then checks `len(content) > _MAX_UPLOAD_BYTES`
- Returns HTTP 413 with a clear message if exceeded

---

## Fix 6: Idempotent Startup Migrations (Issue #10 — MEDIUM)

**File:** `v2/backend/app/main.py`

**Problem:** Startup `ALTER TABLE` statements used raw SQL with no error handling. On multi-worker deployments (Render with 2+ gunicorn workers), a race condition could cause both workers to try adding the same column, crashing one of them.

**Fix:**
- Wrapped each `ALTER TABLE` block in `try/except Exception` with `logger.debug()` fallback
- If the column already exists (or any other migration error occurs), it's logged at debug level and startup continues
- The existing `existing_cols` check still prevents unnecessary attempts, but the try/except catches race conditions

---

## Fix 7: Email Template Format String Injection (Issue #8 — MEDIUM)

**File:** `v2/backend/app/services/email_service.py`

**Problem:** Email subject and body templates used Python `str.format()`, which allows attribute access via format specifiers (e.g., `{student_name.__class__.__mro__}`). A maliciously crafted template could leak internal Python object state.

**Fix:**
- Replaced `str.format()` with `string.Template.safe_substitute()`
- Template placeholders like `{student_name}` are converted to `${student_name}` format
- `safe_substitute()` leaves unrecognized placeholders as-is instead of raising — no risk of crashing on partial templates
- Added `from string import Template` import

---

## Issues Flagged but NOT Fixed (Risky)

| Issue | Reason Not Fixed |
|-------|-----------------|
| #4 — Default seed passwords | Requires env-var infrastructure + migration strategy. Changing passwords on existing deployments could lock users out. Flagged for Week 1. |
| #7 — Login rate limiting | Requires adding `slowapi` dependency or implementing custom middleware. Should be tested under load. Flagged for Week 1. |
| #9 — SMTP password encryption | Requires Fernet key management, migration of existing plaintext values, and careful rollout. Breaking change if encryption key is lost. Flagged for Week 2. |
