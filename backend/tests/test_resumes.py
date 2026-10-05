"""Resume upload + storage tests (authenticated)."""


def test_upload_txt_resume(client, auth_headers):
    r = client.post(
        "/api/resumes",
        files={"file": ("resume.txt", b"Jane Doe\nSenior AI Engineer\nBuilt RAG pipelines.", "text/plain")},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["filename"] == "resume.txt"
    assert body["parse_status"] == "parsed"
    assert body["id"]

    r2 = client.get(f"/api/resumes/{body['id']}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]


def test_upload_empty_file_rejected(client, auth_headers):
    r = client.post(
        "/api/resumes", files={"file": ("empty.txt", b"", "text/plain")}, headers=auth_headers
    )
    assert r.status_code == 400


def test_get_missing_resume_404(client, auth_headers):
    assert client.get("/api/resumes/does-not-exist", headers=auth_headers).status_code == 404


def test_invalid_extension_rejected(client, auth_headers):
    r = client.post(
        "/api/resumes",
        files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
        headers=auth_headers,
    )
    assert r.status_code == 400
    assert "unsupported file type" in r.json()["detail"]


def test_invalid_content_type_rejected(client, auth_headers):
    r = client.post(
        "/api/resumes",
        files={"file": ("resume.txt", b"text", "image/png")},
        headers=auth_headers,
    )
    assert r.status_code == 400


def test_malicious_filename_sanitized(client, auth_headers):
    r = client.post(
        "/api/resumes",
        files={"file": ("../../etc/passwd.txt", b"Jane Doe", "text/plain")},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    assert "/" not in r.json()["filename"]


def test_oversized_upload_rejected(client, auth_headers, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("MAX_UPLOAD_MB", "0")
    get_settings.cache_clear()
    try:
        r = client.post(
            "/api/resumes",
            files={"file": ("big.txt", b"x" * 100, "text/plain")},
            headers=auth_headers,
        )
        assert r.status_code == 400
    finally:
        get_settings.cache_clear()


def test_upload_requires_auth(client):
    r = client.post("/api/resumes", files={"file": ("a.txt", b"x", "text/plain")})
    assert r.status_code == 401
