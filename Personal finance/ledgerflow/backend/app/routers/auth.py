"""
Auth router
===========
Endpoints:
  GET  /auth/status            – whether any account exists yet (public)
  POST /auth/register          – create a new account, with its own private
                                  data (public — registration is open)
  POST /auth/login              – exchange credentials for a session cookie (public)
  POST /auth/logout             – revoke the current session
  GET  /auth/me                 – current logged-in username
  POST /auth/change-password    – change the logged-in user's password
"""
import uuid
from datetime import datetime, timezone
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import (
    LOCKOUT_MINUTES,
    hash_token,
    clear_session_cookie,
    create_session,
    get_current_user,
    hash_password,
    is_locked_out,
    register_failed_login,
    register_successful_login,
    set_session_cookie,
    verify_password,
    SESSION_COOKIE_NAME,
    _as_aware_utc,
)
from app.core.database import get_db
from app.models.models import Session as SessionModel, User
from app.services.category_engine import seed_default_categories

router = APIRouter(prefix="/auth", tags=["Auth"])


class Credentials(BaseModel):
    username: str
    password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.get("/status", summary="Whether any account exists yet")
def auth_status(db: Session = Depends(get_db)):
    # Used by the frontend to decide whether to default a brand-new install
    # straight to the register form — registration itself stays open beyond
    # that, this isn't a gate.
    return {"initialized": db.query(User).first() is not None}


@router.post("/register", status_code=201, summary="Create a new account")
def register(body: Credentials, response: Response, db: Session = Depends(get_db)):
    if not body.username.strip() or len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Username is required and password must be at least 8 characters")

    username = body.username.strip()
    if db.query(User).filter(User.username == username).first() is not None:
        raise HTTPException(status_code=409, detail="That username is already taken")

    user = User(
        id            = uuid.uuid4(),
        username      = username,
        password_hash = hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    seed_default_categories(db, user.id)

    token = create_session(db, user)
    set_session_cookie(response, token)
    return {"username": user.username}


@router.post("/login", summary="Log in with username and password")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip()).first()

    if user and is_locked_out(user):
        remaining_minutes = ceil(
            (_as_aware_utc(user.locked_until) - datetime.now(timezone.utc)).total_seconds() / 60
        )
        raise HTTPException(
            status_code=423,
            detail=f"Too many failed attempts — try again in {max(remaining_minutes, 1)} minute(s)",
        )

    if not user or not verify_password(body.password, user.password_hash):
        if user:
            register_failed_login(db, user)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    register_successful_login(db, user)
    token = create_session(db, user)
    set_session_cookie(response, token)
    return {"username": user.username}


@router.post("/logout", summary="Log out and revoke the current session")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        db.query(SessionModel).filter(SessionModel.token_hash == hash_token(token)).delete()
        db.commit()
    clear_session_cookie(response)
    return {"status": "logged_out"}


@router.get("/me", summary="Current logged-in username")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username}


@router.post("/change-password", summary="Change the logged-in user's password")
def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=422, detail="New password must be at least 8 characters")

    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"status": "password_changed"}
