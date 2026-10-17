# Master prompt and 10 ordered implementation prompts

Use the master prompt at the beginning of a coding session. Then paste one numbered prompt at a time, in order. Each numbered prompt is also usable in a fresh session because it names the required documentation. Replace only values in angle brackets when needed.

“Master prompt” means the overall implementation instructions; it does not require working directly on the Git main/master branch. Follow the repository's branch workflow.

## Master prompt

```text
You are implementing the backend of thedaaakhouse, an existing job-search application.

Read repository instructions, docs/backend/README.md, docs/backend/codebase-map.md,
docs/backend/specification.md, and docs/backend/build-prompts.md. Inspect the current
source before changing anything; the codebase may have advanced beyond this snapshot.

Product goal:
Discover suitable jobs and potentially overlooked opportunities; create truthful,
job-specific resumes with explainable compatibility scores; prepare and submit
applications through supported integrations; discover public professional contacts;
and draft/send personalized startup outreach even when no vacancy is advertised.
Track external receipts, replies and outcomes.

Preserve the existing FastAPI + SQLAlchemy + Alembic backend and Next.js contracts.
Reuse application tracking, career profiles, fit evaluation, parsing, ATS v2,
optimization, resume versions, exports and company research. Do not rebuild them.
Keep interview and learning features working. Use a modular monolith and separate
workers. PostgreSQL is the deployed source of truth; Redis/RQ is the proposed queue.
Validate new library/provider choices against current official documentation.

Work through steps 01–10 in this file. When a specific step is requested, implement
that step completely and stop at its acceptance boundary. When asked to build the
whole backend, continue through all steps and maintain a progress record. Inspect
already completed work rather than assuming a prior prompt succeeded.

Rules:
- Distinguish implemented, partial, mocked and live-verified features.
- Strictly enforce ownership, including related objects and worker inputs.
- Never invent jobs, applicant counts, founder identities, email verification,
  candidate experience, credentials or submission/delivery success.
- ATS scores are this app's estimates; missing facts remain unknown.
- Separate vacancy opportunities from startup prospects without a job listing.
- Keep evidence and immutable submitted document/payload snapshots.
- Centralize safe URL fetching; treat fetched content as untrusted input.
- Use durable tasks, transactional outbox, finite retries and idempotency.
- Ambiguous external side effects require reconciliation, not blind retry.
- Support individual approvals and bounded user-configured automation policies;
  check current authorization, suppression and quotas immediately before execution.
- Keep normal development and deterministic tests independent of live credentials.
  Do not send real outreach or submit real applications during implementation tests.
- Never reset user data, hide missing integrations behind mock success, or stamp
  unknown database schemas as migrated.

For each step:
1. Inspect relevant code, migration history and tests; summarize concrete changes.
2. Implement the smallest complete vertical slice, including schemas, migration,
   services, routes, worker behavior and integration contracts where applicable.
3. Add meaningful regression/failure-path tests; run relevant checks and expand only
   when the change warrants it. Use PostgreSQL for locking/concurrency verification.
4. Update docs and .env.example for actual behavior without adding real secrets.
5. Update docs/backend/implementation-progress.md with step status, files changed,
   test commands/results, assumptions and unresolved dependencies. Create it if absent.
6. Report what works, how to run it, and remaining limitations. Do not claim checks
   passed when they were not run.

If credentials or provider permissions are missing, complete the adapter contract,
fixtures, configuration validation and setup guide. Mark live verification blocked;
do not claim the integration is finished. Continue independent work. Ask only for
information that genuinely blocks dependent implementation.
```

## 01 — Secure foundations and establish the baseline

```text
Implement step 01 using the master instructions in docs/backend/build-prompts.md.
Read docs/backend/codebase-map.md and specification.md, then inspect current source.

Audit authentication, related-object ownership, null-owner legacy rows, file downloads,
URL-fetch paths, configuration and Alembic history. Record an initial test baseline.
Close ownership gaps with a documented legacy quarantine/claim strategy; never assign
or expose ownerless rows automatically. Centralize safe URL fetching for job import
and company research: destination checks at connection time and redirects, bounded
streamed bodies, allowed schemes/ports, timeout and sanitized error behavior.

Preserve current API success contracts. Establish migration upgrade tests instead of
relying on create_all or stamp head. Add regressions for cross-user references,
ownerless records, redirect-to-private targets, IPv6 and oversized responses.

Done when existing flows still work, ownership/fetch regressions pass, and the schema
revision graph plus reproducible baseline are documented. Report pre-existing failures
separately; do not hide them or perform an unrelated rewrite.
```

## 02 — Durable task execution and automation controls

