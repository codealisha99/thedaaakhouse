"""Scheduled discovery of job listings from feeds and career pages.

Step 03 of docs/backend/build-prompts.md. Submodules:

- models     — discovery_sources / job_listings / listing_sources / discovery_runs
- adapters   — greenhouse, lever, company_careers (JSON-LD)
- normalize  — URL canonicalization, title/company/location hygiene, hashing
- dedup      — stable-ID → canonical-URL → conservative fuzzy matching
- service    — scan engine (create/update/close/reopen listings, run records)
- scheduler  — asyncio loop that scans due enabled sources

Everything user-supplied is fetched through app.ingestion.safe_fetch at
call time (lazy import); tests inject stub fetchers and never touch the
network.
"""
