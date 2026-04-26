"""User-realistic prompt corpus for The Forge QA.

Each row pins the expected sub_type so Tier A can fail fast on registry
regressions. Tier B/C subsets are taken from the same list.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QAPrompt:
    id: int
    prompt: str
    expected_sub_type: str
    tier: str
    category: str


CORPUS: tuple[QAPrompt, ...] = (
    QAPrompt(1,  "iron longsword", "Broadsword", "Tier1_Starter", "longsword (Broadsword family)"),
    QAPrompt(2,  "frostbrand katana with rime-etched edge", "Sword", "Tier3_Hardmode", "sword themed"),
    QAPrompt(3,  "Storm Brand — a long sword wreathed in crackling cobalt lightning", "Sword", "Tier3_Hardmode", "sword demo"),
    QAPrompt(4,  "thundering broadsword of dawn", "Broadsword", "Tier3_Hardmode", "broadsword (substring trap)"),
    QAPrompt(5,  "shortsword of the bog wraith", "Shortsword", "Tier1_Starter", "shortsword"),
    QAPrompt(6,  "repeating crystal pistol", "Pistol", "Tier2_Dungeon", "pistol"),
    QAPrompt(7,  "obsidian shotgun with brass barrels", "Shotgun", "Tier3_Hardmode", "shotgun (substring trap)"),
    QAPrompt(8,  "aether sniper rifle", "Rifle", "Tier3_Hardmode", "rifle"),
    QAPrompt(9,  "verdant elven longbow", "Bow", "Tier1_Starter", "bow"),
    QAPrompt(10, "bonecrusher repeater crossbow", "Repeater", "Tier2_Dungeon", "repeater"),
    QAPrompt(11, "frost staff of the glacier", "Staff", "Tier2_Dungeon", "staff"),
    QAPrompt(12, "arcane spellbook of thunder", "Spellbook", "Tier3_Hardmode", "spellbook"),
    QAPrompt(13, "crystal wand of stardust", "Wand", "Tier4_Endgame", "wand"),
    QAPrompt(14, "grimoire of forgotten kings", "Tome", "Tier3_Hardmode", "tome"),
    QAPrompt(15, "obsidian pickaxe with magma cracks", "Pickaxe", "Tier2_Dungeon", "pickaxe (substring trap)"),
    QAPrompt(16, "gilded hamaxe of the hunt", "Hamaxe", "Tier3_Hardmode", "hamaxe"),
    QAPrompt(17, "runic trident of the deep", "Spear", "Tier2_Dungeon", "spear/trident"),
    QAPrompt(18, "chitin lance of the swarm", "Lance", "Tier2_Dungeon", "lance"),
    QAPrompt(19, "the moonlit echo", "Sword", "Tier3_Hardmode", "ambiguous edge (fallback)"),
    QAPrompt(20, "bladed spear of the marsh", "Spear", "Tier2_Dungeon", "cross-keyword (Spear over Sword)"),
    QAPrompt(21, "pickaxe-bladed greatsword", "Broadsword", "Tier2_Dungeon", "cross-keyword (greatsword head noun wins)"),
)


TIER_B_SUBSET_IDS: tuple[int, ...] = (1, 3, 4, 6, 7, 9, 11, 15, 17, 20)
TIER_C_SUBSET_IDS: tuple[int, ...] = (3, 7, 9, 11, 15)


def by_id(prompt_id: int) -> QAPrompt:
    for p in CORPUS:
        if p.id == prompt_id:
            return p
    raise KeyError(prompt_id)
