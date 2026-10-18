"""Submission adapters — the boundary between this app and apply destinations.

An adapter may only execute a live submission for a destination whose current
API access permits authenticated submission. Everything else — every real job
board and ATS today — gets a deterministic *manual handoff*: the frozen
package plus a concrete next step for the user. ``live`` capability is always
derived from configuration, never from ambition.

Deterministic testing: the test-destination adapter's HTTP transport is
injectable (``app.submissions.adapters.test_destination._transport_override``)
so the full submit path runs on canned responses without network or a real
destination. That is a fixture, not a live integration.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Adapter:
    name: str
    live: bool
    reason: str
    required_questions: list[dict]
    submit_fn: object | None = None
    reconcile_fn: object | None = None


class SubmissionRejected(Exception):
    """The destination refused the submission.

    ``transient=False``: definitive refusal, no retry. ``transient=True``:
    destination-side error (5xx) where duplicate deliveries collapse on the
    server's Idempotency-Key, so a bounded retry is safe.
    """

    def __init__(self, code: str, detail: str, transient: bool = False):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail
        self.transient = transient


class SubmissionTimeout(Exception):
    """Ambiguous: the request may have been processed. State -> unknown."""

    def __init__(self, detail: str = ""):
        super().__init__(detail or "submission timed out")
        self.detail = detail


class AdapterUnavailable(Exception):
    """No usable transport for this adapter right now."""


from app.submissions.adapters.manual import build_manual
from app.submissions.adapters.test_destination import build_test_destination


AVAILABLE_KINDS = ("manual", "test_destination")


def build(kind: str) -> "object | None":
    """Build the adapter named by `kind`, reflecting current configuration."""
    builders: dict[str, object] = {
        "manual": build_manual,
        "test_destination": build_test_destination,
    }
    builder = builders.get(kind)
    return builder() if builder is not None else None


def available_adapters() -> list["object"]:
    """Capabilities for every known adapter; only genuinely configured ones
    report ``live=True``. Unknown kinds are never invented into existence."""
    return [build_manual(), build_test_destination()]


def selection_for(destination_url: str | None) -> tuple[str, "object"]:
    """Pick the adapter for a destination.

    Returns (kind, adapter). Only an exact match with the configured test
    destination gets the live adapter; every other destination gets the
    manual-handoff adapter with actionable instructions.
    """
    from app.core.config import get_settings

    manual = build_manual()
    configured = get_settings().submission_test_url.strip()
    if configured and destination_url and destination_url.strip() == configured:
        return "test_destination", build_test_destination()
    return "manual", manual
