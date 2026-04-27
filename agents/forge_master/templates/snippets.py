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
    "Pistol": "DamageClass.Ranged",
    "Shotgun": "DamageClass.Ranged",
    "Rifle": "DamageClass.Ranged",
    "Repeater": "DamageClass.Ranged",
    "Staff": "DamageClass.Magic",
    "Wand": "DamageClass.Magic",
    "Tome": "DamageClass.Magic",
    "Spellbook": "DamageClass.Magic",
    "Launcher": "DamageClass.Ranged",
    "Cannon": "DamageClass.Ranged",
    "Summon": "DamageClass.Summon",
    "Whip": "DamageClass.SummonMeleeSpeed",
}

USE_STYLE_MAP: dict[str, str] = {
    "Sword": "ItemUseStyleID.Swing",
    "Gun": "ItemUseStyleID.Shoot",
    "Bow": "ItemUseStyleID.Shoot",
    "Pistol": "ItemUseStyleID.Shoot",
    "Shotgun": "ItemUseStyleID.Shoot",
    "Rifle": "ItemUseStyleID.Shoot",
    "Repeater": "ItemUseStyleID.Shoot",
    "Staff": "ItemUseStyleID.Shoot",
    "Wand": "ItemUseStyleID.Shoot",
    "Tome": "ItemUseStyleID.Shoot",
    "Spellbook": "ItemUseStyleID.Shoot",
    "Launcher": "ItemUseStyleID.Shoot",
    "Cannon": "ItemUseStyleID.Shoot",
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
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.2f;
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
                    DustID.Torch, player.velocity.X * 0.2f, player.velocity.Y * 0.2f);
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
            Item.scale = 1.15f;
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
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.2f;
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

SKY_STRIKE_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.DataStructures;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Sky-strike weapon: projectiles spawn from above the screen and fall
    // toward the cursor.  Based on the vanilla Star Wrath / Starfury mechanic.
    // Works for any weapon type (staff, sword, etc.) — adapt SetDefaults to match.

    public class ExampleSkyStrikeStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.2f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 25;
            Item.useAnimation = 25;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 30;
            Item.knockBack = 4f;
            Item.mana = 10;
            Item.noMelee = true;

            // Use a vanilla sky-projectile: StarWrath, Starfury, or LunarFlare
            Item.shoot = ProjectileID.StarWrath;
            Item.shootSpeed = 8f;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item43;
        }

        // Sky-strike Shoot() override: spawn projectiles high above the player,
        // aimed downward at the cursor position.
        public override bool Shoot(Player player, EntitySource_ItemUse_WithAmmo source,
            Vector2 position, Vector2 velocity, int type, int damage, float knockback)
        {
            Vector2 target = Main.screenPosition + new Vector2(Main.mouseX, Main.mouseY);
            float ceilingLimit = target.Y;
            if (ceilingLimit > player.Center.Y - 200f)
                ceilingLimit = player.Center.Y - 200f;

            for (int i = 0; i < 3; i++)
            {
                position = player.Center - new Vector2(Main.rand.NextFloat(401) * player.direction, 600f);
                position.Y -= 100 * i;
                Vector2 heading = target - position;
                if (heading.Y < 0f) heading.Y *= -1f;
                if (heading.Y < 20f) heading.Y = 20f;
                heading.Normalize();
                heading *= velocity.Length();
                heading.Y += Main.rand.Next(-40, 41) * 0.02f;
                Projectile.NewProjectile(source, position, heading, type,
                    damage, knockback, player.whoAmI, 0f, ceilingLimit);
            }
            return false;  // suppress default projectile spawn
        }

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

