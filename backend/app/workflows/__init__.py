"""Workflow engine — durable tasks, outbox, automation policy.

See docs/backend/specification.md §7. PostgreSQL is the authoritative task
state; Redis/RQ is only a delivery bus (optional in local dev: the poll mode
worker and dispatcher work without Redis).
"""
