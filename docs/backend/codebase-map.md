# Codebase map

Snapshot: 2026-10-18. Paths below are relative to the repository root. “Implemented” means code exists; external integrations and runtime behavior were not certified by this documentation pass.

## Stack and execution

- Frontend: Next.js 14 App Router, React 18, TypeScript, Tailwind. Pages live in `frontend/app/`; backend requests in `frontend/lib/api.ts`; shared frontend types in `frontend/types/index.ts`.
- Backend: FastAPI, Pydantic 2, SQLAlchemy 2, Alembic; dependencies in `backend/requirements.txt`.
- API wiring: `backend/app/main.py`. Default backend port is 8001; frontend development port is 3000.
- Persistence: SQLite by default, PostgreSQL configurable through `DATABASE_URL`. `docker-compose.yml` provides PostgreSQL/pgvector and a reserved Redis service. A running Redis service does not mean workers exist.
- Configuration: `backend/app/core/config.py`, `.env.example`. Resume files and generated files use configured storage paths.
- Authentication: `backend/app/core/security.py`, `api/dependencies.py`, and `api/routes/auth.py`; JWT and password hashing are implemented.
- Tests: `backend/tests/`; fixtures use isolated SQLite databases. Frontend login E2E exists in `frontend/e2e/login.spec.ts`.

## Existing functionality and limitations

| Area | Source files under `backend/app/` | Current state |
|---|---|---|
| Application tracker | `api/routes/applications.py`, `services.py`, `schemas/application.py` | CRUD, filtering, status history, linked resume versions and analyses |
| Import one job URL | `analysis/jobpage.py`, application `/from-url` route | Fetches and extracts JSON-LD/HTML; URL validation exists; no scheduled multi-source discovery |
| Resume ingestion | `ingestion/docparse.py`, `services.py:ResumeService` | PDF/DOCX extraction, text/LaTeX handling, contact/section parsing and warnings exist |
| Structured candidate profile | `ingestion/resume_parser.py`, `schemas/resume.py` | `BasicResumeParser` still returns a minimal name-based profile; binary parsing is more advanced than profile extraction |
| Career preferences and fit | `api/routes/profile.py`, `api/routes/fit.py`, `analysis/fit.py` | Career profile, demonstrated/claimed/to-learn skills, stored fit evaluations |
| ATS scoring | `analysis/ats.py`, `analysis/ats_v2.py` | Two scoring versions; v2 includes category weights, unknowns, evidence and blockers; token cosine is a heuristic, not a learned semantic model |
| Resume tailoring | `analysis/tailor.py`, `analysis/optimize.py`, `services.py:run_optimization` | Extractive tailoring and bounded optimization with stored attempts, gaps and stage traces |
| Resume exports | `resume/pdf.py`, `resume/latex/`, `api/routes/optimize.py` | PDF export and conditional `pdflatex` compilation exist; some LaTeX AST methods remain stubs |
| Company research | `analysis/company.py`, `ingestion/web_loader.py` | User-supplied website fetch and source-attached extracted statements; no founder/contact discovery pipeline |
| Interview and learning | `api/routes/arena.py`, `api/routes/learn.py`, analysis modules | Existing features to preserve while expanding backend |
| AI adapters | `ai/providers/`, `ai/structured_output.py` | Provider abstractions exist; Grok is a disabled placeholder; do not assume every product workflow uses an LLM |
| Future endpoints | `api/routes/future.py` | Some routes explicitly return 501; similarly named functionality exists through application routes |

## Existing persistence

`backend/app/db/models/__init__.py` contains:

- Identity and core objects: `User`, `Resume`, `Job`, `Application`, `ResumeVersion`.
- Analysis history: `ATSAnalysis`, `Company`, `InterviewPrep`, `OptimizationRun`, `FitEvaluation`.
- Career and learning: `CareerProfile`, `StudyPlan`, `TopicProgress`, `InterviewSession`, `InterviewTurn`.

An application links a job and the resume version used. A master resume can have many derived versions. The existing `Company` table represents research records and is not yet a canonical startup directory.

Application statuses are `saved`, `applied`, `oa`, `interview`, `final_round`, `offer`, `rejected`, and `withdrawn`. Keep submission execution states separate from these business statuses.

## Important gaps to address first

1. **Ownership is not uniformly strict.** `ResumeService.get()` and `JobService.get()` allow rows whose `user_id` is null. Audit legacy ownership and every related-object reference before adding workers. Do not assign legacy rows to an arbitrary user.
2. **Fetch protections differ.** `analysis/jobpage.py` validates URLs, while `ingestion/web_loader.py` follows redirects without equivalent destination validation. Introduce one bounded fetch service covering redirects, DNS/address changes and all research/discovery callers.
3. **Startup schema creation is not migration validation.** `db/database.py:init_db()` uses `create_all`; production changes must run explicit Alembic migrations. Verify the existing revision graph before adding revisions. Never use `stamp head` as a substitute for applying unknown schema changes.
4. **No durable workflow engine.** Long operations currently run through request/service paths; Redis is reserved but workers, run records, leases and retry reconciliation are missing.
5. **No discovery, application-submit or email provider implementation.** Tracker status changes are not proof that a real application was submitted.
6. **Structured evidence is incomplete.** Existing raw text, parsed sections and career profiles need a consistent evidence model before generated claims or form answers can be trusted.
7. **Older docs mix milestones and current behavior.** README planned PDF/DOCX extraction and LaTeX descriptions lag actual code. Older architecture/data-model files describe an earlier subset. Use this snapshot and source inspection when executing the new plan.

## Useful inspection and validation commands

Run from the repository root unless noted:

```bash
backend/.venv/bin/python -m pytest backend/tests -q
backend/.venv/bin/python -m alembic -c backend/alembic.ini heads
backend/.venv/bin/python -m alembic -c backend/alembic.ini history
npm run typecheck --prefix frontend
```

These commands require the local environment/dependencies. For migration tests, use a fresh temporary database and a disposable PostgreSQL database; never the user's working data. See [development setup](../development.md) for environment details.
