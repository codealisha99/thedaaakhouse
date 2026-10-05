# Deployment

> Status: foundation only — no live production environment exists yet.
> PostgreSQL config is dialect-tested but NOT live-tested; treat as draft.

## Backend (FastAPI)

Local:

```bash
uvicorn app.main:app --reload --port 8001   # run from backend/
```

Container (after `docker build -f backend/Dockerfile -t thedaaakhouse-api .`):

```bash
docker run -e JWT_SECRET='<long-random>' \
  -e DATABASE_URL='postgresql+psycopg2://user:pass@db:5432/thedaaakhouse' \
  -p 8001:8001 thedaaakhouse-api
```

The entrypoint runs `alembic upgrade head` before serving, and with
`ENVIRONMENT=production` the process refuses to start on the dev JWT secret.

Required env: `JWT_SECRET`, `DATABASE_URL` (or accept SQLite `DATA_DIR` volume),
`CORS_ORIGINS` (must list the real frontend origin), `ENVIRONMENT=production`.

## Frontend (Next.js)

```bash
npm run build --prefix frontend
NEXT_PUBLIC_API_URL=https://api.example.com npm run start --prefix frontend
```

`NEXT_PUBLIC_API_URL` is baked at build time — set it for the deployment target.

## Database

- Dev: SQLite at `backend/data/thedaaakhouse.db` (deterministic, cwd-independent).
- Docker Compose: `docker compose up -d db` gives Postgres+pgvector on :5432.
- Migrations: `backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head`
  (existing DBs: `... alembic stamp head` once to adopt the baseline).

## Health checks

- Liveness: `GET /health` (always 200 when the process answers).
- Readiness: `GET /ready` (200 + `{"ready": true}` only if the DB answers).