HOMING_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Homing weapon: fires a custom ModProjectile that tracks the nearest enemy.
    // The projectile uses FindClosestNPC() to acquire targets and smoothly
    // interpolates toward them using an inertia factor.

    public class ExampleHomingStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.2f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 25;
            Item.useAnimation = 25;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 30;
            Item.knockBack = 4f;
            Item.mana = 10;
            Item.noMelee = true;

            Item.shoot = ModContent.ProjectileType<ExampleHomingProjectile>();
            Item.shootSpeed = 8f;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item43;
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.FallenStar, 10)
                .AddIngredient(ItemID.GoldBar, 5)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExampleHomingProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 5;
            ProjectileID.Sets.TrailingMode[Type] = 0;
        }

        public override void SetDefaults()
        {
            Projectile.width = 16;
            Projectile.height = 16;
            Projectile.friendly = true;
            Projectile.hostile = false;
            Projectile.DamageType = DamageClass.Magic;
            Projectile.penetrate = 3;
            Projectile.timeLeft = 300;
            Projectile.tileCollide = true;
            Projectile.ignoreWater = true;
            Projectile.light = 0.5f;
        }

        public override void AI()
        {
            // Seek the closest enemy within detection radius
            float maxDetectRadius = 400f;
            float projSpeed = 8f;
            NPC closestNPC = FindClosestNPC(maxDetectRadius);
            if (closestNPC != null)
            {
                Vector2 dirToTarget = (closestNPC.Center - Projectile.Center).SafeNormalize(Vector2.UnitX);
                float inertia = 20f;
                Projectile.velocity = (Projectile.velocity * (inertia - 1) + dirToTarget * projSpeed) / inertia;
            }

            Projectile.rotation = Projectile.velocity.ToRotation();

            // Dust trail
            if (Main.rand.NextBool(3))
            {
                Dust.NewDust(Projectile.position, Projectile.width, Projectile.height,
                    DustID.MagicMirror, Projectile.velocity.X * 0.3f, Projectile.velocity.Y * 0.3f);
            }
        }

        private NPC FindClosestNPC(float maxDetectDistance)
        {
            NPC closestNPC = null;
            float sqrMaxDetectDistance = maxDetectDistance * maxDetectDistance;
            for (int i = 0; i < Main.maxNPCs; i++)
            {
                NPC target = Main.npc[i];
                if (target.CanBeChasedBy())
                {
                    float sqrDist = Vector2.DistanceSquared(target.Center, Projectile.Center);
                    if (sqrDist < sqrMaxDetectDistance)
                    {
                        sqrMaxDetectDistance = sqrDist;
                        closestNPC = target;
                    }
                }
            }
            return closestNPC;
        }

        public override void OnKill(int timeLeft)
        {
            for (int k = 0; k < 8; k++)
            {
                Dust.NewDust(Projectile.position + Projectile.velocity, Projectile.width, Projectile.height,
                    DustID.MagicMirror, Projectile.oldVelocity.X * 0.5f, Projectile.oldVelocity.Y * 0.5f);
            }
        }

        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            Projectile.velocity *= 0.8f;
        }
    }
}"""

BOOMERANG_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Boomerang weapon: uses vanilla ProjAIStyleID.Boomerang (aiStyle 3)
    // which handles outward travel, deceleration, and return automatically.
    // The item hides its held sprite — the projectile IS the visible weapon.

    public class ExampleBoomerang : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 30;
            Item.height = 30;
            Item.scale = 1.1f;
            Item.useStyle = ItemUseStyleID.Swing;
            Item.useTime = 20;
            Item.useAnimation = 20;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Melee;
            Item.damage = 25;
            Item.knockBack = 5f;
            Item.noMelee = true;
            Item.noUseGraphic = true;  // hide held sprite — projectile IS the weapon

            Item.shoot = ModContent.ProjectileType<ExampleBoomerangProjectile>();
            Item.shootSpeed = 12f;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item1;
        }

        // Limit to one active boomerang at a time
        public override bool CanUseItem(Player player)
        {
            return player.ownedProjectileCounts[Item.shoot] < 1;
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.IronBar, 8)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExampleBoomerangProjectile : ModProjectile
    {
        public override void SetDefaults()
        {
            Projectile.width = 22;
            Projectile.height = 22;
            Projectile.friendly = true;
            Projectile.DamageType = DamageClass.Melee;
            Projectile.penetrate = -1;  // infinite — passes through enemies both ways
            Projectile.aiStyle = ProjAIStyleID.Boomerang;  // vanilla boomerang behavior
        }

        public override void AI()
        {
            // Spin the sprite (vanilla AI handles movement)
            Projectile.rotation += 0.4f * Projectile.direction;
        }
    }
}"""

