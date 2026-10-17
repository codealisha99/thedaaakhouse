# Ownership policy (step 01 — secure foundations)

Every user-visible record — resumes, jobs, applications, resume versions —
belongs to exactly one user. From this step on the rule is **strict scoping**:
a record is visible or mutable by its owner and no one else.

## Quarantine of ownerless rows

Rows created before authentication existed may have `user_id = NULL`.
They are **quarantined**, not grandfathered:

- `NULL user_id` no longer means "public". The old rule
  (`user_id not in (None, current_user_id)`) is gone from every service; a
  service with no authenticated user returns nothing at all.
- Any `NULL user_id` row is refused through the API with the same response a
  nonexistent id would get — no information leaks about its existence.
- Nothing in application code ever claims an ownerless row implicitly.

## Claiming ownerless rows (operator-only)

The only sanctioned path is an explicit operator action:

```bash
backend/.venv/bin/python backend/scripts/claim_legacy_records.py --dry-run
backend/.venv/bin/python backend/scripts/claim_legacy_records.py \
    --apply --user-id <users.id>
# optionally: --table jobs (repeat for more)
```

Rules:

- ran by an operator on the server, never from request handling
- after an explicit, named user decision — no automatic claiming
- Postgres only; refuses unmigrated databases
- always `--dry-run` first (the default)

## Cross-user references are rejected

An application referencing a `job_id` the caller does not own fails with
"job not found"; a patch setting another user's `resume_version_id` fails
with "version not found". Referenced records are validated at the service
layer **at write time** — a caller cannot adopt a foreign record by purely
asserting its id.

## Why quarantine instead of claiming

Silent adoption made pre-auth data readable by the first user who tripped
over the row. An explicit operator claim keeps the default insecure-free:
the vulnerable state (ownerless) is observable and closes one row at a time.
