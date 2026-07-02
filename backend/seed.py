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

# --- RBAC seed (mirrors data-users.jsx) ---
SEED_PERMISSIONS = [
    ("agent.create", "Agents", "สร้าง Agent", "Create agents"),
    ("agent.appearance", "Agents", "แก้รูปลักษณ์/คลาส Agent", "Edit appearance & class"),
    ("character.manage", "Agents", "เพิ่ม/จัดการการ์ดตัวละคร", "Manage character cards"),
    ("options.manage", "Agents", "เพิ่มตัวเลือก ตำแหน่ง/ทักษะ/เครื่องมือ", "Add roster options"),
    ("rules.manage", "Agents", "แก้กฎหลัก (บังคับทุกตัว)", "Manage core rules"),
    ("agent.config", "Agents", "แก้ตั้งค่าขั้นสูง (ตำแหน่ง/หน้าที่/โมเดล/API)", "Edit advanced config"),
    ("profile.manage", "Agents", "สร้าง/จัดการโปรไฟล์ (Profile)", "Manage profiles"),
    ("agent.edit.any", "Agents", "แก้ Agent ของผู้อื่น", "Edit any agent"),
    ("agent.delete.any", "Agents", "ลบ Agent ของผู้อื่น", "Delete any agent"),
    ("task.run", "Work", "สั่งรันงาน", "Run quests"),
    ("task.delete", "Work", "ลบงาน (Task)", "Delete tasks"),
    # Chat access (channel-agnostic — enforced by the Telegram bot today, the web chat later).
    # Two tiers per the access model in features/telegram-integration.md: read-only vs read+command.
    ("chat.read", "Chat", "อ่าน/รับข้อความจาก agent ผ่านแชต (อ่านอย่างเดียว)", "Read agent chat (read-only)"),
    ("chat.use", "Chat", "อ่าน + สั่งงาน agent ผ่านแชต", "Use agent chat (read & command)"),
    ("codex.view", "Knowledge", "ดู/ค้นหาคลังความรู้", "View & search codex"),
    ("codex.manage", "Knowledge", "อัปโหลด/จัดการเนื้อหาคลังความรู้", "Upload & manage codex content"),
    ("codex.delete", "Knowledge", "ลบเอกสารในคลังความรู้", "Delete codex documents"),
    ("workflow.manage", "Workflows", "จัดการ workflow", "Manage workflows"),
    ("room.build", "Room", "เปิดโหมดสร้างห้อง", "Open build mode"),
    ("room.place", "Room", "วางของ/เฟอร์นิเจอร์", "Place items"),
    ("room.move", "Room", "แก้ไขตำแหน่ง/รื้อของ", "Edit positions"),
    ("room.reset", "Room", "รีเซตห้องเป็นค่าเริ่มต้น", "Reset room layout"),
    ("room.create", "Room", "สร้างห้องใหม่", "Create rooms"),
    ("room.template", "Room", "สร้าง/บันทึกเทมเพลตห้อง", "Create room templates"),
    ("room.delete", "Room", "ลบห้อง", "Delete rooms"),
    ("token.manage", "Admin", "ตั้งโควตาโทเคน", "Manage token quota"),
    ("user.view.any", "Admin", "ดูข้อมูลสมาชิก", "View any user"),
    ("user.manage", "Admin", "จัดการสมาชิก", "Manage users"),
    ("role.manage", "Admin", "จัดการบทบาท/สิทธิ์", "Manage roles"),
    ("audit.view", "Admin", "ดูบันทึกการตรวจสอบ", "View audit log"),
    ("llm.view", "Admin", "ดูการตั้งค่า LLM/โมเดล", "View LLM provider config"),
    ("llm.manage", "Admin", "ตั้งค่า LLM/โมเดล (provider/API หรือ Local)", "Manage LLM provider config"),
    ("llm.assign", "Admin", "มอบหมายโมเดลให้ระบบ (engine/search/summarize)", "Assign LLM to system roles"),
    ("infra.manage", "Admin", "ดู/ทดสอบการเชื่อมต่อ Storage/ระบบภายนอก", "View/test infrastructure connections"),
    ("telegram.manage", "Admin", "ตั้งค่าบอท Telegram (เชื่อมต่อ/webhook)", "Manage Telegram bot connection"),
    ("plugins.manage", "Admin", "ติดตั้ง/เปิด-ปิด/ถอนปลั๊กอิน", "Install / enable / uninstall plugins"),
]
_PERM_KEYS = [p[0] for p in SEED_PERMISSIONS]

SEED_ROLES = [
    ("admin", "ผู้ดูแลระบบ", "Admin", "เข้าถึงและจัดการได้ทุกอย่าง", "magic", True),
    ("manager", "ผู้จัดการ", "Manager", "ดูและจัดการงานของสมาชิก แต่ไม่จัดการบัญชี", "info", True),
    ("member", "สมาชิก", "Member", "สร้างและจัดการของตัวเอง รันงานได้", "on", True),
    ("viewer", "ผู้อ่าน", "Viewer", "ดูอย่างเดียว ไม่มีสิทธิ์แก้ไข", "idle", True),
]

SEED_ROLE_PERMS = {
    "admin": list(_PERM_KEYS),
    "manager": ["agent.create", "agent.edit.any", "agent.delete.any", "task.run",
                "codex.view", "codex.manage", "codex.delete", "chat.use",
                "workflow.manage", "user.view.any", "audit.view", "room.build", "room.place",
                "room.move", "room.reset", "room.create", "room.delete", "room.template",
                "options.manage", "character.manage", "rules.manage", "agent.config", "task.delete"],
    "member": ["agent.create", "task.run", "codex.view", "codex.manage", "codex.delete", "chat.use",
               "workflow.manage", "room.build", "room.place", "room.move"],
    "viewer": ["codex.view", "chat.read"],
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

        # --- permissions ---
        existing_perms = set((await db.execute(select(Permission.key))).scalars().all())
        for key, grp, th, en in SEED_PERMISSIONS:
            if key not in existing_perms:
                db.add(Permission(key=key, grp=grp, name_th=th, name_en=en))

        # --- roles ---
        existing_roles = set((await db.execute(select(Role.key))).scalars().all())
        for key, th, en, desc, color, system in SEED_ROLES:
            if key not in existing_roles:
                db.add(Role(key=key, name_th=th, name_en=en, description=desc, color=color, system=system))

        # --- role_perms ---
        existing_rp = set((await db.execute(select(RolePerm.role_key, RolePerm.perm_key))).all())
        for role_key, perm_keys in SEED_ROLE_PERMS.items():
            for perm_key in perm_keys:
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
                if (uid, perm_key) not in existing_up:
                    db.add(UserPerm(user_id=uid, perm_key=perm_key, allow=allow))
                    up_added += 1
        await db.commit()

        print(f"[seed:auth] users +{users_added} (had {len(existing_users)}) · "
              f"perms {len(_PERM_KEYS)} · roles {len(SEED_ROLES)} · user_perms +{up_added}")


if __name__ == "__main__":
    # Standalone dev seed — build a throwaway engine from settings (the kernel owns none now).
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    _sf = async_sessionmaker(create_async_engine(settings.database_url), expire_on_commit=False)
    asyncio.run(seed(_sf))
