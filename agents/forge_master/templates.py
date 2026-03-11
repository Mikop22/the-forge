"""Reference C# snippets (inline RAG), sub-type mappings, and validation rules.

The reference snippets are injected into the system prompt so the LLM has
correct tModLoader 1.4.4 examples to follow.  The validation rules catch
common 1.3 hallucinations *before* the code reaches an actual compiler.

All templates are sourced from / validated against the official tModLoader
1.4.4 ExampleMod: https://github.com/tModLoader/tModLoader/tree/1.4.4/ExampleMod
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Sub-type → API constant mappings
# ---------------------------------------------------------------------------

DAMAGE_CLASS_MAP: dict[str, str] = {
    "Sword": "DamageClass.Melee",
    "Gun": "DamageClass.Ranged",
    "Bow": "DamageClass.Ranged",
    "Staff": "DamageClass.Magic",
    "Summon": "DamageClass.Summon",
    "Whip": "DamageClass.SummonMeleeSpeed",
}

USE_STYLE_MAP: dict[str, str] = {
    "Sword": "ItemUseStyleID.Swing",
    "Gun": "ItemUseStyleID.Shoot",
    "Bow": "ItemUseStyleID.Shoot",
    "Staff": "ItemUseStyleID.Shoot",
    "Summon": "ItemUseStyleID.Swing",
    "Whip": "ItemUseStyleID.Swing",
}

# ---------------------------------------------------------------------------
# Reference snippets — correct tModLoader 1.4.4 C# examples
# ---------------------------------------------------------------------------

SWORD_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleSword : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 40;
            Item.height = 40;
            Item.useStyle = ItemUseStyleID.Swing;
            Item.useTime = 20;
            Item.useAnimation = 20;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Melee;
            Item.damage = 50;
            Item.knockBack = 6f;
            Item.crit = 6;  // Added ON TOP of the player's base 4% crit = 10% total

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item1;
        }

        // Spawn dust particles along the swing hitbox (melee visual flair)
        public override void MeleeEffects(Player player, Rectangle hitbox)
        {
            if (Main.rand.NextBool(3))
            {
                Dust.NewDust(new Vector2(hitbox.X, hitbox.Y), hitbox.Width, hitbox.Height,
                    DustID.Torch, Projectile.velocity.X * 0.5f, Projectile.velocity.Y * 0.5f);
            }
        }

        // 1.4.4 signature: NPC.HitInfo replaces old (int damage, float knockBack, bool crit)
        public override void OnHitNPC(Player player, NPC target, NPC.HitInfo hit, int damageDone)
        {
            target.AddBuff(BuffID.OnFire, 180);  // 180 frames = 3 seconds
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.IronBar, 5)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}"""

GUN_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.DataStructures;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleGun : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 62;
            Item.height = 32;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 8;
            Item.useAnimation = 8;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 20;
            Item.knockBack = 5f;
            Item.noMelee = true;

            // Guns always set shoot to a vanilla placeholder; actual projectile
            // comes from the player's equipped ammo (resolved in Shoot/ModifyShootStats).
            Item.shoot = ProjectileID.PurificationPowder;
            Item.shootSpeed = 10f;
            Item.useAmmo = AmmoID.Bullet;  // AmmoID.Arrow for bows, AmmoID.Rocket for launchers

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item11;
        }

        // Adjust the sprite's position in the player's hand
        public override Vector2? HoldoutOffset()
        {
            return new Vector2(2f, -2f);
        }

        // Change which projectile fires without taking over the full spawn logic.
        // 'type' is the projectile ID resolved from the player's ammo slot.
        public override void ModifyShootStats(Player player, ref Vector2 position, ref Vector2 velocity,
            ref int type, ref int damage, ref float knockback)
        {
            // Example: 1-in-3 chance to fire a special explosive round instead
            // if (Main.rand.NextBool(3))
            //     type = ModContent.ProjectileType<MyExplosiveRound>();
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.IronBar, 10)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}"""

STAFF_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleStaff : ModItem
    {
        // REQUIRED: makes the use animation render as a rotating staff, not a gun aim.
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 40;
            Item.height = 40;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 25;
            Item.useAnimation = 25;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 30;
            Item.knockBack = 4f;
            Item.mana = 10;
            Item.noMelee = true;

            // Use a vanilla projectile ID or ModContent.ProjectileType<MyProj>() for custom ones
            Item.shoot = ProjectileID.MagicMissile;
            Item.shootSpeed = 8f;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item43;  // Classic staff cast sound
        }

        // Reduce mana cost when player HP is low (Space Gun-style mechanic example)
        // public override void ModifyManaCost(Player player, ref float reduce, ref float mult)
        // {
        //     if (player.statLife < player.statLifeMax2 / 2)
        //         mult *= 0.5f;
        // }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.FallenStar, 10)
                .AddIngredient(ItemID.GoldBar, 5)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}"""

