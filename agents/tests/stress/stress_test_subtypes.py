"""Stress-test Suite 2: shot_style routing for non-Staff sub_types.

Run with:
    OPENAI_API_KEY=<key> .venv/bin/python stress_test_subtypes.py
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

TEST_CASES = [
    {
        "prompt": "A sword that summons blades raining from the sky",
        "sub_type": "Sword",
        "expected_shot_style": "sky_strike",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
    },
    {
        "prompt": "A bow that fires homing arrows that track enemies",
        "sub_type": "Bow",
        "expected_shot_style": "homing",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
    },
    {
        "prompt": "A gun that fires explosive rounds",
        "sub_type": "Gun",
        "expected_shot_style": "explosion",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
    },
    {
        "prompt": "A thrown returning disc",
        "sub_type": "Sword",
        "expected_shot_style": "boomerang",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
    },
    {
        "prompt": "A rifle that fires piercing energy bolts through walls",
        "sub_type": "Gun",
        "expected_shot_style": "pierce",
        "tier": "Tier2_Dungeon",
        "content_type": "Weapon",
    },
]


def run_tests() -> None:
    architect = ArchitectAgent()
    coder = CoderAgent()

    results = []

    print("\n" + "=" * 86)
    print(f"{'SUB_TYPE':<8} {'EXPECTED':<16} {'ACTUAL':<18} {'MANIFEST':^10} {'CODE':^8} {'STATUS':<12} NOTES")
    print("=" * 86)

    for tc in TEST_CASES:
        expected = tc["expected_shot_style"]
        sub_type = tc["sub_type"]
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
                sub_type=sub_type,
            )
        except Exception as exc:
            notes.append(f"Architect error: {exc}")
            manifest_ok = False
            results.append((f"{sub_type}/{expected}", False, notes))
            _print_row(sub_type, expected, actual_style, "FAIL", "SKIP", "error", notes)
            continue

        actual_style = manifest.get("mechanics", {}).get("shot_style", "<missing>")
        if actual_style != expected:
            notes.append(f"WRONG shot_style: got {actual_style!r}, expected {expected!r}")
            manifest_ok = False

        # -- Coder --
        try:
            code_result = coder.write_code(manifest)
        except Exception as exc:
            notes.append(f"Coder error: {exc}")
            code_ok = False
            results.append((f"{sub_type}/{expected}", False, notes))
            _print_row(sub_type, expected, actual_style, "PASS" if manifest_ok else "FAIL", "FAIL", "error", notes)
            continue

        status = code_result.get("status", "<missing>")
        if status != "success":
            err = code_result.get("error") or {}
            msg = err.get("message", str(err))[:80]
            notes.append(f"status={status!r}: {msg}")
            code_ok = False

        cs_code = code_result.get("cs_code", "") or ""
        cs_errors = validate_cs(cs_code)
        if cs_errors:
            notes.append(f"validate_cs errors: {cs_errors}")
            code_ok = False

        passed = manifest_ok and code_ok and status == "success"
        results.append((f"{sub_type}/{expected}", passed, notes))
        _print_row(
            sub_type,
            expected,
            actual_style,
            "PASS" if manifest_ok else "FAIL",
            "PASS" if (code_ok and status == "success") else "FAIL",
            status,
            notes,
        )

    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 86)
    print(f"\nSUMMARY: {passed_count}/{total} passed\n")

    if passed_count < total:
        print("FAILED CASES:")
        for key, passed, notes in results:
            if not passed:
                print(f"  [{key}]")
                for note in notes:
                    print(f"    - {note}")
        print()


def _print_row(sub_type, expected, actual, manifest_label, code_label, status, notes):
    note_str = "; ".join(notes) if notes else "OK"
    if len(note_str) > 40:
        note_str = note_str[:37] + "..."
    print(f"{sub_type:<8} {expected:<16} {actual:<18} {manifest_label:^10} {code_label:^8} {status:<12} {note_str}")


if __name__ == "__main__":
    run_tests()
