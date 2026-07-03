"""Token-mode auth integration tests — run against the LIVE server (see test_auth.py).

Desktop clients send `X-Client-Mode: token` to get the refresh token back in the JSON
body instead of an httpOnly cookie, and use `X-Refresh-Token` on refresh/logout. The
web cookie flow must stay byte-identical (see test_login_cookie_mode_unchanged).
"""
from __future__ import annotations

import os

import httpx
import pytest

from app.core.config import settings

BASE = os.environ.get("TEST_BASE_URL", "http://localhost:8000")
PW = settings.seed_password


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=BASE, timeout=10.0)


@pytest.mark.asyncio
async def test_login_token_mode_returns_refresh_in_body():
    async with client() as c:
        r = await c.post(
            "/api/auth/login",
            headers={"X-Client-Mode": "token"},
            json={"usernameOrEmail": "somchai", "password": PW},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["token"]["accessToken"]
        assert body["refreshToken"]
        assert settings.refresh_cookie_name not in r.cookies


@pytest.mark.asyncio
async def test_login_cookie_mode_unchanged():
    async with client() as c:
        r = await c.post(
            "/api/auth/login",
            json={"usernameOrEmail": "somchai", "password": PW},
        )
        assert r.status_code == 200, r.text
        assert r.json().get("refreshToken") is None
        assert settings.refresh_cookie_name in r.cookies


@pytest.mark.asyncio
async def test_refresh_via_header():
    async with client() as c:
        login = await c.post(
            "/api/auth/login",
            headers={"X-Client-Mode": "token"},
            json={"usernameOrEmail": "somchai", "password": PW},
        )
        assert login.status_code == 200, login.text
        rt = login.json()["refreshToken"]

        r = await c.post(
            "/api/auth/refresh",
            headers={"X-Client-Mode": "token", "X-Refresh-Token": rt},
        )
        assert r.status_code == 200, r.text
        assert r.json()["refreshToken"]


@pytest.mark.asyncio
async def test_logout_token_mode_revokes():
    async with client() as c:
        login = await c.post(
            "/api/auth/login",
            headers={"X-Client-Mode": "token"},
            json={"usernameOrEmail": "somchai", "password": PW},
        )
        assert login.status_code == 200, login.text
        body = login.json()
        access = body["token"]["accessToken"]
        rt = body["refreshToken"]

        out = await c.post(
            "/api/auth/logout",
            headers={
                "X-Client-Mode": "token",
                "X-Refresh-Token": rt,
                "Authorization": f"Bearer {access}",
            },
        )
        assert out.status_code == 204, out.text
        # nothing to clear in token mode — logout must not set/touch the refresh cookie
        assert settings.refresh_cookie_name not in out.cookies

        r3 = await c.post(
            "/api/auth/refresh",
            headers={"X-Client-Mode": "token", "X-Refresh-Token": rt},
        )
        assert r3.status_code == 401, r3.text
