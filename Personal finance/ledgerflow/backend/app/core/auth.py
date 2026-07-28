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

    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        # SQLite (test suite only) doesn't round-trip tzinfo on DateTime(timezone=True)
        # columns the way Postgres does — treat a naive value as UTC.
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Session expired")

    return session.user
