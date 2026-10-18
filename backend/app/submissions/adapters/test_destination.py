"""The test-destination adapter.

The only live submission path in this system, and only against an exact,
operator-configured destination (``settings.submission_test_url``) that the
operator runs and controls — a test application endpoint, never a real
vacancy. The transport is injectable so tests are fully deterministic
HTTP fixtures.

Protocol:
- ``POST <destination>`` with JSON ``{submission_id, idempotency_key,
  artifact_sha256, payload_sha256, answers, resume_text}``. A new external
  receipt is the JSON body; HTTP 4xx is a definitive rejection; read/network
  timeouts are ambiguous (state -> unknown, reconciliation decides).
- ``GET <destination>?submission_id=`` resolves a receipt for
  reconciliation. 404 means the submission never arrived.
"""

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.submissions.adapters import (
    Adapter,
    AdapterUnavailable,
    SubmissionRejected,
    SubmissionTimeout,
)

log = get_logger(__name__)

# Tests pin a canned httpx transport here; None = live HTTP.
_transport_override: "httpx.BaseTransport | None" = None

#: Required questions this destination's form asks. Sensitive/screening
#: questions (work authorization, sponsorship) are NEVER prefilled or
#: inferred — they block the submission until the user answers them.
REQUIRED_QUESTIONS: list[dict] = [
    {"id": "full_name", "label": "Full legal name", "required": True},
    {"id": "email", "label": "Contact email", "required": True},
    {"id": "work_authorized", "label": "Are you legally authorized to work in this location?", "required": True},
    {"id": "sponsorship_required", "label": "Will you now or in the future require sponsorship?", "required": True},
]

_READ_TIMEOUT = httpx.ReadTimeout
_CONNECT_TIMEOUT = httpx.ConnectTimeout


def _client() -> httpx.Client:
    settings = get_settings()
    if not settings.submission_test_url:
        raise AdapterUnavailable("SUBMISSION_TEST_URL is not configured")
    if _transport_override is not None:
        return httpx.Client(transport=_transport_override, timeout=settings.submission_timeout_s)
    return httpx.Client(timeout=settings.submission_timeout_s)


def _post(payload: dict, destination: str, idempotency_key: str) -> dict:
    try:
        with _client() as client:
            resp = client.post(
                destination,
                json=payload,
                headers={"Idempotency-Key": idempotency_key},
            )
    except (_READ_TIMEOUT, _CONNECT_TIMEOUT, httpx.TimeoutException) as exc:
        raise SubmissionTimeout(f"destination did not answer in time: {type(exc).__name__}") from None
    except httpx.HTTPError as exc:
        # Once a request has entered the transport, a dropped connection or
        # protocol error does not prove the server failed to process it.
        # Treat it as ambiguous so the worker never blindly sends it again.
        raise SubmissionTimeout(
            f"destination connection ended ambiguously: {type(exc).__name__}"
        ) from None
    if 200 <= resp.status_code < 300:
        try:
            body = resp.json()
        except ValueError:
            raise SubmissionTimeout("destination accepted the request but returned invalid JSON") from None
        if not isinstance(body, dict) or "receipt_id" not in body:
            raise SubmissionTimeout("destination accepted the request but returned a malformed receipt")
        if body.get("submission_id") not in (None, idempotency_key):
            raise SubmissionTimeout("destination returned a receipt for a different submission")
        return body
    if 400 <= resp.status_code < 500:
        raise SubmissionRejected(
            f"destination_http_{resp.status_code}",
            str(resp.text or "")[:300] or "destination refused the submission",
        )
    # 5xx: transient — safe to retry because the idempotency key means the
    # destination collapses duplicate deliveries.
    raise SubmissionRejected(  # refined by the service into a transient error
        f"destination_http_{resp.status_code}", "destination server error", transient=True
    )


def _get_receipt(destination: str, submission_id: str) -> dict:
    """Reconciliation lookup with explicit outcome status.

    Returns {"status": "found", "receipt": {...}} | {"status": "not_found"} |
    {"status": "unreachable"}. Only ``found`` receipts flip state;
    ``unreachable`` keeps the submission unknown.
    """
    try:
        with _client() as client:
            resp = client.get(destination, params={"submission_id": submission_id})
    except (httpx.TimeoutException, httpx.HTTPError):
        return {"status": "unreachable"}
    if resp.status_code == 200:
        try:
            body = resp.json()
        except ValueError:
            return {"status": "unreachable"}
        if isinstance(body, dict) and body.get("submission_id") == submission_id:
            return {"status": "found", "receipt": body}
        return {"status": "not_found"}
    return {"status": "unreachable"}


def build_test_destination() -> Adapter:
    from app.core.config import get_settings

    configured = bool(get_settings().submission_test_url.strip())
    return Adapter(
        name="test_destination",
        live=configured,
        reason=(
            "configured test application destination"
            if configured
            else "set SUBMISSION_TEST_URL to enable; never points at a real vacancy"
        ),
        required_questions=REQUIRED_QUESTIONS,
        submit_fn=_post,
        reconcile_fn=_get_receipt,
    )
