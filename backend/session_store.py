"""Redis-backed session store — refresh tokens, the access deny-list, and the effective-perms cache.

These left Core with the Redis extraction: they are AUTH business logic, not kernel infra. The aioredis
client is resolved from the `redis.Connection` DI contract (bound by the redis tool) at this plugin's
register() and stashed in `_redis` — the same module-global shape the old kernel `redis_client` had, just
sourced from the container instead of created at import.

Graceful degradation (A9): the read path every authenticated request hits (`is_access_denied`,
`get_cached_perms`) tolerates a Redis outage — the deny-list fails OPEN and the perms cache reports a miss
so the caller reads the DB. Best-effort writes (logout / cache-bust) swallow errors. Login/refresh
(`create_refresh_token` / `consume_refresh_token`) genuinely cannot work without Redis and raise on
failure. `_redis is None` (redis tool disabled / not yet bound) is treated exactly like a Redis outage.
See docs/process/lessons.md §A.
"""
from __future__ import annotations

import json
import logging
import secrets

from redis.exceptions import RedisError

from ...core.config import settings

log = logging.getLogger("pikaos.auth.session")

_redis = None  # the aioredis client, bound from redis.Connection at register()

_REFRESH = "refresh:{}"      # refresh:<token> -> user_id
_DENY = "denylist:{}"        # denylist:<jti> -> "1"
_PERMS = "perms:{}"          # perms:<user_id> -> JSON list of effective permission keys


def bind(client) -> None:
    """Wire the aioredis client resolved from `redis.Connection` (called by the plugin's register())."""
    global _redis
    _redis = client


def _require():
    if _redis is None:
        raise RuntimeError("auth session store: redis.Connection is not bound (enable the redis tool)")
    return _redis


async def create_refresh_token(user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    await _require().set(_REFRESH.format(token), user_id, ex=settings.refresh_ttl_seconds)
    return token


async def consume_refresh_token(token: str) -> str | None:
    """Validate + rotate: returns user_id and deletes the old token (single-use)."""
    key = _REFRESH.format(token)
    client = _require()
    user_id = await client.get(key)
    if user_id is not None:
        await client.delete(key)
    return user_id


async def revoke_refresh_token(token: str) -> None:
    # Best-effort (logout path): a Redis outage shouldn't make logout 500.
    if _redis is None:
        return
    try:
        await _redis.delete(_REFRESH.format(token))
    except RedisError as exc:
        log.warning("redis down — could not revoke refresh token: %s", exc)


async def deny_access_jti(jti: str, ttl_seconds: int) -> None:
    # Best-effort (logout path): if Redis is down we can't deny-list, but the client still drops its
    # token and the access token expires on its own (short TTL).
    if ttl_seconds <= 0 or _redis is None:
        return
    try:
        await _redis.set(_DENY.format(jti), "1", ex=ttl_seconds)
    except RedisError as exc:
        log.warning("redis down — could not deny-list access jti: %s", exc)


async def is_access_denied(jti: str) -> bool:
    # Deny-list lookup on every authenticated request. If Redis is unreachable we cannot verify
    # revocation, so fail OPEN (treat as not-denied) to keep valid, unexpired tokens working through a
    # Redis outage — access tokens are short-lived (15m) so the revocation gap is bounded. (A9)
    if _redis is None:
        return False
    try:
        return await _redis.exists(_DENY.format(jti)) == 1
    except RedisError as exc:
        log.warning("redis down — skipping deny-list check (fail-open): %s", exc)
        return False


# --- effective-permissions cache (avoid joining 3 tables every request) ---

async def get_cached_perms(user_id: str) -> list[str] | None:
    """Cached effective perms, or None on a miss / Redis outage (caller falls back to DB)."""
    if _redis is None:
        return None
    try:
        raw = await _redis.get(_PERMS.format(user_id))
    except RedisError as exc:
        log.warning("redis down — perms cache miss, reading DB: %s", exc)
        return None
    if raw is None:
        return None
    try:
        return list(json.loads(raw))
    except (ValueError, TypeError):
        return None


async def set_cached_perms(user_id: str, perms: list[str], ttl_seconds: int) -> None:
    if ttl_seconds <= 0 or _redis is None:
        return
    try:
        await _redis.set(_PERMS.format(user_id), json.dumps(sorted(perms)), ex=ttl_seconds)
    except RedisError as exc:
        log.warning("redis down — skipped caching perms: %s", exc)


async def clear_cached_perms(user_id: str) -> None:
    """Drop a user's cached perms — call after any role/override change."""
    if _redis is None:
        return
    try:
        await _redis.delete(_PERMS.format(user_id))
    except RedisError as exc:
        log.warning("redis down — could not clear perms cache (will expire via TTL): %s", exc)
