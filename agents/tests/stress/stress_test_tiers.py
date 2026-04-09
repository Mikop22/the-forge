"""Stress-test Suite 3: stat scaling across all 4 tiers.

Run with:
    OPENAI_API_KEY=<key> .venv/bin/python stress_test_tiers.py
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
from architect.models import TIER_TABLE

PROMPT = "A magic staff that fires a seeking projectile"

TIERS_IN_ORDER = [
    "Tier1_Starter",
    "Tier2_Dungeon",
    "Tier3_Hardmode",
    "Tier4_Endgame",
]

EXPECTED_DAMAGE_RANGES = {
    tier: TIER_TABLE[tier]["damage"] for tier in TIERS_IN_ORDER
}


def run_tests() -> None:
    architect = ArchitectAgent()
    coder = CoderAgent()

    results = []       # (tier, passed, damage, notes)
    damage_by_tier: dict[str, int | None] = {}

    print("\n" + "=" * 82)
    print(f"{'TIER':<20} {'EXPECTED':^14} {'ACTUAL':^10} {'RANGE':^8} {'CODE':^8} {'STATUS':<12} NOTES")
    print("=" * 82)

    for tier in TIERS_IN_ORDER:
        lo, hi = EXPECTED_DAMAGE_RANGES[tier]
        notes: list[str] = []
        range_ok = True
        code_ok = True
        status = "<error>"
        actual_damage: int | None = None

        # -- Architect --
        try:
            manifest = architect.generate_manifest(
                prompt=PROMPT,
                tier=tier,
                content_type="Weapon",
                sub_type="Staff",
            )
        except Exception as exc:
            notes.append(f"Architect error: {exc}")
            damage_by_tier[tier] = None
            results.append((tier, False, None, notes))
            _print_row(tier, lo, hi, None, False, False, "error", notes)
            continue

        stats = manifest.get("stats", {})
        actual_damage = stats.get("damage")
        damage_by_tier[tier] = actual_damage

        if actual_damage is None:
            notes.append("damage missing from manifest")
            range_ok = False
        elif not (lo <= actual_damage <= hi):
            notes.append(f"damage {actual_damage} out of range [{lo}, {hi}]")
            range_ok = False

        # -- Coder --
        try:
            code_result = coder.write_code(manifest)
        except Exception as exc:
            notes.append(f"Coder error: {exc}")
            code_ok = False
            results.append((tier, False, actual_damage, notes))
            _print_row(tier, lo, hi, actual_damage, range_ok, False, "error", notes)
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

        passed = range_ok and code_ok and status == "success"
        results.append((tier, passed, actual_damage, notes))
        _print_row(tier, lo, hi, actual_damage, range_ok, code_ok and status == "success", status, notes)

    # Monotonic damage check
    print()
    damages = [damage_by_tier.get(t) for t in TIERS_IN_ORDER]
    monotonic = all(
        damages[i] is not None and damages[i + 1] is not None and damages[i] < damages[i + 1]
        for i in range(len(damages) - 1)
    )
    mono_label = "PASS" if monotonic else "FAIL"
    print(f"Monotonic damage increase: {mono_label}  {damages}")

    passed_count = sum(1 for _, p, _, _ in results if p)
    total = len(results)
    overall_passed = passed_count == total and monotonic
    print("=" * 82)
    print(f"\nSUMMARY: {passed_count}/{total} tier checks passed, monotonic={mono_label}")
    print(f"OVERALL: {'PASS' if overall_passed else 'FAIL'}\n")

    if not overall_passed:
        print("FAILED CASES:")
        for tier, passed, dmg, notes in results:
            if not passed:
                print(f"  [{tier}] damage={dmg}")
                for note in notes:
                    print(f"    - {note}")
        if not monotonic:
            print(f"  [monotonic] damages={damages}")
        print()


def _print_row(tier, lo, hi, actual, range_ok, code_ok, status, notes):
    note_str = "; ".join(notes) if notes else "OK"
    if len(note_str) > 38:
        note_str = note_str[:35] + "..."
    range_label = "PASS" if range_ok else "FAIL"
    code_label = "PASS" if code_ok else "FAIL"
    actual_str = str(actual) if actual is not None else "N/A"
    print(
        f"{tier:<20} {f'[{lo}-{hi}]':^14} {actual_str:^10} {range_label:^8} {code_label:^8} {status:<12} {note_str}"
    )


if __name__ == "__main__":
    run_tests()
