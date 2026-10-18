# Backend operations and release readiness

This runbook describes the checked-in implementation as of 2026-10-18. It is
not a production release approval. The repository has no configured Gmail
OAuth client, owned test mailbox, deployment environment, or live secrets, so
Gmail authorization and sending have not been exercised against Google.

## Local prerequisites and startup

1. Copy `.env.example` to `.env` and configure `DATABASE_URL`, `JWT_SECRET`,
   and `NEXT_PUBLIC_API_URL`. Local development can use SQLite; PostgreSQL is
   required for the concurrency and deployment checks.
2. Apply migrations from the repository root:

   ```sh
   backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
   ```

3. Start the API and one durable-task worker:

   ```sh
   cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001
   cd backend && PYTHONPATH=. .venv/bin/python -m app.workflows.worker --mode auto
   ```

   `REDIS_URL` selects the RQ transport. With it empty, the database poll
   worker executes queued work. Keep the dispatcher running when Redis/RQ is
   enabled. The database task and outbox rows remain authoritative.

4. Run the frontend with `cd frontend && npm run dev`. `/health` is liveness;
   `/ready` checks the database. Neither endpoint claims provider connectivity.

## Vacancy and startup prospect walkthrough

Both pathways use the same authenticated API and durable task engine:

1. Create a profile and resume version. Add a discovery source or a user-known
   vacancy URL, run a scan, then inspect its source evidence and freshness.
2. Rank the listing as a vacancy, or add a user-supplied startup URL as a
   `startup_prospect`. A startup prospect has no synthetic vacancy.
3. Save a vacancy into the tracker, or review a startup prospect. Contact
   research (step 06) is not implemented in this branch: enter a known recipient
   from an independently reviewed source, or mark the address unknown/inferred.
4. Prepare a submission package for supported test destinations or create an
   outreach draft. A draft has an immutable payload hash and editable revisions.
5. For email, configure Gmail as below, connect the mailbox, then create an
   `outreach.send` approval for the exact task payload:

   ```json
   {"draft_id":"<draft-id>","payload_sha256":"<current-draft-hash>"}
   ```

   Submit `POST /api/outreach/drafts/{draft_id}/send` with an
   `Idempotency-Key`, poll the returned task URL, and inspect
   `/api/outreach/sends`. `accepted` means Gmail accepted the API request; it
   does not prove inbox delivery or that a person read it. `unknown` means the
   provider outcome could not be confirmed. The worker reconciles a stable
   message ID before any further action and never automatically repeats an
   ambiguous send.
6. Use `POST /api/integrations/gmail/sync` to poll known Gmail threads for
   replies/bounces. Events are unique by provider message ID. Bounces and
   explicit opt-out language suppress the recipient; manual suppression is
   available at `POST /api/outreach/suppressions`.

## Gmail setup and limits

Gmail delivery is off by default. Create a Google OAuth web application,
enable Gmail API, and register the exact redirect URI configured in
`GMAIL_REDIRECT_URI`. Configure `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and
`GMAIL_ENABLED=true`. The app asks for offline access and the `gmail.send`,
`gmail.readonly`, `openid`, and `email` scopes. Google OAuth requires a
user-consent screen; Gmail scopes can require app verification before broad
deployment. Review Google's current [web-server OAuth guide](https://developers.google.com/identity/protocols/oauth2/web-server),
[Gmail scopes](https://developers.google.com/workspace/gmail/api/auth/scopes),
and [send API](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/send)
before enabling this integration.

Generate a Fernet key using `cryptography.fernet.Fernet.generate_key()` and
provide it as `GMAIL_TOKEN_ENCRYPTION_KEY` through the deployment secret
manager. Refresh tokens are encrypted in the database. Do not put the key in
source control or logs. Google refresh-token revocation is supported by the
disconnect route. Google OAuth changes or user revocation require reconnecting.

The connector has a configured daily send cap and UTC quiet hours. Individual
approval and policy quotas are checked by the durable task authorization layer
at execution. Reply polling is manual; Gmail push requires Google Cloud Pub/Sub
setup, and is not enabled here. Gmail does not expose a general recipient
delivery receipt through `messages.send`, so the implementation never equates
API acceptance with delivery. Automatic follow-up sends are disabled. Do not
use this connector for a campaign without reviewing recipient consent,
applicable law, Google's user-data policies, and rate limits.

## Secrets and key rotation

Rotate OAuth client credentials in Google Cloud, then update deployment
secrets and restart API/workers. For the Fernet key, use a maintenance window:

1. Pause workers and disable Gmail sending.
2. Back up the database and retain the old key securely.
3. Decrypt each stored token with the old key and re-encrypt with the new key;
   verify every row can be decrypted before switching configuration.
4. Deploy the new key, run an account-status check, then resume workers.
5. Revoke the old key only after verification. If the old key is lost, users
   must disconnect/reconnect their Gmail accounts.

No key-rotation utility is shipped yet; rotation is an operator procedure and
requires an audited one-off migration script before a production deployment.

## Migration, backup, restore, rollback

- Take a consistent PostgreSQL backup before every schema release. For example,
  use `pg_dump --format=custom` and verify the artifact in protected storage.
- Run `alembic upgrade head` as a release job before API/worker rollout. Startup
  refuses PostgreSQL when its Alembic revision is not the single code head.
- Keep API and worker versions aligned. Rollback means redeploying the previous
  code only if its schema is still compatible. Do not automatically downgrade
  after new delivery rows exist; restore the tested backup into a separate
  database and validate before switching traffic.
- Restore practice must include the database, uploaded resume files under
  `DATA_DIR`, and compatible encryption keys. This repository has no automated
  backup scheduler or verified restore environment.

## Operational controls and release gates

- Discovery sources can be disabled per source. No source-wide kill switch,
  budget dashboard, metrics exporter, or retention scheduler is configured.
- Gmail is a provider kill switch (`GMAIL_ENABLED=false`); disabling it blocks
  new OAuth and sends, while already queued work will fail safely. Disconnect
  individual accounts to revoke their credentials.
- `/health`, `/ready`, task polling, source run history, and send/event APIs
  expose basic runtime state. Structured metrics and alerting are not shipped.
- User-scoped foreign keys cascade delivery data on user deletion at the
  database level where supported. A user-facing account deletion/retention
  workflow is not implemented; operational deletion must be handled by a
  reviewed database process. Do not claim retention compliance from cascade
  declarations alone.
- Steps 06 (contact research) and parts of step 10 (release-grade E2E, verified
  restore, metrics, scheduled retention, live PostgreSQL/Redis checks) remain
  incomplete. Do not describe the system as production-ready.

## Verification commands

```sh
cd backend && PYTHONPATH=. .venv/bin/pytest -q
cd frontend && npm run typecheck
```

PostgreSQL concurrency/migration tests require a disposable database via
`TEST_DATABASE_URL`; Redis transport tests require a disposable Redis via
`TEST_REDIS_URL`. Live Gmail smoke tests must use a specifically owned test
mailbox and must be run manually after OAuth consent and secrets are configured.
