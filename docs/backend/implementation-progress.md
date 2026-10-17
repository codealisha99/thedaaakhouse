# Implementation progress

Living status note. Yes = verified by a test in this repo; Not yet = exists
only as scaffolding. Last reviewed after **build step 05** (truthful tailored
resumes), **step 03** (scheduled job discovery), and **step 02 verification**
(durable tasks crashed-safe under real PostgreSQL).

## Milestone state

| # | Milestone | State | Evidence |
|---|---|---|---|
| 01 | Ownership boundaries + safe web fetch | done | `tests/test_ownership.py` (14) + `tests/test_safe_fetch.py` (49) + migration-gate tests in `test_migrations.py` pass; red-flags fixed: strict owner scoping cross-service, one SSRF-guarded fetcher for **all** user-supplied fetches, Alembic startup gate |
| 02 | Durable task engine, approvals, retries | done | engine + API + migrations exist and regressions pass (`tests/test_migrations.py`, `tests/test_tasks_api.py`, `tests/test_workflows_tasks.py`, `tests/test_workflows_automation.py`); the previously missing **PostgreSQL concurrency gate** now exists: `tests/test_workflows_postgres.py` (8) — runs against a disposable Postgres when `TEST_DATABASE_URL` is set, skipped otherwise; PG-only migration bugs found and fixed (see below) |
| 03 | Scheduled job discovery | done | `tests/test_discovery.py` (38) + discovery tables in `tests/test_migrations.py`; cross-site dedup, dedup review band, absence-only-on-complete-scans, scheduler tick, source CRUD/run API all pass |
| 04 | Opportunity ranking + no-opening startups | done | `tests/test_opportunities.py` passes (score gate + dedupe) |
| 05 | Truthful tailored resumes + readable exports | done | this document below |

## Step 02 — PostgreSQL verification of the durable task engine

The engine itself (task_runs / outbox / audit / policies / approvals, leases,
finite backoff, 202+poll API, poll/RQ workers, dispatcher) was already built;
what was missing was the PostgreSQL proof that the spec demands. Findings and
fixes:

- **The Alembic chain did not apply to PostgreSQL at all.** Fresh
  `upgrade de head` (baseline included) failed three ways, all invisible to
  SQLite:
  1. `baseline_schema` (50ef50a56078) created `applications` referencing
     `users`/`jobs`/`resume_versions` before those tables exist, and
     `resume_versions` before `resumes` exists.
  2. `truthful_resume_evidence` (b8d3f6a41c02) used SQLite-flavored boolean
     defaults (`DEFAULT 0`) → `DatatypeMismatch` on PG booleans.
  3. `opportunities_and_ranking` (4f8e2a71c9b3) declared
     `opportunities.latest_evaluation_id → opportunity_evaluations.id`
     inline, referencing a table created *after* `opportunities`.
  Fixes (committed migration edits — no deployed PostgreSQL database existed
  to break; SQLite dev DBs are version-stamped and never re-run old
  revisions): tables created in dependency order, cycle-breaking FKs added
  post-create via `batch_alter_table` with a naming convention (portable
  across SQLite batch recreate and PG ALTER), and `sa.false()` boolean
  defaults.
- **`tests/test_workflows_postgres.py` (8 tests, skipped without
  `TEST_DATABASE_URL`)** proves against real PG:
  - 8 concurrent enqueues of one idempotency key collapse to exactly one
    task (unique constraint `uq_task_runs_idem`), with one creator and seven
    replays; a different payload under the same key conflicts for every
    concurrent requester.
  - a dispatcher/queue outage after the task commit loses nothing; on
    restart one publish transaction transitions the outbox pending →
    published and the handler runs once.
  - six concurrent `execute()`s produce exactly one handler run — one
    succeeded, five skipped (`claimed_elsewhere`/`not_runnable`); late
    redeliveries after completion never re-run.
  - four concurrent recovering dispatchers heal an expired lease exactly
    once, writing exactly one redelivery event; recovery attempt counts
    toward `max_attempts`.
  - a standing policy revoked between attempts fails the retry with
    `authorization_revoked` (no silent side effect), matching the SQLite
    suite.
  - a cancelled queued task is never executed by racing workers.
