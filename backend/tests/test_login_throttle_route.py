"""Route-level test: the throttle is actually wired into POST /api/auth/login.

A bare FastAPI app mounts only the auth router; the DB dependency is overridden and auth_service.login is
forced to always reject, so this exercises the real request → throttle → 429 path without postgres. The
throttle is bound to fakeredis. Complements the unit tests (which cover the counter logic in isolation).
"""
from __future__ import annotations

import pytest
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.db import get_db
from app.plugins.auth import auth_service, login_throttle
from app.plugins.auth.auth_service import InvalidCredentials
from app.plugins.auth.router import router


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "login_throttle_account_max", 5, raising=False)
    monkeypatch.setattr(settings, "login_throttle_ip_max", 20, raising=False)
    monkeypatch.setattr(settings, "login_throttle_window_seconds", 900, raising=False)
    login_throttle.bind(FakeAsyncRedis())

    async def _always_reject(*_a, **_k):
        raise InvalidCredentials()

    monkeypatch.setattr(auth_service, "login", _always_reject)

    app = FastAPI()
    app.include_router(router)

    async def _no_db():
        yield None

    app.dependency_overrides[get_db] = _no_db
    with TestClient(app) as c:
        yield c
    login_throttle.bind(None)


def _login(client):
    return client.post("/api/auth/login", json={"usernameOrEmail": "somchai", "password": "wrong"})


def test_sixth_failed_login_is_throttled(client):
    for _ in range(5):
        assert _login(client).status_code == 401  # five real attempts, all wrong
    blocked = _login(client)                        # the sixth is refused before hitting auth_service
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0


def test_a_throttle_flood_writes_one_audit_line_not_one_per_request(client, tmp_path, monkeypatch):
    # A blocked source pounding the endpoint must not amplify into unbounded audit writes: many 429s,
    # exactly one auth.login.throttled line for the window. Without the per-IP dedup this was N lines.
    from app.core import audit, kernel_state
    monkeypatch.setattr(kernel_state.settings, "kernel_state_dir", str(tmp_path))

    for _ in range(5):
        _login(client)                              # burn the account cap
    for _ in range(30):
        assert _login(client).status_code == 429    # 30 refused requests

    throttled = [r for r in audit.read(limit=999) if r["action"] == "auth.login.throttled"]
    assert len(throttled) == 1                       # one lockout line, not thirty
