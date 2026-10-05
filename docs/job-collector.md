# Job Collector — architecture (DESIGN ONLY, not implemented)

## Intended workflow

```
User views a job page
        ↓  keyboard shortcut / browser action
thedaaakhouse Collector (browser extension)
        ↓  captures current page (URL + rendered text/HTML, user-initiated only)
POST /api/collect {url, text} (authenticated)
        ↓  extract → normalize → deduplicate → save
Job row in the Tracker (source + collected_at)
```

## Why current-page capture (not crawling)

- No aggressive scraping: one user-initiated page at a time, same content the
  user already sees. Respects robots/ToS far better than blind crawlers.
- Works on LinkedIn/Naukri/Wellfound/Indeed/Greenhouse/Lever/career pages
  without per-site scrapers (fragile) — extraction runs on captured text.

## Backend pieces needed

1. `POST /api/collect` (auth required): accepts `{url, text, captured_at}`,
   validates size (reuse MAX_UPLOAD_MB), returns `{application_id, deduped: bool}`.
2. Extraction: reuse `analysis/keywords.py` + a site-aware title/company splitter
   (Greenhouse/Lever embed JSON-LD — parse it when present).
3. Normalization: company/role/location/apply-URL canonicalization.
4. Deduplication: `source_url_hash UNIQUE` + fuzzy (company, role) check that
   links to the existing application instead of duplicating.
5. Rate limiting: reuse `core/ratelimit.py` with a stricter bucket (e.g. 30/hr).

## Database changes (future migration)

- `applications.source_url_hash VARCHAR(64) UNIQUE NULLABLE`
- `applications.source VARCHAR(32)` (extension | manual | import)
- `applications.collected_at DATETIME NULLABLE`

## Security

- Auth token lives in extension storage (same JWT, short expiry recommended).
- Cap payload size; strip scripts from captured HTML server-side (extract text only).
- Never auto-submit applications — collector only SAVES to the tracker.

## Explicitly out of scope

Auto-applying, mass crawling, LinkedIn automation (ban risk), circumventing
paywalls/logins.
