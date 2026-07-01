"""RBAC queries — role permission sets, per-user overrides, the permission catalog.

Moved from Core `repositories/rbac.py` in Phase C. All SQL for the permission model lives here; the
effective-permission math (union/grant/deny) is in `rbac_service.py`.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Permission, RolePerm, UserPerm


async def role_perm_keys(db: AsyncSession, role_key: str) -> set[str]:
    """Permission keys granted to a role by default."""
    stmt = select(RolePerm.perm_key).where(RolePerm.role_key == role_key)
    return set((await db.execute(stmt)).scalars().all())


async def user_overrides(db: AsyncSession, user_id: uuid.UUID) -> dict[str, bool]:
    """Per-user overrides: {perm_key: allow}. allow=True grants, False denies."""
    stmt = select(UserPerm.perm_key, UserPerm.allow).where(UserPerm.user_id == user_id)
    return {key: allow for key, allow in (await db.execute(stmt)).all()}


async def all_perm_keys(db: AsyncSession) -> list[str]:
    """Every permission key in the catalog (admin implicitly holds all of these)."""
    return list((await db.execute(select(Permission.key))).scalars().all())
