import hashlib
from datetime import timedelta
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from app.core.config import settings
from app.database.session import get_db, utcnow
from app.models.entities import User, Role, APIKey

bearer = HTTPBearer(auto_error=False)
MANAGERS = {'Admin', 'Plant Manager', 'Supervisor'}
WORKERS = MANAGERS | {'Engineer', 'Technician', 'Safety Officer', 'Quality Officer', 'Stores Manager'}


def hash_password(password):
    if not 10 <= len(password.encode()) <= 72:
        raise HTTPException(422, 'Password must contain 10–72 UTF-8 bytes')
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password, hashed):
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def token_for(user, purpose='access', minutes=480):
    return jwt.encode({'sub': str(user.id), 'purpose': purpose, 'exp': utcnow() + timedelta(minutes=minutes)}, settings.jwt_secret, algorithm='HS256')


def decode_user(token, db, purpose='access'):
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'])
        if payload.get('purpose') != purpose:
            raise ValueError()
        user = db.get(User, int(payload['sub']))
        if not user or not user.is_active:
            raise ValueError()
        return user
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(401, 'Session expired or invalid credentials')


def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer), db=Depends(get_db)):
    if not credentials:
        raise HTTPException(401, 'Sign in to continue')
    return decode_user(credentials.credentials, db)


def role_name(db, user):
    return db.get(Role, user.role_id).name


def require_role(db, user, roles):
    if role_name(db, user) not in roles:
        raise HTTPException(403, 'Your role does not permit this action')


def key_user(key, db):
    row = db.scalar(select(APIKey).where(APIKey.key_hash == hashlib.sha256(key.encode()).hexdigest(), APIKey.active.is_(True)))
    user = db.get(User, row.user_id) if row else None
    if not user or not user.is_active:
        raise HTTPException(401, 'Invalid API key')
    return user
