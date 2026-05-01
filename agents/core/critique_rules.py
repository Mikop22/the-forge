"""Deterministic critique rules for generated Terraria mod C#."""

from __future__ import annotations

import re

from core.critique_engine import CritiqueContext, critique_generated_code
from core.csharp_parse import first_modprojectile_setdefaults_body


def critique_violations(manifest: dict, cs_code: str) -> list[str]:
    """Run structural critique and return prefixed strings for Roslyn-style surfaces.

    Each entry is ``CRITIQUE: [rule_id] message`` suitable for gatekeeper repair loops.
    """
    item_name = str(manifest.get("item_name") or "GeneratedItem")
    critique = critique_generated_code(
        cs_code,
        CritiqueContext(
            manifest=manifest,
            relative_path=f"Content/Items/{item_name}.cs",
        ),
    )
    return [f"CRITIQUE: [{issue.rule}] {issue.message}" for issue in critique.issues]


def validate_projectile_hitbox_contract(manifest: dict, cs_code: str) -> list[str]:
    """Ensure generated projectile dimensions honor Pixelsmith-derived hitbox size."""
    if not re.search(r"class\s+\w+\s*:\s*(?:[\w.]+\.)?ModProjectile\b", cs_code):
        return []
    projectile_visuals = manifest.get("projectile_visuals")
    if not isinstance(projectile_visuals, dict):
        return []
    hitbox_size = projectile_visuals.get("hitbox_size")
    if not isinstance(hitbox_size, list) or len(hitbox_size) != 2:
        return []
    try:
        expected_width, expected_height = [int(value) for value in hitbox_size]
    except (TypeError, ValueError):
        return []

    setdefaults_body = first_modprojectile_setdefaults_body(cs_code)
    width_match = re.search(r"Projectile\.width\s*=\s*(\d+)\s*;", setdefaults_body)
    height_match = re.search(r"Projectile\.height\s*=\s*(\d+)\s*;", setdefaults_body)
    if not width_match or not height_match:
        return [
            "Projectile hitbox must match projectile_visuals.hitbox_size "
            f"{hitbox_size}; missing Projectile.width or Projectile.height assignment."
        ]

    actual_width = int(width_match.group(1))
    actual_height = int(height_match.group(1))
    if (actual_width, actual_height) == (expected_width, expected_height):
        return []

    return [
        "Projectile hitbox must match projectile_visuals.hitbox_size "
        f"{hitbox_size}; found Projectile.width={actual_width}, "
        f"Projectile.height={actual_height}."
    ]
