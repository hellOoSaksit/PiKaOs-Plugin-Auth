"""POST /api/auth/bootstrap-admin — the one-shot create-first-admin endpoint. In-process: DB calls are
monkeypatched (count/create), kernel state goes to a tmp dir; the real router + schema validate."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core import kernel_state, setup_state
from app.core.config import settings
from app.core.db import get_db
from app.plugins.auth import security, users_repo
from app.plugins.auth.router import router

CODE = "PIKA-ABCD-2345"
GOOD = dict(setupCode=CODE, username="somchai", password="correct horse battery staple",
            confirmPassword="correct horse battery staple")


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(kernel_state.settings, "kernel_state_dir", str(tmp_path))
    monkeypatch.setattr(settings, "password_min_length", 12, raising=False)
    setup_state.write(CODE, "tok")
    setup_state.write_auth_mode("login")

    created = []

    async def _count(db):
        return len(created)

    async def _create(db, username, password_hash):
        created.append((username, password_hash))
        return object()

    monkeypatch.setattr(users_repo, "count_users", _count)
    monkeypatch.setattr(users_repo, "create_admin", _create)

    app = FastAPI()
    app.include_router(router)

    async def _no_db():
        yield None

    app.dependency_overrides[get_db] = _no_db
    with TestClient(app) as c:
        c._created = created
        yield c


def _post(client, **over):
    return client.post("/api/auth/bootstrap-admin", json={**GOOD, **over})


def test_creates_the_owner_and_kills_the_code(client):
    resp = _post(client)
    assert resp.status_code == 201
    username, password_hash = client._created[0]
    assert username == "somchai"
    assert security.verify_password(GOOD["password"], password_hash)   # stored hashed, verifiable
    assert setup_state.read_code() is None                             # single-use: window closed


def test_wrong_code_is_401_and_creates_nothing(client):
    resp = _post(client, setupCode="PIKA-XXXX-XXXX")
    assert resp.status_code == 401
    assert client._created == []


def test_second_bootstrap_is_409(client):
    assert _post(client).status_code == 201
    setup_state.write(CODE, "tok")   # even a re-planted code must not allow a second owner
    assert _post(client).status_code == 409
    assert len(client._created) == 1


def test_weak_password_is_422(client):
    resp = _post(client, password="short1", confirmPassword="short1")
    assert resp.status_code == 422
    assert client._created == []


def test_confirm_mismatch_is_422(client):
    resp = _post(client, confirmPassword="different horse battery staple")
    assert resp.status_code == 422
    assert client._created == []


def test_concurrent_duplicate_username_is_409_not_500(tmp_path, monkeypatch):
    """TOCTOU: two requests both pass the count_users()==0 check before either commits. The loser's
    INSERT hits the users.username/email unique constraint — that IntegrityError must map to this
    endpoint's own 409 contract (not leak as a raw 500), and the code must stay alive since no owner
    was actually created by THIS request."""
    monkeypatch.setattr(kernel_state.settings, "kernel_state_dir", str(tmp_path))
    monkeypatch.setattr(settings, "password_min_length", 12, raising=False)
    setup_state.write(CODE, "tok")
    setup_state.write_auth_mode("login")

    async def _count(db):
        return 0   # still 0 from this request's point of view — the race is in the INSERT, not the count

    async def _create(db, username, password_hash):
        raise IntegrityError("stmt", {}, Exception("dup"))

    monkeypatch.setattr(users_repo, "count_users", _count)
    monkeypatch.setattr(users_repo, "create_admin", _create)

    class _FakeDB:
        rolled_back = False

        async def rollback(self):
            self.rolled_back = True

    fake_db = _FakeDB()

    app = FastAPI()
    app.include_router(router)

    async def _fake_db():
        yield fake_db

    app.dependency_overrides[get_db] = _fake_db
    with TestClient(app) as c:
        resp = c.post("/api/auth/bootstrap-admin", json=GOOD)

    assert resp.status_code == 409
    assert fake_db.rolled_back is True
    assert setup_state.read_code() == CODE   # create failed here: the window must stay open
