# Development

## Prerequisites

- Python 3.11+ (3.9 works for M1; 3.11 recommended)
- Node 20+
- Docker (only needed for PostgreSQL; M1 runs fine on SQLite)

## 1. Start PostgreSQL (optional in M1)

```bash
cp .env.example .env        # then set DATABASE_URL for postgres:
# DATABASE_URL=postgresql+psycopg2://thedaaakhouse:thedaaakhouse@localhost:5432/thedaaakhouse
docker compose up -d db
```

Skip this and the backend uses `sqlite:///./data/thedaaakhouse.db` automatically.

## 2. Backend

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --port 8000   # run from backend/
```

Health check: `curl localhost:8000/health`

## 3. Frontend

```bash
npm install --prefix frontend
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > frontend/.env.local
npm run dev --prefix frontend               # http://localhost:3000
```

## 4. Tests

```bash
source backend/.venv/bin/activate
pytest backend/tests -v                     # isolated tmp SQLite DB per test
```

## 5. Environment variables

See `.env.example`. Key ones:

| Var | Meaning | Default |
|---|---|---|
| DATABASE_URL | SQLAlchemy URL (postgres or sqlite) | sqlite file in `data/` |
| LLM_PROVIDER | `ollama` \| `openai_compatible` | `ollama` |
| OLLAMA_BASE_URL / OLLAMA_MODEL | local LLM | `localhost:11434 / llama3.1:8b` |
| OPENAI_COMPATIBLE_* | API endpoint/key/model | — |
| NEXT_PUBLIC_API_URL | backend URL for frontend | `http://localhost:8000` |
| MAX_UPLOAD_MB | upload cap | `10` |

## 6. Project layout cheat-sheet

- `backend/app/main.py` — wiring only
- `backend/app/api/routes/` — HTTP adapters
- `backend/app/services.py` — business logic (this is where you add features)
- `backend/app/schemas/` — Pydantic contracts
- `backend/tests/` — contract + unit tests
- `frontend/app/` — dashboard (`page.tsx`) + job workspace (`jobs/[id]/page.tsx`)
