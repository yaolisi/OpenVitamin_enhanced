"""本地账号：密码哈希与会话（Cookie）。"""
from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from config.settings import settings
from core.data.models.platform_user import PlatformUserORM, PlatformUserSessionORM
from core.security.rbac import PlatformRole

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,63}$")


def local_auth_enabled() -> bool:
    return bool(getattr(settings, "local_auth_enabled", False))


def registration_allowed() -> bool:
    if not local_auth_enabled():
        return False
    return bool(getattr(settings, "local_auth_allow_registration", True))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_username(username: str) -> Optional[str]:
    u = (username or "").strip()
    if not _USERNAME_RE.match(u):
        return "invalid_username"
    return None


def validate_password(password: str) -> Optional[str]:
    if len(password or "") < 8:
        return "password_too_short"
    return None


def _session_ttl() -> timedelta:
    hours = int(getattr(settings, "local_auth_session_ttl_hours", 168) or 168)
    return timedelta(hours=max(1, min(hours, 24 * 90)))


def count_users(db: Session) -> int:
    return int(db.scalar(select(func.count()).select_from(PlatformUserORM)) or 0)


def get_user_by_username(db: Session, username: str) -> Optional[PlatformUserORM]:
    u = (username or "").strip()
    if not u:
        return None
    return db.scalar(select(PlatformUserORM).where(PlatformUserORM.username == u))


def register_user(
    db: Session,
    *,
    username: str,
    password: str,
    email: Optional[str] = None,
    display_name: Optional[str] = None,
) -> Tuple[Optional[PlatformUserORM], Optional[str]]:
    if not registration_allowed():
        return None, "registration_disabled"
    err = validate_username(username) or validate_password(password)
    if err:
        return None, err
    if get_user_by_username(db, username):
        return None, "username_taken"
    email_norm = (email or "").strip() or None
    if email_norm:
        existing = db.scalar(select(PlatformUserORM).where(PlatformUserORM.email == email_norm))
        if existing:
            return None, "email_taken"
    role = PlatformRole.ADMIN.value if count_users(db) == 0 else PlatformRole.OPERATOR.value
    user = PlatformUserORM(
        id=str(uuid.uuid4()),
        username=username.strip(),
        email=email_norm,
        password_hash=hash_password(password),
        display_name=(display_name or username).strip()[:128],
        platform_role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, None


def authenticate_user(
    db: Session, *, username: str, password: str
) -> Tuple[Optional[PlatformUserORM], Optional[str]]:
    if not local_auth_enabled():
        return None, "local_auth_disabled"
    user = get_user_by_username(db, username)
    if user is None or not user.is_active:
        return None, "invalid_credentials"
    if not verify_password(password, user.password_hash):
        return None, "invalid_credentials"
    return user, None


def create_session(db: Session, user_id: str) -> str:
    raw = secrets.token_urlsafe(32)
    row = PlatformUserSessionORM(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=_hash_token(raw),
        expires_at=datetime.now(timezone.utc) + _session_ttl(),
    )
    db.add(row)
    db.commit()
    return raw


def resolve_session_token(db: Session, raw_token: str) -> Optional[PlatformUserORM]:
    if not raw_token:
        return None
    now = datetime.now(timezone.utc)
    row = db.scalar(
        select(PlatformUserSessionORM).where(PlatformUserSessionORM.token_hash == _hash_token(raw_token))
    )
    if row is None:
        return None
    exp = row.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp <= now:
        db.delete(row)
        db.commit()
        return None
    user = db.get(PlatformUserORM, row.user_id)
    if user is None or not user.is_active:
        return None
    return user


def revoke_session(db: Session, raw_token: str) -> None:
    if not raw_token:
        return
    row = db.scalar(
        select(PlatformUserSessionORM).where(PlatformUserSessionORM.token_hash == _hash_token(raw_token))
    )
    if row is not None:
        db.delete(row)
        db.commit()


def platform_role_from_user(user: PlatformUserORM) -> PlatformRole:
    try:
        return PlatformRole(str(user.platform_role).lower())
    except ValueError:
        return PlatformRole.OPERATOR
