"""Brute-force guard on /api/auth/login — Redis-backed failure counters shared across the workers.

Same shape as session_store: the aioredis client is bound at the plugin's register() and stashed in
`_redis`. The model is ONE unified INCR+EXPIRE counter per account and per source IP — each failed login
bumps a counter whose TTL is the throttle window, and once a counter reaches its cap the account/IP is
refused until that counter expires. That makes the lockout SOFT and self-healing (window == lockout, no
separate lock key, no manual unlock): a throttled username auto-recovers, so account lockout can't be
weaponised into a permanent DoS on a known login. A successful login clears the account counter.

Fail-open (A9, mirrors session_store): the check every login hits (`blocked_for`) tolerates a Redis
outage — it reports "not blocked" so an outage can never lock the whole system out; the writes are
best-effort. `_redis is None` (redis tool disabled / not yet bound) is treated exactly like an outage.
"""
from __future__ import annotations

import logging

from redis.exceptions import RedisError

from ...core.config import settings

log = logging.getLogger("pikaos.auth.throttle")

_redis = None  # the aioredis client, bound from redis.Connection at register()

_ACCT = "login:fail:acct:{}"   # login:fail:acct:<username> -> failed-attempt count (TTL = window)
_IP = "login:fail:ip:{}"       # login:fail:ip:<ip>         -> failed-attempt count (TTL = window)


def bind(client) -> None:
    """Wire the aioredis client (called by register(); the SAME client session_store uses)."""
    global _redis
    _redis = client


def _as_int(raw) -> int:
    """Redis counters come back as int (INCR) or bytes/str (GET) depending on the call — normalise."""
    if raw is None:
        return 0
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode()
    return int(raw)


async def _count_and_ttl(key: str) -> tuple[int, int]:
    n = _as_int(await _redis.get(key))
    if n == 0:
        return 0, 0
    ttl = await _redis.ttl(key)
    return n, max(int(ttl), 0)


async def blocked_for(username: str, ip: str) -> int:
    """Seconds the caller must wait before retrying, or 0 if allowed. Account cap OR IP cap trips it.

    Fails OPEN on a Redis outage (returns 0) so an outage never becomes a lockout."""
    if _redis is None:
        return 0
    try:
        acct_n, acct_ttl = await _count_and_ttl(_ACCT.format(username))
        if acct_n >= settings.login_throttle_account_max:
            return acct_ttl or settings.login_throttle_window_seconds
        ip_n, ip_ttl = await _count_and_ttl(_IP.format(ip))
        if ip_n >= settings.login_throttle_ip_max:
            return ip_ttl or settings.login_throttle_window_seconds
        return 0
    except RedisError as exc:
        log.warning("redis down — skipping login throttle check (fail-open): %s", exc)
        return 0


async def _bump(key: str) -> None:
    if await _redis.incr(key) == 1:  # first failure in this window → start the expiry clock
        await _redis.expire(key, settings.login_throttle_window_seconds)


async def record_failure(username: str, ip: str) -> None:
    """Count one failed attempt against both the account and the source IP. Best-effort."""
    if _redis is None:
        return
    try:
        await _bump(_ACCT.format(username))
        await _bump(_IP.format(ip))
    except RedisError as exc:
        log.warning("redis down — could not record login failure: %s", exc)


async def reset(username: str) -> None:
    """Clear the account counter after a successful login. The IP counter is left to expire on its own —
    one good login from an IP shouldn't absolve that IP's assault on other accounts. Best-effort."""
    if _redis is None:
        return
    try:
        await _redis.delete(_ACCT.format(username))
    except RedisError as exc:
        log.warning("redis down — could not reset login throttle: %s", exc)
