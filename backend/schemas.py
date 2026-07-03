"""Auth plugin request/response schemas. Moved from Core `schemas.py` in Phase C (the auth-specific
subset — login/token/user); the kernel keeps the non-auth config schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    usernameOrEmail: str = Field(min_length=1)
    password: str = Field(min_length=1)


class ForgotIn(BaseModel):
    usernameOrEmail: str = Field(min_length=1)


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
