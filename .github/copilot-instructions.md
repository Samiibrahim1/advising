# Workspace Instructions for GitHub Copilot

## Documentation Sync Rule — ALWAYS ENFORCED

Two living documentation files exist in `v2/` and **must be kept in sync with the V2 codebase**:

- `v2/LAY_TERMS_GUIDE.md` — Plain-language description of the app (for non-engineers)
- `v2/TECHNICAL_GUIDE.md` — Full engineering reference (architecture, APIs, models, services)

### When to update them

After **any** change to files inside `v2/` that affects:

| Change Type | Update Target |
|---|---|
| New API route or endpoint | TECHNICAL_GUIDE.md (§8 API Endpoint Reference) |
| New or changed service function | TECHNICAL_GUIDE.md (§4.7 Service Layer) |
| New ORM model or changed schema | TECHNICAL_GUIDE.md (§4.4 ORM Models, §6 Data Models) |
| New environment variable | TECHNICAL_GUIDE.md (§9 Environment Variables) |
| New page or component in frontend | TECHNICAL_GUIDE.md (§5), LAY_TERMS_GUIDE.md (relevant feature section) |
| New feature visible to users | LAY_TERMS_GUIDE.md (relevant section) |
| New major/program added | Both files |
| Parity gap closed or new gap found | TECHNICAL_GUIDE.md (§12 Parity Status) |
| Changed default values or credentials | Both files |
| Changed startup/bootstrap behavior | TECHNICAL_GUIDE.md (§4.1) |
| New dependencies added | TECHNICAL_GUIDE.md (§3 Technology Stack) |

### How to update

- Edit only the affected sections — do not rewrite sections that weren't touched by the change.
- Keep the lay-terms file jargon-free. Explain concepts as if the reader has never seen code.
- Keep the technical file precise: include function signatures, table names, route paths, and env var names as they actually appear in the code.
- After completing a code change, update the relevant documentation sections in the same response. Do not defer or skip this.

## Project Overview (Quick Context)

This is a **university academic advising tool**:
- **Backend**: FastAPI + SQLAlchemy, in `v2/backend/`
- **Frontend**: React + TypeScript + Vite + React Query, in `v2/frontend/`
- **Eligibility engine**: Shared legacy Python module at the workspace root (`eligibility_utils.py`, `reporting.py`) — imported by the V2 backend via `sys.path` manipulation
- **Two user roles**: `admin` (setup/configuration) and `adviser` (student advising)
- **Per-major isolation**: PBHL, SPTH-New, SPTH-Old, NURS

## Code Style Conventions

- Backend: Python with `from __future__ import annotations`, SQLAlchemy 2.0 mapped columns, Pydantic v2 schemas
- Frontend: TypeScript strict mode, React Query for all server state, no Redux
- All mutations go through service functions — route handlers must not contain raw DB queries
- Always use `ensure_major_access()` in routes that take a `major_code` parameter
