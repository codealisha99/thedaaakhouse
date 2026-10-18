# Implementation progress

Living status note. Yes = verified by a test in this repo; Not yet = exists
only as scaffolding. Last reviewed after **steps 09–10 implementation**. Step
09 has deterministic Gmail adapter fixtures but no live provider verification.
Step 10 remains partial: this branch adds an operations runbook and a minimal
Gmail integration panel, while step 06, release-grade E2E, and production
operations are not complete.

## Milestone state

| # | Milestone | State | Evidence |
|---|---|---|---|
| 01 | Ownership boundaries + safe web fetch | done | `tests/test_ownership.py` (14) + `tests/test_safe_fetch.py` (49) + migration-gate tests in `test_migrations.py` pass; red-flags fixed: strict owner scoping cross-service, one SSRF-guarded fetcher for **all** user-supplied fetches, Alembic startup gate |
| 02 | Durable task engine, approvals, retries | done | engine + API + migrations exist and regressions pass (`tests/test_migrations.py`, `tests/test_tasks_api.py`, `tests/test_workflows_tasks.py`, `tests/test_workflows_automation.py`); the previously missing **PostgreSQL concurrency gate** now exists: `tests/test_workflows_postgres.py` (8) — runs against a disposable Postgres when `TEST_DATABASE_URL` is set, skipped otherwise; PG-only migration bugs found and fixed (see below) |
| 03 | Scheduled job discovery | done | `tests/test_discovery.py` (38) + discovery tables in `tests/test_migrations.py`; cross-site dedup, dedup review band, absence-only-on-complete-scans, scheduler tick, source CRUD/run API all pass |
| 04 | Opportunity ranking + no-opening startups | done | `tests/test_opportunities.py` passes (score gate + dedupe) |
| 05 | Truthful tailored resumes + readable exports | done | this document below |
| 07 | Application packages and supported submission | done (live integration limited to controlled test destination) | `tests/test_submissions.py` (7) + `tests/test_migrations.py`; frozen packages, manual handoff, capability discovery, approval-bound durable task, receipt reconciliation, Alembic migration |
| 08 | Personalized cold-email drafts | done (offline drafts only; delivery is step 09) | `tests/test_outreach.py` (6); vacancy and startup templates, confirmed evidence, immutable attachment, revisions and approval invalidation |
| 09 | Email delivery, replies and follow-ups | partial (Gmail send/reply polling fixture-complete; follow-ups disabled; live blocked) | `tests/test_gmail_delivery.py` plus outreach/migration tests; encrypted OAuth refresh-token storage, approval-bound durable sends, immutable ledger, suppression, accepted/unknown states and manual reply sync; live Google OAuth/mailbox not configured |
| 10 | End-to-end integration and release readiness | partial | `docs/backend/operations.md`, Gmail API/UI contracts and operational limitation audit; step 06 remains unimplemented, no verified restore/metrics/retention job, live PostgreSQL/Redis and full UI journey remain unverified |

## Step 09 — Gmail send and reply tracking

- Added an opt-in Gmail OAuth authorization-code flow with state values stored
  as hashes for ten minutes and single use. Refresh tokens are encrypted at
  rest with a configured Fernet key and removed/revoked on disconnect.
- Added `outreach.send` durable tasks bound to the draft's current payload
  hash. The worker checks account state, provider kill switch, suppression,
  UTC quiet hours and a database-backed daily cap, then snapshots the exact
  recipient, copy and optional attachment. Existing task approval/policy
  checks run before the provider call.
- Gmail's `messages.send` response is recorded as `accepted`, not delivered.
  A network ambiguity becomes `unknown`; redelivery searches the stable
  RFC822 Message-ID and never repeats the send. Gmail polling uses thread
  retrieval and idempotent provider message event keys; replies and recognized
  bounce/opt-out content suppress future sends. Reply polling is user-triggered.
- Configured Gmail OAuth consent, the Google API and an owned mailbox are
  absent. Live verification is blocked. Automatic follow-up sends and Gmail
  Pub/Sub notifications are intentionally not enabled; the UI discloses manual
  sync and provider-acceptance semantics.
- New checks: `cd backend && PYTHONPATH=. .venv/bin/pytest -q
  tests/test_gmail_delivery.py tests/test_outreach.py tests/test_migrations.py`
  — 18 passed. These use SQLite and a mocked provider; they do not prove real
  provider behavior or PostgreSQL locking.

## Step 10 — Runbook and integration readiness audit

- Added `docs/backend/operations.md` with local startup, vacancy/startup
  walkthrough, provider setup, migration/backup/restore/rollback, secret
  rotation, kill switch and verification instructions. The Integrations page
  can connect/disconnect Gmail and trigger reply polling.
