# QA Prompt Corpus — User-Realistic Modded Terraria Prompts

These prompts simulate what a Terraria modder would type into The Forge. Each row pins the expected `sub_type` for Tier A classification. Tier B (architect) and Tier C (full pipeline) draw subsets from this list.

| # | Prompt | Expected sub_type | Tier (intended) | Category |
|---|---|---|---|---|
| 1 | iron longsword | Sword | Tier1_Starter | sword direct |
| 2 | frostbrand katana with rime-etched edge | Sword | Tier3_Hardmode | sword themed |
| 3 | Storm Brand — a long sword wreathed in crackling cobalt lightning | Sword | Tier3_Hardmode | sword demo |
| 4 | thundering broadsword of dawn | Broadsword | Tier3_Hardmode | broadsword (substring trap) |
| 5 | shortsword of the bog wraith | Shortsword | Tier1_Starter | shortsword |
| 6 | repeating crystal pistol | Pistol | Tier2_Dungeon | pistol |
| 7 | obsidian shotgun with brass barrels | Shotgun | Tier3_Hardmode | shotgun (substring trap) |
| 8 | aether sniper rifle | Rifle | Tier3_Hardmode | rifle |
| 9 | verdant elven longbow | Bow | Tier1_Starter | bow |
| 10 | bonecrusher repeater crossbow | Repeater | Tier2_Dungeon | repeater |
| 11 | frost staff of the glacier | Staff | Tier2_Dungeon | staff |
| 12 | arcane spellbook of thunder | Spellbook | Tier3_Hardmode | spellbook |
| 13 | crystal wand of stardust | Wand | Tier4_Endgame | wand |
| 14 | grimoire of forgotten kings | Tome | Tier3_Hardmode | tome |
| 15 | obsidian pickaxe with magma cracks | Pickaxe | Tier2_Dungeon | pickaxe (substring trap) |
| 16 | gilded hamaxe of the hunt | Hamaxe | Tier3_Hardmode | hamaxe |
| 17 | runic trident of the deep | Spear | Tier2_Dungeon | spear/trident |
| 18 | chitin lance of the swarm | Lance | Tier2_Dungeon | lance |
| 19 | the moonlit echo | Sword (fallback) | Tier3_Hardmode | ambiguous edge |
| 20 | bladed spear of the marsh | Spear | Tier2_Dungeon | cross-keyword (Spear wins over Sword) |
| 21 | pickaxe-bladed greatsword | Pickaxe | Tier2_Dungeon | cross-keyword (Pickaxe before Sword) |

## Substring-trap intent

Several prompts deliberately probe the keyword-registry ordering in `agents/orchestrator.py:_WEAPON_SUBTYPE_KEYWORDS`:

- **broadsword** must beat **sword** (#4)
- **shotgun** must beat **gun** (#7)
- **pickaxe** must beat **axe** (#15, #21)
- **spear** must beat **blade**/**sword** (#20)

If any of these flip, the tier-A run will fail and the registry needs a fix.

## Expected Tier B subset (architect manifests)

Run architect on a balanced 10-prompt subset that exercises every major sub_type family:

`#1, #3, #4, #6, #7, #9, #11, #15, #17, #20`

## Expected Tier C subset (full pipeline)

5 prompts that should produce visually distinct sprites + valid C# across weapon families:

`#3 (Storm Brand sword)`, `#7 (obsidian shotgun)`, `#9 (elven bow)`, `#11 (frost staff)`, `#15 (obsidian pickaxe)`
