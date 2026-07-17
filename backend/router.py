"""Auth HTTP endpoints. Thin layer: parse request -> call auth_service -> shape response.

The refresh token travels as an httpOnly cookie; the access token is returned in
the JSON body for the SPA to send as `Authorization: Bearer ...`.

Desktop clients use "token mode" instead: request header `X-Client-Mode: token` makes
login/refresh return the refresh token in the JSON body (`refreshToken`) and skip setting
the cookie; refresh/logout then read the refresh token from `X-Refresh-Token` (falling back
to the `pikaos_refresh` cookie when that header is absent). The web cookie flow is unchanged.
"""
from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ...core import audit
from ...core.config import settings
from ...core.db import get_db
from ...core.identity import get_current_user
from . import auth_service, login_throttle, rbac_service, security, users_repo
from .models import User
from .schemas import BootstrapAdminIn, ForgotIn, LoginIn, LoginResult, TokenOut, UserOut
from .auth_service import InactiveAccount, InvalidCredentials, Session

router = APIRouter(prefix="/api/auth", tags=["auth"])

# the refresh cookie is scoped to the auth routes only
COOKIE_PATH = "/api/auth"


def _is_token_mode(x_client_mode: str | None) -> bool:
    return (x_client_mode or "").lower() == "token"


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


def _session_response(
    response: Response,
    session: Session,
    perms: set[str],
    token_mode: bool = False,
) -> LoginResult:
    result = LoginResult(
        token=TokenOut(accessToken=session.access_token, expiresIn=session.expires_in),
        user=_user_out(session.user, perms),
    )
    if token_mode:
        # desktop client: hand the refresh token back in the body, no cookie set
        result.refreshToken = session.refresh_token
    else:
        _set_refresh_cookie(response, session.refresh_token)
    return result


def _client_ip(request: Request) -> str:
    # The peer socket address — correct for the direct-connect desktop/dev client (the only deployment
    # today). CAVEAT: behind a reverse proxy (the deferred web/nginx path) every request carries the
    # proxy's IP, so the per-IP cap would throttle globally; revive that path with trusted X-Forwarded-For
    # parsing before it ships. The per-ACCOUNT cap is proxy-independent and stays the primary guard.
    return request.client.host if request.client else "unknown"


@router.post("/login", response_model=LoginResult)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    x_client_mode: str | None = Header(default=None),
) -> LoginResult:
    ip = _client_ip(request)
    # Brute-force guard: refuse before touching credentials once the account or the IP is over its cap.
    # A generic 429 (never "which of the two tripped", never whether the account exists) + Retry-After.
    retry_after = await login_throttle.blocked_for(body.usernameOrEmail, ip)
    if retry_after > 0:
        # Audit the lockout ONCE per IP per window, not on every 429 — a blocked source can send
        # unlimited refused requests, and auditing each lets it flood the trail (see first_throttle_from_ip).
        if await login_throttle.first_throttle_from_ip(ip):
            audit.log("anonymous", "auth.login.throttled", body.usernameOrEmail)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many login attempts, try again later",
            headers={"Retry-After": str(retry_after)},
        )
    try:
        session = await auth_service.login(db, body.usernameOrEmail, body.password)
    except InvalidCredentials:
        await login_throttle.record_failure(body.usernameOrEmail, ip)
        audit.log("anonymous", "auth.login.failed", body.usernameOrEmail)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    except InactiveAccount:
        # A suspended account being probed is a forensic signal worth keeping — it was the one login
        # outcome the trail didn't record. (Extends the spec's §1 action list with auth.login.inactive.)
        audit.log("anonymous", "auth.login.inactive", body.usernameOrEmail)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is not active")
    await login_throttle.reset(body.usernameOrEmail)  # a good login clears the account's failure streak
    audit.log(str(session.user.id), "auth.login", body.usernameOrEmail)
    perms = await rbac_service.get_effective_perms(db, session.user)
    return _session_response(response, session, perms, token_mode=_is_token_mode(x_client_mode))


@router.post("/refresh", response_model=LoginResult)
async def refresh(
    response: Response,
    db: AsyncSession = Depends(get_db),
    pikaos_refresh: str | None = Cookie(default=None),
    x_client_mode: str | None = Header(default=None),
    x_refresh_token: str | None = Header(default=None),
) -> LoginResult:
    token_mode = _is_token_mode(x_client_mode)
    effective_refresh = x_refresh_token or pikaos_refresh
    try:
        session = await auth_service.rotate(db, effective_refresh)
    except InvalidCredentials:
        if not token_mode:
            response.delete_cookie(settings.refresh_cookie_name, path=COOKIE_PATH)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    perms = await rbac_service.get_effective_perms(db, session.user)
    return _session_response(response, session, perms, token_mode=token_mode)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    authorization: str | None = Header(default=None),
    pikaos_refresh: str | None = Cookie(default=None),
    x_client_mode: str | None = Header(default=None),
    x_refresh_token: str | None = Header(default=None),
) -> Response:
    effective_refresh = x_refresh_token or pikaos_refresh
    sub = await auth_service.revoke(effective_refresh, authorization)
    audit.log(sub or "unknown", "auth.logout")
    if not _is_token_mode(x_client_mode):
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


@router.post("/bootstrap-admin", status_code=status.HTTP_201_CREATED)
async def bootstrap_admin(body: BootstrapAdminIn, db: AsyncSession = Depends(get_db)) -> dict:
    """One-shot create-first-admin (2026-07-14 spec): auth is enabled but has zero users, and the
    operator proves console access with this boot's setup code. No throttle by design — the code is
    40-bit, rotates every boot, and dies on success (same call as the 2026-07-02 setup-code design).
    Order: owner-exists first (the window being closed is public knowledge), then the code
    (constant-time via setup_state), then password strength."""
    from ...core import setup_state  # kernel state seam, same import style as identity's usage

    if await users_repo.count_users(db) > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "already initialized")
    if not setup_state.verify_code(body.setupCode):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid setup code")
    try:
        security.validate_password_strength(body.password)
    except security.WeakPassword as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    try:
        await users_repo.create_admin(db, body.username, security.hash_password(body.password))
    except IntegrityError:
        # A concurrent bootstrap already created the owner (unique username/email) — map the DB
        # constraint to this endpoint's own one-owner contract instead of leaking a raw 500.
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "already initialized")
    audit.log(body.username, "auth.bootstrap_admin")
    setup_state.clear()   # single-use: the window closes the moment the owner exists
    return {"ok": True}