BOW_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.DataStructures;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleBow : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 24;
            Item.height = 56;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 22;
            Item.useAnimation = 22;
            Item.autoReuse = false;  // Most bows do NOT auto-reuse

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 25;
            Item.knockBack = 3f;
            Item.noMelee = true;

            // The arrow type actually shot comes from the player's equipped ammo.
            // WoodenArrowFriendly is the standard placeholder for bows.
            Item.shoot = ProjectileID.WoodenArrowFriendly;
            Item.shootSpeed = 9f;
            Item.useAmmo = AmmoID.Arrow;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item5;
        }

        // Override Shoot to fire multiple arrows in a spread (shotgun bow style).
        // 'type' is already resolved to the player's equipped arrow projectile.
        public override bool Shoot(Player player, EntitySource_ItemUse_WithAmmo source, Vector2 position,
            Vector2 velocity, int type, int damage, float knockback)
        {
            // Fire 3 arrows in a slight spread
            const int numArrows = 3;
            for (int i = 0; i < numArrows; i++)
            {
                Vector2 spreadVelocity = velocity.RotatedByRandom(MathHelper.ToRadians(8));
                Projectile.NewProjectileDirect(source, position, spreadVelocity, type, damage, knockback, player.whoAmI);
            }
            return false;  // false = suppress the vanilla single-arrow shot
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.Wood, 20)
                .AddIngredient(ItemID.IronBar, 3)
                .AddTile(TileID.WorkBenches)
                .Register();
        }
    }
}"""

SUMMON_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.DataStructures;
using Terraria.ID;
using Terraria.ModLoader;

// A complete summon weapon requires THREE classes that work together:
// 1. The ModItem   — held and used by the player
// 2. The ModBuff   — active while the minion exists
// 3. The ModProjectile — the actual minion AI

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleMinionItem : ModItem
    {
        public override void SetStaticDefaults()
        {
            ItemID.Sets.GamepadWholeScreenUseRange[Type] = true;  // allows targeting anywhere on screen
            ItemID.Sets.LockOnIgnoresCollision[Type] = true;
            ItemID.Sets.StaffMinionSlotsRequired[Type] = 1f;      // minion slot cost
        }

        public override void SetDefaults()
        {
            Item.width = 32;
            Item.height = 32;
            Item.useStyle = ItemUseStyleID.Swing;
            Item.useTime = 36;
            Item.useAnimation = 36;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Summon;
            Item.damage = 30;
            Item.knockBack = 3f;
            Item.mana = 10;
            Item.noMelee = true;

            Item.buffType = ModContent.BuffType<ExampleMinionBuff>();
            // NOTE: do NOT set Item.buffTime — it hides the "X minute duration" tooltip
            Item.shoot = ModContent.ProjectileType<ExampleMinion>();

            Item.value = Item.buyPrice(gold: 5);
            Item.rare = ItemRarityID.Cyan;
            Item.UseSound = SoundID.Item44;
        }

        public override void ModifyShootStats(Player player, ref Vector2 position, ref Vector2 velocity,
            ref int type, ref int damage, ref float knockback)
        {
            position = Main.MouseWorld;
            player.LimitPointToPlayerReachableArea(ref position);
        }

        public override bool Shoot(Player player, EntitySource_ItemUse_WithAmmo source, Vector2 position,
            Vector2 velocity, int type, int damage, float knockback)
        {
            // Apply the buff for 2 ticks; ExampleMinionBuff.Update() extends it while the minion lives.
            player.AddBuff(Item.buffType, 2);
            return true;  // true = let vanilla spawn the minion projectile
        }
    }
}

namespace ForgeGeneratedMod.Content.Buffs
{
    public class ExampleMinionBuff : ModBuff
    {
        public override void SetStaticDefaults()
        {
            Main.buffNoSave[Type] = true;         // does not persist across save/load
            Main.buffNoTimeDisplay[Type] = true;  // hide countdown timer
        }

        public override void Update(Player player, ref int buffIndex)
        {
            if (player.ownedProjectileCounts[ModContent.ProjectileType<ExampleMinion>()] > 0)
            {
                // Reset timer while the minion is alive
                player.buffTime[buffIndex] = 18000;
            }
            else
            {
                player.DelBuff(buffIndex);
                buffIndex--;
            }
        }
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExampleMinion : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            Main.projFrames[Type] = 4;                            // sprite sheet has 4 animation frames
            ProjectileID.Sets.MinionTargettingFeature[Type] = true;  // enable right-click targeting
            Main.projPet[Type] = true;
            ProjectileID.Sets.MinionSacrificable[Type] = true;   // allows replacement when slots are full
            ProjectileID.Sets.CultistIsResistantTo[Type] = true;
        }

        public sealed override void SetDefaults()
        {
            Projectile.width = 18;
            Projectile.height = 28;
            Projectile.tileCollide = false;

            Projectile.friendly = true;
            Projectile.minion = true;
            Projectile.DamageType = DamageClass.Summon;
            Projectile.minionSlots = 1f;
            Projectile.penetrate = -1;  // REQUIRED: -1 = infinite penetration for minions
        }

        public override bool? CanCutTiles() { return false; }
        public override bool MinionContactDamage() { return true; }

        public override void AI()
        {
            Player owner = Main.player[Projectile.owner];

            // Kill the projectile if the player no longer has the buff
            if (!owner.HasBuff(ModContent.BuffType<ExampleMinionBuff>()))
            {
                Projectile.Kill();
                return;
            }

            // Basic follow-owner logic; replace with combat AI as needed
            Vector2 toOwner = owner.Center - Projectile.Center;
            if (toOwner.Length() > 800f)
            {
                Projectile.Center = owner.Center;
            }
            else if (toOwner.Length() > 100f)
            {
                Projectile.velocity = Vector2.Lerp(Projectile.velocity, toOwner * 0.05f, 0.1f);
            }

            // Animate frames
            if (++Projectile.frameCounter >= 5)
            {
                Projectile.frameCounter = 0;
                Projectile.frame = (Projectile.frame + 1) % Main.projFrames[Type];
            }
        }
    }
}"""

