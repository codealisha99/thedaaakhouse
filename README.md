# thedaaakhouse

**Your job-search operating system — one place to track applications, tailor resumes, check ATS compatibility, prepare for interviews, and research companies.**

Evidence-driven: tailored resumes are extractive (reordered, never rewritten), ATS scores show their methodology, and anything missing from your profile is reported — never invented.

## Architecture

```
 ┌────────────┐  REST + JWT  ┌────────────┐      ┌─────────────────────┐
 │  Next.js   ├─────────────►│  FastAPI   ├─────►│ SQLite (dev) or     │
 │  sidebar   │              │  services  │      │ Postgres + pgvector │
 │  workspace │              │  analyzers │      │ users · apps ·      │
 └────────────┘              └────────────┘      │ resumes · versions  │
                                                 └─────────────────────┘
```

Details: `docs/architecture.md` · Data model: `docs/data-model.md` · Setup: `docs/development.md`

## Sidebar

```
thedaaakhouse
Applications — Overview · Job Analyzer · Company Research · Interview Prep
Job Tracker  — spreadsheet-style application table
Resume       — My Resumes · Tailor Resume · ATS Checker
```

One application connects its JD, resume version, ATS runs, interview plans, and research.

## Status (v0.2)

### Implemented ✅

- JWT auth (register/login, PBKDF2 + HS256, stdlib-only) — all data user-scoped
- Job Tracker: create/edit/delete/search/filter/sort, status history timeline, persisted
- Job Analyzer: JD → skills, keywords, responsibilities, experience requirements
- Resume upload + versioning (masters never overwritten; versions auto-attach)
- ATS Checker: real computed score (50% keywords · 25% skills · 15% experience · 10% formatting) with methodology shown
- Tailor: extractive bullet reordering with evidence-carrying change ops
- Interview prep: questions derived from the JD, each with category/reason/source
- Company research: real page fetch + extraction with sources (no fabricated profiles)
- Loading / empty / error states everywhere; no mock data in production flows

### Planned 📋

- LLM-backed resume parsing → full `CandidateProfile` (Ollama reachable; stub extracts name only)
- PDF/DOCX text extraction (currently UTF-8 best-effort), LaTeX + `pdflatex` pipeline
- Alembic migrations (currently `create_all`; v0.2 required a one-time fresh DB)
- Redis background jobs (`{job_id, status, progress, result, error}` polling)

## Quickstart

```bash
# Backend (:8001) — run from backend/
source backend/.venv/bin/activate 2>/dev/null || /opt/homebrew/bin/python3.12 -m venv backend/.venv
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --port 8001

# Frontend (:3000)
npm install --prefix frontend
echo "NEXT_PUBLIC_API_URL=http://127.0.0.1:8001" > frontend/.env.local
npm run dev --prefix frontend

# Tests
backend/.venv/bin/python -m pytest backend/tests -v
```

Then open the frontend, create an account, and add your first application.
If the UI says "backend unreachable", confirm the API is up: `curl 127.0.0.1:8001/health`
(note: `CORS_ORIGINS` must include the port you serve the frontend from).
