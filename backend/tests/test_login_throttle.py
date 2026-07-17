"""Unit tests for login_throttle — the brute-force guard on /api/auth/login.

Runs in-process against fakeredis (a real Redis implementation, not a hand-rolled stub — so these
exercise the actual INCR/EXPIRE/TTL semantics the module relies on), so no live server, postgres, or
redis sidecar is needed. Threshold policy is config-driven; these bind small values so intent is clear.
"""
from __future__ import annotations

import pytest
from fakeredis import FakeAsyncRedis

from app.core.config import settings
from app.plugins.auth import login_throttle

ACCT = "somchai"
IP = "203.0.113.7"


@pytest.fixture
def redis():
    """A fresh in-memory redis bound into the throttle for each test."""
    client = FakeAsyncRedis()
    login_throttle.bind(client)
    yield client
    login_throttle.bind(None)


@pytest.fixture(autouse=True)
def _known_thresholds(monkeypatch):
    # Pin policy so the tests read as spec, independent of the shipped defaults.
    monkeypatch.setattr(settings, "login_throttle_account_max", 5, raising=False)
    monkeypatch.setattr(settings, "login_throttle_ip_max", 20, raising=False)
    monkeypatch.setattr(settings, "login_throttle_window_seconds", 900, raising=False)


@pytest.mark.asyncio
async def test_under_account_threshold_is_not_blocked(redis):
    for _ in range(4):  # 4 failures < max 5
        await login_throttle.record_failure(ACCT, IP)
    assert await login_throttle.blocked_for(ACCT, IP) == 0


@pytest.mark.asyncio
async def test_account_blocked_after_max_failures(redis):
    for _ in range(5):  # hit the account cap
        await login_throttle.record_failure(ACCT, IP)
    # the 6th attempt is refused; retry-after is a positive, bounded slice of the window
    retry = await login_throttle.blocked_for(ACCT, IP)
    assert 0 < retry <= 900


@pytest.mark.asyncio
async def test_success_resets_the_account_counter(redis):
    for _ in range(5):
        await login_throttle.record_failure(ACCT, IP)
    await login_throttle.reset(ACCT)
    assert await login_throttle.blocked_for(ACCT, IP) == 0


@pytest.mark.asyncio
async def test_ip_blocked_across_many_accounts(redis):
    # 20 failures spread over distinct usernames from ONE ip → the ip is throttled even for a
    # brand-new account it hasn't targeted yet (distributed brute force from a single host).
    for i in range(20):
        await login_throttle.record_failure(f"victim{i}", IP)
    assert await login_throttle.blocked_for("never-tried", IP) > 0


@pytest.mark.asyncio
async def test_fail_open_when_redis_unbound():
    # Redis outage must never lock everyone out: the check fails OPEN and writes are best-effort.
    login_throttle.bind(None)
    assert await login_throttle.blocked_for(ACCT, IP) == 0
    await login_throttle.record_failure(ACCT, IP)  # must not raise
    await login_throttle.reset(ACCT)               # must not raise


@pytest.mark.asyncio
async def test_throttle_audit_is_deduped_per_ip(redis):
    # A blocked source can send unlimited refused requests. The throttle audit must fire ONCE per IP
    # per window, or an attacker floods the trail — so only the first call is truthy.
    assert await login_throttle.first_throttle_from_ip(IP) is True
    for _ in range(50):
        assert await login_throttle.first_throttle_from_ip(IP) is False
    # a different source is independent — its own first throttle still records
    assert await login_throttle.first_throttle_from_ip("198.51.100.9") is True


@pytest.mark.asyncio
async def test_throttle_dedup_is_amplification_safe_when_redis_unbound():
    # If the marker can't be set, skip the audit (False) rather than write it — auditing on every
    # error would be the amplification this guards against.
    login_throttle.bind(None)
    assert await login_throttle.first_throttle_from_ip(IP) is False