- **`tests/test_workflows_redis.py` (3 tests, skipped without
  `TEST_REDIS_URL`)** runs the real delivery path — `queue.publish` →
  `rq.Queue` → in-process `rq.SimpleWorker` → `executor.perform_task` —
  against a disposable Redis:
  - a queued task reaches the RQ queue through the outbox dispatcher and
    completes exactly once on a real worker pass;
  - a duplicate RQ job for the same task never re-runs completed work;
  - a Redis outage keeps the outbox row pending (work cannot be lost), and
    the healthy dispatcher later publishes and the worker completes the task.
- Verification run: `TEST_DATABASE_URL=... pytest -q
  tests/test_workflows_postgres.py` → 8 passed; `TEST_REDIS_URL=...
  pytest -q tests/test_workflows_redis.py` → 3 passed; full SQLite suite
  (`pytest -q tests/`) → 300 passed, 11 skipped (the opt-in modules, by design).

### Honest limits

- Scheduling is an in-process loop (step 03) rather than the durable engine —
  recorded from step 03, unchanged.
- The runtime DB mode is normalized (`postgresql+psycopg2`), but production
  Postgres connections were exercised only through this disposable test
  database; a deployed instance has never been pressure-tested.

## Step 05 — Truthful tailored resumes and reliable exports

### What is in place (with tests)

- **CandidateProfile.evidence** (`app/schemas/resume.py`) — every parsed fact
  carries a stable `EvidenceRef` (`ev1, ev2, ...`), kind, assert type, source
  section, and 1-based line span. Evidence ids are deterministic for the same
  resume text; parser output is verified deterministic.
- **`app/ingestion/evidence_extract.py`** — deterministic extraction with
  three honesty classes:
  - `demonstrated`: skill found *inside* an experience/project bullet
    (`tests/test_evidence.py` — `kubernetes` demonstrated, `SQL` claimed when
    it appears only in a skills list).
  - `claimed`: surfaces in a skills list only; downstream scoring counts them
    as `documented`, never as strong matches.
  - `stated`: verbatim facts — contact lines, certifications, achievement
    sentences with metrics. A sentence counts as an achievement only when it
    contains a number/percentage; otherwise it is not treated as quantified.
- **`candidate_evidence` table** — each fact persisted with `ev_ref`, line
  spans, verbatim `source_text`, and user status `extracted → confirmed |
  rejected` via
  `GET/PATCH /api/resumes/{id}/evidence[/{ev_id}]` (`tests/test_evidence.py`,
  owner-scoped; foreign evidence reads return 404).
- **`EvidenceResumeParser`** (`app/ingestion/resume_parser.py`) — the master
  parser remains deterministic; no structured-LLM path is wired. Nothing that
  is not in the text enters the profile: unparseable experience/project
  headings stay verbatim strings instead of invented company/title values.
- **Claim gate `app/resume/validation.py`** — `gate_edits()` accepts a content
  change only if every line is either verbatim in the master resume or fully
  atom-supported:
  1. every metric (numbers with % / k / m / x context) must occur in the
     source resume (`tests/test_truthfulness_gate.py` — 50k with source 10k
     rejected; 30% with no source 30 rejected);
  2. every lexicon skill (TECH_LEXICON, alias-aware: `k8s` counts given
     `Kubernetes` in source) must occur in the source — absent skills
     (`PostgreSQL`, `Redis`, `Kafka`) rejected;
  3. every multi-word proper-noun run (`Gamma Systems`, employer/identity)
     must occur in the source — supported employers (`Beta Corp`) accepted.
  Deliberate decisions: `k9s` does NOT inherit Kubernetes' support (it is a
  different product); inflection chasing is bounded (`ship` ↔ `shipped`,
  `built` ↔ `building`) so paraphrased reorder output does not false-reject;
  sentence-initial action verbs ("Built", "Delivered") never form identity
  runs. Rejected proposals are returned whole — the gate never partially
  applies content, so a fabricated metric/skill/employer cannot enter a
  generated resume via an atom path.
