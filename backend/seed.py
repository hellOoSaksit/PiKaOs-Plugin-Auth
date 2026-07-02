"""Seed users + RBAC to mirror Frontend/src/data/data-users.jsx.

Moved from Core `scripts/seed.py` in Phase C — auth owns its own seed now. Run by the plugin migration
step (`scripts.migrate_plugins`) after this plugin's tables are created, or standalone
(`python -m app.plugins.auth.seed`).

Idempotent: skips rows that already exist (users by username; roles/permissions by key;
role_perms/user_perms by their composite key). All seeded users share the dev password from
settings.seed_password (default "pikaos123"). The frontend keys per-user overrides by a `u_<username>`
slug; here we map them to the real user_id by username (server is the source of truth).
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from ... import plugin_loader
from ...core.config import settings
from . import security
from .models import Permission, Role, RolePerm, User, UserPerm

SEED_USERS = [
    dict(username="somchai", display="สมชาย วีรกุล", email="somchai@guildos.io", role="admin",   status="active",    quota=500000, period="weekly",  used=318400, avatar="🧙"),
    dict(username="nicha",   display="ณิชา ทองดี",   email="nicha@guildos.io",   role="manager", status="active",    quota=300000, period="weekly",  used=184200, avatar="🦉"),
    dict(username="kitt",    display="กิตติ ศรีสุข",  email="kitt@guildos.io",    role="member",  status="active",    quota=100000, period="weekly",  used=91800,  avatar="🛠️"),
    dict(username="ploy",    display="พลอย จันทร์",   email="ploy@guildos.io",    role="member",  status="active",    quota=100000, period="weekly",  used=42600,  avatar="📜"),
    dict(username="anan",    display="อนันต์ พรหม",   email="anan@guildos.io",    role="viewer",  status="active",    quota=20000,  period="monthly", used=5400,   avatar="👁️"),
    dict(username="dao",     display="ดาว ประเสริฐ",  email="dao@guildos.io",     role="member",  status="suspended", quota=100000, period="weekly",  used=99200,  avatar="🌙"),
]

# --- RBAC seed ---
# Permissions are NO LONGER hardcoded here (Phase D permission-catalog seam): each plugin declares the
# perms it owns in its manifest, and the auth plugin aggregates them across every ENABLED plugin via the
# kernel's `plugin_loader.permission_catalog`. Base ships zero plugin perms; installing a plugin adds its
# perms to what gets seeded. Roles + their default bindings below stay auth-owned (auth is the RBAC home),
# and a binding is applied ONLY if its perm exists in the current catalog (an uninstalled plugin's perms
# are simply skipped, never seeded as dangling bindings).


def permission_catalog() -> list[dict]:
    """{key, group, name_th, name_en, plugin} for every perm declared by the enabled plugins."""
    return plugin_loader.permission_catalog(
        plugin_loader.enabled_optional_modules(), plugin_loader.PLUGIN_MANIFESTS)

SEED_ROLES = [
    ("admin", "ผู้ดูแลระบบ", "Admin", "เข้าถึงและจัดการได้ทุกอย่าง", "magic", True),
    ("manager", "ผู้จัดการ", "Manager", "ดูและจัดการงานของสมาชิก แต่ไม่จัดการบัญชี", "info", True),
    ("member", "สมาชิก", "Member", "สร้างและจัดการของตัวเอง รันงานได้", "on", True),
    ("viewer", "ผู้อ่าน", "Viewer", "ดูอย่างเดียว ไม่มีสิทธิ์แก้ไข", "idle", True),
]

# Default role→perm bindings. `admin` = "*" (every perm in the current catalog). The others are curated
# subsets by bare key; a key absent from the catalog (its plugin isn't installed) is skipped at seed time.
# room.* (the World plugin) has no backend manifest yet, so it's simply not in the catalog and drops out.
SEED_ROLE_PERMS = {
    "admin": "*",
    "manager": ["agent.create", "agent.edit.any", "agent.delete.any", "task.run",
                "knowledge.view", "knowledge.manage", "knowledge.delete", "chat.use",
                "workflow.manage", "user.view.any", "audit.view",
                "options.manage", "character.manage", "rules.manage", "agent.config", "task.delete"],
    "member": ["agent.create", "task.run", "knowledge.view", "knowledge.manage", "knowledge.delete",
               "chat.use", "workflow.manage"],
    "viewer": ["knowledge.view", "chat.read"],
}

# username -> {perm_key: allow(bool)}  (frontend "grant"/"deny" -> True/False)
SEED_USER_PERMS = {
    "kitt": {"audit.view": True},   # trusted member who can see the audit log
    "ploy": {"task.run": False},   # temporarily blocked from running quests
}


async def seed(session_factory) -> None:
    """Seed auth data. `session_factory` is required — the migration runner passes the postgres Tool's
    factory (the zero-datastore kernel has no SessionLocal). For a standalone run, `__main__` below builds
    a throwaway engine from settings."""
    sf = session_factory
    password_hash = security.hash_password(settings.seed_password)
    async with sf() as db:
        # --- users ---
        existing_users = set((await db.execute(select(User.username))).scalars().all())
        users_added = 0
        for u in SEED_USERS:
            if u["username"] not in existing_users:
                db.add(User(password_hash=password_hash, **u))
                users_added += 1

        # --- permissions (from the aggregated plugin catalog, not a hardcoded list) ---
        catalog = permission_catalog()
        catalog_keys = [p["key"] for p in catalog]
        catalog_key_set = set(catalog_keys)
        existing_perms = set((await db.execute(select(Permission.key))).scalars().all())
        for p in catalog:
            if p["key"] not in existing_perms:
                db.add(Permission(key=p["key"], grp=p["group"], name_th=p["name_th"], name_en=p["name_en"]))

        # --- roles ---
        existing_roles = set((await db.execute(select(Role.key))).scalars().all())
        for key, th, en, desc, color, system in SEED_ROLES:
            if key not in existing_roles:
                db.add(Role(key=key, name_th=th, name_en=en, description=desc, color=color, system=system))

        # --- role_perms (bind only perms present in the catalog; "*" = all of them) ---
        existing_rp = set((await db.execute(select(RolePerm.role_key, RolePerm.perm_key))).all())
        for role_key, perm_keys in SEED_ROLE_PERMS.items():
            keys = catalog_keys if perm_keys == "*" else [k for k in perm_keys if k in catalog_key_set]
            for perm_key in keys:
                if (role_key, perm_key) not in existing_rp:
                    db.add(RolePerm(role_key=role_key, perm_key=perm_key))

        await db.commit()  # commit users first so we can resolve usernames -> ids

        # --- user_perms (needs user ids) ---
        username_to_id = dict((await db.execute(select(User.username, User.id))).all())
        existing_up = set((await db.execute(select(UserPerm.user_id, UserPerm.perm_key))).all())
        up_added = 0
        for username, overrides in SEED_USER_PERMS.items():
            uid = username_to_id.get(username)
            if uid is None:
                continue
            for perm_key, allow in overrides.items():
                if perm_key in catalog_key_set and (uid, perm_key) not in existing_up:
                    db.add(UserPerm(user_id=uid, perm_key=perm_key, allow=allow))
                    up_added += 1
        await db.commit()

        print(f"[seed:auth] users +{users_added} (had {len(existing_users)}) · "
              f"perms {len(catalog_keys)} (from catalog) · roles {len(SEED_ROLES)} · user_perms +{up_added}")


if __name__ == "__main__":
    # Standalone dev seed — build a throwaway engine from settings (the kernel owns none now).
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    _sf = async_sessionmaker(create_async_engine(settings.database_url), expire_on_commit=False)
    asyncio.run(seed(_sf))
