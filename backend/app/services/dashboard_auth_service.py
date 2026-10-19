"""Passwordless WhatsApp proof, opaque sessions, and account ownership."""

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import DashboardLoginChallenge, DashboardSession, DashboardUser
from app.schemas.dashboard_auth import LoginChallengeRead

COOKIE_NAME = "ledger_session"


class DashboardAuthError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def start_login(db: Session, phone: str, client_address: str) -> LoginChallengeRead:
    if settings.dashboard_auth_mode != "whatsapp" or not settings.twilio_auth_token:
        raise DashboardAuthError("WhatsApp sign-in needs Twilio signature validation to be configured.", 503)
    bot = (settings.twilio_whatsapp_from or "").removeprefix("whatsapp:")
    if not re.fullmatch(r"\+[1-9]\d{6,14}", bot):
        raise DashboardAuthError("The WhatsApp bot number is not configured.", 503)
    now = utcnow()
    identity = "whatsapp:" + phone
    client_hash = digest(client_address)
    recent = db.query(DashboardLoginChallenge).filter(
        DashboardLoginChallenge.created_at >= now - timedelta(minutes=10)
    )
    # Database-backed limits survive process restarts. A proxy may group clients
    # under one address; do not trust arbitrary forwarded headers here.
    if (recent.filter(DashboardLoginChallenge.whatsapp_user_id == identity).count() >= 5
            or recent.filter(DashboardLoginChallenge.client_hash == client_hash).count() >= 30
            or recent.count() >= 500):
        raise DashboardAuthError("Too many sign-in requests. Please try again in ten minutes.", 429)
    db.query(DashboardLoginChallenge).filter(
        DashboardLoginChallenge.expires_at < now - timedelta(days=1)
    ).delete(synchronize_session=False)
    db.query(DashboardSession).filter(DashboardSession.expires_at <= now).delete(synchronize_session=False)
    code = secrets.token_hex(8).upper()
    poll_secret = secrets.token_urlsafe(32)
    challenge = DashboardLoginChallenge(
        id=str(uuid4()), whatsapp_user_id=identity, code_hash=digest(code),
        poll_secret_hash=digest(poll_secret), client_hash=client_hash,
        created_at=now, expires_at=now + timedelta(minutes=settings.dashboard_login_minutes),
    )
    db.add(challenge)
    db.commit()
    command = "login " + code
    return LoginChallengeRead(
        request_id=challenge.id, poll_secret=poll_secret, command=command,
        whatsapp_url="https://wa.me/" + bot[1:] + "?" + urlencode({"text": command}),
        expires_at=_utc(challenge.expires_at),
    )


def approve_login(db: Session, sender: str, code: str, *, verified_twilio: bool) -> str:
    # A forged development webhook must never grant access to financial records.
    if not verified_twilio or settings.dashboard_auth_mode != "whatsapp":
        return "Dashboard sign-in requires a verified Twilio webhook. Please contact the app owner."
    challenge = db.query(DashboardLoginChallenge).filter(
        DashboardLoginChallenge.code_hash == digest(code.upper())
    ).with_for_update().first()
    now = utcnow()
    if (challenge is None or challenge.consumed_at is not None
            or _utc(challenge.expires_at) <= now or challenge.whatsapp_user_id != sender):
        return "This sign-in code is invalid, expired, or for a different number. Start again in your dashboard."
    challenge.approved_at = now
    db.commit()
    return "Dashboard sign-in approved. Return to the browser where you requested this code. Only approve codes from your own browser."


def complete_login(db: Session, request_id: str, poll_secret: str):
    challenge = db.query(DashboardLoginChallenge).filter(
        DashboardLoginChallenge.id == request_id
    ).with_for_update().first()
    now = utcnow()
    if challenge is None or not hmac.compare_digest(challenge.poll_secret_hash, digest(poll_secret)):
        raise DashboardAuthError("Invalid sign-in request.", 401)
    if challenge.consumed_at is not None or _utc(challenge.expires_at) <= now:
        raise DashboardAuthError("Sign-in expired. Please start again.", 410)
    if challenge.approved_at is None:
        return None
    # The conditional update also prevents a double claim on databases without
    # SELECT FOR UPDATE support. It commits atomically with the new session.
    claimed = db.query(DashboardLoginChallenge).filter(
        DashboardLoginChallenge.id == request_id,
        DashboardLoginChallenge.consumed_at.is_(None),
        DashboardLoginChallenge.expires_at > now,
        DashboardLoginChallenge.approved_at.is_not(None),
    ).update({DashboardLoginChallenge.consumed_at: now}, synchronize_session="fetch")
    if claimed != 1:
        raise DashboardAuthError("This sign-in was already completed. Start again.", 410)
    account = db.query(DashboardUser).filter(
        DashboardUser.whatsapp_user_id == challenge.whatsapp_user_id
    ).first()
    if account is None:
        # Different approved browser challenges may finish at the same time.
        try:
            with db.begin_nested():
                account = DashboardUser(id=str(uuid4()), whatsapp_user_id=challenge.whatsapp_user_id)
                db.add(account)
                db.flush()
        except IntegrityError:
            account = db.query(DashboardUser).filter(
                DashboardUser.whatsapp_user_id == challenge.whatsapp_user_id
            ).one()
    token = secrets.token_urlsafe(32)
    db.add(DashboardSession(
        token_hash=digest(token), account_id=account.id, created_at=now,
        expires_at=now + timedelta(hours=settings.dashboard_session_hours),
    ))
    db.commit()
    return token, account


def session_account(db: Session, token: str | None) -> DashboardUser:
    if not token or len(token) != 43:
        raise DashboardAuthError("Sign in to access your dashboard.", 401)
    account = db.query(DashboardUser).join(DashboardSession).filter(
        DashboardSession.token_hash == digest(token), DashboardSession.expires_at > utcnow()
    ).first()
    if account is None:
        raise DashboardAuthError("Your session expired. Please sign in again.", 401)
    return account


def revoke_session(db: Session, token: str | None) -> None:
    if token:
        db.query(DashboardSession).filter(DashboardSession.token_hash == digest(token)).delete()
        db.commit()
