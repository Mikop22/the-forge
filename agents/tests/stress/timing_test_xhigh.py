"""Quick timing test: measure Forge Master response times with xhigh reasoning.

Run with:
    cd agents && source .venv/bin/activate
    python timing_test_xhigh.py
"""

from __future__ import annotations

import os
import sys
import time

_AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _AGENTS_DIR not in sys.path:
    sys.path.insert(0, _AGENTS_DIR)

from forge_master.forge_master import CoderAgent

# A variety of manifests to exercise different code paths (simple → complex)
TEST_MANIFESTS = [
    {
        "label": "simple_sword",
        "manifest": {
            "item_name": "TimingTestSword",
            "display_name": "Timing Test Sword",
            "tooltip": "A basic sword for timing.",
            "type": "Weapon",
            "sub_type": "Sword",
            "stats": {
                "damage": 15, "knockback": 4.0, "crit_chance": 4,
                "use_time": 25, "auto_reuse": True, "rarity": "ItemRarityID.Green",
            },
            "mechanics": {
                "on_hit_buff": "BuffID.OnFire",
                "crafting_material": "ItemID.IronBar",
                "crafting_cost": 5,
                "crafting_tile": "TileID.Anvils",
            },
        },
    },
    {
        "label": "channeled_staff",
        "manifest": {
            "item_name": "TimingChannelStaff",
            "display_name": "Timing Channel Staff",
            "tooltip": "A channeled beam staff for timing.",
            "type": "Weapon",
            "sub_type": "Staff",
            "stats": {
                "damage": 35, "knockback": 3.0, "crit_chance": 4,
                "use_time": 20, "auto_reuse": True, "rarity": "ItemRarityID.Pink",
            },
            "mechanics": {
                "shot_style": "channeled",
                "custom_projectile": False,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 10,
                "crafting_tile": "TileID.Anvils",
            },
        },
    },
    {
        "label": "homing_staff",
        "manifest": {
            "item_name": "TimingHomingStaff",
            "display_name": "Timing Homing Staff",
            "tooltip": "A homing orb staff for timing.",
            "type": "Weapon",
            "sub_type": "Staff",
            "stats": {
                "damage": 30, "knockback": 4.0, "crit_chance": 4,
                "use_time": 25, "auto_reuse": True, "rarity": "ItemRarityID.Orange",
            },
            "mechanics": {
                "shot_style": "homing",
                "crafting_material": "ItemID.GoldBar",
                "crafting_cost": 10,
                "crafting_tile": "TileID.Anvils",
            },
        },
    },
]

CURRENT_TIMEOUT = 120  # seconds — what's configured in forge_master.py


def run_timing_tests() -> None:
    agent = CoderAgent()

    print("\n" + "=" * 72)
    print(f"{'LABEL':<24} {'TIME':>8}  {'STATUS':^8}  {'vs TIMEOUT'}")
    print("=" * 72)

    results = []

    for tc in TEST_MANIFESTS:
        label = tc["label"]
        t0 = time.monotonic()

        try:
            result = agent.write_code(tc["manifest"])
            elapsed = time.monotonic() - t0
            status = result.get("status", "?")
        except Exception as exc:
            elapsed = time.monotonic() - t0
            status = f"ERR: {type(exc).__name__}"

        pct = (elapsed / CURRENT_TIMEOUT) * 100
        margin_ok = "✅" if elapsed < CURRENT_TIMEOUT * 0.7 else ("⚠️" if elapsed < CURRENT_TIMEOUT else "❌")

        print(f"{label:<24} {elapsed:>7.1f}s  {status:^8}  {pct:>5.1f}% of {CURRENT_TIMEOUT}s {margin_ok}")
        results.append((label, elapsed, status))

    print("=" * 72)

    max_time = max(t for _, t, _ in results)
    avg_time = sum(t for _, t, _ in results) / len(results)
    any_failed = any("ERR" in s or "error" in s for _, _, s in results)
    any_timeout = any(t >= CURRENT_TIMEOUT for _, t, _ in results)

    print(f"\nMax: {max_time:.1f}s  |  Avg: {avg_time:.1f}s  |  Current timeout: {CURRENT_TIMEOUT}s")

    if any_timeout:
        suggested = int(max_time * 1.5)
        print(f"\n❌ TIMEOUT HIT — increase to at least {suggested}s")
    elif max_time > CURRENT_TIMEOUT * 0.7:
        suggested = int(max_time * 1.5)
        print(f"\n⚠️  Cutting it close (>{CURRENT_TIMEOUT * 0.7:.0f}s) — consider bumping to {suggested}s")
    else:
        print(f"\n✅ Comfortable margin — {CURRENT_TIMEOUT}s timeout is fine")

    if any_failed:
        print("\n⚠️  Some requests returned errors (check status column)")


if __name__ == "__main__":
    run_timing_tests()
