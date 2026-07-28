"""
Auth router
===========
Endpoints:
  GET  /auth/status   – whether a bootstrap account exists yet (public)
  POST /auth/register – create the (single) bootstrap account (public, once)
  POST /auth/login    – exchange credentials for a session cookie (public)
  POST /auth/logout   – revoke the current session
  GET  /auth/me        – current logged-in username
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import (
    hash_token,
    clear_session_cookie,
    create_session,
    get_current_user,
    hash_password,
    set_session_cookie,
    verify_password,
    SESSION_COOKIE_NAME,
)
from app.core.database import get_db
from app.models.models import Session as SessionModel, User

router = APIRouter(prefix="/auth", tags=["Auth"])


class Credentials(BaseModel):
    username: str
    password: str


@router.get("/status", summary="Whether the bootstrap account has been created")
def auth_status(db: Session = Depends(get_db)):
    return {"initialized": db.query(User).first() is not None}


@router.post("/register", status_code=201, summary="Create the bootstrap account (once)")
def register(body: Credentials, response: Response, db: Session = Depends(get_db)):
    if db.query(User).first() is not None:
        raise HTTPException(status_code=409, detail="An account already exists — log in instead")

    if not body.username.strip() or len(body.password) < 8:
        raise HTTPException(status_code=422, detail="Username is required and password must be at least 8 characters")

    user = User(
        id            = uuid.uuid4(),
        username      = body.username.strip(),
        password_hash = hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_session(db, user)
    set_session_cookie(response, token)
    return {"username": user.username}


@router.post("/login", summary="Log in with username and password")
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username.strip()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

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
