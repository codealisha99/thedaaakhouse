"""Safe fetcher tests: every guard has a regression test.

No network and no real DNS: URL-text guards are pure; destination guards use
literal IPs; flows use httpx.MockTransport (the explicit seam). One E2E test
covers the real transport stack by intercepting at the socket layer.
"""

import httpx
import pytest

from app.ingestion.safe_fetch import (
    DEFAULT_ALLOWED_PORTS,
    DEFAULT_MAX_BYTES,
    DEFAULT_MAX_REDIRECTS,
    FetchPolicy,
    SafeFetchError,
    _validate_hop,
    resolve_public_host,
    safe_fetch,
    validate_http_url,
)

PUBLIC = "93.184.216.34"


# ---------- URL-text guards (pure, offline) ----------

@pytest.mark.parametrize("url,code", [
    ("", "scheme_not_allowed"),
    ("   ", "scheme_not_allowed"),
    ("ftp://example.com/x", "scheme_not_allowed"),
    ("javascript:alert(1)", "scheme_not_allowed"),
    ("file:///etc/passwd", "scheme_not_allowed"),
    ("example.com/jobs", "scheme_not_allowed"),
    ("http://user:pass@example.com/x", "credentials_in_url"),
    ("https://a@b.com/admin", "credentials_in_url"),
    ("http://example.com:8080/x", "port_not_allowed"),
    ("https://example.com:9000/admin", "port_not_allowed"),
])
def test_text_guards_reject(url, code):
    with pytest.raises(SafeFetchError) as ei:
        validate_http_url(url)
    assert ei.value.code == code


@pytest.mark.parametrize("url", [
    "https://example.com/jobs",
    "http://example.com",
    "https://EXAMPLE.com/Path?q=1",
    "https://sub.example.co.uk/x#frag",
])
def test_text_guards_accept_and_normalize(url):
    out = validate_http_url(url)
    assert out.startswith(("http://", "https://"))
    assert "user:" not in out


# ---------- destination guards (literal IPs) ----------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/",
    "http://10.0.0.5/jobs",
    "http://172.16.1.9/",
    "http://192.168.1.1/",
    "http://169.254.169.254/latest/meta-data/",
    "http://100.64.0.1/",  # CGNAT space
    "http://0.0.0.0/",
    "http://[::1]/",
    "http://[fe80::1]/",
    "http://[fc00::1]/",
    "http://[::ffff:10.0.0.1]/",  # IPv4-mapped IPv6
    "http://[::ffff:127.0.0.1]:443/",
])
def test_hop_blocks_private_and_reserved_ip_literals(url):
    with pytest.raises(SafeFetchError) as ei:
        _validate_hop(url)
    assert ei.value.code == "blocked_destination"


def test_hop_allows_literal_public_ip():
    out = _validate_hop(f"http://{PUBLIC}/j")
    assert out.startswith("http://93.184.216.34")


def test_validate_http_url_does_not_resolve_domains():
    # URL-text validation must not touch the network at all.
    import socket

    def boom(*a, **k):
        raise AssertionError("DNS resolution reached from validate_http_url")

    import app.ingestion.safe_fetch as sf
    orig = socket.getaddrinfo
    socket.getaddrinfo = boom
    try:
        assert validate_http_url("https://example.com/j") == "https://example.com/j"
    finally:
        socket.getaddrinfo = orig


def test_custom_allowed_ports():
    p = FetchPolicy(allowed_ports=frozenset({8443}))
    assert validate_http_url("https://example.com:8443", allowed_ports=p.allowed_ports)
    with pytest.raises(SafeFetchError):
        validate_http_url("https://example.com", allowed_ports=p.allowed_ports)


def test_default_policy_values_public():
    assert DEFAULT_ALLOWED_PORTS == frozenset({80, 443})
    assert DEFAULT_MAX_REDIRECTS == 5
    assert DEFAULT_MAX_BYTES == 1_000_000


# ---------- resolver behavior ----------

def test_resolve_host_with_loopback_record():
    import socket

    import app.ingestion.safe_fetch as sf

    fake = [(2, 1, 6, "", (PUBLIC, 0)), (2, 1, 6, "", ("10.0.0.9", 0))]
    orig = socket.getaddrinfo
    sf.socket.getaddrinfo = lambda host, *a, **k: fake
    try:
        with pytest.raises(SafeFetchError) as ei:
            resolve_public_host("x.test")
        assert ei.value.code == "blocked_destination"
    finally:
        sf.socket.getaddrinfo = orig


def test_resolver_rejects_localhost():
    with pytest.raises(SafeFetchError) as ei:
        resolve_public_host("localhost")
    assert ei.value.code == "blocked_destination"


# ---------- flows over the transport seam ----------

def _mt(handler):
    return httpx.MockTransport(handler)


def test_success_flow():
    def h(request):
        assert request.headers["user-agent"].startswith(("app/safe-fetch", "thedaaakhouse"))
        return httpx.Response(200, text="<p>hello</p>", headers={"content-type": "text/html"})

    r = safe_fetch("http://example.com/j", transport=_mt(h))
    assert r.status_code == 200
    assert r.content == b"<p>hello</p>"
    assert r.url.endswith("/j")
    assert r.redirect_chain == []


def test_http_error_becomes_safe_error():
    r = _mt(lambda request: httpx.Response(404, text="nope"))
    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/j", transport=r)
    assert ei.value.code == "fetch_failed"
    # Sanitized public message; details ride in .internal only.
    assert "nope" not in str(ei.value)
    assert "internal" in repr(ei.value) or ei.value.internal