```text
Implement step 02 using docs/backend/build-prompts.md master instructions and the
workflow/API sections of docs/backend/specification.md. Verify step 01 first.

Add task_runs, transactional outbox, audit events, automation policies and payload-bound
approvals with migrations and typed contracts. Implement Redis/RQ worker and dispatcher,
finite backoff, leases/heartbeats, expired-lease recovery, cancellation, idempotency-key
conflict detection and task polling. Use PostgreSQL as authoritative task state.
Add a task handler interface so later features can register work without changing
the worker's core. Provide a harmless diagnostic handler for execution tests.

Add owner-scoped policy management, revocation, expiry, quota reservation and reusable
execution authorization checks. Return 202 with task_id/status/poll_url. Add local
worker/dispatcher startup commands, configuration examples and health checks.

Done when concurrent identical requests create one logical task, a crash after DB
commit recovers publication, duplicate queue deliveries do not repeat completed work,
and cancellation/revoked policy is respected. Verify locks with PostgreSQL; mocked
unit tests alone do not prove these concurrency guarantees.
```

## 03 — Scheduled multi-source job discovery

```text
Implement step 03 using the master instructions and discovery specification.
Verify the shared fetch and durable task interfaces from steps 01–02.

Add discovery sources, canonical job listings and source observations with migrations.
Implement two structured job-board/feed adapters and a company careers HTML/JSON-LD
adapter. Verify supported access and API formats from current official documentation;
record actual capabilities and configuration. Reuse jobpage extraction where useful.

Add create/list/update source APIs, scheduled and manual runs, cursors, budgets,
rate-limit backoff, normalization, stable-ID/URL deduplication, conservative fuzzy
review, freshness and evidence-backed closure/reopening. Preserve every source.
Discovery must not automatically create a tracked Application for every found job.

Done when fixture scans from multiple sources merge duplicate jobs, support pagination,
recover partial failures and never interpret unavailable sources as closed listings.
Include SSRF, malformed data, repeated/concurrent scan and repost tests. Document an
opt-in real read-only smoke test; label live access unverified if not exercised.
```

## 04 — Opportunity ranking and startup prospects

```text
Implement step 04 using the master instructions and opportunity/ranking specification.
Verify discovery output from step 03. Extend existing CareerProfile and fit evaluation.

Add organizations, opportunities and versioned evaluation snapshots. Support both
vacancies linked to listings and startup prospects with no listing. Add an injectable
search-provider adapter plus user-supplied startup URLs; document provider setup and
source evidence. Research product/team/hiring signals without inventing an opening.

Implement separate eligibility, fit, competition evidence and priority outputs.
Store observed applicant counts with source, timestamp and measurement meaning.
Missing counts remain unknown; proxy signals appear as potentially overlooked,
not confirmed low competition. Validate configurable weights and expose contributions.

Add paginated list/detail/filter APIs and idempotent save-to-existing-Application.
Preserve user preferences and explicit exclusions. Done when no-vacancy prospects
work without synthetic JDs, duplicates save once, exclusions win over scores, and
missing/unlike competition measurements are not misleadingly compared.
```

## 05 — Truthful tailored resumes and reliable exports

```text
Implement step 05 using the master instructions and resume specification.
Inspect existing docparse, candidate/profile schemas, ATS v1/v2, tailoring, optimization,
LaTeX and PDF code before extending them. Do not create a competing resume pipeline.

Complete structured candidate evidence extraction with stable source references and
user-confirmed revisions. Preserve claimed versus demonstrated skills. Use validated
structured model output where beneficial, with a deterministic fallback.

Extend optimization to use evidence-linked edits, immutable document snapshots,
versioned score/config/input hashes, bounded attempts and clear stop reasons. Fix
unsupported aliases and weak experience/match assumptions using regression fixtures.
Reparse the exported PDF and validate content/readability. Isolate compilation and
report missing tooling accurately. Add asynchronous preparation through the task engine
without silently breaking current synchronous frontend contracts.

Done when an actual exported resume preserves supported facts, missing requirements
stay gaps, manual edits invalidate stale derived analyses, and unavailable models or
LaTeX tools produce honest recoverable outcomes. Test both supported paraphrases and
fabricated metrics/employers/skills, plus malformed and unreadable uploads.
```

## 06 — Founder and hiring-contact research

```text
Implement step 06 using the master instructions and contact specification.
Verify opportunity/organization and safe-fetch interfaces from previous steps.

Add contacts and source evidence with public professional identity, role, organization,
email, discovery method, verification state and checked/expiry timestamps. Implement
bounded official-site research and an optional enrichment/verification provider
interface. Provide asynchronous discover and owner-scoped contact list/detail contracts.

Keep published, provider-reported and inferred-pattern addresses distinguishable.
Do not treat a valid domain as a verified mailbox or a matching name as proven identity.
Record ambiguity, stale verification and no-contact outcomes. Support public team inbox
or contact-page fallback. Never expose provider credentials in results or logs.

Done when a startup prospect with no job can yield sourced contact candidates, an
ambiguous founder requires review, guessed emails remain unverified, and provider
failure produces an explicit result. Test conflicting domains, prompt injection in
pages, ownership, duplicate contacts and verification expiry with deterministic fixtures.
```

