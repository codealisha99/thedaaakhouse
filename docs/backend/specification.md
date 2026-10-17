# Backend specification

Status: proposed implementation plan, grounded in [the current code](codebase-map.md). No provider access, API permissions, pricing or submission capability is assumed. Verify current official provider documentation when implementing an adapter and record the decision in the repository.

## 1. Product workflows

### Discover and apply to a vacancy

1. User uploads a master resume, verifies extracted facts, and sets target roles, locations, remote preferences, experience level, salary preferences and exclusions.
2. A discovery run checks configured sources and company career pages within a page/time budget.
3. Normalize jobs, preserve original source evidence, merge duplicates, and mark stale/closed listings.
4. Filter explicit eligibility conflicts; rank remaining opportunities by fit and freshness. Show competition information separately with evidence and uncertainty.
5. Save a selected opportunity as an existing `Application`; create a tailored `ResumeVersion` and score report.
6. Prepare required answers and a submission preview. Unknown mandatory answers require user input; never infer work authorization, legal declarations or demographic answers.
7. Submit through a supported adapter under the user's action approval or configured automation policy. Unsupported sites get a complete downloadable application package and manual handoff.
8. Record receipt and exact submitted document. Set `applied` automatically only after confirmed submission; retain manually reported applications as a separately identified provenance.

### Find startups and contact a founder without a vacancy

1. Start from configured startup directories, search-provider results or user-supplied company URLs; establish the company's domain and identity.
2. Research its product, team, technical needs and hiring signals from public sources.
3. Record a `startup_prospect`, with `job_id=null`. Absence of a discovered vacancy means “no opening found in checked sources,” not proof that the company is not hiring.
4. Form a contribution hypothesis tied to the candidate's actual projects and sourced company needs. Label it a hypothesis.
5. Find a relevant founder, hiring manager, recruiter or published team inbox. Store identity evidence and contact provenance.
6. Draft a short introduction with a specific reason for contacting them, one evidenced contribution and a clear ask. Do not imply an advertised job or a previous relationship.
7. Send under explicit action approval or a bounded outreach policy. Track response, bounce, opt-out and any permitted follow-up. A reply or opt-out stops automated follow-ups.

## 2. Architectural decisions

Keep FastAPI, SQLAlchemy, Alembic and the current Next.js API contract. Use a modular monolith with a separate worker process; a microservice split is unnecessary for this scope.

Use PostgreSQL for deployed workers and concurrency-sensitive integration tests. Retain SQLite for fast unit tests. Proposed initial queue: Redis + RQ, with PostgreSQL task/outbox records as the source of truth. Pin compatible versions after checking official documentation. Redis loss must not erase accepted work.

Proposed modules under `backend/app/`:

| Module | Responsibility |
|---|---|
| `workflows/` | Task lifecycle, scheduler, leases, retries, outbox and automation policy |
| `discovery/` | Source adapters, normalized listings, deduplication and freshness |
| `opportunities/` | Eligibility and explainable ranking; startup prospects |
| `contacts/` | Professional identity/contact discovery, verification evidence |
| `submissions/` | Application packages, adapter capabilities, receipts and reconciliation |
| `outreach/` | Drafts, send requests, provider events, suppression and follow-ups |
| `integrations/` | Provider clients, encrypted credentials, quotas and capability checks |
| `ingestion/` | Shared safe fetch and document extraction; extend existing code |

Keep HTTP routes thin, business rules in services and persistence in repositories. Use focused new service modules rather than growing `services.py` indefinitely. Avoid moving existing services wholesale while changing behavior.

## 3. Discovery contract

Every adapter exposes `discover(cursor, filters, budget)` and returns listings, a next cursor, and source diagnostics. An adapter that cannot fetch reports a failure, not an empty successful job list.

Start with two structured career-board/feed adapters plus a bounded company-careers HTML/JSON-LD adapter. Greenhouse and Lever are candidates to investigate, not promised integrations. Implement source enable/disable, cadence, fetch limits, backoff and run-now. Add search-provider startup discovery behind an interchangeable interface.

Store source URL, source identifier, external listing ID, fetched timestamp, posting date if supplied, content hash, canonical apply URL, title, company, location, remote mode, employment type, description and expiry/closure observations. Missing values stay null.

