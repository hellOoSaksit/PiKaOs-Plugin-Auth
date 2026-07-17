"""Auth plugin request/response schemas. Moved from Core `schemas.py` in Phase C (the auth-specific
subset — login/token/user); the kernel keeps the non-auth config schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


# RFC 5321 caps an email address at 254 chars, and a username is far shorter — so nothing legitimate
# comes close. Unbounded, this field was an attack surface twice over: it is written to Core's audit
# trail on a FAILED (anonymous) login, where oversized entries can rotate real history away, and it is
# interpolated into a Redis throttle key. Bound at the edge (rule 10); Core's audit sink clips too.
_IDENTIFIER_MAX = 254


class LoginIn(BaseModel):
    usernameOrEmail: str = Field(min_length=1, max_length=_IDENTIFIER_MAX)
    password: str = Field(min_length=1, max_length=1024)


class ForgotIn(BaseModel):
    usernameOrEmail: str = Field(min_length=1, max_length=_IDENTIFIER_MAX)


class TokenOut(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    expiresIn: int


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    username: str
    email: str
    display: str
    role: str
    status: str
    avatar: str
    quota: int | None
    period: str
    used: int
    last_login: datetime | None = None
    created_at: datetime
    permissions: list[str] = []  # server-resolved effective perms (set by /me + login)


class LoginResult(BaseModel):
    token: TokenOut
    user: UserOut
    refreshToken: str | None = None  # populated only in token mode (desktop); web relies on the cookie


class BootstrapAdminIn(BaseModel):
    """Create-first-admin form. setupCode is this boot's console code (constant-time-checked
    server-side); username/password are the owner's hand-picked credentials."""

    setupCode: str = Field(min_length=1)
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=1)          # real strength check = validate_password_strength
    confirmPassword: str = Field(min_length=1)

    @model_validator(mode="after")
    def _confirm_matches(self):
        if self.password != self.confirmPassword:
            raise ValueError("passwords do not match")
        return self
