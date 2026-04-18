# Advising V2

Modern parity rebuild of the advising dashboard.

## Workspaces
- `backend`: FastAPI API, SQLAlchemy models, Neon/R2 integrations, legacy parity services.
- `frontend`: React + TypeScript adviser/admin interface.

## Roles
- `Admin`: datasets, periods, templates, imports, backups, user access.
- `Adviser`: dashboard, advising workspace, insights, reports, email.

## Local development

### Backend
```bash
cd v2/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd v2/frontend
npm install
npm run dev
```

## Environment
Copy `.env.example` from `v2/backend` and `v2/frontend` and fill in secrets for Neon, R2, and auth.