Deduplicate in order: stable source ID, canonical URL, then conservative company/domain + title + location similarity. Preserve all source references; uncertain matches go to review. Strip tracking parameters without deleting meaningful job identifiers. Reposts preserve history and can reopen a closed listing based on fresh evidence.

A failed fetch must not close a listing. Closure requires explicit evidence or a configured number of successful complete source scans where the listing is absent. Store which rule triggered closure.

Use configured public sources and permitted APIs; handle access restrictions with a clear unsupported/manual result. A browser-rendering adapter is optional only for sources that need it, with isolated credentials and strict time budgets. Never promise universal browser auto-apply.

## 4. Fit and lower-competition discovery

Keep three separate outputs: eligibility, fit, and competition evidence.

- Eligibility: `eligible`, `ineligible`, or `unknown`, with reasons. Unknown requirements must not silently become satisfied.
- Fit: extend existing career-fit evaluation with actual evidence and versioned weights.
- Competition: observed applicant count, observation time, source and meaning when supplied. Click counts and “people who clicked apply” are not completed application counts.
- Visibility signals: first seen recently, company-only posting, niche specialization, small distribution footprint. These are proxies, not proof of fewer applicants. First-seen date is not posting date.

Initial proposed priority formula: 70% fit + 20% freshness + 10% evidence-backed opportunity signal, each normalized to 0–100. Exclude unavailable factors and renormalize; persist available-data coverage, inputs and formula version. Make weights configurable and validate them. Do not score missing applicant counts as zero competition. Keep hard exclusions separate from the weighted score.

Expose factor contributions and source links. A “lower observed competition” filter includes only comparable, recent observed counts under a user-set threshold. A separate “potentially overlooked” filter uses labeled proxies. Do not compare unlike platforms' counts as equivalent measurements.

## 5. Evidence-backed resume generation

Extend document parsing into a validated candidate profile with stable evidence IDs linking facts to resume sections/text spans and user-confirmed edits. Keep demonstrated, claimed and learning goals distinct. Preserve master uploads and immutable artifact snapshots for submitted versions.

Pipeline: parse → validate candidate facts → extract JD requirements → match evidence → propose edits → validate every claim → render → reparse exported document → score → store version and trace.

Reuse current ATS v2 and optimization logic. Correct unsupported equivalences, weak matching and experience-duration handling with fixtures before adding complexity. Store score version, weights, JD hash, resume hash, gaps, blockers and before/after values. A high score never overrides an eligibility conflict or unsupported claim.

Allow truthful paraphrasing only when all factual content maps to evidence. Never add unsupported skills, employers, dates, metrics or achievements. Provide a conservative extractive fallback for invalid or unavailable model output. Bound attempts, runtime and cost; stop on target, plateau, invalid output or budget exhaustion. `target_not_reached` is a valid outcome.

Prefer a clean, single-column searchable PDF and readable text output. Compare extracted PDF text against the validated content. Isolate LaTeX compilation, disable shell escape, restrict filesystem/network access and enforce resource limits. Report unavailable toolchains honestly.

## 6. Contact discovery and outreach

Contact records need person name, role, company/domain, public professional source URL, retrieved timestamp, email if found, discovery method and verification state.

Discovery order: official team/contact/careers pages → public professional profiles or source links → configured enrichment provider. Record `published`, `provider_reported`, `inferred_pattern`, `unavailable` separately from verification states `unverified`, `deliverable`, `risky`, `invalid`, `unknown`.

A guessed pattern must never be presented as a verified founder address. A domain with mail records does not prove that a mailbox exists or belongs to that person. Store provider verification timestamp and expire stale checks. Ambiguous names/domains require review. Offer a public team inbox or contact-page link when no suitable address is found.

Drafts contain subject, body, recipient, source-backed personalization, resume artifact, and factuality findings. Default to one recipient per message and no follow-up unless configured. Proposed initial policy limits: 10 new emails per day per user, at most one follow-up after 7 days, quiet hours in the user's timezone, and stop on any reply, bounce, complaint or opt-out. These are conservative product defaults, not deliverability guarantees.

Store suppression at both user and sending-account scope where needed. Check suppression again immediately before sending. Provider acceptance means `sent`; it does not mean delivery or a reply. Do not use email opens as reliable proof of interest. Retention/deletion periods and provider-specific sending requirements must be configured before production launch.

## 7. Durable work and external side effects

