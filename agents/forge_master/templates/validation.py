"""Post-generation C# validation for Forge Master."""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Post-generation validation
# ---------------------------------------------------------------------------

# Patterns that MUST NOT appear in generated code.
BANNED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"using\s+System\.Drawing"),
        "BANNED: System.Drawing (crashes Linux builds). Use Microsoft.Xna.Framework.",
    ),
    (
        re.compile(r"new\s+ModRecipe"),
        "BANNED: ModRecipe is 1.3 API. Use CreateRecipe().",
    ),
    (
        re.compile(r"item\.melee\s*=", re.IGNORECASE),
        "BANNED: item.melee is 1.3 API. Use Item.DamageType = DamageClass.Melee.",
    ),
    (
        re.compile(r"item\.ranged\s*=", re.IGNORECASE),
        "BANNED: item.ranged is 1.3 API. Use Item.DamageType = DamageClass.Ranged.",
    ),
    (
        re.compile(r"item\.magic\s*=", re.IGNORECASE),
        "BANNED: item.magic is 1.3 API. Use Item.DamageType = DamageClass.Magic.",
    ),
    (
        re.compile(r"item\.summon\s*=", re.IGNORECASE),
        "BANNED: item.summon is 1.3 API. Use Item.DamageType = DamageClass.Summon.",
    ),
    (
        # ModItem.OnHitNPC must have NPC.HitInfo (1.4.4); old signature used (int damage, float knockBack, bool crit)
        re.compile(r"override\s+void\s+OnHitNPC\s*\((?![^)]*NPC\.HitInfo)[^)]*\)"),
        "BANNED: Old OnHitNPC signature. ModItem must use (Player player, NPC target, NPC.HitInfo hit, int damageDone); ModProjectile must use (NPC target, NPC.HitInfo hit, int damageDone).",
    ),
    (
        re.compile(r"override\s+bool\s+Shoot\s*\(\s*Player\s+\w+\s*,\s*IEntitySource\s+\w+"),
        "BANNED: Invalid ModItem.Shoot source parameter. Use EntitySource_ItemUse_WithAmmo source for tModLoader 1.4.4.",
    ),
    (
        re.compile(r"\bMathHelper\.(?:Sin|Cos|Tan)\s*\("),
        "BANNED: MathHelper.Sin/Cos/Tan do not exist. Use System.MathF.Sin/Cos/Tan.",
    ),
    (
        re.compile(r"mod\.GetItem\b"),
        "BANNED: mod.GetItem is 1.3 API. Use ModContent.GetInstance<T>() or ItemID.",
    ),
    (
        re.compile(r"\.GetModItem\s*<"),
        "BANNED: GetModItem<T> is 1.3 API. Use ModContent.GetInstance<T>().",
    ),
    (
        # Summon projectiles must have penetrate = -1; a digit after '=' means a positive value was set.
        re.compile(r"Projectile\.minion\s*=\s*true[\s\S]{0,2000}Projectile\.penetrate\s*=\s*\d"),
        "BANNED: Minion projectiles must use Projectile.penetrate = -1 (infinite). Positive penetrate causes the minion to die after hitting enemies.",
    ),
    (
        # Whips must use ModContent.ProjectileType<T>(), not a vanilla ProjectileID constant.
        re.compile(r"DefaultToWhip\s*\(\s*ProjectileID\."),
        "BANNED: DefaultToWhip must use ModContent.ProjectileType<YourWhipProjectile>(), not a vanilla ProjectileID constant. Whips require a custom ModProjectile.",
    ),
]

# Patterns that MUST appear in generated code.
REQUIRED_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"using\s+Terraria;"), "MISSING: 'using Terraria;' import."),
    (re.compile(r"using\s+Terraria\.ID;"), "MISSING: 'using Terraria.ID;' import."),
    (re.compile(r"using\s+Terraria\.ModLoader;"), "MISSING: 'using Terraria.ModLoader;' import."),
    (re.compile(r":\s*ModItem"), "MISSING: Class must inherit from ModItem."),
    (re.compile(r"void\s+SetDefaults\s*\(\s*\)"), "MISSING: SetDefaults() method not found."),
]


_PROJ_CLASS_START = re.compile(r"class\s+\w+\s*:\s*ModProjectile")
_ONHITNPC_WITH_PLAYER = re.compile(
    r"override\s+void\s+OnHitNPC\s*\(\s*Player\s+\w+"
)
_MODCONTENT_BUFF_REF = re.compile(r"ModContent\.BuffType<(\w+)>\s*\(\s*\)")
_CLASS_DECL = re.compile(r"\bclass\s+(\w+)\b")


def validate_cs(code: str) -> list[str]:
    """Validate generated C# code against 1.4.4 compliance rules.

    Returns a list of violation descriptions (empty == valid).
    """
    violations: list[str] = []

    for pattern, message in BANNED_PATTERNS:
        if pattern.search(code):
            violations.append(message)

    for pattern, message in REQUIRED_PATTERNS:
        if not pattern.search(code):
            violations.append(message)

    # Context-sensitive check: within each ModProjectile subclass body,
    # OnHitNPC must NOT have a Player parameter.
    # We scan from each "class X : ModProjectile" declaration forward up to 3000 chars
    # (covers any reasonable class body) so that a ModItem.OnHitNPC(Player...) in the
    # same file doesn't cause a false positive.
    for proj_match in _PROJ_CLASS_START.finditer(code):
        window = code[proj_match.start(): proj_match.start() + 3000]
        if _ONHITNPC_WITH_PLAYER.search(window):
            violations.append(
                "BANNED: ModProjectile.OnHitNPC must NOT have a Player parameter. "
                "Correct signature is (NPC target, NPC.HitInfo hit, int damageDone). "
                "Only ModItem.OnHitNPC includes the Player parameter."
            )
            break

    # Cross-reference check: every type used in ModContent.BuffType<T>() must be
    # defined as a class in the same file. Summon weapons require the ModBuff
    # (and the minion ModProjectile it references) to be co-located in one file.
    defined_classes = {m.group(1) for m in _CLASS_DECL.finditer(code)}
    for ref_match in _MODCONTENT_BUFF_REF.finditer(code):
        type_name = ref_match.group(1)
        if type_name not in defined_classes:
            violations.append(
                f"MISSING: ModContent.BuffType<{type_name}>() referenced but class "
                f"'{type_name}' is not defined in this file. Summon weapons require "
                f"the ModBuff and ModProjectile minion classes to be defined in the same file."
            )

    return violations
