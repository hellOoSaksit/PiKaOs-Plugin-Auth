"""Tests for server-side RBAC (A1) — permission-resolution math + seed integrity.

Pure/network-free. The `require_perm` *dependency* behaviour now lives in the kernel identity seam
and is covered by test_identity_deps.py (401/403 through app.state.container); this file tests the
resolution algebra (`rbac_service.resolve_perms`) and that the seed's role→perm map is consistent.

    docker compose exec backend pytest tests/test_rbac.py
"""
from __future__ import annotations

from app.plugins.auth.rbac_service import resolve_perms  # moved to the auth plugin (Phase B)

CATALOG = {"agent.create", "task.run", "audit.view", "user.manage", "room.build"}


# --- resolve_perms (pure) --------------------------------------------------

def test_admin_gets_entire_catalog():
    # admin ignores role_perms/overrides and holds every permission
    assert resolve_perms("admin", set(), {}, CATALOG) == CATALOG


def test_role_perms_passthrough():
    assert resolve_perms("member", {"agent.create", "task.run"}, {}, set()) == {"agent.create", "task.run"}


def test_grant_adds_beyond_role():
    out = resolve_perms("member", {"task.run"}, {"audit.view": True}, set())
    assert out == {"task.run", "audit.view"}


def test_deny_wins_over_role():
    out = resolve_perms("member", {"task.run", "agent.create"}, {"task.run": False}, set())
    assert out == {"agent.create"}


def test_deny_absent_perm_is_noop():
    assert resolve_perms("viewer", set(), {"user.manage": False}, set()) == set()


# --- seed data integrity ---------------------------------------------------

def test_seed_role_perms_are_within_catalog():
    from app.plugins.auth.seed import SEED_ROLE_PERMS, _PERM_KEYS

    catalog = set(_PERM_KEYS)
    assert len(catalog) == len(_PERM_KEYS)  # no duplicate permission keys
    for role, perms in SEED_ROLE_PERMS.items():
        assert set(perms) <= catalog, f"{role} references unknown permission"
    assert set(SEED_ROLE_PERMS["admin"]) == catalog  # admin = full catalog
