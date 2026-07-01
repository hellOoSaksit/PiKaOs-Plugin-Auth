"""Password hashing (argon2id) and JWT access tokens.

Moved out of the kernel into the auth plugin in Phase C — the kernel keeps only the identity
*contract* (app/core/identity.py); this is the auth *implementation*. Reads JWT/TTL settings from the
kernel config (`app.core.config`), which stays in the kernel.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from ...core.config import settings

# argon2id with the library's vetted defaults. Calls argon2-cffi directly (A5) — the same
# backend passlib[argon2] wrapped — so hashes seeded under passlib (standard $argon2id$
# strings) still verify; no password reset needed. passlib 1.7.4 was unmaintained.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (Argon2Error, ValueError, TypeError):
        return False


def make_access_token(*, user_id: str, role: str) -> tuple[str, str]:
    """Return (jwt, jti). jti lets us deny-list a token on logout."""
    jti = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + settings.access_ttl_seconds,
        "type": "access",
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return token, jti


def decode_access_token(token: str) -> dict:
    """Raises jwt.PyJWTError on invalid/expired token."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