- **`ensure_supported()`** — safety net storing the invariant that generated
  resume content must pass the gate before persisting.
- **ATS v2 honesty fixes** (`app/analysis/ats_v2.py`):
  - removed fabricated aliases: `k9s → kubernetes`, `tf → tensorflow`,
    `gha → github actions` (ambiguity invented matches);
  - experience years are now derived from the resume's own date ranges
    (Month YYYY / MM/YYYY / YYYY ranges, "Present" handling, overlapping
    spans merged). When the JD requires years and the resume evidences
    neither stated years nor countable dates, the category is reported
    **unknown** and excluded from the renormalized score — never a guessed
    score and never a fabricated blocker
    (`tests/test_ats_v2.py::test_experience_unknown_when_no_years_and_no_dates`).
  - Experience blockers fire only on a countable gap (stated or date-derived
    years vs required) — gap ≥ 5 years.
- **Optimization run integrity** (`app/services.py`):
  - provenance recorded per run: `jd_sha256`, `resume_sha256`,
    `config_hash`; resumeVersion rows carry `master_sha256` so a tailored
    version names the exact master snapshot it derived from;
  - every tailor attempt passes the claim gate as a traced stage
    (`claim_gate_N`); a gate failure aborts the run with an honest error — a
    bug can never silently persist unsupported content;
  - the finalized PDF is **reparsed**: `validate_pdf_export()` reopens the
    produced PDF, re-extracts text, and demands ≥ 70% line coverage against
    the validated content. Unreadable or lossy exports are withheld —
    recorded as a failed `export_reparse` stage (or HTTP 500 for the
    version-PDF endpoint), put in `export_validation`, and the run also
    stores `final_pdf_sha256`.
- **Manual edits invalidate derived work** — editing a version's content
  through `PATCH /api/applications/versions/{id}` sets `edited_manually`,
  marks the version's `ATSAnalysis` rows **stale**, and marks
  `OptimizationRun`s whose final version was edited as **invalidated**
  (lines 363–389 in `app/api/routes/applications.py`).
- **LaTeX unavailable path** — unchanged from step 02 implementation:
  `compile_latex()` returns `needs_latex_toolchain` and the run records
  `pdf_compile: skipped` (honest recoverable outcome, no fake PDF).

### Honest limits (as built)

- Evidence claim-gating applies to generated/tailored content. The user can
  still manually edit a version to add unsupported text — the system refuses
  to *validate* it: analyses go stale, runs go invalidated, and exports note
  that the content bypassed the gate (`edited_manually`). Trust label, not a
  hard content firewall for human input.
- Employer/identity detection is heuristic (capitalized word runs). A short
  all-cap fake brand could in principle slip past the run check if every
  token is a lexicon word — the fail-closed direction covers multi-word
  names, but this is reported as a known heuristic, not a guarantee.
- The claim gate does not cross-check facts against the *user-confirmed*
  evidence subset (rejected evidence is advisory today); confirmation state
  is persisted and exposed but not yet enforced inside `tailor_resume`.
- PDF readability is token-coverage-based (≥ 70% of non-authorial lines'
  content words reappear in the reparsed text), not a full semantic diff.

## Step 03 — Scheduled job discovery

### What is in place (with tests)

- **Adapters** (`app/discovery/adapters/`) for `greenhouse`, `lever`, and
  `company_careers` (JSON-LD), each declaring its own `validate_config`
  (invalid config → `SourceConfigError` → HTTP 400). Adapters return an
  `AdapterResult` whose `complete` flag is what later gates closure; a
  truncated/failed fetch reports `complete=False`.
