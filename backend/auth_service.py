"""Authentication logic — login, session issue/rotate, and revoke.

HTTP concerns (cookies, status codes) live in routers/auth.py. This module only
knows about users, tokens, and Redis. It raises two small domain errors that the
router maps to 401 / 403.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from . import session_store as redis_client
from ...core.config import settings
from . import security, users_repo
from .models import User


class InvalidCredentials(Exception):
    """Wrong username/email or password."""


class InactiveAccount(Exception):
    """Account exists but is suspended/disabled."""


@dataclass
class Session:
    """A freshly issued session — what the router needs to build a response."""

    user: User
    access_token: str
    refresh_token: str
    expires_in: int


async def _issue_session(db: AsyncSession, user: User) -> Session:
    access_token, _jti = security.make_access_token(user_id=str(user.id), role=user.role)
    refresh_token = await redis_client.create_refresh_token(str(user.id))
    return Session(
        user=user,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_ttl_seconds,
    )


async def login(db: AsyncSession, username_or_email: str, password: str) -> Session:
    """Verify credentials and start a session. Raises InvalidCredentials / InactiveAccount."""
    user = await users_repo.get_by_login(db, username_or_email)
    if user is None or not security.verify_password(password, user.password_hash):
        raise InvalidCredentials()
    if user.status != "active":
        raise InactiveAccount()

    user.last_login = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(user)
    return await _issue_session(db, user)


async def rotate(db: AsyncSession, refresh_token: str | None) -> Session:
    """Single-use refresh: consume the old token, issue a new pair. Raises InvalidCredentials."""
    if not refresh_token:
        raise InvalidCredentials()
    user_id = await redis_client.consume_refresh_token(refresh_token)
    if user_id is None:
        raise InvalidCredentials()
    user = await users_repo.get_by_id(db, uuid.UUID(user_id))
    if user is None or user.status != "active":
        raise InvalidCredentials()
    return await _issue_session(db, user)


async def revoke(refresh_token: str | None, authorization_header: str | None) -> str | None:
    """Best-effort logout: drop the refresh token and deny the current access jti.
    Returns the access token's subject (user id) when it decodes, for the audit trail."""
    sub: str | None = None
    if refresh_token:
        await redis_client.revoke_refresh_token(refresh_token)
    if authorization_header and authorization_header.lower().startswith("bearer "):
        try:
            payload = security.decode_access_token(authorization_header.split(" ", 1)[1])
            sub = payload.get("sub")
            jti = payload.get("jti")
            ttl = int(payload.get("exp", 0)) - int(datetime.now(timezone.utc).timestamp())
            if jti and ttl > 0:
                await redis_client.deny_access_jti(jti, ttl)
        except jwt.PyJWTError:
            pass
    return sub
