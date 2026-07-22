"""The auth manifest owns the cross-cutting admin perms that Core gates on (infra.manage for
storage, options.manage for the shared-nav write, mcp.manage for the MCP & Skills screen). G1:
options.manage was dangling (declared nowhere -> never in the catalog -> no role could hold it ->
PUT /settings/nav was ungrantable). Declaring them here puts them in the catalog whenever auth is
enabled. Parametrized so the next cross-cutting perm is one list entry, not another test file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app import plugin_loader

_MANIFEST = Path(__file__).resolve().parent.parent / "manifest.json"

# Perms Core enforces but does not declare — every one of these must be declared here.
CROSS_CUTTING = ["options.manage", "mcp.manage"]


@pytest.mark.parametrize("key", CROSS_CUTTING)
def test_manifest_declares_cross_cutting_perm(key):
    perms = {p["key"] for p in json.loads(_MANIFEST.read_text(encoding="utf-8"))["permissions"]}
    assert key in perms


@pytest.mark.parametrize("key", CROSS_CUTTING)
def test_cross_cutting_perm_enters_the_catalog_when_auth_enabled(key):
    # PLUGIN_MANIFESTS is discovered at import from app/plugins/* (auth must be linked).
    catalog = plugin_loader.permission_catalog({"auth"}, plugin_loader.PLUGIN_MANIFESTS)
    assert key in {p["key"] for p in catalog}