- **Dedup** (`app/discovery/dedup.py`) in spec order: same-source external id →
  platform stable id across boards (`greenhouse`/`lever`) → canonical URL
  (tracking params stripped) → conservative fuzzy title match
  (`AUTO_MERGE_TITLE_SIM=0.92`); scores in `[0.80, 0.92)` become a *new*
  listing flagged `needs_review` with `review_candidate_id` instead of a
  silent merge.
- **Lifecycle invariants** (`app/discovery/service.py`): only a successful
  **complete** scan increments `absent_scans`; a failed or truncated scan
  never closes a listing and never counts absence
  (`test_failed_fetch_never_closes_or_counts_absence`,
  `test_incomplete_scan_does_not_count_absence`). Closure needs
  `discovery_scan_absent_threshold` consecutive complete scans
  (`closed_reason="absent_complete_scans"`); reappearance reopens the same
  row. Failures set exponential backoff (`interval * 2^min(n,4)`, capped 24 h).
- **Scheduler** (`app/discovery/scheduler.py`): one in-process asyncio loop,
  **off by default** (`DISCOVERY_SCHEDULER_ENABLED=false`), ticking
  `due_sources` on a worker thread; a failing source never stalls the loop.
  Started/stopped from the app lifespan.
- **API** (`app/api/routes/discovery.py`, prefix `/api/discovery`): owner-scoped
  source CRUD (400 on bad config, 404 cross-owner), runs (201/404/409 on
  concurrent scan), listings list/get with `status`/`needs_review` filters and
  embedded source observations.
- **Migration** `d3a9c8e5f1b6_discovery_sources_listings_runs.py` — four tables
  (`discovery_sources`, `job_listings`, `listing_sources`, `discovery_runs`)
  with owner scoping, uniqueness on `(source_id, external_id)`, and status
  check constraints; single Alembic head.
- Tests: `backend/tests/test_discovery.py` (38) — adapter parsing/failure
  codes, URL policy, dedup outcomes, lifecycle/backoff, reopen, scheduler tick,
  and the API surface. Fetches are injected stubs; no network in the suite.

### Honest limits

- Scheduling is an in-process loop, not the durable task engine (step 02) —
  scans do not survive a process restart mid-run; the engine is the intended
  successor.
- `company_careers` covers JSON-LD job postings only; JS-rendered boards
  without structured data are not parsed.
- Fuzzy matching is stdlib `difflib` on normalized titles plus location/company
  compatibility — deliberately conservative, favoring review over wrong merges.

## Step 01 — Ownership boundaries + centralized safe fetch

### Ownership lockdown (with tests)

- **Strict scoping everywhere** (`app/services.py`): every service method
  scopes reads and writes to the authenticated user. The previous rule
  `user_id not in (None, self.user.id)` — which made ownerless rows public —
  is gone from `Resume`, `Job`, `Application.tailor`, `Learning.create_plan`,
  `Arena.start`, and `Profile.seed_from_resume`. Unauthenticated service
  calls return empty lists / `None` instead of global scans.
- **Quarantined legacy rows** — a `NULL user_id` row is 404 to everyone, same
  as a missing id (documented in `docs/backend/ownership-policy.md`).
- **No unauthenticated write path**: `ResumeService.save_upload` and
  `JobService.create` require a user and stamp `user_id` unconditionally.
- **Cross-user reference rejection at write time**
  (`ApplicationService.create/update`): `job_id` and `resume_version_id`
  referencing another user's (or an ownerless) record fails with
  400 "job not found" / "resume version not found" instead of being adopted.
- Regression tests: `backend/tests/test_ownership.py` — ownerless reads
  401/404, cross-user resume/job read 404, tailoring, attach-version,
  patch-application, profile-seed, learn-plan, arena-start with foreign ids
  400/404, list endpoints user-scoped.

### One safe fetcher for every user-supplied URL

