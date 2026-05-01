#!/usr/bin/env python3
"""Deterministic stress harness for Tier 3 prompt/basis planning.

This intentionally avoids LLM calls, image generation, C# generation, and tML
builds. It checks whether Prompt Director + deterministic basis seeding produce
usable `mechanics_ir` contracts for a spread of high-ceiling weapon prompts.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

_AGENTS_DIR = Path(__file__).resolve().parent
if str(_AGENTS_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENTS_DIR))

from architect.prompt_director import enhance_prompt  # noqa: E402
from architect.ranged_defaults import apply_default_custom_projectile  # noqa: E402


DEFAULT_PROMPTS = [
    "a staff that shoots gojo's hollow purple from jjk",
    "a wand that fires a sweeping moon beam lance",
    "a cursed pistol that opens rifts under enemies",
    "a bow that plants delayed void marks then collapses them",
    "a hammer that sends a ground rupture forward and breaks weak blocks",
    "a tome that summons a temporary eye that fires a beam for the player",
    "a spear that throws orbiting shards which converge into one final strike",
    "a gun that fires a ricocheting portal round that tears space at each bounce",
]


@dataclass
class StressResult:
    prompt: str
    enhanced_prompt: str
    sub_type: str
    protected_reference_terms: list[str]
    projectile_reference_subject: str
    atom_kinds: list[str]
    passed: bool
    failures: list[str]


def run_deterministic_stress(
    prompts: Iterable[str] = DEFAULT_PROMPTS, *, tier: str = "Tier3_Hardmode"
) -> list[StressResult]:
    return [_stress_prompt(prompt, tier=tier) for prompt in prompts]


def _stress_prompt(prompt: str, *, tier: str) -> StressResult:
    director = enhance_prompt(prompt, tier=tier)
    data = _base_manifest(prompt, sub_type=_infer_sub_type(prompt))
    apply_default_custom_projectile(data, director.enhanced_prompt, tier)

    ir = data.get("mechanics_ir") if isinstance(data.get("mechanics_ir"), dict) else {}
    atoms = ir.get("atoms") if isinstance(ir, dict) else []
    atom_kinds = [
        str(atom.get("kind"))
        for atom in atoms
        if isinstance(atom, dict) and str(atom.get("kind") or "").strip()
    ]

    failures: list[str] = []
    if len(set(atom_kinds)) < 2:
        failures.append("mechanics_ir produced fewer than 2 atom kinds")
    if not director.enhanced_prompt.strip():
        failures.append("enhanced_prompt is empty")

    return StressResult(
        prompt=prompt,
        enhanced_prompt=director.enhanced_prompt,
        sub_type=data["sub_type"],
        protected_reference_terms=list(director.protected_reference_terms),
        projectile_reference_subject=director.reference_slots.projectile.subject,
        atom_kinds=atom_kinds,
        passed=not failures,
        failures=failures,
    )


def _base_manifest(prompt: str, *, sub_type: str) -> dict:
    return {
        "item_name": "StressTestItem",
        "display_name": "Stress Test Item",
        "type": "weapon",
        "content_type": "Weapon",
        "sub_type": sub_type,
        "tier": "Tier3_Hardmode",
        "mechanics": {"custom_projectile": None, "shoot_projectile": None},
        "visuals": {"description": prompt},
        "projectile_visuals": {
            "description": prompt,
            "icon_size": [20, 20],
        },
    }


def _infer_sub_type(prompt: str) -> str:
    lowered = prompt.lower()
    for token, sub_type in (
        ("staff", "Staff"),
        ("wand", "Wand"),
        ("pistol", "Pistol"),
        ("bow", "Bow"),
        ("hammer", "Hammer"),
        ("tome", "Tome"),
        ("spear", "Spear"),
        ("gun", "Gun"),
    ):
        if token in lowered:
            return sub_type
    return "Staff"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tier", default="Tier3_Hardmode")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    return parser.parse_args()


def main() -> None:
    ns = _parse_args()
    results = run_deterministic_stress(DEFAULT_PROMPTS, tier=ns.tier)
    if ns.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            atoms = ", ".join(result.atom_kinds)
            print(f"{status} | {result.sub_type:<7} | {atoms} | {result.prompt}")
            for failure in result.failures:
                print(f"  - {failure}")
    raise SystemExit(0 if all(result.passed for result in results) else 1)


if __name__ == "__main__":
    main()