Tasks: `queued → running → succeeded | failed | cancelled`; deferred retries carry `next_attempt_at`. Persist stage, attempt count, heartbeat, lease expiry, error code, cancellation request and result references. One worker owns a task lease at a time. Use finite retries with jitter for transient failures; invalid credentials or invalid input are not endlessly retried.

Write the task and outbox event in one database transaction. A dispatcher publishes pending outbox rows; workers deduplicate deliveries by task ID. Recover expired leases and reconcile publication after restarts. Recheck cancellation between stages. Cancellation cannot undo a submission already accepted remotely.

Submission states: `draft → needs_input | ready → queued → submitting → submitted | failed | unknown`. An ambiguous timeout after sending becomes `unknown` and triggers receipt reconciliation, not blind resubmission.

Email states: `draft → ready → queued → sending → sent | failed | unknown`, with separate delivery/reply events. Use provider idempotency keys when supported and persist provider IDs. Exactly-once external delivery cannot be guaranteed when the remote system lacks idempotency or reconciliation; ambiguous results need manual review.

An action approval binds user, action kind, recipient/destination, artifact hash, payload hash and expiry. Editing the recipient, answers, resume or email invalidates it. A standing automation policy defines allowed sources/domains, action types, limits, minimum evidence/fit requirements, expiry and revocation. Workers validate the current policy and counters at execution time, including concurrency-safe quota reservations.

## 8. Proposed database additions

Names below are design contracts; introduce them incrementally with Alembic migrations.

| Entity | Main fields and constraints |
|---|---|
| `discovery_sources` | Owner, adapter, config, cadence, cursor, enabled, next run, last successful scan |
| `task_runs` / `outbox_events` | Owner, kind, input references, state, attempts, lease, result, error; unique owner+kind+idempotency key |
| `organizations` | Canonical company name/domain and provenance; distinct from existing research snapshots |
| `job_listings` / `listing_sources` | Canonical vacancy and observations; unique source+external ID when present |
| `opportunities` | Owner, kind (`vacancy` or `startup_prospect`), organization, nullable listing, ranking and evidence; vacancy requires listing |
| `opportunity_evaluations` | Input hashes, fit/eligibility/competition factors, configuration version and timestamp |
| `candidate_evidence` | Owner, resume/profile revision, fact, source span, confirmation state |
| `contacts` / `contact_evidence` | Owner, organization, identity, address, source, method, verification and expiry |
| `integration_accounts` | Owner, provider, encrypted credentials/reference, granted scopes, expiry and connection status |
| `application_submissions` | Owner, application, adapter, immutable payload/artifact hashes, state, receipt, idempotency key |
| `outreach_messages` | Owner, opportunity, contact, draft revision, sending account, payload hash and state |
| `message_events` / `suppressions` | Unique provider event ID, event type/time; scoped normalized address and suppression reason |
| `automation_policies` / `action_approvals` | Owner, permitted actions, constraints, expiry, revocation and payload bindings |
| `audit_events` | Owner, actor, action, object, timestamp, correlation ID and redacted result |

Keep private candidate/contact/automation data user-owned. Initially scope discovery records to the user too; do not accidentally turn research into a public shared directory. Database constraints and service checks must enforce tenant consistency for foreign references. Use UTC instants, indexed foreign keys and explicit deletion behavior.

Link an opportunity to an existing application through a nullable `Application.opportunity_id`, unique per user/opportunity for the initial workflow. Saving the same opportunity twice returns the same application. A startup prospect can have outreach with no application and no fabricated job description.

## 9. Proposed API contract

Existing routes continue working. New async work returns HTTP 202 with `{task_id, status, poll_url}`; task IDs are not job-listing IDs. Mutating work requests accept an `Idempotency-Key` scoped to user and operation; replay returns the original result, while the same key with a different payload returns 409.

