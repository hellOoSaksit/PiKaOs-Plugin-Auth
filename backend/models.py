"""Auth plugin SQLAlchemy models — the identity + RBAC schema this plugin OWNS.

These tables (`users`, `roles`, `permissions`, `role_perms`, `user_perms`, `departments`,
`user_departments`) left Core in Phase C. They live on this plugin's OWN declarative `Base` (separate
metadata from the kernel), created by the plugin's migration step on install (see `migrate.py` /
`scripts.migrate_plugins`), never by Core's Alembic baseline.

Cross-plugin refs are logical UUIDs, NOT foreign keys: other plugins/Core features store a bare
`owner_id`/`department_id`/`user_id` UUID pointing here (no DB-level FK across the plugin boundary).
Foreign keys are kept only BETWEEN this plugin's own tables (role_perms→roles/permissions,
user_perms→users/permissions, user_departments→users/departments).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """This plugin's declarative base — its metadata is independent of the kernel's `app.core.db.Base`."""


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    avatar: Mapped[str] = mapped_column(String(64), nullable=False, default="🙂")
    quota: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    period: Mapped[str] = mapped_column(String(16), nullable=False, default="monthly")
    used: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# --- RBAC (server-side permission model — mirrors Frontend/src/data/data-users.jsx) ---
# Roles map to permission sets; per-user overrides grant/deny single permissions on top.
# Effective perms = role_perms ∪ grants − denies (deny wins); admin implicitly has all.


class Role(Base):
    __tablename__ = "roles"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    name_th: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    name_en: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    color: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class Permission(Base):
    __tablename__ = "permissions"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    grp: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    name_th: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    name_en: Mapped[str] = mapped_column(String(128), nullable=False, default="")


class RolePerm(Base):
    """A permission granted to a role (the role's default set)."""

    __tablename__ = "role_perms"

    role_key: Mapped[str] = mapped_column(
        String(32), ForeignKey("roles.key", ondelete="CASCADE"), primary_key=True
    )
    perm_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("permissions.key", ondelete="CASCADE"), primary_key=True
    )


class UserPerm(Base):
    """A per-user override: allow=True grants beyond the role, allow=False denies below it."""

    __tablename__ = "user_perms"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    perm_key: Mapped[str] = mapped_column(
        String(64), ForeignKey("permissions.key", ondelete="CASCADE"), primary_key=True
    )
    allow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Department(Base):
    """A department within the single org — scoping/visibility dimension (system-design §7.1)."""

    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name_th: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    name_en: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class UserDepartment(Base):
    """m:n user↔department — a user can belong to several departments; is_primary = default dept."""

    __tablename__ = "user_departments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
