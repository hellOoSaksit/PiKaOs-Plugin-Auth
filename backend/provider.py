"""The kernel's built-in identity provider — Core's current auth impl behind the `IdentityProvider`
contract (identity.py). Bound as the DEFAULT under `IDENTITY` at composition time, only when no auth
plugin has bound one. Temporary: once the auth plugin lands (Phase B) it binds its own provider and this
adapter + the code it wraps move into the plugin.

Opens its own DB session per call via the app's session factory, so the provider owns its data access
instead of leaning on the request's `get_db` dependency.
"""
from __future__ import annotations

import uuid

import jwt

from ...core import redis_client, security
from ...core.repositories import users as users_repo
from . import rbac_service


class AuthIdentityProvider:
    def __init__(self, session_factory):
        self._sf = session_factory

    async def authenticate(self, token: str | None):
        if not token:
            return None
        try:
            payload = security.decode_access_token(token)
        except jwt.PyJWTError:
            return None
        if payload.get("type") != "access":
            return None
        jti = payload.get("jti")
        if not jti or await redis_client.is_access_denied(jti):
            return None
        try:
            user_id = uuid.UUID(payload["sub"])
        except (KeyError, ValueError, TypeError):
            return None
        async with self._sf() as db:
            user = await users_repo.get_by_id(db, user_id)
        if user is None or user.status != "active":
            return None
        return user

    async def has_perm(self, user, perm: str) -> bool:
        async with self._sf() as db:
            return perm in await rbac_service.get_effective_perms(db, user)

    def has_role(self, user, *roles: str) -> bool:
        return user.role in roles
