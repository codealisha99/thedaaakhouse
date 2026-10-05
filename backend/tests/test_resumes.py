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
