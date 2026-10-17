"""Single safe HTTP fetcher for every user-supplied URL.

All external web fetches (job import, company research, discovery, contacts)
must go through this module. Guarantees:

- HTTP(S) only, allowed ports only (default 80/443), no embedded credentials.
- Destination checked at *connection* time: DNS is resolved here and the
  socket is pinned to a validated public address, so a redirect or a DNS
  rebinding trick cannot reach a private / loopback / link-local host.
- Every redirect hop is re-validated (scheme, port, credentials, destination).
- Response bodies are streamed and bounded (too-large downloads abort).
- Errors carry short sanitized messages; internal details stay out of API
  responses.

Treat anything fetched as untrusted input — it is never authorized to act.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpcore
import httpx

DEFAULT_ALLOWED_PORTS = frozenset({80, 443})
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_MAX_BYTES = 1_000_000
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_USER_AGENT = "thedaaakhouse/0.3 (+safe-fetch)"


class SafeFetchError(RuntimeError):
    """Failed/blocked fetch with a sanitized, user-safe message."""

    def __init__(self, message: str, code: str, internal: str | None = None):
        super().__init__(message)
        self.code = code
        self.internal = internal or message


@dataclass
class FetchResult:
    status_code: int
    url: str
    headers: dict[str, str]
    content: bytes
    redirect_chain: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- addresses

def _validate_ip(ip: ipaddress.IPAddress) -> ipaddress.IPAddress:
    """Fold IPv4-mapped IPv6 back to IPv4, then require a globally routable
    public address (blocks loopback, private, link-local incl. 169.254.169.254
    cloud metadata, multicast, reserved, shared CGNAT, unspecified, broadcast)."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    allowed = (
        ip.is_global
        and not ip.is_loopback
        and not ip.is_link_local
        and not ip.is_multicast
        and not ip.is_reserved
        and not ip.is_private
        and not ip.is_unspecified
    )
    if not allowed:
        raise SafeFetchError(
            f"refusing to fetch non-public address {ip}", code="blocked_destination"
        )
    return ip


def resolve_public_host(host: str) -> list[ipaddress.IPAddress]:
    """Resolve `host` and return pinned public addresses.

    Raises SafeFetchError when anything about the resolution is unsafe:
    unresolvable hosts, or any resolved address that is not public (one
    poisoned A record among many must not create a pivot).
    """
    host = (host or "").strip().strip("[]").lower()
    # Literal IP targets are validated directly — no resolution.
    try:
        literal = ipaddress.ip_address(host)
        return [_validate_ip(literal)]
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise SafeFetchError(
            f"could not resolve host '{host}'", code="unresolvable_host", internal=str(e)
        ) from e
    pinned: list[ipaddress.IPAddress] = []
    for info in infos:
        sockaddr = info[4]
        try:
            ip = ipaddress.ip_address(sockaddr[0])
        except ValueError:
            continue
        pinned.append(_validate_ip(ip))  # raises on first non-public entry
    if not pinned:
        raise SafeFetchError(f"no usable address for host '{host}'", code="unresolvable_host")
    unique: list[ipaddress.IPAddress] = []
    seen: set[str] = set()
    for ip in pinned:
        key = ip.exploded
        if key not in seen:
            seen.add(key)
            unique.append(ip)
    return unique


def _pinned_connect_address(ips: list[ipaddress.IPAddress]) -> str:
    return str(ips[0])


# ------------------------------------------------------------------- client

class _SafeDNSBackend(httpcore.SyncBackend):
    """httpcore network backend that validates + pins DNS at connect time.

    The name might resolve to one address while validation ran and another
    while httpx connects. Here validation and the socket connection use the
    same resolved address, eliminating DNS-rebinding / TOCTOU gaps.
    """

    def connect_tcp(self, host, port, timeout=None, local_address=None,
                    socket_options=None) -> httpcore.NetworkStream:
        ip = resolve_public_host(host)
        return super().connect_tcp(
            _pinned_connect_address(ip), port,
            timeout=timeout, local_address=local_address, socket_options=socket_options,
        )


class _SafeTransport(httpx.HTTPTransport):
    """httpx transport whose connection pool uses the DNS-pinning backend."""

    def __init__(self, **kwargs):
        limits = kwargs.get("limits") or httpx.Limits()
        super().__init__(**kwargs)
        # Rebuild the underlying pool with our backend; the default one was
        # created in super().__init__ without it. No proxies: trust_env=False.
        self._pool.close()
        self._pool = httpcore.ConnectionPool(
            max_connections=limits.max_connections,
            max_keepalive_connections=limits.max_keepalive_connections,
            keepalive_expiry=limits.keepalive_expiry,
            http2=kwargs.get("http2", False),
            uds=kwargs.get("uds"),
            local_address=kwargs.get("local_address"),
            retries=kwargs.get("retries", 0),
            socket_options=kwargs.get("socket_options"),
            network_backend=_SafeDNSBackend(),
        )


# ------------------------------------------------------------------- config

