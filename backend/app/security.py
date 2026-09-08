import hashlib
import hmac
import os
import secrets
from datetime import timedelta
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, LoginSession, Membership, Workspace, utcnow
from .config import SESSION_HOURS


def hash_password(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password, encoded):
    try:
        _, salt, expected = encoded.split("$")
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1)
        return hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db, user):
    token = secrets.token_urlsafe(48)
    db.add(LoginSession(token_hash=token_hash(token), user_id=user.id, expires_at=utcnow() + timedelta(hours=SESSION_HOURS)))
    return token


def current_user(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("mccia_session")
    session = db.query(LoginSession).filter(LoginSession.token_hash == token_hash(token), LoginSession.expires_at > utcnow()).first() if token else None
    user = db.get(User, session.user_id) if session else None
    if not user:
        raise HTTPException(401, "Please sign in to continue.")
    return user


def require_editor(user=Depends(current_user)):
    if user.role not in ("Admin", "Manager"):
        raise HTTPException(403, "Your Viewer role does not permit this action.")
    return user


def require_admin(user=Depends(current_user)):
    if user.role != "Admin":
        raise HTTPException(403, "Administrator access is required.")
    return user


def visible_workspace_ids(db, user):
    if user.role == "Admin":
        return [row[0] for row in db.query(Workspace.id).all()]
    return [row[0] for row in db.query(Membership.workspace_id).filter(Membership.user_id == user.id).all()]


def check_workspace(db, user, workspace_id):
    workspace = db.get(Workspace, workspace_id)
    if not workspace or workspace_id not in visible_workspace_ids(db, user):
        raise HTTPException(404, "Workspace not found or access unavailable.")
    return workspace
