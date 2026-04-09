"""Stress-test Suite 4: on-hit buff prompt normalization.

Run with:
    OPENAI_API_KEY=<key> .venv/bin/python stress_test_buff_normalization.py
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
from architect.models import VALID_BUFF_IDS

TEST_CASES = [
    {
        "prompt": "A staff that sets enemies on fire on hit",
        "expected_buff": "BuffID.OnFire",
        "sub_type": "Staff",
    },
    {
        "prompt": "A blade that poisons enemies with each strike",
        "expected_buff": "BuffID.Poisoned",
        "sub_type": "Sword",
    },
    {
        "prompt": "A wand that inflicts Frostburn on contact",
        "expected_buff": "BuffID.Frostburn",
        "sub_type": "Staff",
    },
    {
        "prompt": "A sword that applies Cursed Inferno debuff",
        "expected_buff": "BuffID.CursedInferno",
        "sub_type": "Sword",
    },
    {
        "prompt": "A staff that causes ShadowFlame on hit",
        "expected_buff": "BuffID.ShadowFlame",
        "sub_type": "Staff",
    },
]


def run_tests() -> None:
    architect = ArchitectAgent()
    coder = CoderAgent()

    results = []

    print("\n" + "=" * 90)
    print(f"{'EXPECTED_BUFF':<24} {'ACTUAL_BUFF':<24} {'IN_VALID':^10} {'MATCH':^8} {'CODE':^8} {'STATUS':<12} NOTES")
    print("=" * 90)

    for tc in TEST_CASES:
        expected_buff = tc["expected_buff"]
        notes: list[str] = []
        buff_ok = True
        code_ok = True
        actual_buff = "<error>"
        status = "<error>"

        # -- Architect --
        try:
            manifest = architect.generate_manifest(
                prompt=tc["prompt"],
                tier="Tier2_Dungeon",
                content_type="Weapon",
                sub_type=tc["sub_type"],
            )
        except Exception as exc:
            notes.append(f"Architect error: {exc}")
            buff_ok = False
            results.append((expected_buff, False, notes))
            _print_row(expected_buff, actual_buff, False, False, False, "error", notes)
            continue

        mechanics = manifest.get("mechanics", {})
        actual_buff = mechanics.get("on_hit_buff") or mechanics.get("buff_id") or "<null>"

        in_valid = actual_buff in VALID_BUFF_IDS
        match = actual_buff == expected_buff

        if actual_buff == "<null>":
            notes.append("on_hit_buff is null")
            buff_ok = False
        elif not in_valid:
            notes.append(f"buff {actual_buff!r} not in VALID_BUFF_IDS")
            buff_ok = False
        elif not match:
            notes.append(f"WRONG buff: got {actual_buff!r}, expected {expected_buff!r}")
            buff_ok = False

        # -- Coder --
        try:
            code_result = coder.write_code(manifest)
        except Exception as exc:
            notes.append(f"Coder error: {exc}")
            code_ok = False
            results.append((expected_buff, False, notes))
            _print_row(expected_buff, actual_buff, in_valid, match, False, "error", notes)
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

        passed = buff_ok and code_ok and status == "success"
        results.append((expected_buff, passed, notes))
        _print_row(expected_buff, actual_buff, in_valid, match, code_ok and status == "success", status, notes)

    passed_count = sum(1 for _, p, _ in results if p)
    total = len(results)
    print("=" * 90)
    print(f"\nSUMMARY: {passed_count}/{total} passed\n")

    if passed_count < total:
        print("FAILED CASES:")
        for buff, passed, notes in results:
            if not passed:
                print(f"  [{buff}]")
                for note in notes:
                    print(f"    - {note}")
        print()


def _print_row(expected, actual, in_valid, match, code_ok, status, notes):
    note_str = "; ".join(notes) if notes else "OK"
    if len(note_str) > 38:
        note_str = note_str[:35] + "..."
    valid_label = "YES" if in_valid else "NO"
    match_label = "PASS" if match else "FAIL"
    code_label = "PASS" if code_ok else "FAIL"
    print(
        f"{expected:<24} {actual:<24} {valid_label:^10} {match_label:^8} {code_label:^8} {status:<12} {note_str}"
    )


if __name__ == "__main__":
    run_tests()
