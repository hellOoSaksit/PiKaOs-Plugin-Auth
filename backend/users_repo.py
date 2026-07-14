"""User queries (auth plugin). Moved from Core `repositories/users.py` in Phase C."""
from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User


async def get_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await db.get(User, user_id)


async def get_by_login(db: AsyncSession, username_or_email: str) -> User | None:
    """Look a user up by either username or email (case-insensitive)."""
    ident = username_or_email.strip().lower()
    stmt = select(User).where(
        (func.lower(User.username) == ident) | (func.lower(User.email) == ident)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def count_users(db: AsyncSession) -> int:
    return (await db.execute(select(func.count()).select_from(User))).scalar_one()


async def create_admin(db: AsyncSession, username: str, password_hash: str) -> User:
    """The bootstrap owner. Email is a derived placeholder (no email field on the first-admin form);
    the admin can change it once profile editing exists."""
    user = User(username=username, email=f"{username}@local", display=username,
                role="admin", status="active", password_hash=password_hash)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
