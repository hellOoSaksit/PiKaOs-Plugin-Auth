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
    # Permissions are no longer a hardcoded list — the catalog is aggregated from the enabled plugins'
    # manifests (permission-catalog seam). A curated role binding may only reference perms in that catalog;
    # `admin` is "*" (the whole catalog). A key whose plugin isn't installed is skipped at seed time.
    from app.plugins.auth.seed import SEED_ROLE_PERMS, permission_catalog

    catalog = {p["key"] for p in permission_catalog()}
    assert catalog, "the enabled plugins must contribute a non-empty permission catalog"
    assert SEED_ROLE_PERMS["admin"] == "*"  # admin binds to the full catalog
    for role, perms in SEED_ROLE_PERMS.items():
        if perms == "*":
            continue
        assert set(perms) <= catalog, f"{role} references a permission not in the catalog"