ORBIT_TEMPLATE = """\
using System;
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Orbit weapon: spawns projectiles that circle the player, damaging
    // enemies they contact.

    public class ExampleOrbitStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.2f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 30;
            Item.useAnimation = 30;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 25;
            Item.knockBack = 3f;
            Item.mana = 12;
            Item.noMelee = true;

            Item.shoot = ModContent.ProjectileType<ExampleOrbitProjectile>();
            Item.shootSpeed = 0f;  // zero — position is computed, not velocity-driven

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item43;
        }

        // Cap active orbit projectiles to prevent stacking exploitation
        public override bool CanUseItem(Player player)
        {
            return player.ownedProjectileCounts[Item.shoot] < 3;
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.FallenStar, 10)
                .AddIngredient(ItemID.GoldBar, 5)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExampleOrbitProjectile : ModProjectile
    {
        public override void SetDefaults()
        {
            Projectile.width = 16;
            Projectile.height = 16;
            Projectile.friendly = true;
            Projectile.DamageType = DamageClass.Magic;
            Projectile.penetrate = -1;
            Projectile.tileCollide = false;
            Projectile.timeLeft = 300;  // 5 seconds
            Projectile.light = 0.4f;
        }

        public override void AI()
        {
            Player owner = Main.player[Projectile.owner];
            if (!owner.active || owner.dead)
            {
                Projectile.Kill();
                return;
            }

            // Increment orbit angle (radians per frame)
            Projectile.ai[0] += 0.08f;
            float radius = 100f;

            // Position on circle around owner
            Projectile.Center = owner.Center + new Vector2(
                (float)Math.Cos(Projectile.ai[0]) * radius,
                (float)Math.Sin(Projectile.ai[0]) * radius
            );

            // Zero velocity — position is computed, not physics-driven
            Projectile.velocity = Vector2.Zero;

            // Face tangent direction for visual rotation
            Projectile.rotation = Projectile.ai[0] + MathHelper.PiOver2;

            // Dust trail on the orbit path
            if (Main.rand.NextBool(3))
            {
                Dust.NewDust(Projectile.position, Projectile.width, Projectile.height,
                    DustID.MagicMirror);
            }
        }
    }
}"""

EXPLOSION_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.Audio;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Explosive weapon: fires a projectile that explodes on impact,
    // dealing AoE damage via Projectile.Resize() in OnKill.

    public class ExampleExplosiveLauncher : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 50;
            Item.height = 20;
            Item.scale = 1.15f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 30;
            Item.useAnimation = 30;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 40;
            Item.knockBack = 6f;
            Item.noMelee = true;

            Item.shoot = ModContent.ProjectileType<ExampleExplosiveProjectile>();
            Item.shootSpeed = 10f;

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
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExampleExplosiveProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.Explosive[Type] = true;  // mark as explosive type
        }

        public override void SetDefaults()
        {
            Projectile.width = 16;
            Projectile.height = 16;
            Projectile.friendly = true;
            Projectile.DamageType = DamageClass.Ranged;
            Projectile.penetrate = -1;  // hits all enemies in blast radius via Resize
            Projectile.tileCollide = true;
            Projectile.timeLeft = 180;
        }

        public override void AI()
        {
            // Apply gravity
            Projectile.velocity.Y += 0.2f;
            Projectile.rotation = Projectile.velocity.ToRotation();

            // Smoke trail
            if (Main.rand.NextBool(2))
            {
                Dust.NewDust(Projectile.position, Projectile.width, Projectile.height,
                    DustID.Smoke);
            }
        }

        public override void OnKill(int timeLeft)
        {
            // Expand hitbox for AoE — the 1.4.4 way to deal explosion damage
            Projectile.Resize(128, 128);

            // Explosion sound
            SoundEngine.PlaySound(SoundID.Item14, Projectile.position);

            // Visual: fire burst in a circle
            for (int i = 0; i < 30; i++)
            {
                Vector2 speed = Main.rand.NextVector2CircularEdge(8f, 8f);
                Dust.NewDustPerfect(Projectile.Center, DustID.Torch, speed, Scale: 2f);
            }
            // Visual: smoke ring
            for (int i = 0; i < 20; i++)
            {
                Vector2 speed = Main.rand.NextVector2CircularEdge(5f, 5f);
                Dust.NewDustPerfect(Projectile.Center, DustID.Smoke, speed, Scale: 1.5f);
            }
        }

        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            // Explode on first enemy contact
            Projectile.Kill();
        }
    }
}"""

PIERCE_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Piercing beam weapon: fires a fast projectile that passes through
    // all enemies and tiles, using local NPC immunity to prevent damage stacking.

    public class ExamplePierceStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.2f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 20;
            Item.useAnimation = 20;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 35;
            Item.knockBack = 2f;
            Item.mana = 8;
            Item.noMelee = true;

            Item.shoot = ModContent.ProjectileType<ExamplePierceBeam>();
            Item.shootSpeed = 16f;  // fast beam

            Item.value = Item.buyPrice(gold: 2);
            Item.rare = ItemRarityID.Orange;
            Item.UseSound = SoundID.Item43;
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.FallenStar, 10)
                .AddIngredient(ItemID.GoldBar, 5)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExamplePierceBeam : ModProjectile
    {
        public override void SetDefaults()
        {
            Projectile.width = 10;
            Projectile.height = 10;
            Projectile.friendly = true;
            Projectile.DamageType = DamageClass.Magic;
            Projectile.penetrate = -1;      // infinite pierce
            Projectile.tileCollide = false;  // passes through tiles (beam)
            Projectile.timeLeft = 120;
            Projectile.light = 0.8f;
            Projectile.extraUpdates = 2;     // moves 3x per frame for smooth fast travel
            Projectile.usesLocalNPCImmunity = true;  // per-NPC hit cooldown
            Projectile.localNPCHitCooldown = 10;     // frames between hits on same NPC
            Projectile.ignoreWater = true;
        }

        public override void AI()
        {
            Projectile.rotation = Projectile.velocity.ToRotation();

            // Bright dust trail for beam visual
            for (int i = 0; i < 2; i++)
            {
                Dust dust = Dust.NewDustDirect(Projectile.position, Projectile.width,
                    Projectile.height, DustID.MagicMirror);
                dust.noGravity = true;
                dust.scale = 1.2f;
                dust.velocity *= 0.3f;
            }
        }
    }
}"""

