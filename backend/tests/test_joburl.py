"""Job URL ingestion tests: extraction, guards, and the from-url route."""

import json

LD_HTML = """<html><head><title>Ignored Title</title>
<script type="application/ld+json">%s</script></head>
<body><h1>Should not win</h1><p>Body text.</p></body></html>""" % json.dumps({
    "@type": "JobPosting",
    "title": "Senior AI Engineer",
    "hiringOrganization": {"name": "Acme Corp"},
    "description": "<p>Build RAG pipelines with Python and FastAPI. 3+ years required.</p>",
    "qualifications": "BS in CS",
    "experienceRequirements": "3 years",
})

PLAIN_HTML = """<html><head><title>Backend Engineer — Beta Inc</title>
<meta name="description" content="Join Beta to build APIs."></head>
<body><h1>Backend Engineer</h1><p>We need Python, Docker, and Kubernetes skills.</p></body></html>"""


def test_validate_rejects_bad_scheme():
    from app.analysis.jobpage import validate_job_url

    for bad in ["", "ftp://x.com/j", "notaurl", "javascript:alert(1)"]:
        try:
            validate_job_url(bad)
        except ValueError:
            continue
        raise AssertionError(f"accepted bad URL: {bad!r}")


def test_validate_blocks_nonpublic_hosts():
    from app.analysis.jobpage import validate_job_url

    for blocked in ["http://127.0.0.1/x", "http://localhost/x", "http://10.0.0.5/jobs"]:
        try:
            validate_job_url(blocked)
        except ValueError:
            continue
        raise AssertionError(f"SSRF guard missed: {blocked!r}")


def test_validate_rejects_unresolvable():
    from app.analysis.jobpage import validate_job_url

    try:
        validate_job_url("https://nonexistent.invalid-tld-xyz/job")
    except ValueError:
        return
    raise AssertionError("unresolvable host accepted")


def test_extract_prefers_json_ld():
    from app.analysis.jobpage import extract_job_posting

    p = extract_job_posting(LD_HTML, "https://example.com/j/1")
    assert p["title"] == "Senior AI Engineer"
    assert p["company"] == "Acme Corp"
    assert "RAG" in p["description"]
    assert p["role_category"] == "AI Engineer"
    assert p["source_url"] == "https://example.com/j/1"


def test_extract_falls_back_to_heuristics():
    from app.analysis.jobpage import extract_job_posting

    p = extract_job_posting(PLAIN_HTML, "https://example.com/j/2")
    assert "Backend Engineer" in p["title"]
    assert "Python" in p["description"]
    assert p["role_category"] == "Backend Engineer"


def test_categorize_other():
    from app.analysis.jobpage import categorize_role

    assert categorize_role("Chief Happiness Officer", "spreadsheets and smiles") == "Other"


def _fake_http(monkeypatch, html_text, content_type="text/html"):
    """Patch the network seams safe_fetch leaves for tests: host resolution
    (validate_job_url -> safe_fetch.resolve_public_host) and page fetch
    (jp._fetch_page, which otherwise drives the full safe fetcher)."""
    import socket

    import app.analysis.jobpage as jp

    monkeypatch.setattr(socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])

    def fake_fetch(url, timeout_s, max_bytes):
        assert len(url) < 2048
        return html_text, {"content-type": content_type}

    monkeypatch.setattr(jp, "_fetch_page", fake_fetch)


def test_from_url_route_end_to_end(client, auth_headers, monkeypatch):
    _fake_http(monkeypatch, LD_HTML)
    r = client.post("/api/applications/from-url",
                    json={"url": "https://example.com/j/1"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["company"] == "Acme Corp"
    assert body["role"] == "Senior AI Engineer"
    assert body["job_url"] == "https://example.com/j/1"
    assert "python" in (body["jd_analysis"] or {}).get("skills", [])
    assert (body["jd_analysis"] or {}).get("posting", {}).get("role_category") == "AI Engineer"


def test_from_url_explicit_overrides_win(client, auth_headers, monkeypatch):
    _fake_http(monkeypatch, LD_HTML)
    r = client.post("/api/applications/from-url",
                    json={"url": "https://example.com/j/1", "company": "Mine", "role": "Mine Role"},
                    headers=auth_headers)
    assert r.status_code == 201, r.text
    assert r.json()["company"] == "Mine"
    assert r.json()["role"] == "Mine Role"


def test_from_url_bad_scheme_400(client, auth_headers):
    r = client.post("/api/applications/from-url",
                    json={"url": "ftp://example.com/j"}, headers=auth_headers)
    assert r.status_code == 400


def test_from_url_empty_page_400(client, auth_headers, monkeypatch):
    _fake_http(monkeypatch, "<html><head></head><body></body></html>")
    r = client.post("/api/applications/from-url",
                    json={"url": "https://example.com/empty"}, headers=auth_headers)
    assert r.status_code == 400


def test_from_url_non_html_400(client, auth_headers, monkeypatch):
    _fake_http(monkeypatch, "%PDF-1.4...", content_type="application/pdf")
    r = client.post("/api/applications/from-url",
                    json={"url": "https://example.com/f.pdf"}, headers=auth_headers)
    assert r.status_code == 400
