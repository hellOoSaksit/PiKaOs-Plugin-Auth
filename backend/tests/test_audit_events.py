"""Route-level audit events (audit-notifications v2 spec §1): login success/failed/throttled,
logout, and revoke()'s subject return. Bare FastAPI app + fakeredis + overridden DB — no postgres,
no live server (same harness as test_login_throttle_route.py)."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fakeredis import FakeAsyncRedis
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import audit, kernel_state
from app.core.config import settings
from app.core.db import get_db
from app.plugins.auth import auth_service, login_throttle, rbac_service, security
from app.plugins.auth.auth_service import InactiveAccount, InvalidCredentials, Session
from app.plugins.auth.models import User
from app.plugins.auth.router import router


def _fake_user() -> User:
    return User(id=uuid4(), username="somchai", email="s@example.com", display="Somchai",
                role="admin", status="active", avatar="🙂", quota=None, period="monthly",
                used=0, last_login=None, created_at=datetime.now(timezone.utc),
                password_hash="x")


@pytest.fixture
def app_client(monkeypatch, tmp_path):
    monkeypatch.setattr(kernel_state.settings, "kernel_state_dir", str(tmp_path / "state"))
    monkeypatch.setattr(settings, "login_throttle_account_max", 2, raising=False)
    monkeypatch.setattr(settings, "login_throttle_ip_max", 20, raising=False)
    monkeypatch.setattr(settings, "login_throttle_window_seconds", 900, raising=False)
    login_throttle.bind(FakeAsyncRedis())
    app = FastAPI()
    app.include_router(router)

    async def _no_db():
        yield None

    app.dependency_overrides[get_db] = _no_db
    with TestClient(app) as c:
        yield c
    login_throttle.bind(None)


# Distinctive enough that a hit can only be the real thing. The old value was "pw" — two chars, which
# would also match by accident inside an unrelated word.
_PASSWORD = "SECRET-PASSWORD-3f9a2c"


def _login(client):
    return client.post("/api/auth/login", json={"usernameOrEmail": "somchai", "password": _PASSWORD})


def test_failed_login_is_audited_without_the_password(app_client, monkeypatch):
    async def _reject(*_a, **_k):
        raise InvalidCredentials()
    monkeypatch.setattr(auth_service, "login", _reject)
    assert _login(app_client).status_code == 401
    rows = audit.read(action="auth.login.failed")
    assert rows and rows[0]["target"] == "somchai"
    import json as _json
    # Search the WHOLE trail, not just `detail`. These call sites pass three positional args, so
    # `detail` is always `{}` — asserting against it alone reads as a rule-2 guarantee while actually
    # testing `"pw" not in "{}"`, which is true no matter what the implementation leaks. Any field
    # (target, actor, a future detail) that ever carried the password must fail this.
    assert _PASSWORD not in _json.dumps(audit.read())


def test_throttled_login_is_audited(app_client, monkeypatch):
    async def _reject(*_a, **_k):
        raise InvalidCredentials()
    monkeypatch.setattr(auth_service, "login", _reject)
    _login(app_client); _login(app_client)             # burn the per-account cap (2 in this fixture)
    assert _login(app_client).status_code == 429
    assert audit.read(action="auth.login.throttled")


def test_login_to_a_suspended_account_is_audited(app_client, monkeypatch):
    # A probe against a suspended account is forensic signal — record it (auth.login.inactive), never
    # the password.
    async def _inactive(*_a, **_k):
        raise InactiveAccount()
    monkeypatch.setattr(auth_service, "login", _inactive)
    assert _login(app_client).status_code == 403
    rows = audit.read(action="auth.login.inactive")
    assert rows and rows[0]["target"] == "somchai"
    import json as _json
    assert _PASSWORD not in _json.dumps(audit.read())


def test_successful_login_is_audited_with_the_user_id(app_client, monkeypatch):
    user = _fake_user()

    async def _accept(*_a, **_k):
        return Session(user=user, access_token="a", refresh_token="r", expires_in=900)

    async def _no_perms(*_a, **_k):
        return set()

    monkeypatch.setattr(auth_service, "login", _accept)
    monkeypatch.setattr(rbac_service, "get_effective_perms", _no_perms)
    assert _login(app_client).status_code == 200
    rows = audit.read(action="auth.login")
    assert rows and rows[0]["actor"] == str(user.id) and rows[0]["target"] == "somchai"


def test_logout_is_audited_with_the_token_subject(app_client, monkeypatch):
    async def _noop(*_a, **_k):
        return None
    monkeypatch.setattr(auth_service.redis_client, "revoke_refresh_token", _noop)
    monkeypatch.setattr(auth_service.redis_client, "deny_access_jti", _noop)
    token, _jti = security.make_access_token(user_id="user-77", role="member")
    resp = app_client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
    rows = audit.read(action="auth.logout")
    assert rows and rows[0]["actor"] == "user-77"
