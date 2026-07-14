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


# A small blocklist of well-known weak secrets (NIST SP 800-63B Rev 4 SHALL-check). Lower-cased; the
# check is case-insensitive. This is a floor, not a breach corpus — a Have-I-Been-Pwned k-anonymity
# lookup is the eventual upgrade (tracked as a follow-up), but it must never be a login-time dependency.
_COMMON_PASSWORDS = frozenset(
    {
        "123456789012", "1234567890123", "12345678901234", "123456789012345",
        "password1234", "password12345", "passwordpassword", "qwertyuiop123",
        "administrator", "iloveyou1234", "letmein12345", "welcome12345",
    }
)


class WeakPassword(ValueError):
    """Password fails the strength policy (too short, or a known-common/compromised secret)."""


def validate_password_strength(password: str) -> None:
    """Enforce the password policy — call on create/change, NEVER on login or system seeding.

    NIST SP 800-63B Rev 4-aligned: a configurable minimum length (`settings.password_min_length`) + a
    common-password blocklist, and deliberately NO composition rules (no forced character-class mixes).
    Length is measured in Unicode code points; spaces and all printable characters are allowed. Raises
    WeakPassword on a violation; returns None when the password is acceptable."""
    if len(password) < settings.password_min_length:
        raise WeakPassword(f"Password must be at least {settings.password_min_length} characters")
    if password.lower() in _COMMON_PASSWORDS:
        raise WeakPassword("Password is too common — choose a less predictable one")


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
