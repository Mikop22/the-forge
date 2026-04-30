"""Tests for core.critique_rules."""
from __future__ import annotations

from core.critique_rules import critique_violations, validate_projectile_hitbox_contract


def test_critique_violations_returns_list() -> None:
    manifest = {"item_name": "Test", "display_name": "Test"}
    cs_code = "namespace ForgeGeneratedMod.Content.Items { class Test {} }"
    result = critique_violations(manifest, cs_code)
    assert isinstance(result, list)


def test_validate_projectile_hitbox_contract_returns_list() -> None:
    manifest = {"projectile_visuals": {"icon_size": [18, 18]}}
    cs_code = ""
    result = validate_projectile_hitbox_contract(manifest, cs_code)
    assert isinstance(result, list)