CHAIN_LIGHTNING_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Chain lightning weapon: projectile jumps between enemies on hit,
    // dealing reduced damage with each chain.  ai[0] tracks chain depth.

    public class ExampleChainLightningStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.2f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 25;
            Item.useAnimation = 25;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 28;
            Item.knockBack = 3f;
            Item.mana = 10;
            Item.noMelee = true;

            Item.shoot = ModContent.ProjectileType<ExampleChainLightningBolt>();
            Item.shootSpeed = 12f;

            Item.value = Item.buyPrice(gold: 2);
            Item.rare = ItemRarityID.Orange;
            Item.UseSound = SoundID.Item43;
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.FallenStar, 10)
                .AddIngredient(ItemID.GoldBar, 5)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExampleChainLightningBolt : ModProjectile
    {
        public override void SetDefaults()
        {
            Projectile.width = 10;
            Projectile.height = 10;
            Projectile.friendly = true;
            Projectile.DamageType = DamageClass.Magic;
            Projectile.penetrate = 2;   // hits 2 enemies per bolt
            Projectile.tileCollide = true;
            Projectile.timeLeft = 120;
            Projectile.light = 0.6f;
        }

        public override void AI()
        {
            // Stop chaining after 3 jumps
            if (Projectile.ai[0] >= 3f)
            {
                Projectile.penetrate = 1;
            }

            Projectile.rotation = Projectile.velocity.ToRotation();

            // Electric dust trail
            if (Main.rand.NextBool(2))
            {
                Dust dust = Dust.NewDustDirect(Projectile.position, Projectile.width,
                    Projectile.height, DustID.Electric);
                dust.noGravity = true;
                dust.scale = 1.5f;
            }
        }

        // Chain to nearest enemy on hit (multiplayer-safe: only owner spawns)
        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            if (Main.myPlayer != Projectile.owner) return;
            if (Projectile.ai[0] >= 3f) return;  // max chain depth reached

            float maxDist = 300f;
            NPC closest = null;
            float closestDistSq = maxDist * maxDist;

            for (int i = 0; i < Main.maxNPCs; i++)
            {
                NPC npc = Main.npc[i];
                if (npc.CanBeChasedBy() && npc.whoAmI != target.whoAmI)
                {
                    float distSq = Vector2.DistanceSquared(npc.Center, target.Center);
                    if (distSq < closestDistSq)
                    {
                        closestDistSq = distSq;
                        closest = npc;
                    }
                }
            }

            if (closest != null)
            {
                Vector2 dir = (closest.Center - target.Center).SafeNormalize(Vector2.UnitX) * 12f;
                // Chain depth increments via ai[0]; damage reduces per chain
                Projectile.NewProjectile(
                    Projectile.GetSource_FromThis(), target.Center, dir,
                    Projectile.type, (int)(Projectile.damage * 0.8f),
                    Projectile.knockBack * 0.5f, Projectile.owner,
                    ai0: Projectile.ai[0] + 1f);
            }
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
            Item.scale = 1.15f;
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

PISTOL_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExamplePistol : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 42;
            Item.height = 24;
            Item.scale = 1.1f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 12;
            Item.useAnimation = 12;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 18;
            Item.knockBack = 3f;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.Bullet;
            Item.shootSpeed = 11f;
            Item.useAmmo = AmmoID.Bullet;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item11;
        }

        public override Vector2? HoldoutOffset()
        {
            return new Vector2(2f, -1f);
        }
    }
}"""

SHOTGUN_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.DataStructures;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleShotgun : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 58;
            Item.height = 28;
            Item.scale = 1.15f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 34;
            Item.useAnimation = 34;
            Item.autoReuse = false;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 14;
            Item.knockBack = 5f;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.Bullet;
            Item.shootSpeed = 10f;
            Item.useAmmo = AmmoID.Bullet;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item38;
        }

        public override bool Shoot(Player player, EntitySource_ItemUse_WithAmmo source, Vector2 position,
            Vector2 velocity, int type, int damage, float knockback)
        {
            const int numPellets = 3;
            for (int i = 0; i < numPellets; i++)
            {
                Vector2 spreadVelocity = velocity.RotatedByRandom(MathHelper.ToRadians(10));
                Projectile.NewProjectileDirect(source, position, spreadVelocity, type, damage, knockback, player.whoAmI);
            }
            return false;
        }
    }
}"""

