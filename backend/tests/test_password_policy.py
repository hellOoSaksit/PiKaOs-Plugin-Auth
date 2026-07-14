"""Unit tests for validate_password_strength — the password policy applied on create/change.

Pure function (no redis/db/live server). Policy is NIST SP 800-63B Rev 4-aligned: a real minimum length
+ a common/compromised blocklist, and deliberately NO composition rules (no forced character mixes). It
is NOT applied on login (login checks the stored hash) nor on system seeding.
"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.plugins.auth.security import WeakPassword, validate_password_strength


@pytest.fixture(autouse=True)
def _known_min(monkeypatch):
    monkeypatch.setattr(settings, "password_min_length", 12, raising=False)


def test_rejects_a_password_shorter_than_the_minimum():
    with pytest.raises(WeakPassword):
        validate_password_strength("short1")  # 6 chars < 12


def test_accepts_a_strong_unique_password():
    validate_password_strength("correct horse battery staple")  # long, spaces allowed (NIST), not common


def test_rejects_a_common_password_even_when_long_enough():
    # meets the length bar but is a well-known weak secret → the blocklist must still reject it
    with pytest.raises(WeakPassword):
        validate_password_strength("123456789012")


def test_blocklist_match_is_case_insensitive():
    with pytest.raises(WeakPassword):
        validate_password_strength("Password1234")


def test_no_composition_rules_a_long_all_lowercase_passphrase_is_fine():
    # NIST Rev 4: SHALL NOT require character-class mixes — an all-lowercase passphrase passes on length
    validate_password_strength("thequickbrownfoxjumps")
