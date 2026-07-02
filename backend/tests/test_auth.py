"""Auth integration tests — run against the LIVE server.

Run inside the backend container where uvicorn is listening on :8000:
    docker compose exec backend pytest

Hitting the real server (instead of in-process ASGITransport) avoids event-loop
binding issues with the module-level async engine/redis, and exercises the actual
running stack (db + redis). Relies on the seeded users.
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
async def test_health():
    async with client() as c:
        r = await c.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["db"] == "ok"
        assert body["redis"] == "ok"
        # version/build are surfaced here per the versions.md registry rule
        assert body["version"] == settings.app_version
        assert body["build"] == settings.build_hash


@pytest.mark.asyncio
async def test_version():
    # liveness probe — no deps, so it must answer even when a datastore is down (the HEALTHCHECK relies on this)
    async with client() as c:
        r = await c.get("/api/version")
        assert r.status_code == 200
        body = r.json()
        assert body["version"] == settings.app_version
        assert body["build"] == settings.build_hash
        assert body["name"] == settings.app_name


@pytest.mark.asyncio
async def test_login_success_and_me():
    async with client() as c:
        r = await c.post("/api/auth/login", json={"usernameOrEmail": "somchai", "password": PW})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["role"] == "admin"
        assert data["user"]["username"] == "somchai"
        assert settings.refresh_cookie_name in r.cookies

        token = data["token"]["accessToken"]
        me = await c.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["username"] == "somchai"


@pytest.mark.asyncio
async def test_login_by_email_works():
    async with client() as c:
        r = await c.post("/api/auth/login", json={"usernameOrEmail": "somchai@guildos.io", "password": PW})
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_login_bad_password():
    async with client() as c:
        r = await c.post("/api/auth/login", json={"usernameOrEmail": "somchai", "password": "nope-wrong"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_suspended_user_rejected():
    async with client() as c:
        r = await c.post("/api/auth/login", json={"usernameOrEmail": "dao", "password": PW})
        assert r.status_code == 403


@pytest.mark.asyncio
async def test_me_requires_auth():
    async with client() as c:
        r = await c.get("/api/auth/me")
        assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_refresh_then_logout_revokes():
    async with client() as c:
        r = await c.post("/api/auth/login", json={"usernameOrEmail": "nicha", "password": PW})
        assert r.status_code == 200

        r2 = await c.post("/api/auth/refresh")
        assert r2.status_code == 200
        token = r2.json()["token"]["accessToken"]

        out = await c.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert out.status_code == 204

        r3 = await c.post("/api/auth/refresh")
        assert r3.status_code == 401