RIFLE_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleRifle : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 64;
            Item.height = 28;
            Item.scale = 1.15f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 30;
            Item.useAnimation = 30;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 42;
            Item.knockBack = 5.5f;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.Bullet;
            Item.shootSpeed = 15f;
            Item.useAmmo = AmmoID.Bullet;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item40;
        }

        public override Vector2? HoldoutOffset()
        {
            return new Vector2(4f, -2f);
        }
    }
}"""

REPEATER_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleRepeater : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 46;
            Item.height = 38;
            Item.scale = 1.1f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 14;
            Item.useAnimation = 14;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 26;
            Item.knockBack = 3f;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.WoodenArrowFriendly;
            Item.shootSpeed = 10.5f;
            Item.useAmmo = AmmoID.Arrow;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item5;
        }
    }
}"""

WAND_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleWand : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 34;
            Item.height = 34;
            Item.scale = 1.1f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 22;
            Item.useAnimation = 22;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 28;
            Item.knockBack = 4f;
            Item.mana = 8;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.MagicMissile;
            Item.shootSpeed = 9f;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item43;
        }
    }
}"""

TOME_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleTome : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 32;
            Item.height = 32;
            Item.scale = 1.1f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 28;
            Item.useAnimation = 28;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 34;
            Item.knockBack = 4.5f;
            Item.mana = 12;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.WaterBolt;
            Item.shootSpeed = 8f;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item21;
        }
    }
}"""

SPELLBOOK_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleSpellbook : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 32;
            Item.height = 32;
            Item.scale = 1.1f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 24;
            Item.useAnimation = 24;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 30;
            Item.knockBack = 4f;
            Item.mana = 10;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.MagicMissile;
            Item.shootSpeed = 8.5f;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item43;
        }
    }
}"""

LAUNCHER_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleLauncher : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 66;
            Item.height = 30;
            Item.scale = 1.15f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 36;
            Item.useAnimation = 36;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 48;
            Item.knockBack = 6f;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.RocketI;
            Item.shootSpeed = 9f;
            Item.useAmmo = AmmoID.Rocket;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item11;
        }
    }
}"""

