"""RBAC service — resolve a user's effective permissions.

effective = role's default perms ∪ per-user grants − per-user denies (deny wins);
the `admin` role implicitly holds every permission in the catalog. Results are cached
in Redis (`perms:<user_id>`, short TTL) to avoid joining role_perms/user_perms on every
request; mutating a role or override must call `invalidate()` to drop the stale entry.

See docs/architecture/risk-mitigation.md §2.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ...core import redis_client
from ...core.config import settings
from ...core.identity import ADMIN_ROLE
from . import rbac_repo
from .models import User

__all__ = ["ADMIN_ROLE", "resolve_perms", "get_effective_perms", "invalidate"]


def resolve_perms(
    role_key: str,
    role_perms: set[str],
    overrides: dict[str, bool],
    all_perms: set[str],
) -> set[str]:
    """Pure permission math (no DB/cache) — easy to unit-test.

    admin → every permission. Otherwise start from the role set, apply grants
    (allow=True) then denies (allow=False); a deny always wins over a grant.
    """
    if role_key == ADMIN_ROLE:
        return set(all_perms)
    effective = set(role_perms)
    for key, allow in overrides.items():
        if allow:
            effective.add(key)
        else:
            effective.discard(key)
    return effective


async def get_effective_perms(db: AsyncSession, user: User) -> set[str]:
    """Effective permission keys for a user (Redis-cached, TTL from settings)."""
    uid = str(user.id)
    cached = await redis_client.get_cached_perms(uid)
    if cached is not None:
        return set(cached)

    role_perms = await rbac_repo.role_perm_keys(db, user.role)
    overrides = await rbac_repo.user_overrides(db, user.id)
    all_perms = set(await rbac_repo.all_perm_keys(db)) if user.role == ADMIN_ROLE else set()
    perms = resolve_perms(user.role, role_perms, overrides, all_perms)

    await redis_client.set_cached_perms(uid, list(perms), settings.perms_cache_ttl_seconds)
    return perms


async def invalidate(user_id: str) -> None:
    """Drop a user's cached perms after a role/override change."""
    await redis_client.clear_cached_perms(user_id)