- The walkthrough explicitly calls out that step 06 contact research is
  missing. Contact identity must be independently reviewed and supplied by
  the user. The full contact-to-submission/email outcome path therefore is not
  claimed complete. No deployment was performed.
- Remaining release gates: run the full backend/frontend suite; run migration
  and concurrency tests on disposable PostgreSQL; run Redis tests; build true
  vacancy and startup E2E journeys; implement user-facing retention/deletion,
  metrics/budget reporting and automated backup/restore checks; configure and
  verify Gmail OAuth with an owned test mailbox. Production readiness is not
  established.

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

## Step 07 — Application packages and supported submission

### Implemented

- **Frozen package and preview** (`app/submissions/service.py`): the
  application, selected resume text, form questions, answers, destination and
  SHA-256 hashes are snapshotted. Required unanswered questions produce
  `needs_input`; sensitive test form questions are never inferred. Resume
  versions are owner-checked, including the version already attached to an
  application.
- **Honest adapter boundary** (`app/submissions/adapters/`): unsupported
  destinations resolve to manual handoff with an actionable URL and
  instruction. The only live adapter is a test destination enabled by the
  exact `SUBMISSION_TEST_URL`; its HTTP transport is injectable for fixtures.
  No real job-board integration is claimed.
- **Durable authorized send**: submission stores the exact package and resume
  snapshot, obtains a one-shot approval bound to task payload and artifact
  hash, then queues through the task/outbox engine. Replays with the same
  idempotency key return the original attempt, including terminal attempts;
  conflicting payloads fail. Concurrent insert races resolve to the winning
  record.
- **Worker safeguards and receipts**: before the external effect, the worker
  rechecks frozen package integrity, linked resume integrity, task state and
  adapter configuration. Definitive refusal becomes `failed`; ambiguous
  timeout becomes `unknown` and is never automatically resent. Receipt lookup
  or an affirmative absence can reconcile that state. Only a confirmed
  receipt marks the application `applied` and records the artifact hash.
- **API and schema**: prepare, submit, history, detail, cancel and reconcile
  routes live under `/api/applications/{id}`. Migration
  `e1a7c4b902d6_application_submissions.py` creates the history table,
  ownership FKs, idempotency uniqueness and active-package uniqueness. Both
  SQLite startup metadata and Alembic metadata load the model.

### Limits

- Live sending is intentionally limited to an explicitly configured,
  operator-controlled test endpoint. There is no provider with access to
  submit applications to real vacancies.
- The step 07 fixture proves the controlled endpoint contract only; no real
  vacancy or production destination was contacted.

## Step 08 — Personalized cold-email drafts

### Implemented

- **Offline draft API** (`app/api/routes/outreach.py`): authenticated create,
  list, get, preview and edit endpoints under `/api/outreach/drafts`. Draft
  creation does not enqueue a task or send email.
- **Two distinct modes** (`app/outreach/service.py`): vacancy messages refer
  only to the sourced role/company; startup introductions do not claim an
  opening. Deterministic templates run locally with no model/provider
  dependency. External source notes are carried as review metadata and are
  never interpreted as instructions or copied into the email.
- **Truthfulness and traceability**: candidate contributions can only be
  selected from owner-scoped, user-confirmed `CandidateEvidence`; each
  contribution retains its evidence ID, source line and exact source text.
  Recipient address, source, source method and known/unknown identity stay
  outside the body. Inferred addresses are always marked unknown, and
  missing identity/source and missing attachment are returned as factuality
  findings.
- **Versioned immutable attachment**: selected resume-version text and hash
  are frozen on the draft. Every edit updates the payload hash, stores an
  immutable revision snapshot, and revokes active approvals referring to the
  old draft payload.
- **Migration** `f23d8a1b72c4_versioned_outreach_drafts.py` adds draft and
  revision tables with owner, opportunity and resume foreign keys.

### Limits

- Step 06 contact discovery is not present in this checkout. Draft creation
  therefore accepts a user-supplied recipient and source; it does not claim
  to discover or verify contacts.
- Email account connections and delivery belong to step 09 and are not
  implemented here. Drafts remain editable and unsent.
- Editing body or subject adds a factual-review finding; send-time claim
  enforcement and provider delivery status must be completed with step 09.

### Verification

- Focused: `PYTHONPATH=backend backend/.venv/bin/pytest -q
  backend/tests/test_submissions.py backend/tests/test_outreach.py
  backend/tests/test_migrations.py` → 19 passed.
- Full backend: `PYTHONPATH=backend backend/.venv/bin/pytest -q
  backend/tests` → 313 passed, 11 skipped. The skipped modules require
  opt-in PostgreSQL/Redis services. One existing Starlette deprecation
  warning and pytest-asyncio fixture-loop warning were reported.

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