CANNON_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class ExampleCannon : ModItem
    {
        public override void SetDefaults()
        {
            Item.width = 70;
            Item.height = 34;
            Item.scale = 1.2f;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 42;
            Item.useAnimation = 42;
            Item.autoReuse = false;

            Item.DamageType = DamageClass.Ranged;
            Item.damage = 70;
            Item.knockBack = 9f;
            Item.noMelee = true;

            // Use the manifest's mechanics.shoot_projectile value here.
            Item.shoot = ProjectileID.Boulder;
            Item.shootSpeed = 7f;

            Item.value = Item.buyPrice(gold: 1);
            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item14;
        }
    }
}"""

CHANNELED_TEMPLATE = """\
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.Audio;
using Terraria.DataStructures;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Channeled / held-button weapon: player holds USE to sustain a persistent
    // orb projectile that follows the cursor.  Based on the Rainbow Rod / Last
    // Prism pattern from ExampleMod (1.4.4 branch).
    //
    // Key flags:
    //   Item.channel = true  — keeps player.channel == true while held
    //   Item.noUseGraphic = true — projectile draws the staff in-hand
    //   CanUseItem guard — prevents a second orb spawning on auto-refire

    public class ExampleChanneledStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 38;
            Item.height = 38;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useAnimation = 20;
            Item.useTime = 20;
            Item.noMelee = true;
            Item.noUseGraphic = true;
            Item.channel = true;  // CRITICAL: keeps player.channel true while held

            Item.DamageType = DamageClass.Magic;
            Item.damage = 35;
            Item.knockBack = 3f;
            Item.mana = 6;
            Item.crit = 4;

            Item.shoot = ModContent.ProjectileType<ExampleChanneledProjectile>();
            Item.shootSpeed = 28f;  // used as holdout radius by the projectile

            Item.rare = ItemRarityID.Pink;
            Item.value = Item.sellPrice(gold: 5);
            Item.UseSound = SoundID.Item20;
        }

        // Prevent a second orb from spawning while one is already alive
        public override bool CanUseItem(Player player)
        {
            return player.ownedProjectileCounts[ModContent.ProjectileType<ExampleChanneledProjectile>()] <= 0;
        }

        public override bool Shoot(Player player, EntitySource_ItemUse_WithAmmo source,
            Vector2 position, Vector2 velocity, int type, int damage, float knockback)
        {
            Projectile.NewProjectile(source, position, velocity, type, damage, knockback, Main.myPlayer);
            return false;
        }

        public override void AddRecipes()
        {
            CreateRecipe()
                .AddIngredient(ItemID.SoulofLight, 10)
                .AddIngredient(ItemID.CrystalShard, 5)
                .AddTile(TileID.Anvils)
                .Register();
        }
    }
}

namespace ForgeGeneratedMod.Content.Projectiles
{
    public class ExampleChanneledProjectile : ModProjectile
    {
        private const float HoldoutRadius = 28f;
        private const float AimResponsiveness = 0.15f;

        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.HeldProjDoesNotUsePlayerGfxOffY[Type] = true;
        }

        public override void SetDefaults()
        {
            Projectile.width = 20;
            Projectile.height = 20;
            Projectile.friendly = true;
            Projectile.DamageType = DamageClass.Magic;
            Projectile.penetrate = -1;
            Projectile.tileCollide = false;
            Projectile.ignoreWater = true;
            Projectile.hide = true;
            Projectile.usesLocalNPCImmunity = true;
            Projectile.localNPCHitCooldown = 20;
        }

        public override bool? Colliding(Rectangle projHitbox, Rectangle targetHitbox)
        {
            Vector2 tipCenter = Projectile.Center + Projectile.velocity;
            Rectangle tipRect = new Rectangle(
                (int)(tipCenter.X - Projectile.width * 0.5f),
                (int)(tipCenter.Y - Projectile.height * 0.5f),
                Projectile.width, Projectile.height);
            return tipRect.Intersects(targetHitbox) ? true : (bool?)null;
        }