WHIP_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleWhip : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 28;
            Item.height = 28;

            // DefaultToWhip(projectileType, damage, knockBack, useTime)
            Item.DefaultToWhip(ModContent.ProjectileType<ExampleWhipProjectile>(), 20, 2f, 26);

            Item.rare = ItemRarityID.Green;
            Item.value = Item.buyPrice(gold: 1);
            Item.channel = true;  // REQUIRED: whips must have channel = true
        }

        // Whips accept melee prefixes (Legendary, etc.)
        public override bool MeleePrefix() { return true; }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.Leather, 8)
                .AddTile(TileID.WorkBenches)
                .Register();
        }
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExampleWhipProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            // Number of segments in the whip chain
            ProjectileID.Sets.IsAWhip[Type] = true;
        }

        public override void SetDefaults()
        {
            Projectile.DefaultToWhip();  // Sets friendly=true, tileCollide=false, etc.
            Projectile.WhipSettings.Segments = 20;
            Projectile.WhipSettings.RangeMultiplier = 1f;
        }

        // Apply a tag debuff so minions deal bonus damage to struck enemies
        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            // ExampleMod uses a custom tag buff; for vanilla use BuffID.ShadowFlame, etc.
            target.AddBuff(BuffID.ShadowFlame, 180);
        }
    }
}"""

CUSTOM_PROJECTILE_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.Audio;
using Terraria.DataStructures;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // A gun that fires a custom bouncing magic projectile.
    // The item class and projectile class are often in separate files in real mods;
    // shown together here for reference.

    public class ExampleCustomGun : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 62;
            Item.height = 32;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 12;
            Item.useAnimation = 12;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 35;
            Item.knockBack = 5f;
            Item.noMelee = true;

            Item.shoot = ModContent.ProjectileType<ExampleCustomProjectile>();
            Item.shootSpeed = 12f;

            Item.value = Item.buyPrice(gold: 2);
            Item.rare = ItemRarityID.Orange;
            Item.UseSound = SoundID.Item11;
        }

        public override Vector2? HoldoutOffset()
        {
            return new Vector2(2f, -2f);
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.HellstoneBar, 15)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }

    public class ExampleCustomProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            // Trail/afterimage cache (optional visual)
            ProjectileID.Sets.TrailCacheLength[Type] = 5;
            ProjectileID.Sets.TrailingMode[Type] = 0;
        }

        public override void SetDefaults()
        {
            Projectile.width = 16;
            Projectile.height = 16;
            Projectile.friendly = true;
            Projectile.hostile = false;
            Projectile.DamageType = DamageClass.Ranged;
            Projectile.penetrate = 3;       // bounces up to 3 times before dying
            Projectile.timeLeft = 600;
            Projectile.tileCollide = true;
            Projectile.ignoreWater = true;
            Projectile.light = 0.5f;
        }

        public override void AI()
        {
            // Rotate to face movement direction
            Projectile.rotation = Projectile.velocity.ToRotation();

            // Spawn dust trail
            if (Main.rand.NextBool(3))
            {
                Dust.NewDust(Projectile.position, Projectile.width, Projectile.height,
                    DustID.Torch, Projectile.velocity.X * 0.3f, Projectile.velocity.Y * 0.3f);
            }
        }

        // Return false to handle the collision ourselves instead of auto-killing the projectile.
        public override bool OnTileCollide(Vector2 oldVelocity)
        {
            Projectile.penetrate--;
            if (Projectile.penetrate <= 0)
            {
                Projectile.Kill();
            }
            else
            {
                // Bounce: reverse whichever axis hit the wall
                if (Projectile.velocity.X != oldVelocity.X) Projectile.velocity.X = -oldVelocity.X;
                if (Projectile.velocity.Y != oldVelocity.Y) Projectile.velocity.Y = -oldVelocity.Y;
                SoundEngine.PlaySound(SoundID.Item10, Projectile.position);
            }
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            // Burst of dust on death
            for (int k = 0; k < 8; k++)
            {
                Dust.NewDust(Projectile.position + Projectile.velocity, Projectile.width, Projectile.height,
                    DustID.Torch, Projectile.oldVelocity.X * 0.5f, Projectile.oldVelocity.Y * 0.5f);
            }
            SoundEngine.PlaySound(SoundID.Item25, Projectile.position);
        }

        // ModProjectile.OnHitNPC does NOT have a Player parameter (unlike ModItem.OnHitNPC)
        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            target.AddBuff(BuffID.OnFire, 120);
            // Slow down slightly on each NPC hit
            Projectile.velocity *= 0.8f;
        }
    }
}"""

REFERENCE_SNIPPETS: dict[str, str] = {
    "Sword": SWORD_TEMPLATE,
    "Gun": GUN_TEMPLATE,
    "Staff": STAFF_TEMPLATE,
    "Bow": BOW_TEMPLATE,
    "Summon": SUMMON_TEMPLATE,
    "Whip": WHIP_TEMPLATE,
}


def get_reference_snippet(sub_type: str, custom_projectile: bool = False) -> str:
    """Return the best-matching reference snippet for a given sub-type.

    If custom_projectile is True, returns the custom projectile template
    showing how to create both a ModItem and ModProjectile in the same file.
    """
    if custom_projectile:
        return CUSTOM_PROJECTILE_TEMPLATE
    return REFERENCE_SNIPPETS.get(sub_type, SWORD_TEMPLATE)


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
