"""Stress-test script: verify all 7 shot styles route correctly through the Forge pipeline.

Run with:
    OPENAI_API_KEY=<key> .venv/bin/python stress_test_shot_styles.py
"""

from __future__ import annotations

import sys
import os

# Ensure the agents directory is on sys.path for package imports.
_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _AGENTS_DIR not in sys.path:
    sys.path.insert(0, _AGENTS_DIR)

from architect.architect import ArchitectAgent
from forge_master.forge_master import CoderAgent

# ---------------------------------------------------------------------------
# Test cases definition
# ---------------------------------------------------------------------------

TEST_CASES = [
    {
        "shot_style": "sky_strike",
        "prompt": "A staff that calls down bolts of lightning from the heavens",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
    {
        "shot_style": "homing",
        "prompt": "A magic wand that fires seeking missiles that chase enemies",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
    {
        "shot_style": "boomerang",
        "prompt": "A throwing blade that returns to the player after hitting enemies",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Sword",
    },
    {
        "shot_style": "orbit",
        "prompt": "A magical staff that makes glowing orbs circle around the player",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
    {
        "shot_style": "explosion",
        "prompt": "A rocket launcher that fires explosive shells with area damage",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Gun",
    },
    {
        "shot_style": "pierce",
        "prompt": "A staff that shoots a beam that passes through all enemies",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
    {
        "shot_style": "chain_lightning",
        "prompt": "A staff where lightning jumps from enemy to enemy on hit",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
]

# Per-style code pattern requirements.
# Each value is a list of (description, check_fn) pairs.
CODE_PATTERNS: dict[str, list[tuple[str, callable]]] = {
    "sky_strike": [
        ("override bool Shoot( present",        lambda cs: "override bool Shoot(" in cs),
        ("ModProjectile absent",                lambda cs: "ModProjectile" not in cs),
    ],
    "homing": [
        ("ModProjectile present",               lambda cs: "ModProjectile" in cs),
        ("FindClosestNPC or CanBeChasedBy",     lambda cs: "FindClosestNPC" in cs or "CanBeChasedBy" in cs),
    ],
    "boomerang": [
        ("ModProjectile present",               lambda cs: "ModProjectile" in cs),
        ("ProjAIStyleID.Boomerang or aiStyle",  lambda cs: "ProjAIStyleID.Boomerang" in cs or "aiStyle" in cs),
    ],
    "orbit": [
        ("ModProjectile present",               lambda cs: "ModProjectile" in cs),
        ("Math.Cos or Math.Sin",                lambda cs: "Math.Cos" in cs or "Math.Sin" in cs),
    ],
    "explosion": [
        ("ModProjectile present",               lambda cs: "ModProjectile" in cs),
        ("OnKill or Resize",                    lambda cs: "OnKill" in cs or "Resize" in cs),
    ],
    "pierce": [
        ("ModProjectile present",               lambda cs: "ModProjectile" in cs),
        ("penetrate present",                   lambda cs: "penetrate" in cs),
    ],
    "chain_lightning": [
        ("ModProjectile present",               lambda cs: "ModProjectile" in cs),
        ("OnHitNPC present",                    lambda cs: "OnHitNPC" in cs),
    ],
}


def run_tests() -> None:
    architect = ArchitectAgent()
    coder = CoderAgent()

    results = []  # list of (shot_style, passed, notes)

    print("\n" + "=" * 72)
    print(f"{'SHOT STYLE':<18} {'MANIFEST':^10} {'CODE':^10} {'STATUS':<10}  NOTES")
    print("=" * 72)

    for tc in TEST_CASES:
        expected_style = tc["shot_style"]
        notes: list[str] = []
        manifest_ok = True
        code_ok = True

        # ---- 1. Architect ------------------------------------------------
        try:
            manifest = architect.generate_manifest(
                prompt=tc["prompt"],
                tier=tc["tier"],
                content_type=tc["content_type"],
                sub_type=tc["sub_type"],
            )
        except Exception as exc:
            notes.append(f"Architect error: {exc}")
            manifest_ok = False
            results.append((expected_style, False, notes))
            _print_row(expected_style, "FAIL", "SKIP", "error", notes)
            continue

        actual_style = manifest.get("mechanics", {}).get("shot_style", "<missing>")
        if actual_style != expected_style:
            notes.append(f"WRONG shot_style: got {actual_style!r}, expected {expected_style!r}")
            manifest_ok = False

        # ---- 2. Coder ----------------------------------------------------
        try:
            code_result = coder.write_code(manifest)
        except Exception as exc:
            notes.append(f"Coder error: {exc}")
            code_ok = False
            results.append((expected_style, False, notes))
            _print_row(
                expected_style,
                "PASS" if manifest_ok else "FAIL",
                "FAIL",
                "error",
                notes,
            )
            continue

        status = code_result.get("status", "<missing>")
        if status != "success":
            err = code_result.get("error") or {}
            first_err = err.get("message", str(err))[:120]
            notes.append(f"Coder status={status!r}: {first_err}")
            code_ok = False

        # ---- 3. Code pattern assertions ----------------------------------
        cs_code = code_result.get("cs_code", "") or ""
        for pattern_desc, check_fn in CODE_PATTERNS.get(expected_style, []):
            try:
                if not check_fn(cs_code):
                    notes.append(f"Pattern FAIL: {pattern_desc}")
                    code_ok = False
            except Exception as exc:
                notes.append(f"Pattern check error ({pattern_desc}): {exc}")
                code_ok = False

        passed = manifest_ok and code_ok and status == "success"
        results.append((expected_style, passed, notes))

        manifest_label = "PASS" if manifest_ok else "FAIL"
        code_label = "PASS" if (code_ok and status == "success") else "FAIL"
        _print_row(expected_style, manifest_label, code_label, status, notes)

    # ---- Summary ---------------------------------------------------------
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)

    print("=" * 72)
    print(f"\nSUMMARY: {passed_count}/{total} passed\n")

    if passed_count < total:
        print("FAILED CASES:")
        for style, passed, notes in results:
            if not passed:
                print(f"  [{style}]")
                for note in notes:
                    print(f"    - {note}")
        print()


def _print_row(
    shot_style: str,
    manifest_label: str,
    code_label: str,
    status: str,
    notes: list[str],
) -> None:
    note_str = "; ".join(notes) if notes else "OK"
    # Truncate note for table display
    if len(note_str) > 55:
        note_str = note_str[:52] + "..."
    print(f"{shot_style:<18} {manifest_label:^10} {code_label:^10} {status:<12} {note_str}")


if __name__ == "__main__":
    run_tests()
