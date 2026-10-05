"""Auth primitives with ZERO extra dependencies (stdlib only).

Passwords: PBKDF2-HMAC-SHA256, 200k rounds, per-user salt.
Tokens: HS256 JWT, hand-rolled over hmac/base64/json (~40 lines).
Swap for passlib/pyjwt later without touching callers (same function names).
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

_ROUNDS = 200_000


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _ROUNDS)
    return f"pbkdf2_sha256${_ROUNDS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, rounds_s, salt, hex_dk = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds_s))
        return hmac.compare_digest(dk.hex(), hex_dk)
    except Exception:
        return False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(user_id: str, secret: str, expiry_min: int) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(
        json.dumps({"sub": user_id, "exp": int(time.time()) + expiry_min * 60}).encode()
    )
    sig = _b64url(hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def decode_token(token: str, secret: str) -> str:
    """Return user_id or raise ValueError (bad signature / expired / malformed)."""
    try:
        header, payload, sig = token.split(".")
        expected = _b64url(
            hmac.new(secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig, expected):
            raise ValueError("invalid signature")
        data = json.loads(_unb64url(payload))
        if data.get("exp", 0) < time.time():
            raise ValueError("token expired")
        return str(data["sub"])
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"malformed token: {e}") from e
