"""Auth HTTP endpoints. Thin layer: parse request -> call auth_service -> shape response.

The refresh token travels as an httpOnly cookie; the access token is returned in
the JSON body for the SPA to send as `Authorization: Bearer ...`.
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.db import get_db
from ...core.identity import get_current_user
from ...core.models import User
from ...core.schemas import ForgotIn, LoginIn, LoginResult, TokenOut, UserOut
from . import auth_service, rbac_service
from .auth_service import InactiveAccount, InvalidCredentials, Session

router = APIRouter(prefix="/api/auth", tags=["auth"])

# the refresh cookie is scoped to the auth routes only
COOKIE_PATH = "/api/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=COOKIE_PATH,
    )


def _user_out(user: User, perms: set[str]) -> UserOut:
    out = UserOut.model_validate(user)
    out.permissions = sorted(perms)
    return out


def _session_response(response: Response, session: Session, perms: set[str]) -> LoginResult:
    _set_refresh_cookie(response, session.refresh_token)
    return LoginResult(
        token=TokenOut(accessToken=session.access_token, expiresIn=session.expires_in),
        user=_user_out(session.user, perms),
    )


@router.post("/login", response_model=LoginResult)
async def login(body: LoginIn, response: Response, db: AsyncSession = Depends(get_db)) -> LoginResult:
    try:
        session = await auth_service.login(db, body.usernameOrEmail, body.password)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    except InactiveAccount:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is not active")
    perms = await rbac_service.get_effective_perms(db, session.user)
    return _session_response(response, session, perms)


@router.post("/refresh", response_model=LoginResult)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    pikaos_refresh: str | None = Cookie(default=None),
) -> LoginResult:
    try:
        session = await auth_service.rotate(db, pikaos_refresh)
    except InvalidCredentials:
        response.delete_cookie(settings.refresh_cookie_name, path=COOKIE_PATH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    perms = await rbac_service.get_effective_perms(db, session.user)
    return _session_response(response, session, perms)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    authorization: str | None = Header(default=None),
    pikaos_refresh: str | None = Cookie(default=None),
) -> Response:
    await auth_service.revoke(pikaos_refresh, authorization)
    response.delete_cookie(settings.refresh_cookie_name, path=COOKIE_PATH)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UserOut)
async def me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    perms = await rbac_service.get_effective_perms(db, user)
    return _user_out(user, perms)


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(body: ForgotIn) -> dict:
    # Always 200 — never reveal whether an account exists. Real email = future milestone.
    return {"ok": True}
