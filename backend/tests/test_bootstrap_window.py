"""ensure_bootstrap_window — auth enabled + zero users revives a console setup code (in-process,
no DB: count_users is monkeypatched; kernel state goes to a tmp dir)."""
from __future__ import annotations

import pytest

from app.core import kernel_state, setup_state
from app.plugins.auth import migrate, users_repo


@pytest.fixture
def tmp_state(tmp_path, monkeypatch):
    monkeypatch.setattr(kernel_state.settings, "kernel_state_dir", str(tmp_path))
    return tmp_path


def _session_factory():
    class _Ctx:
        async def __aenter__(self):  # the session is never touched — count_users is patched
            return object()
        async def __aexit__(self, *exc):
            return False
    return _Ctx()


@pytest.mark.asyncio
async def test_zero_users_revives_a_code(tmp_state, monkeypatch, capsys):
    async def _zero(db):
        return 0
    monkeypatch.setattr(users_repo, "count_users", _zero)
    assert setup_state.read_code() is None
    await migrate.ensure_bootstrap_window(_session_factory)
    code = setup_state.read_code()
    assert code and code.startswith("PIKA-")
    assert "first admin" in capsys.readouterr().out.lower()   # operator-visible banner


@pytest.mark.asyncio
async def test_existing_users_leave_the_code_cleared(tmp_state, monkeypatch):
    async def _one(db):
        return 1
    monkeypatch.setattr(users_repo, "count_users", _one)
    await migrate.ensure_bootstrap_window(_session_factory)
    assert setup_state.read_code() is None
