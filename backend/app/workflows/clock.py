"""UTC time helpers. All lease/deadline math goes through here so tests can
freeze or advance time deterministically (monkeypatch ``utcnow``)."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    """Normalize DB-loaded datetimes (naive on SQLite) for comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
