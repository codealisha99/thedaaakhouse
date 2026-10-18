"""Narrow Gmail API boundary. Tokens are encrypted before persistence."""
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.outreach.delivery_models import EmailAccount, GmailOAuthState, OutreachDeliveryEvent, OutreachSend, OutreachSuppression
from app.outreach.models import OutreachDraft
from app.workflows.clock import aware, utcnow
from app.workflows.handlers import TaskPermanentFailure, register

SCOPES = ("openid", "email", "https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly")
AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
API = "https://gmail.googleapis.com/gmail/v1"


class GmailError(ValueError):
    pass


def _fernet() -> Fernet:
    key = get_settings().gmail_token_encryption_key.strip()
    if not key:
        raise GmailError("GMAIL_TOKEN_ENCRYPTION_KEY is not configured")
    try:
        return Fernet(key.encode())
    except Exception:
        raise GmailError("GMAIL_TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from None


def _configured():
    s = get_settings()
    if not s.gmail_enabled or not s.gmail_client_id or not s.gmail_client_secret:
        raise GmailError("Gmail delivery is disabled or OAuth credentials are missing")
    _fernet()
    return s


def begin_oauth(db: Session, user_id: str) -> str:
    s = _configured()
    raw = secrets.token_urlsafe(32)
    digest = hashlib.sha256(raw.encode()).hexdigest()
    db.add(GmailOAuthState(state_hash=digest, user_id=user_id, expires_at=utcnow() + timedelta(minutes=10)))
    db.commit()
    params = {"client_id": s.gmail_client_id, "redirect_uri": s.gmail_redirect_uri,
              "response_type": "code", "scope": " ".join(SCOPES), "access_type": "offline",
              "include_granted_scopes": "true", "prompt": "consent", "state": raw}
    return AUTH + "?" + urlencode(params)


def complete_oauth(db: Session, state: str, code: str) -> str:
    s = _configured()
    digest = hashlib.sha256(state.encode()).hexdigest()
    row = db.query(GmailOAuthState).filter_by(state_hash=digest).with_for_update().first()
    if row is None or aware(row.expires_at) <= utcnow():
        raise GmailError("OAuth state is invalid or expired")
    user_id = row.user_id
    db.delete(row)
    db.commit()  # one-time use, including provider failure
    response = httpx.post(TOKEN, data={"code": code, "client_id": s.gmail_client_id,
        "client_secret": s.gmail_client_secret, "redirect_uri": s.gmail_redirect_uri,
        "grant_type": "authorization_code"}, timeout=15)
    if response.status_code != 200:
        raise GmailError("Google OAuth code exchange failed")
    tokens = response.json()
    refresh = tokens.get("refresh_token")
    scopes = set(tokens.get("scope", "").split())
    if not refresh or not set(SCOPES).issubset(scopes):
        raise GmailError("Google did not grant all required Gmail scopes and offline access; reconnect with consent")
    who = httpx.get("https://openidconnect.googleapis.com/v1/userinfo",
                    headers={"Authorization": f"Bearer {tokens['access_token']}"}, timeout=15)
    if who.status_code != 200 or not who.json().get("email") or not who.json().get("email_verified"):
        raise GmailError("Google account identity could not be verified")
    account = db.query(EmailAccount).filter_by(user_id=user_id).first()
    values = dict(provider="gmail", email=who.json()["email"], refresh_token_ciphertext=_fernet().encrypt(refresh.encode()).decode(), status="connected", scopes=sorted(scopes))
    if account is None:
        account = EmailAccount(user_id=user_id, **values)
        db.add(account)
    else:
        for key, value in values.items(): setattr(account, key, value)
    db.commit()
    return account.email


def disconnect(db: Session, user_id: str) -> bool:
    account = db.query(EmailAccount).filter_by(user_id=user_id, status="connected").first()
    if not account: return False
    try:
        token = _fernet().decrypt(account.refresh_token_ciphertext.encode()).decode()
        httpx.post("https://oauth2.googleapis.com/revoke", data={"token": token}, timeout=10)
    except (InvalidToken, httpx.HTTPError):
        pass
    account.status = "revoked"
    account.refresh_token_ciphertext = ""
    db.commit()
    return True


def _access_token(account: EmailAccount) -> str:
    s = _configured()
    try: refresh = _fernet().decrypt(account.refresh_token_ciphertext.encode()).decode()
    except (InvalidToken, ValueError): raise GmailError("stored Gmail credential cannot be decrypted; reconnect") from None
    r = httpx.post(TOKEN, data={"client_id": s.gmail_client_id, "client_secret": s.gmail_client_secret,
        "refresh_token": refresh, "grant_type": "refresh_token"}, timeout=15)
    if r.status_code != 200: raise GmailError("Gmail credential refresh failed; reconnect the account")
    return r.json()["access_token"]


def _api(account: EmailAccount, method: str, path: str, **kwargs):
    token = _access_token(account)
    r = httpx.request(method, API + path, headers={"Authorization": f"Bearer {token}"}, timeout=20, **kwargs)
    if r.status_code >= 400: raise GmailError(f"Gmail API returned HTTP {r.status_code}")
    return r.json() if r.content else {}


def _mail(snapshot: dict, message_id: str) -> str:
    msg = MIMEMultipart()
    msg["To"] = snapshot["recipient_email"]
    msg["Subject"] = snapshot["subject"]
    msg["Message-ID"] = message_id
    msg["X-Thedaaakhouse-Payload"] = snapshot["payload_sha256"]
    msg.attach(MIMEText(snapshot["body"], "plain", "utf-8"))
    if snapshot.get("attachment_text"):
        from email.mime.application import MIMEApplication
        part = MIMEApplication(snapshot["attachment_text"].encode(), _subtype="octet-stream")
        part.add_header("Content-Disposition", "attachment", filename=snapshot.get("attachment_name") or "resume.txt")
        msg.attach(part)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_payload(db: Session, user_id: str, task_id: str, draft_id: str, payload_sha256: str) -> dict:
    if not get_settings().gmail_enabled:
        raise TaskPermanentFailure("gmail_disabled", "Gmail sending is disabled by the provider kill switch")
    account = db.query(EmailAccount).filter_by(user_id=user_id, status="connected").with_for_update().first()
    if not account: raise TaskPermanentFailure("gmail_disconnected", "Connect a Gmail account before sending")
    draft = db.query(OutreachDraft).filter_by(id=draft_id, user_id=user_id).first()
    if not draft: raise TaskPermanentFailure("draft_not_found", "outreach draft not found")
    if draft.payload_sha256 != payload_sha256:
        raise TaskPermanentFailure("stale_draft", "draft changed after approval; review and approve the new payload")
    snapshot = {"draft_id": draft.id, "payload_sha256": draft.payload_sha256, "recipient_email": draft.recipient_email,
                "subject": draft.subject, "body": draft.body, "attachment_name": draft.attachment_name,
                "attachment_text": draft.attachment_text, "revision": draft.revision}
    email = draft.recipient_email.lower()
    if db.query(OutreachSuppression).filter_by(user_id=user_id, email=email).first():
        raise TaskPermanentFailure("recipient_suppressed", "recipient is suppressed")
    existing = db.query(OutreachSend).filter_by(user_id=user_id, draft_id=draft_id, payload_sha256=payload_sha256).first()
    if existing and existing.status in ("accepted", "delivered", "replied", "bounced"):
        return {"send_id": existing.id, "status": existing.status, "provider_message_id": existing.provider_message_id}
    if existing and existing.status in ("unknown", "sending"):
        # Search Gmail by the stable RFC822 Message-ID before deciding that an
        # ambiguous request was absent. Never repeat messages.send here.
        existing.status = "unknown"
        db.commit()
        try:
            found = _api(account, "GET", "/users/me/messages", params={"q": f"rfc822msgid:{existing.message_id_header.strip('<>')}", "maxResults": 1}).get("messages", [])
            if found:
                existing.provider_message_id = found[0].get("id")
                existing.thread_id = found[0].get("threadId")
                existing.status = "accepted"
                db.commit()
                return {"send_id": existing.id, "status": "accepted", "provider_message_id": existing.provider_message_id}
        except (GmailError, httpx.TimeoutException, httpx.TransportError):
            pass
        return {"send_id": existing.id, "status": "unknown", "provider_message_id": existing.provider_message_id}
    from datetime import datetime
    now = utcnow()
    local_hour = now.hour  # UTC; predictable and documented
    s = get_settings()
    if s.gmail_quiet_start_hour > s.gmail_quiet_end_hour:
        quiet = local_hour >= s.gmail_quiet_start_hour or local_hour < s.gmail_quiet_end_hour
    else: quiet = s.gmail_quiet_start_hour <= local_hour < s.gmail_quiet_end_hour
    if quiet: raise TaskPermanentFailure("quiet_hours", "sending is paused during configured UTC quiet hours")
    if db.query(OutreachSend).filter(OutreachSend.user_id == user_id, OutreachSend.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0), OutreachSend.status.in_(["sending", "unknown", "accepted", "delivered", "replied", "bounced"])).count() >= max(1, s.gmail_daily_limit):
        raise TaskPermanentFailure("daily_limit", "Gmail daily send limit reached")
    if existing is None:
        message_id = f"<{hashlib.sha256(task_id.encode()).hexdigest()}@thedaaakhouse.local>"
        existing = OutreachSend(user_id=user_id, draft_id=draft_id, task_id=task_id, payload_sha256=payload_sha256,
            payload_snapshot=snapshot, message_id_header=message_id, status="sending")
        db.add(existing)
    else:
        # A prior attempt might have crossed the provider boundary. Never retry a send automatically.
        existing.status = "unknown"
        db.commit()
        return {"send_id": existing.id, "status": "unknown", "provider_message_id": None}
    db.commit()
    try:
        response = _api(account, "POST", "/users/me/messages/send", json={"raw": _mail(snapshot, existing.message_id_header)})
    except (GmailError, httpx.TimeoutException, httpx.TransportError):
        existing.status = "unknown"
        db.commit()
        return {"send_id": existing.id, "status": "unknown", "provider_message_id": None}
    existing.status = "accepted"
    existing.provider_message_id = response.get("id")
    existing.thread_id = response.get("threadId")
    db.add(OutreachDeliveryEvent(user_id=user_id, send_id=existing.id, event_key=f"accepted:{response.get('id')}", kind="accepted", occurred_at=now, detail={"provider": "gmail"}))
    db.commit()
    return {"send_id": existing.id, "status": "accepted", "provider_message_id": existing.provider_message_id}