        public override void AI()
        {
            Player player = Main.player[Projectile.owner];
            Vector2 playerHand = player.RotatedRelativePoint(player.MountedCenter, true);

            if (Projectile.owner == Main.myPlayer)
            {
                if (player.channel && !player.noItems && !player.CCed)
                {
                    Vector2 toMouse = Main.MouseWorld - playerHand;
                    if (toMouse == Vector2.Zero) toMouse = Vector2.UnitX;
                    Vector2 targetDir = Vector2.Normalize(toMouse) * HoldoutRadius;
                    Vector2 newVel = Vector2.Lerp(Projectile.velocity, targetDir, AimResponsiveness);
                    if (newVel != Projectile.velocity)
                        Projectile.netUpdate = true;
                    Projectile.velocity = newVel;
                }
                else
                {
                    Projectile.Kill();
                    return;
                }
            }

            // Dust ring at orb tip
            if (Main.rand.NextBool(3))
            {
                Vector2 orbTip = playerHand + Projectile.velocity;
                Dust dust = Dust.NewDustDirect(orbTip - new Vector2(4f), 8, 8,
                    DustID.MagicMirror, 0f, 0f, 100, Color.White, 1.0f);
                dust.noGravity = true;
                dust.velocity *= 0.4f;
            }

            if (Projectile.velocity.X != 0f)
                Projectile.direction = Projectile.velocity.X > 0 ? 1 : -1;
            Projectile.spriteDirection = Projectile.direction;

            player.ChangeDir(Projectile.direction);
            player.heldProj = Projectile.whoAmI;
            player.SetDummyItemTime(2);  // must use SetDummyItemTime, not direct assignment
            Projectile.Center = playerHand;
            Projectile.rotation = Projectile.velocity.ToRotation() + MathHelper.PiOver2;
            player.itemRotation = (Projectile.velocity * Projectile.direction).ToRotation();
            Projectile.timeLeft = 2;  // refresh each frame to keep alive
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            Vector2 drawPos = (Projectile.Center + Projectile.velocity - Main.screenPosition).Floor();
            Color drawColor = Color.White;
            drawColor.A = 200;
            Main.EntitySpriteDraw(texture, drawPos, texture.Bounds, drawColor,
                Projectile.rotation, texture.Size() * 0.5f, Projectile.scale,
                SpriteEffects.None, 0);
            return false;
        }

        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            Vector2 orbTip = Projectile.Center + Projectile.velocity;
            for (int i = 0; i < 8; i++)
                Dust.NewDust(orbTip, 1, 1, DustID.MagicMirror,
                    Main.rand.NextFloat(-2f, 2f), Main.rand.NextFloat(-2f, 2f));
        }

        public override void OnKill(int timeLeft)
        {
            SoundEngine.PlaySound(SoundID.Item8, Projectile.Center);
            Vector2 orbTip = Projectile.Center + Projectile.velocity;
            for (int i = 0; i < 16; i++)
            {
                float angle = MathHelper.TwoPi / 16f * i;
                Vector2 vel = angle.ToRotationVector2() * Main.rand.NextFloat(1f, 3f);
                Dust.NewDustDirect(orbTip, 1, 1, DustID.MagicMirror,
                    vel.X, vel.Y, 0, Color.White, 1.2f).noGravity = true;
            }
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
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.2f;
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
            Item.width = 48;
            Item.height = 48;
            Item.scale = 1.1f;

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
            Item.scale = 1.15f;
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

STORM_BRAND_TEMPLATE = """\
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Combat package: storm_brand. Direct seed bolts stack marks, then cash out in a burst.
    public class ExampleStormBrandStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 42;
            Item.height = 42;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 18;
            Item.useAnimation = 18;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 24;
            Item.knockBack = 3.5f;
            Item.mana = 8;
            Item.noMelee = true;
            Item.shoot = ModContent.ProjectileType<ExampleStormBrandBolt>();
            Item.shootSpeed = 9f;

            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item43;
        }
    }

    public class ExampleStormBrandBolt : ModProjectile
    {
        public override void SetDefaults()
        {
            Projectile.width = 16;
            Projectile.height = 16;
            Projectile.friendly = true;
            Projectile.hostile = false;
            Projectile.DamageType = DamageClass.Magic;
            Projectile.penetrate = 1;
            Projectile.timeLeft = 180;
        }
    }
}"""

ORBIT_FURNACE_TEMPLATE = """\
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Combat package: orbit_furnace. Build ember satellites before the divebomb finisher.
    public class ExampleOrbitFurnaceStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 40;
            Item.height = 40;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 20;
            Item.useAnimation = 20;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 22;
            Item.knockBack = 4f;
            Item.mana = 7;
            Item.noMelee = true;
            Item.shoot = ProjectileID.BallofFire;
            Item.shootSpeed = 8f;

            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item20;
        }
    }
}"""

FROST_SHATTER_TEMPLATE = """\
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items.Weapons
{
    // Combat package: frost_shatter. Chill targets until the crystal fan burst triggers.
    public class ExampleFrostShatterStaff : ModItem
    {
        public override void SetStaticDefaults()
        {
            Item.staff[Type] = true;
        }

        public override void SetDefaults()
        {
            Item.width = 38;
            Item.height = 38;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = 22;
            Item.useAnimation = 22;
            Item.autoReuse = true;

            Item.DamageType = DamageClass.Magic;
            Item.damage = 20;
            Item.knockBack = 4.5f;
            Item.mana = 6;
            Item.noMelee = true;
            Item.shoot = ProjectileID.IceSickle;
            Item.shootSpeed = 8.5f;

            Item.rare = ItemRarityID.Green;
            Item.UseSound = SoundID.Item28;
        }
    }
}"""

REFERENCE_SNIPPETS: dict[str, str] = {
    "Sword": SWORD_TEMPLATE,
    "Gun": GUN_TEMPLATE,
    "Staff": STAFF_TEMPLATE,
    "Bow": BOW_TEMPLATE,
    "Pistol": PISTOL_TEMPLATE,
    "Shotgun": SHOTGUN_TEMPLATE,
    "Rifle": RIFLE_TEMPLATE,
    "Repeater": REPEATER_TEMPLATE,
    "Wand": WAND_TEMPLATE,
    "Tome": TOME_TEMPLATE,
    "Spellbook": SPELLBOOK_TEMPLATE,
    "Launcher": LAUNCHER_TEMPLATE,
    "Cannon": CANNON_TEMPLATE,
    "Summon": SUMMON_TEMPLATE,
    "Whip": WHIP_TEMPLATE,
}

# Non-"direct" shot_style → full reference example (module-level for stable identity).
STYLE_TEMPLATES: dict[str, str] = {
    "sky_strike": SKY_STRIKE_TEMPLATE,
    "homing": HOMING_TEMPLATE,
    "boomerang": BOOMERANG_TEMPLATE,
    "orbit": ORBIT_TEMPLATE,
    "explosion": EXPLOSION_TEMPLATE,
    "pierce": PIERCE_TEMPLATE,
    "chain_lightning": CHAIN_LIGHTNING_TEMPLATE,
    "channeled": CHANNELED_TEMPLATE,
}

PACKAGE_TEMPLATES: dict[str, str] = {
    "storm_brand": STORM_BRAND_TEMPLATE,
    "orbit_furnace": ORBIT_FURNACE_TEMPLATE,
    "frost_shatter": FROST_SHATTER_TEMPLATE,
}


def get_reference_snippet(
    sub_type: str,
    custom_projectile: bool = False,
    shot_style: str = "direct",
    combat_package: str | None = None,
) -> str:
    """Return the best-matching reference snippet for a given sub-type.

    Priority order:
    1. combat_package - package templates win when present.
    2. shot_style — if a non-"direct" shot_style is set, its template wins
       (e.g. channeled, homing, sky_strike).
    3. custom_projectile — only honoured when shot_style is "direct"; returns
        the custom projectile template (ModItem + ModProjectile in one file).
    4. sub_type fallback — e.g. Staff → STAFF_TEMPLATE, Sword → SWORD_TEMPLATE.
    """
    package_tmpl = PACKAGE_TEMPLATES.get(combat_package or "")
    if package_tmpl:
        return package_tmpl
    style_tmpl = STYLE_TEMPLATES.get(shot_style)
    if style_tmpl:
        return style_tmpl
    if custom_projectile:
        return CUSTOM_PROJECTILE_TEMPLATE
    return REFERENCE_SNIPPETS.get(sub_type, SWORD_TEMPLATE)