@dataclass(frozen=True)
class FetchPolicy:
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_bytes: int = DEFAULT_MAX_BYTES
    max_redirects: int = DEFAULT_MAX_REDIRECTS
    allowed_ports: frozenset[int] = DEFAULT_ALLOWED_PORTS
    user_agent: str = DEFAULT_USER_AGENT

    def __post_init__(self):
        if self.timeout_s <= 0 or self.max_bytes <= 0 or self.max_redirects < 0:
            raise ValueError("fetch policy: timeout/size must be positive, redirects >= 0")


# -------------------------------------------------------------- URL checks

def validate_http_url(url: str, *, allowed_ports: frozenset[int] = DEFAULT_ALLOWED_PORTS) -> str:
    """Validate the URL *text* only: scheme, port, credentials. No DNS."""
    url = (url or "").strip()
    try:
        parts = urlparse(url)
    except ValueError as e:
        raise SafeFetchError("invalid URL", code="invalid_url", internal=str(e)) from e
    if parts.scheme not in ("http", "https"):
        raise SafeFetchError(
            "URL must start with http:// or https://", code="scheme_not_allowed"
        )
    if parts.username or parts.password:
        raise SafeFetchError(
            "URLs with embedded credentials are not allowed", code="credentials_in_url"
        )
    host = (parts.hostname or "").strip().strip("[]").lower()
    if not host:
        raise SafeFetchError("URL has no host", code="invalid_url")
    port = parts.port  # raises ValueError for out-of-range ports
    if port is None:
        port = 443 if parts.scheme == "https" else 80
    if port not in allowed_ports:
        raise SafeFetchError(
            f"port {port} is not allowed (allowed: {sorted(allowed_ports)})",
            code="port_not_allowed",
            internal=str(parts),
        )
    return url


def _validate_hop(url: str, *, allowed_ports: frozenset[int] = DEFAULT_ALLOWED_PORTS) -> str:
    """Validate a URL hop from text only (scheme/port/credentials), plus any
    literal-IP host. Domain hosts are validated at connect time (DNS)."""
    url = validate_http_url(url, allowed_ports=allowed_ports)
    host = urlparse(url).hostname or ""
    try:
        literal = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return url
    _validate_ip(literal)  # raises blocked_destination for private targets
    return url


# ----------------------------------------------------------------- fetching

def safe_fetch(
    url: str,
    *,
    policy: FetchPolicy | None = None,
    transport: httpx.BaseTransport | None = None,
) -> FetchResult:
    """Fetch a URL through every guard. Raises SafeFetchError on any failure.

    `transport` is a test seam: a mock transport replaces network + DNS checks,
    so tests must keep using literal-IP URLs (URL-text checks still apply).
    """
    policy = policy or FetchPolicy()
    url = _validate_hop(url, allowed_ports=policy.allowed_ports)

    timeout = httpx.Timeout(policy.timeout_s, connect=min(policy.timeout_s, 10.0))
    client = httpx.Client(
        transport=transport or _SafeTransport(),
        timeout=timeout,
        follow_redirects=False,  # each hop validated manually below
        trust_env=False,  # never honor HTTP(S)_PROXY: proxies bypass local guards
        headers={"User-Agent": policy.user_agent, "Accept": "text/html,*/*"},
        http2=False,
    )
    chain: list[str] = []
    current = url
    try:
        for _hop in range(policy.max_redirects + 1):
            request = client.build_request("GET", current)
            try:
                response = client.send(request, stream=True)
            except SafeFetchError:
                raise
            except (httpx.HTTPError, OSError) as e:
                raise SafeFetchError(
                    "fetch failed (blocked, unreachable, or timeout)",
                    code="fetch_failed",
                    internal=f"{type(e).__name__}: {e}",
                ) from e
            if 300 <= response.status_code < 400 and response.headers.get("location"):
                chain.append(str(response.url))
                location = response.headers["location"]
                response.close()
                next_url = urljoin(str(response.request.url), location.strip())
                _validate_hop(next_url, allowed_ports=policy.allowed_ports)
                current = next_url
                continue
            return _read_bounded(response, policy, chain)
        raise SafeFetchError(
            f"too many redirects (limit {policy.max_redirects})", code="too_many_redirects"
        )
    finally:
        client.close()


def _read_bounded(response: httpx.Response, policy: FetchPolicy,
                  chain: list[str]) -> FetchResult:
    """Stream the response body, capping bytes (and abort on excess)."""
    chunks: list[bytes] = []
    total = 0
    try:
        response.raise_for_status()
        for chunk in response.iter_bytes(chunk_size=64 * 1024):
            total += len(chunk)
            if total > policy.max_bytes:
                raise SafeFetchError(
                    f"response exceeds {policy.max_bytes} byte limit",
                    code="response_too_large",
                )
            chunks.append(chunk)
    except SafeFetchError:
        raise
    except (httpx.HTTPError, OSError) as e:
        raise SafeFetchError(
            "fetch failed (blocked, unreachable, or timeout)",
            code="fetch_failed",
            internal=f"{type(e).__name__}: {e}",
        ) from e
    finally:
        response.close()
    headers = {k: v for k, v in response.headers.items()}
    return FetchResult(
        status_code=response.status_code,
        url=str(response.url),
        headers=headers,
        content=b"".join(chunks),
        redirect_chain=chain,
    )