@register("outreach.send", external_side_effect=True, summary="Send approved immutable draft via connected Gmail")
def _send_task(payload: dict, ctx):
    return send_payload(ctx.db, ctx.task.user_id, ctx.task.id, payload["draft_id"], payload["payload_sha256"])


def add_suppression(db: Session, user_id: str, email: str, reason: str, send_id: str | None = None):
    email = email.strip().lower()
    if reason not in {"opt_out", "bounce", "manual"}: raise GmailError("invalid suppression reason")
    row = db.query(OutreachSuppression).filter_by(user_id=user_id, email=email).first()
    if row is None:
        db.add(OutreachSuppression(user_id=user_id, email=email, reason=reason, source_send_id=send_id))
    else:
        row.reason = reason
        row.source_send_id = send_id or row.source_send_id
    db.commit()


def sync_replies(db: Session, user_id: str) -> int:
    account = db.query(EmailAccount).filter_by(user_id=user_id, status="connected").first()
    if not account: raise GmailError("Gmail account is not connected")
    sends = db.query(OutreachSend).filter(OutreachSend.user_id == user_id, OutreachSend.thread_id.is_not(None), OutreachSend.status.in_(["accepted", "unknown"])).all()
    count = 0
    for send in sends:
        result = _api(account, "GET", f"/users/me/threads/{send.thread_id}", params={"format": "full"})
        for item in result.get("messages", []):
            mid = item.get("id")
            if not mid or db.query(OutreachDeliveryEvent).filter_by(user_id=user_id, event_key=f"gmail:{mid}").first(): continue
            message = item
            if "SENT" in (message.get("labelIds") or []): continue
            headers = {h["name"].lower(): h["value"] for h in message.get("payload", {}).get("headers", [])}
            sender = headers.get("from", "").lower()
            if account.email.lower() in sender: continue
            body_parts = []
            def gather(part):
                data = (part.get("body") or {}).get("data")
                if data:
                    try: body_parts.append(base64.urlsafe_b64decode(data + "==").decode("utf-8", "ignore"))
                    except Exception: pass
                for child in part.get("parts", []): gather(child)
            gather(message.get("payload", {}))
            body_text = " ".join(body_parts).lower()
            kind = "bounce" if ("mailer-daemon" in sender or "delivery status notification" in headers.get("subject", "").lower()) else "reply"
            opt_out = kind == "reply" and any(phrase in body_text for phrase in ("unsubscribe", "remove me", "stop emailing", "do not contact"))
            db.add(OutreachDeliveryEvent(user_id=user_id, send_id=send.id, event_key=f"gmail:{mid}", kind=kind, occurred_at=utcnow(), detail={"provider_message_id": mid}))
            send.status = "bounced" if kind == "bounce" else "replied"
            if kind == "bounce": add_suppression(db, user_id, send.payload_snapshot["recipient_email"], "bounce", send.id)
            if opt_out: add_suppression(db, user_id, send.payload_snapshot["recipient_email"], "opt_out", send.id)
            count += 1
        db.commit()
    return count
