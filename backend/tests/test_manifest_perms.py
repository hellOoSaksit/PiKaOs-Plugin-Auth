"""The auth manifest owns the cross-cutting admin perms that Core routes enforce (infra.manage for
storage, options.manage for the shared-nav write). G1: options.manage was dangling (declared nowhere →
never in the catalog → no role could hold it → PUT /settings/nav was ungrantable). Declaring it here
puts it in the catalog whenever auth is enabled.
"""
from __future__ import annotations

import json
from pathlib import Path

from app import plugin_loader

_MANIFEST = Path(__file__).resolve().parent.parent / "manifest.json"


def test_manifest_declares_options_manage():
    perms = {p["key"] for p in json.loads(_MANIFEST.read_text(encoding="utf-8"))["permissions"]}
    assert "options.manage" in perms


def test_options_manage_enters_the_catalog_when_auth_enabled():
    # PLUGIN_MANIFESTS is discovered at import from app/plugins/* (auth is linked); after the manifest
    # edit + re-link (plan Task 2 Step 4) the discovered auth manifest carries options.manage.
    catalog = plugin_loader.permission_catalog({"auth"}, plugin_loader.PLUGIN_MANIFESTS)
    assert "options.manage" in {p["key"] for p in catalog}
