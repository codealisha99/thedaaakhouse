# Development

## Prerequisites

- Python 3.12 (see `backend/.venv`)
- Node 20+
- Docker Desktop (only for PostgreSQL; dev runs on SQLite)

Port contract: Sherlock owns `:8000`. thedaaakhouse backend → `127.0.0.1:8001`.

## 1. PostgreSQL (optional)

```bash
cp .env.example .env        # then set DATABASE_URL for postgres:
# DATABASE_URL=postgresql+psycopg2://thedaaakhouse:thedaaakhouse@localhost:5432/thedaaakhouse
docker compose up -d db
```

Skip this and the backend uses SQLite at `backend/data/thedaaakhouse.db`
(deterministic regardless of working directory).

## 2. Backend

```bash
/opt/homebrew/bin/python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --port 8001   # run from backend/
```

Health: `curl 127.0.0.1:8001/health` · Readiness: `curl 127.0.0.1:8001/ready`

## 3. Frontend

```bash
npm install --prefix frontend
cp frontend/.env.example frontend/.env.local   # NEXT_PUBLIC_API_URL=http://127.0.0.1:8001
npm run dev --prefix frontend                  # http://localhost:3000
```

## 4. Tests

```bash
backend/.venv/bin/python -m pytest backend/tests -v   # isolated tmp SQLite DB per test
npm run lint --prefix frontend
npm run typecheck --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend   # Playwright login E2E (spins its own servers)
```

## 5. Migrations (Alembic)

```bash
# apply (fresh or existing DB — never destroys data):
backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
# adopt an existing pre-Alembic database at the baseline:
backend/.venv/bin/python -m alembic -c backend/alembic.ini stamp head
# after changing models, generate the next revision:
DATABASE_URL=sqlite:////tmp/blank.db backend/.venv/bin/python -m alembic \
  -c backend/alembic.ini revision --autogenerate -m "describe change"
```

`DATABASE_URL`/`DATA_DIR` env vars select the target. CI validates every
migration against a fresh database.

## 6. Environment variables

See `.env.example`. Key ones:

| Var | Meaning | Default |
|---|---|---|
| DATABASE_URL | SQLAlchemy URL (postgres or sqlite) | SQLite in `backend/data/` |
| DATA_DIR | uploads + SQLite home (absolute, cwd-independent) | `backend/data` |
| ENVIRONMENT | `development` \| `production` | `development` |
| JWT_SECRET | HS256 secret (**required** in production) | dev default (refused in prod) |
| JWT_EXPIRY_MIN | token lifetime | `10080` |
| CORS_ORIGINS | allowed browser origins | `http://localhost:3000,http://localhost:3100` |
| BACKEND_HOST/PORT | bind | `127.0.0.1` / `8001` |
| NEXT_PUBLIC_API_URL | backend URL for frontend | `http://127.0.0.1:8001` |
| MAX_UPLOAD_MB | upload cap | `10` |

Generate a secret: `python3 -c "import secrets; print(secrets.token_hex(32))"`

## 7. Project layout cheat-sheet

- `backend/app/main.py` — wiring, CORS, security headers, 500 handler
- `backend/app/api/routes/` — HTTP adapters (auth, applications, resumes, jobs)
- `backend/app/services.py` — business logic
- `backend/app/analysis/` — deterministic JD/ATS/tailor/interview/company engines
- `backend/app/core/security.py` — PBKDF2 + HS256 (stdlib)
- `backend/alembic/` — migrations
- `backend/tests/` — pytest suite
- `frontend/app/` — sidebar layout, tracker, applications, resume, login
- `frontend/e2e/` — Playwright login coverage
