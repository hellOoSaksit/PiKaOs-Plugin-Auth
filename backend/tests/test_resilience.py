"""Graceful degradation of the auth session store when Redis is down / disabled (A9).

The refresh-token / deny-list / perms-cache helpers moved from the kernel into the auth plugin
(`app.plugins.auth.session_store`) with the Redis extraction; the aioredis client is bound from the
`redis.Connection` contract. Network-free: bind a fake whose every call raises (Redis down) or bind None
(redis tool disabled), then assert the read path degrades instead of erroring — the deny-list fails open
(not denied), the perms cache reports a miss (so the caller reads the DB), and best-effort writes don't
raise.

    docker compose exec backend pytest tests/test_resilience.py
"""
from __future__ import annotations

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.plugins.auth import session_store


class _DeadRedis:
    """Every operation behaves as if Redis is unreachable."""

    async def _boom(self, *args, **kwargs):
        raise RedisConnectionError("redis is down")

    get = set = delete = exists = ping = _boom


@pytest.fixture
def dead_redis():
    session_store.bind(_DeadRedis())
    yield
    session_store.bind(None)


@pytest.fixture
def no_redis():
    """The redis tool is disabled — the client was never bound."""
    session_store.bind(None)
    yield


async def test_deny_list_fails_open_when_redis_down(dead_redis):
    # can't verify revocation → treat token as not denied (valid tokens keep working)
    assert await session_store.is_access_denied("any-jti") is False


async def test_perms_cache_reports_miss_when_redis_down(dead_redis):
    # cache miss → caller (rbac_service) falls back to the DB
    assert await session_store.get_cached_perms("user-1") is None


async def test_best_effort_writes_do_not_raise_when_redis_down(dead_redis):
    # logout / cache-bust paths must not 500 just because Redis is down
    await session_store.deny_access_jti("jti", 60)
    await session_store.revoke_refresh_token("tok")
    await session_store.set_cached_perms("user-1", ["agent.create"], 60)
    await session_store.clear_cached_perms("user-1")


async def test_read_paths_degrade_when_redis_tool_disabled(no_redis):
    # unbound client (redis tool off) is treated exactly like a Redis outage
    assert await session_store.is_access_denied("any-jti") is False
    assert await session_store.get_cached_perms("user-1") is None
    await session_store.deny_access_jti("jti", 60)  # no-op, must not raise