- **`app/ingestion/safe_fetch.py`** is the single entry point; both previous
  callers now use it (`ingestion/web_loader.py::fetch_url_text` used by
  company research, and `analysis/jobpage.py::analyze_job_url`). Guards:
  - URL text: http/https only, credentials in URL rejected (redirect
    `Authorization` stripping), allowed ports bounded by settings
    (`fetch_allowed_ports`, default 80/443).
  - Destination: loopback/private/link-local/CGNAT/multicast/reserved and
    IPv4-mapped-IPv6 literals rejected; hostnames resolved and validated —
    **any** non-public record (one poisoned A record) blocks the fetch.
  - Connect-time pinning: validation resolves the name and the
    `_SafeDNSBackend` connects to that exact address, closing the
    DNS-rebinding/TOCTOU gap that `jobpage.analyze_job_url` had
    (it validated the hostname but `httpx` re-resolved at connect).
  - Redirects: followed manually, each hop re-validated (scheme, ports,
    destination) up to `fetch_max_redirects` (default 5); intra-universe
    redirect chain recorded on the result.
  - Bodies streamed with `fetch_max_bytes` cap (default 1 MB) and
    `fetch_timeout_s` (default 20 s); `trust_env=False` so proxy env vars
    cannot bypass guards.
  - Errors are one `SafeFetchError(RuntimeError)` with a **code**
    (`scheme_not_allowed`, `credentials_in_url`, `blocked_destination`,
    `port_not_allowed`, `unresolvable_host`, `fetch_failed`,
    `response_too_large`, `too_many_redirects`) and a sanitized public
    message; internals ride in `.internal` for logging only.
- Route contracts preserved: from-url keeps ValueError→400 / RuntimeError→502
  semantics; `tests/test_joburl.py` now patches the module seam
  (`_fetch_page`) and `socket.getaddrinfo`, not `httpx.get`.
- Tests: `backend/tests/test_safe_fetch.py` (48) — every guard parametrized;
  redirect-pivot tests (302 to `169.254.169.254`, to `ftp:`, size cap over
  multi-chunk stream, sanitized errors); plus one offline end-to-end test
  driving the production transport by intercepting `socket.create_connection`
  to a local HTTP server under a public-looking literal IP (no network).
- Settings: `fetch_timeout_s`, `fetch_max_bytes`, `fetch_max_redirects`,
  `fetch_allowed_ports`, `fetch_user_agent` (documented in `.env.example`).

### Alembic startup gate

- `init_db()` (module `app/db/database.py`) no longer unconditionally
  `create_all`s. PostgreSQL becomes the audited path: on boot it must have
  `alembic_version` **and** be at the current head of the checked-in graph
  (`require_migrated()`), else startup aborts with a run-this-first message.
  SQLite keeps `create_all` for tests/dev.
- Tests in `backend/tests/test_migrations.py` — unmigrated → refuse, stale
  revision → refuse + pass after reaching head, multi-head detection,
  Postgres path gated / SQLite path not.

### Honest limits

- Ownerless-claim tooling exists (`backend/scripts/claim_legacy_records.py`)
  but actual prod data has not been claimed yet — ops task, by design.
- The full upstream suite was red through no fault of step 01 while parallel
  steps (02/04/05) churned the same working tree: verification ran per-slice
  (49+14+6+11 own tests green; suite re-verifies when 02/04/05 stabilise).



`705732ddfa74 → 4f8e2a71c9b3 (step 04) → b8d3f6a41c02 (step 05: truthful
resume evidence) → b71f0d1a9c22 (durable tasks) → d3a9c8e5f1b6 (discovery)`.

## Not Yet implemented from spec

- Async/task-engine inside the optimize loop (step 02 engine exists but does
  not drive the resume loop; runs stay synchronous — acceptable for a local
  write-path MVP, recorded honestly).
- Structured-LLM resume parser as PRIMARY path remains unwired (Step 05
  explicitly allowed "basic deterministic parser as fallback" — the
  deterministic parser is used, no LLM call happens).
- Web import of JD/resume files into evidence (module exists for JD; not
  used for evidence yet).