## 07 — Application packages and supported submission

```text
Implement step 07 using the master instructions and submission specification.
Verify task, authorization, opportunity and immutable resume contracts.

Add application_submissions and prepare/submit/history APIs. Build frozen application
packages with selected resume, verified profile answers, required unanswered fields,
destination and payload hash. Provide adapter capability discovery and manual handoff
for unsupported sites. Implement one real submission adapter only for a destination
whose current API/access permits the authenticated user to submit; document requirements.
If no such access is available, finish the adapter boundary/fixtures and clearly mark
live submission blocked rather than inventing a working provider.

Recheck authorization, quota, destination availability and artifact hash immediately
before submission. Persist receipts. Handle provider timeout as unknown and reconcile;
do not mark applied until confirmed. Preserve manual tracking with explicit provenance.

Done when repeated requests and worker redelivery cannot blindly resubmit, unknown
mandatory answers block sending, changed files invalidate approval, unsupported sites
return an actionable handoff and confirmed receipts attach the exact submitted version.
Use fixtures or an explicitly configured test destination; never test on a real vacancy.
```

## 08 — Personalized cold-email drafts

```text
Implement step 08 using the master instructions and outreach specification.
Verify opportunity, evidence, contact and resume contracts.

Add versioned outreach drafts, create/edit/preview APIs and a drafting service for
vacancy outreach and startup introduction without a vacancy. Generate subject/body,
recipient, sourced reason for contact, evidenced contribution, concise ask and optional
immutable resume attachment. Include source and factuality metadata outside the email
body for UI review. Fall back to deterministic templates when model output is invalid.

Validate identity, role and company claims; do not imply an opening, relationship or
candidate accomplishment that is not supported. Editing recipient/body/attachment
changes the payload hash and invalidates prior approval. Draft creation must never send.

Done when both outreach modes produce editable drafts with traceable personalization,
unknown contact identity is exposed, missing facts are not filled in, and malicious
source instructions cannot redirect recipients or insert unsupported claims. Include
ownership, versioning, attachment access and unavailable-provider tests.
```

## 09 — Email delivery, replies and follow-ups

```text
Implement step 09 using the master instructions and outreach/external-side-effect
specification. Verify drafts, approvals, quotas and durable tasks.

Implement one configured email provider adapter with encrypted account credentials,
connection/revocation flow, send capability checks, immutable payloads and provider IDs.
Check current official authentication, event and idempotency documentation; document
actual support instead of assuming all providers behave alike.

Add send/status APIs, signed replay-safe webhooks or provider polling where required,
delivery/bounce/reply events, suppression, opt-out handling and bounded optional
follow-ups. Enforce limits and quiet hours. Recheck suppression, reply state, account
connection and authorization inside the worker. Reconcile ambiguous sends.

Done when duplicate/out-of-order events are safe, edited drafts cannot use stale
approval, replies/bounces/opt-outs stop pending follow-ups, and concurrent sends cannot
exceed quotas. Test provider acceptance separately from delivery. Provide an opt-in
smoke test using an owned mailbox; no real cold-email campaign in tests. If credentials
are missing, label live verification blocked and keep fixture tests runnable.
```

## 10 — End-to-end integration and deployment readiness

```text
Implement step 10 using the master instructions and all acceptance criteria in
docs/backend/specification.md. Audit actual completion of steps 01–09; do not assume
provider-dependent features are live because their fixtures pass.

Connect the workflow: profile → discovery → ranking → saved application or startup
prospect → resume → contact → prepared submission/email → authorization → confirmed
receipt → tracker/outcome. Add typed frontend API contracts and only the minimal UI
integration necessary to exercise these backend flows; preserve existing screens.

Add operational metrics, provider/source kill switches, budget reporting, retention
and deletion behavior, secret rotation guidance, API/worker/scheduler health checks,
backup/restore and migration deployment runbooks. Document required environment
variables, workers, provider configuration, sandbox mode and rollback limitations.

Run the backend regression suite, PostgreSQL concurrency/migration integration checks,
relevant frontend typechecking and end-to-end fixture scenarios for both vacancy and
no-vacancy paths. Exercise queue loss, restart, revoked authorization, stale listings,
malformed sources and unknown submission/send outcomes. Run live sandbox smoke tests
only when explicitly configured with owned/test destinations.

Done when the documented local walkthrough is reproducible, status and evidence are
visible through APIs, all critical acceptance cases are checked, and the release report
clearly separates passed checks, pre-existing failures and missing live credentials.
Produce docs/backend/operations.md and update implementation-progress.md and README.
Do not deploy or announce a production-ready integration that has not been verified.
```
