"""Deterministic critique rules for generated Terraria mod C#."""

from __future__ import annotations

import re

from forge_master.critique import CritiqueContext, critique_generated_code


def critique_violations(manifest: dict, cs_code: str) -> list[str]:
    item_name = str(manifest.get("item_name") or "GeneratedItem")
    critique = critique_generated_code(
        cs_code,
        CritiqueContext(
            manifest=manifest,
            relative_path=f"Content/Items/{item_name}.cs",
        ),
    )
    return [f"CRITIQUE: [{issue.rule}] {issue.message}" for issue in critique.issues]


def _strip_csharp_comments(code: str) -> str:
    code = re.sub(r"/\*[\s\S]*?\*/", "", code)
    return re.sub(r"//.*", "", code)


def _balanced_block(text: str, open_idx: int) -> str:
    depth = 0
    for idx in range(open_idx, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
            continue
        if char != "}":
            continue
        depth -= 1
        if depth == 0:
            return text[open_idx + 1 : idx]
    return ""


def _first_modprojectile_setdefaults_body(cs_code: str) -> str:
    code = _strip_csharp_comments(cs_code)
    for class_match in re.finditer(
        r"class\s+\w+\s*:\s*(?:[\w.]+\.)?ModProjectile\b", code
    ):
        class_open = code.find("{", class_match.end())
        if class_open == -1:
            continue
        class_body = _balanced_block(code, class_open)
        method_match = re.search(r"override\s+void\s+SetDefaults\s*\(\s*\)", class_body)
        if not method_match:
            continue
        method_open = class_body.find("{", method_match.end())
        if method_open == -1:
            continue
        return _balanced_block(class_body, method_open)
    return ""


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

    setdefaults_body = _first_modprojectile_setdefaults_body(cs_code)
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
