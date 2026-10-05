# Architecture — thedaaakhouse

## 1. High-level design (HLD)

```
                    ┌──────────────┐
                    │   Next.js    │  dashboard · job workspace ·
                    │   frontend   │  diff views · evidence panels
                    └──────┬───────┘
                           │ REST/JSON (NEXT_PUBLIC_API_URL)
                    ┌──────▼───────┐
                    │   FastAPI    │  thin routes → services → repositories
                    │   backend    │  deterministic core + LLM-backed adapters
                    └──┬───┬───┬───┘
                       │   │   └──► PostgreSQL + pgvector (profiles, JDs, embeddings)
                       │   └──────► Redis (future job queue — NOT required in M1)
                       └──────────► LLM (Ollama | OpenAI-compatible, via LLMProvider)
```

**AI engineering workspace, not a chatbot.** The UI is dashboards, cards, document
and diff views, progress indicators, evidence panels, source citations.

## 2. Low-level design — backend layers

```
api/routes/      HTTP only: validate input, call service, serialize. No business logic.
services.py      Business logic + orchestration (ResumeService, JobService, …).
db/repositories/ Persistence only (SQLAlchemy sessions).
schemas/         Pydantic contracts — the shared language between layers.
ingestion/       Deterministic bytes/URL → clean text. No AI.
ai/providers/    LLMProvider interface; Ollama + OpenAI-compatible impls.
ai/embeddings/   EmbeddingProvider interface; deterministic stub in M1.
matching/        JD requirements × CandidateProfile → RequirementMatch list.
resume/latex/    Deterministic LaTeX AST + pdflatex in isolated dir (M2).
research/        Company pipeline with source-attached claims (M3).
interview/       Topic mapper → question generator → prep plan (M4).
projects/        Gap analysis → project recommendations (M4).
evaluation/      JD coverage, factuality gate, LaTeX validator.
```

Dependency rule: **routes → services → repositories/schemas**; AI modules are
called by services behind interfaces, never directly by routes.

## 3. Data flow (core loop)

```
JD text/URL ──► clean_text ──► Job row (status=created)
                                        │  (M2) Requirement Extraction (LLM → JobDescription)
Master resume ─► extract ──► Resume row ├──► CandidateProfile (validated, stored as JSON)
(profile JSON)              (parsed)    │
                                        ▼
                              Requirement Matching → RequirementMatch[]
                                        │
                        ┌───────────────┼───────────────┐
                        ▼               ▼               ▼
                 Resume optimizer  Interview prep   Project recommender
                 (ops → LaTeX →    (topics +        (gaps → buildable
                  PDF, gated)      questions)       projects)
```

## 4. AI components (all behind interfaces)

| Concern | Interface | Impls | Notes |
|---|---|---|---|
| Chat/completion | `LLMProvider.complete()` | Ollama, OpenAI-compatible | Selected by `LLM_PROVIDER` env |
| Structured output | `parse_structured()` | JSON repair + Pydantic validate | Rejects non-conforming output |
| Embeddings | `EmbeddingProvider.embed()` | Local-hash stub (M1) | Real model plugs in later, same signature |
| Resume parse | `ResumeParser.parse()` | Basic stub (M1) | LLM parser later; callers unchanged |
| Matching | `match_requirements()` | Exact baseline (M1) | Semantic + evidence matchers layer on top |

## 5. Deterministic components (no LLM allowed)

- Text cleaning/truncation (`ingestion/jd_parser.py`)
- File storage + size limits (`services.py`)
- LaTeX AST edit/render/validate/compile (`resume/latex/`)
- Factuality gate accept/reject (`evaluation/factuality.py`)
- Skill exact-match baseline (`matching/skill_matcher.py`)

## 6. Database

- Postgres via `docker-compose.yml` (`pgvector/pgvector:pg16`), SQLite fallback for
  zero-dependency dev/tests (same SQLAlchemy models).
- Tables M1: `resumes` (file + raw_text + profile JSON), `jobs` (raw + structured
  JSON), `companies` (profile + sources JSON).
- pgvector columns arrive with the semantic matcher (M2); models degrade on SQLite.

## 7. Resume pipeline

```
CandidateProfile + JobRequirements → OptimizationPlan → Validated ResumeOperations
→ LaTeX Editor (AST) → resume.tex → pdflatex → resume.pdf
```

Operations (`rewrite_bullet`, `reorder_project`, …) each carry
`reason + source_evidence + target_requirement`. The LLM proposes operations;
the deterministic editor applies them.

## 8. Company research pipeline

```
Company URL → web ingestion → source extraction → CompanyProfile → source-backed synthesis
```

Every external claim keeps `{source_url, source_title, retrieved_at}`.
Unsupported claims are dropped, never smoothed over.

## 9. Interview pipeline

```
JD + CompanyResearch + CandidateProfile → TopicMapper → QuestionGenerator → PreparationPlan
```

Every question carries `{category, reason, source}` so the user sees *why* it exists.

## 10. Project recommendation pipeline

```
JobRequirements + CandidateProfile → SkillGapAnalysis → ProjectRecommendation(s)
```

Recommendations list `skills_covered` AND `missing_after_project`. Existing
evidence and recommended future work are never mixed.

## 11. Hallucination prevention

1. **Structured profile as source of truth** — raw text is stored, never queried.
2. **Factuality gate** (`evaluation/factuality.py`): every generated claim is
   looked up in candidate evidence; `ACCEPT` iff supported, else `REJECT` and the
   user is told the skill is missing (e.g. Kubernetes example in spec).
3. **Operations carry evidence** — optimizer ops without `source_evidence` are invalid.
4. **No fake data rule** — unbuilt routes return 501, UI shows empty states, the
   local-hash embedding is labeled non-semantic. Nothing pretends to be real.
5. **Source-attached company claims** — no URL + timestamp, no claim.

## 12. Evaluation strategy

- `jd_coverage` (M2): % of JD requirements addressed by tailored resume (recall-style).
- `factuality` (M1 interface + unit tests): gate precision on supported vs invented claims.
- `latex_validator` (M2): compiles clean / diff applies / no unescaped chars.
- API contract tests (M1, `backend/tests/`): health, upload, JD CRUD, 501 stubs.
