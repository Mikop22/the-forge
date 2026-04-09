"""Stress-test Suite 5: manifest field completeness and safety invariants.

Run with:
    OPENAI_API_KEY=<key> .venv/bin/python stress_test_manifest_integrity.py
"""

from __future__ import annotations

import sys
import os
import re

_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _AGENTS_DIR not in sys.path:
    sys.path.insert(0, _AGENTS_DIR)

from architect.architect import ArchitectAgent
from forge_master.forge_master import CoderAgent
from forge_master.templates import validate_cs

TEST_CASES = [
    {
        "label": "fire_sword_t1",
        "prompt": "A flaming sword that leaves fire trails",
        "tier": "Tier1_Starter",
        "content_type": "Weapon",
        "sub_type": "Sword",
    },
    {
        "label": "homing_staff_t2",
        "prompt": "A magic staff that fires homing orbs toward enemies",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
    {
        "label": "explosion_gun_t2",
        "prompt": "A grenade launcher that fires explosive shells",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Gun",
    },
    {
        "label": "pierce_bow_t3",
        "prompt": "A longbow that fires arrows piercing through all enemies",
        "tier": "Tier3_Hardmode",
        "content_type": "Weapon",
        "sub_type": "Bow",
    },
    {
        "label": "chain_staff_t3",
        "prompt": "A lightning staff where bolts chain between enemies",
        "tier": "Tier3_Hardmode",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
    {
        "label": "sky_sword_t2",
        "prompt": "A sword that calls down meteor strikes on the target",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Sword",
    },
    {
        "label": "boomerang_sword_t1",
        "prompt": "A returning chakram that flies back to the player",
        "tier": "Tier1_Starter",
        "content_type": "Weapon",
        "sub_type": "Sword",
    },
    {
        "label": "orbit_staff_t4",
        "prompt": "A celestial staff that makes glowing spheres orbit the player",
        "tier": "Tier4_Endgame",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
    {
        "label": "direct_gun_t3",
        "prompt": "A precision rifle that fires a single powerful bullet",
        "tier": "Tier3_Hardmode",
        "content_type": "Weapon",
        "sub_type": "Gun",
    },
    {
        "label": "direct_sword_t4",
        "prompt": "An endgame greatsword with massive damage and slow swing",
        "tier": "Tier4_Endgame",
        "content_type": "Weapon",
        "sub_type": "Sword",
    },
]

PASCAL_CASE_RE = re.compile(r"^[A-Z][A-Za-z0-9]+$")


def check_manifest(manifest: dict, cs_code: str, status: str) -> list[str]:
    """Return list of failure descriptions (empty = all OK)."""
    failures: list[str] = []

    item_name = manifest.get("item_name", "")
    if not PASCAL_CASE_RE.match(item_name):
        failures.append(f"item_name not PascalCase: {item_name!r}")

    stats = manifest.get("stats", {})

    damage = stats.get("damage")
    if not isinstance(damage, int) or damage <= 0:
        failures.append(f"stats.damage invalid: {damage!r}")

    use_time = stats.get("use_time")
    if not isinstance(use_time, int) or not (5 <= use_time <= 60):
        failures.append(f"stats.use_time out of range [5,60]: {use_time!r}")

    rarity = stats.get("rarity", "")
    if not str(rarity).startswith("ItemRarityID."):
        failures.append(f"stats.rarity bad prefix: {rarity!r}")

    mechanics = manifest.get("mechanics", {})

    crafting_material = mechanics.get("crafting_material", "")
    if not str(crafting_material).startswith("ItemID."):
        failures.append(f"mechanics.crafting_material bad prefix: {crafting_material!r}")

    crafting_tile = mechanics.get("crafting_tile", "")
    if not str(crafting_tile).startswith("TileID."):
        failures.append(f"mechanics.crafting_tile bad prefix: {crafting_tile!r}")

    shot_style = mechanics.get("shot_style", "direct")
    custom_projectile = mechanics.get("custom_projectile", False)
    if shot_style != "direct" and custom_projectile:
        failures.append(
            f"custom_projectile=True but shot_style={shot_style!r} (should be False for non-direct)"
        )

    if status != "success":
        failures.append(f"coder status={status!r}")

    cs_errors = validate_cs(cs_code)
    if cs_errors:
        failures.append(f"validate_cs errors: {cs_errors}")

    return failures


def run_tests() -> None:
    architect = ArchitectAgent()
    coder = CoderAgent()

    results = []

    print("\n" + "=" * 72)
    print(f"{'LABEL':<24} {'RESULT':^8}  NOTES")
    print("=" * 72)

    for tc in TEST_CASES:
        label = tc["label"]
        notes: list[str] = []
        passed = False

        # -- Architect --
        try:
            manifest = architect.generate_manifest(
                prompt=tc["prompt"],
                tier=tc["tier"],
                content_type=tc["content_type"],
                sub_type=tc["sub_type"],
            )
        except Exception as exc:
            notes.append(f"Architect error: {exc}")
            results.append((label, False, notes))
            _print_row(label, False, notes)
            continue

        # -- Coder --
        try:
            code_result = coder.write_code(manifest)
        except Exception as exc:
            notes.append(f"Coder error: {exc}")
            results.append((label, False, notes))
            _print_row(label, False, notes)
            continue

        status = code_result.get("status", "<missing>")
        cs_code = code_result.get("cs_code", "") or ""

        failures = check_manifest(manifest, cs_code, status)
        if failures:
            notes.extend(failures)
            passed = False
        else:
            passed = True

        results.append((label, passed, notes))
        _print_row(label, passed, notes)

    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 72)
    print(f"\nSUMMARY: {passed_count}/{total} passed\n")

    if passed_count < total:
        print("FAILED CASES (details):")
        for lbl, passed, notes in results:
            if not passed:
                print(f"  [{lbl}]")
                for note in notes:
                    print(f"    - {note}")
        print()


def _print_row(label, passed, notes):
    result_label = "PASS" if passed else "FAIL"
    note_str = "; ".join(notes) if notes else "OK"
    if len(note_str) > 60:
        note_str = note_str[:57] + "..."
    print(f"{label:<24} {result_label:^8}  {note_str}")


if __name__ == "__main__":
    run_tests()