| Route | Purpose |
|---|---|
| `POST/GET /api/discovery/sources` | Configure/list sources |
| `PATCH /api/discovery/sources/{id}` | Change cadence, budget or enabled state |
| `POST /api/discovery/runs` | Start source scan or startup discovery |
| `GET /api/tasks/{id}` | Poll stage, progress, result, errors |
| `POST /api/tasks/{id}/cancel` | Request cancellation |
| `GET /api/opportunities` | Cursor-paginated filters for kind, fit, freshness and competition evidence |
| `GET /api/opportunities/{id}` | Detail, sources and score explanations |
| `POST /api/opportunities/{id}/save` | Idempotently link/create tracked application |
| `POST /api/opportunities/{id}/contacts/discover` | Queue contact research |
| `GET /api/opportunities/{id}/contacts` | View contacts and verification evidence |
| `POST /api/applications/{id}/prepare` | Validate answers and freeze application package |
| `POST /api/applications/{id}/submit` | Queue authorized submission |
| `GET /api/applications/{id}/submissions` | Submission history, receipts and handoff information |
| `POST /api/outreach/drafts` | Generate sourced draft from opportunity/contact |
| `PATCH /api/outreach/drafts/{id}` | Edit draft and invalidate old approval |
| `POST /api/outreach/drafts/{id}/send` | Queue authorized email |
| `GET /api/outreach/messages/{id}` | Send, delivery and reply state |
| `POST /api/actions/{kind}/{id}/approve` | Bind an approval to a current preview and expiry |
| `POST/GET/PATCH /api/automation/policies[/{id}]` | Create/list/update or revoke bounded policies |
| `GET /api/integrations/accounts` | User-owned connection and capability status |
| `POST /api/integrations/{provider}/connect` | Begin supported credential/OAuth connection |
| `GET /api/integrations/{provider}/callback` | Validate OAuth state and finish connection where applicable |
| `POST /api/integrations/accounts/{id}/disconnect` | Revoke connection and stop pending sends |
| `POST /api/webhooks/{provider}` | Signed, replay-safe provider events |

Define explicit Pydantic request/response schemas and OpenAPI examples. Suggested errors: 401 unauthenticated, 404 missing or other-owner object, 409 state/idempotency conflict, 422 invalid input, 429 quota exhausted, 503 unavailable configured dependency. Async failures expose stable error codes, retryability and redacted detail. Cursor pagination must have deterministic ordering.

## 10. Security and operational requirements

- Centralize URL fetching: HTTP(S) only; block credentials in URLs, private/local/reserved destinations, unsafe ports and redirect pivots; enforce DNS/connect-time destination checks, bounded redirects, streamed byte limits and timeouts.
- Treat fetched pages and uploaded documents as untrusted data. Embedded instructions cannot override generation rules, select recipients, request secrets or authorize actions.
- Encrypt integration credentials at rest with a deployment-managed key; support rotation and revocation. Do not log tokens, full resumes or email bodies.
- Authenticate every private endpoint and worker input. Revalidate object ownership rather than trusting client-provided user IDs. Signed webhook verification precedes event processing.
- Track request/task correlation IDs, queue age, task latency, source failures, dedup rate, parse failure rate, provider cost, send failures and ambiguous submissions.
- Provide provider and source kill switches. Budget caps apply to time, pages, tokens and messages, including retries.
- Run migrations as a separate deployment step; back up before migration, test restoration and document rollback compatibility. Provide API, worker and scheduler health checks.
- Implement account deletion across records, documents and queued work, and define how minimal suppression records are retained without retaining message content.

## 11. Completion criteria

A local reproducible demonstration must cover:

1. Two users cannot read, mutate, queue or download one another's data, including null-owner legacy rows.
2. Repeated and concurrent source scans produce one opportunity for a duplicate vacancy while preserving sources.
3. An unavailable source does not silently close jobs; a verified closed listing is excluded from automatic submission.
4. A listing without applicant data shows unknown competition, and proxy-based ranking explains its evidence.
5. Resume generation preserves actual facts; unsupported skills stay gaps; exported PDF text remains readable.
6. A no-vacancy startup produces a sourced prospect and draft without inventing a role or founder address.
7. Retried submission/send requests do not blindly duplicate external actions; uncertain receipts remain unknown.
8. Stale approvals, revoked policies, changed artifacts, suppressed contacts and replied-to threads stop queued actions.
9. Duplicate/out-of-order signed webhooks do not duplicate events or regress delivery state incorrectly.
10. Worker restart, queue loss, expired leases and rate-limit responses recover within bounded retries.

Use deterministic HTTP/provider fixtures for CI, plus opt-in live sandbox smoke tests using an owned mailbox and test application destination. Do not send real cold outreach or apply to real vacancies as a test. Run existing backend regression tests, migration upgrade tests on SQLite/PostgreSQL, and frontend typechecking when contracts change. Record actual results and limitations; a mocked adapter is not a live integration.
