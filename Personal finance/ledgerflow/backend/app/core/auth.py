"""
Auth core
=========
Password hashing, session creation/lookup, and the `get_current_user`
FastAPI dependency used to protect every domain router.

Sessions are opaque bearer tokens handed to the browser as an httponly
cookie. Only a SHA-256 hash of the token is stored server-side, so a
database dump alone can't be replayed as a live session.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session as DBSession

from app.core.database import get_db
from app.models.models import Session as SessionModel, User

SESSION_COOKIE_NAME = "session_token"
SESSION_TTL_DAYS = 30

# The EC2 deployment is still plain HTTP (no domain/HTTPS yet — see
# RECAP.md), so the `secure` cookie flag must stay off until that changes,
# otherwise the browser would silently refuse to send the cookie at all.
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"

# Login lockout: after this many consecutive failed attempts, the account is
# locked for LOCKOUT_MINUTES. Both counters reset on a successful login.
MAX_FAILED_LOGIN_ATTEMPTS = int(os.getenv("MAX_FAILED_LOGIN_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))

# Idle session timeout — independent of SESSION_TTL_DAYS (the absolute
# cap). A session whose last authenticated request was more than this many
# minutes ago is treated as expired even if it's well within its 30-day TTL.
SESSION_IDLE_TIMEOUT_MINUTES = int(os.getenv("SESSION_IDLE_TIMEOUT_MINUTES", "30"))


def _as_aware_utc(dt: datetime) -> datetime:
    """SQLite (test suite only) doesn't round-trip tzinfo on DateTime(timezone=True)
    columns the way Postgres does — treat a naive value as UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: DBSession, user: User) -> str:
    """Create a new session for `user` and return the raw (unhashed) token."""
    token = secrets.token_hex(32)
    session = SessionModel(
        user_id    = user.id,
        token_hash = hash_token(token),
        expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS),
    )
    db.add(session)
    db.commit()
    return token


def is_locked_out(user: User) -> bool:
    if user.locked_until is None:
        return False
    return _as_aware_utc(user.locked_until) > datetime.now(timezone.utc)


def register_failed_login(db: DBSession, user: User) -> None:
    """Increment the failed-attempt counter and lock the account once the
    threshold is hit. Called on every wrong-password login attempt."""
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)
    db.commit()


def register_successful_login(db: DBSession, user: User) -> None:
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME, token,
        httponly=True, secure=SESSION_COOKIE_SECURE, samesite="lax",
        max_age=SESSION_TTL_DAYS * 24 * 3600,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME)


def get_current_user(request: Request, db: DBSession = Depends(get_db)) -> User:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session = db.query(SessionModel).filter(SessionModel.token_hash == hash_token(token)).first()
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")

    now = datetime.now(timezone.utc)
    expires_at = _as_aware_utc(session.expires_at)

    if expires_at < now:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired")

    last_seen_at = _as_aware_utc(session.last_seen_at)
    idle_cutoff = now - timedelta(minutes=SESSION_IDLE_TIMEOUT_MINUTES)
    if last_seen_at < idle_cutoff:
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired due to inactivity")

    session.last_seen_at = now
    db.commit()

    return session.user
