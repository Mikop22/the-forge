"""Stress-test Suite 1: Ambiguous prompts that could map to multiple shot_styles.

Goal: verify the architect picks ONE valid style and the coder generates working code.

Run with:
    OPENAI_API_KEY=<key> .venv/bin/python stress_test_ambiguous_prompts.py
"""

from __future__ import annotations

import sys
import os

_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _AGENTS_DIR not in sys.path:
    sys.path.insert(0, _AGENTS_DIR)

from architect.architect import ArchitectAgent
from forge_master.forge_master import CoderAgent
from forge_master.templates import validate_cs
from architect.models import SHOT_STYLE_CHOICES

VALID_SHOT_STYLES = set(SHOT_STYLE_CHOICES)

TEST_CASES = [
    {
        "label": "boomerang+explosion",
        "prompt": "A boomerang blade that explodes when it returns to the player",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Sword",
    },
    {
        "label": "homing+pierce",
        "prompt": "A homing missile that pierces through the first enemy it hits",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Gun",
    },
    {
        "label": "pierce+chain",
        "prompt": "A staff that fires a beam of lightning that chains between nearby enemies",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Staff",
    },
    {
        "label": "homing+explosion",
        "prompt": "A launcher that fires seeking rockets with explosive warheads",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Gun",
    },
    {
        "label": "orbit+homing",
        "prompt": "A sword that creates orbiting projectiles that also home toward enemies",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
        "sub_type": "Sword",
    },
]


def run_tests() -> None:
    architect = ArchitectAgent()
    coder = CoderAgent()

    results = []

    print("\n" + "=" * 80)
    print(f"{'LABEL':<22} {'SHOT_STYLE':<18} {'MANIFEST':^10} {'CODE':^8} {'STATUS':<12} NOTES")
    print("=" * 80)

    for tc in TEST_CASES:
        label = tc["label"]
        notes: list[str] = []
        manifest_ok = True
        code_ok = True
        actual_style = "<error>"
        status = "<error>"

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
            manifest_ok = False
            results.append((label, False, notes))
            _print_row(label, actual_style, "FAIL", "SKIP", "error", notes)
            continue

        actual_style = manifest.get("mechanics", {}).get("shot_style", "<missing>")
        if actual_style not in VALID_SHOT_STYLES:
            notes.append(f"INVALID shot_style: {actual_style!r}")
            manifest_ok = False

        # -- Coder --
        try:
            code_result = coder.write_code(manifest)
        except Exception as exc:
            notes.append(f"Coder error: {exc}")
            code_ok = False
            results.append((label, False, notes))
            _print_row(label, actual_style, "PASS" if manifest_ok else "FAIL", "FAIL", "error", notes)
            continue

        status = code_result.get("status", "<missing>")
        if status != "success":
            err = code_result.get("error") or {}
            msg = err.get("message", str(err))[:100]
            notes.append(f"status={status!r}: {msg}")
            code_ok = False

        cs_code = code_result.get("cs_code", "") or ""
        cs_errors = validate_cs(cs_code)
        if cs_errors:
            notes.append(f"validate_cs errors: {cs_errors}")
            code_ok = False

        passed = manifest_ok and code_ok and status == "success"
        results.append((label, passed, notes))
        _print_row(
            label,
            actual_style,
            "PASS" if manifest_ok else "FAIL",
            "PASS" if (code_ok and status == "success") else "FAIL",
            status,
            notes,
        )

    # Summary
    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 80)
    print(f"\nSUMMARY: {passed_count}/{total} passed\n")

    if passed_count < total:
        print("FAILED CASES:")
        for lbl, passed, notes in results:
            if not passed:
                print(f"  [{lbl}]")
                for note in notes:
                    print(f"    - {note}")
        print()


def _print_row(label, shot_style, manifest_label, code_label, status, notes):
    note_str = "; ".join(notes) if notes else "OK"
    if len(note_str) > 45:
        note_str = note_str[:42] + "..."
    print(f"{label:<22} {shot_style:<18} {manifest_label:^10} {code_label:^8} {status:<12} {note_str}")


if __name__ == "__main__":
    run_tests()