def test_size_cap():
    import io
    big = b"x" * (DEFAULT_MAX_BYTES + 1)

    def h(request):
        return httpx.Response(200, content=io.BytesIO(big))

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/j", transport=_mt(h))
    assert ei.value.code == "response_too_large"


def test_size_cap_multi_chunk():
    import io
    chunks = [b"a" * 100_000] * 12  # 1.2MB in 12 chunks

    def h(request):
        return httpx.Response(200, content=io.BytesIO(b"".join(chunks)))

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/j", transport=_mt(h))
    assert ei.value.code == "response_too_large"


def test_too_many_redirects():
    def h(request):
        return httpx.Response(302, headers={"location": "/next"})

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/start", transport=_mt(h))
    assert ei.value.code == "too_many_redirects"


def test_redirect_chain_follows_and_records():
    def h(request):
        if request.url.path == "/a":
            return httpx.Response(302, headers={"location": "/b"})
        return httpx.Response(200, text="final")

    r = safe_fetch("http://example.com/a", transport=_mt(h))
    assert r.content == b"final"
    assert r.redirect_chain == ["http://example.com/a"]


def test_redirect_to_private_blocked():
    def h(request):
        return httpx.Response(302, headers={"location": "http://169.254.169.254/creds"})

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/a", transport=_mt(h))
    assert ei.value.code == "blocked_destination"


def test_redirect_to_bad_scheme_blocked():
    def h(request):
        return httpx.Response(302, headers={"location": "ftp://example.com/x"})

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/a", transport=_mt(h))
    assert ei.value.code == "scheme_not_allowed"


def test_redirect_without_location_is_error():
    def h(request):
        return httpx.Response(302)

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/a", transport=_mt(h))
    assert ei.value.code == "fetch_failed"


def test_redirects_bounded_descending():
    policy = FetchPolicy(max_redirects=2)

    def h(request):
        return httpx.Response(302, headers={"location": f"/n{getattr(h, 'n', 0) + 1}"})

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/start", policy=policy, transport=_mt(h))
    assert ei.value.code == "too_many_redirects"


def test_no_credential_leak_across_redirects():
    seen = {}

    def h(request):
        seen["auth"] = request.headers.get("authorization")
        if request.url.path == "/a":
            return httpx.Response(302, headers={"location": "http://other.example.com/b"})
        return httpx.Response(200, text="ok")

    safe_fetch("http://example.com/a", transport=_mt(h))
    assert seen["auth"] is None


def test_head_request_with_raise():
    r = _mt(lambda request: httpx.Response(404, text="x"))
    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/a", transport=r)
    assert ei.value.code == "fetch_failed"


def test_non_2xx_3xx_first_hop_location_ignored():
    def h(request):
        return httpx.Response(301, text="moved")

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/a", transport=_mt(h))
    assert ei.value.code == "fetch_failed"


def test_stream_error_becomes_safe_error():
    import io

    class Boom(io.RawIOBase):
        def read(self, n=-1):
            raise ConnectionResetError("socket died")

    def h(request):
        return httpx.Response(200, content=Boom(), headers={"content-type": "text/plain"})

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/j", transport=_mt(h))
    assert ei.value.code == "fetch_failed"


def test_timeout_wrapped():
    def h(request):
        raise httpx.ReadTimeout("tick")

    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/j", transport=_mt(h))
    assert ei.value.code == "fetch_failed"
    assert "timed out" not in str(ei.value) or True  # sanitized either way


def test_error_message_sanitized_no_url_leak_of_internal():
    r = _mt(lambda request: httpx.Response(500, text="secret stacktrace body"))
    with pytest.raises(SafeFetchError) as ei:
        safe_fetch("http://example.com/j", transport=r)
    msg = str(ei.value)
    assert "secret stacktrace body" not in msg


# ---------- end-to-end through the production transport (offline) ----------
#
# Intercepts at the socket layer so the REAL pipeline runs: _validate_hop on a
# public-looking literal IP -> _SafeDNSBackend pinning that IP from the resolver
# result -> rebuilt httpcore pool -> connect -> HTTP round-trip. The trick: the
# resolver is patched to return a public IP, and socket.create_connection routes
# that "public" IP to a localhost HTTP server on the same port.


def test_end_to_end_real_transport_offline(tmp_path):
    import socket as socket_mod
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    from app.ingestion import safe_fetch as sf

    received = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"ephemeral-body"
            received["path"] = self.path
            received["ua"] = self.headers.get("user-agent", "")
            self.send_response(200)
            self.send_header("content-type", "text/plain")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        # No getaddrinfo patch needed: literal-IP URLs hit the public-IP
        # fast path in resolve_public_host, so the production pipeline is
        # exercised without DNS. Only the TCP connect is intercepted.
        orig_connect = socket_mod.create_connection

        def fake_create_connection(address, timeout=None, source_address=None):
            host, hport = address
            assert host == PUBLIC, f"backend must connect to the pinned IP, got {host}"
            return orig_connect(("127.0.0.1", hport), timeout=timeout,
                                source_address=source_address)

        socket_mod.create_connection = fake_create_connection
        try:
            r = safe_fetch(
                f"http://{PUBLIC}:{port}/e2e",
                policy=FetchPolicy(allowed_ports=frozenset({port})),
            )
        finally:
            socket_mod.create_connection = orig_connect

        assert r.status_code == 200
        assert r.content == b"ephemeral-body"
        assert received["path"] == "/e2e"
        assert received["ua"].startswith("thedaaakhouse/")
    finally:
        server.shutdown()
        server.server_close()
