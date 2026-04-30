"""Tests for deterministic hjson generation."""
from __future__ import annotations

from core.hjson_gen import generate_hjson


def test_generate_hjson_emits_valid_structure() -> None:
    result = generate_hjson(
        item_name="VoidPistol",
        display_name="Void Pistol",
        tooltip="Fires void seeds",
    )
    assert "Mods: {" in result
    assert "ForgeGeneratedMod: {" in result
    assert "VoidPistol: {" in result
    assert '"Void Pistol"' in result
    assert '"Fires void seeds"' in result


def test_generate_hjson_escapes_special_characters() -> None:
    result = generate_hjson(
        item_name="QuoteWand",
        display_name='Wand "with" quotes',
        tooltip="Has\nnewlines and {braces}",
    )
    assert r'\"with\"' in result
    assert r"\n" in result
    assert "{braces}" in result


def test_generate_hjson_supports_custom_mod_name() -> None:
    result = generate_hjson(
        item_name="Foo",
        display_name="Foo",
        tooltip="",
        mod_name="OtherMod",
    )
    assert "OtherMod: {" in result
