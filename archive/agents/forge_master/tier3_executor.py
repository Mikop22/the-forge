"""Constrained C# skeleton rendering for Tier-3 mechanics IR weapons."""

from __future__ import annotations


def render_tier3_skeleton(manifest: dict) -> str:
    """Render a compilable-oriented skeleton anchored on ``mechanics_ir``.

    GPT can enrich hook bodies later, but this skeleton fixes class names,
    signatures, frame setup, hitbox dimensions, and required atom sections.
    """
    item_name = str(manifest.get("item_name") or "GeneratedTier3Item")
    projectile_name = f"{item_name}Projectile"
    stats = manifest.get("stats") if isinstance(manifest.get("stats"), dict) else {}
    mechanics = (
        manifest.get("mechanics") if isinstance(manifest.get("mechanics"), dict) else {}
    )
    projectile_visuals = (
        manifest.get("projectile_visuals")
        if isinstance(manifest.get("projectile_visuals"), dict)
        else {}
    )
    hitbox = projectile_visuals.get("hitbox_size")
    width, height = 18, 18
    if isinstance(hitbox, list) and len(hitbox) == 2:
        try:
            width, height = int(hitbox[0]), int(hitbox[1])
        except (TypeError, ValueError):
            width, height = 18, 18
    frame_count = _frame_count(str(projectile_visuals.get("animation_tier") or "static"))
    damage = int(stats.get("damage") or 50)
    knockback = float(stats.get("knockback") or 5.0)
    use_time = int(stats.get("use_time") or 20)
    rarity = str(stats.get("rarity") or "ItemRarityID.Pink")
    material = str(mechanics.get("crafting_material") or "ItemID.SoulofLight")
    cost = int(mechanics.get("crafting_cost") or 12)
    tile = str(mechanics.get("crafting_tile") or "TileID.Anvils")
    charge_ticks = _atom_int(manifest, "charge_phase", "duration_ticks", 12)
    carve_radius = _atom_int(manifest, "bounded_terrain_carve", "radius_tiles", 1)
    tile_limit = _atom_int(manifest, "bounded_terrain_carve", "tile_limit", 6)

    return f"""\
// Bespoke Tier-3 skeleton: spectacle_plan is the creative brief,
// mechanics_ir is the executable contract.
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria.GameContent;
using Terraria.DataStructures;
using Terraria.Audio;

namespace ForgeGeneratedMod.Content.Items
{{
    public class {item_name} : ModItem
    {{
        public override void SetStaticDefaults()
        {{
            Item.staff[Type] = true;
        }}

        public override void SetDefaults()
        {{
            Item.width = 48;
            Item.height = 48;
            Item.useStyle = ItemUseStyleID.Shoot;
            Item.useTime = {use_time};
            Item.useAnimation = {use_time};
            Item.autoReuse = true;
            Item.DamageType = DamageClass.Magic;
            Item.damage = {damage};
            Item.knockBack = {knockback:.2f}f;
            Item.crit = 8;
            Item.mana = 12;
            Item.noMelee = true;
            Item.shoot = ModContent.ProjectileType<{projectile_name}>();
            Item.shootSpeed = 12f;
            Item.rare = {rarity};
            Item.value = Item.sellPrice(gold: 8);
            Item.UseSound = SoundID.Item43;
        }}

        public override bool Shoot(Player player, EntitySource_ItemUse_WithAmmo source, Vector2 position, Vector2 velocity, int type, int damage, float knockback)
        {{
            Vector2 direction = velocity.SafeNormalize(Vector2.UnitX * player.direction);
            Vector2 muzzle = player.MountedCenter + direction * 42f;
            Projectile.NewProjectile(source, muzzle, direction * Item.shootSpeed, type, damage, knockback, player.whoAmI);
            return false;
        }}

        public override void AddRecipes()
        {{
            CreateRecipe()
                .AddIngredient({material}, {cost})
                .AddTile({tile})
                .Register();
        }}
    }}

    public class {projectile_name} : ModProjectile
    {{
        public override string Texture => "ForgeGeneratedMod/Content/Projectiles/{projectile_name}";
        private const int FrameCount = {frame_count};
        private const int ChargeTicks = {charge_ticks};
        private const int CarveRadius = {carve_radius};
        private const int TileLimit = {tile_limit};

        public override void SetStaticDefaults()
        {{
            Main.projFrames[Type] = FrameCount;
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
            ProjectileID.Sets.TrailingMode[Type] = 2;
        }}

        public override void SetDefaults()
        {{
            Projectile.width = {width};
            Projectile.height = {height};
            Projectile.friendly = true;
            Projectile.hostile = false;
            Projectile.DamageType = DamageClass.Magic;
            Projectile.penetrate = -1;
            Projectile.timeLeft = 180;
            Projectile.tileCollide = true;
            Projectile.ignoreWater = true;
            Projectile.usesLocalNPCImmunity = true;
            Projectile.localNPCHitCooldown = 12;
        }}

        public override bool? CanDamage()
        {{
            return Projectile.ai[0] > ChargeTicks ? null : false;
        }}

        public override void AI()
        {{
            Projectile.ai[0]++;
            // mechanics_ir atoms: charge_phase, singularity_projectile,
            // gravity_pull_field, rift_trail. Enrich this body without changing
            // signatures or removing the phase timer.
            if (Projectile.ai[0] <= ChargeTicks)
            {{
                Projectile.friendly = false;
                Projectile.velocity *= 0.92f;
            }}
            else
            {{
                Projectile.friendly = true;
                Projectile.rotation = Projectile.velocity.ToRotation();
                Projectile.scale = 1f + System.MathF.Sin(Projectile.ai[0] * 0.2f) * 0.08f;
                Lighting.AddLight(Projectile.Center, 0.35f, 0.06f, 0.65f);
            }}

            if (++Projectile.frameCounter >= 5)
            {{
                Projectile.frameCounter = 0;
                Projectile.frame = (Projectile.frame + 1) % FrameCount;
            }}
        }}

        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {{
            Collapse();
        }}

        public override bool OnTileCollide(Vector2 oldVelocity)
        {{
            Collapse();
            CarveTiles();
            return true;
        }}

        public override void OnKill(int timeLeft)
        {{
            Collapse();
        }}

        private void Collapse()
        {{
            // mechanics_ir atoms: implosion_payoff, shock_ring_damage.
            Vector2 center = Projectile.Center;
            Projectile.Resize(96, 96);
            Projectile.Center = center;
            Projectile.Damage();
        }}

        private void CarveTiles()
        {{
            // mechanics_ir atom: bounded_terrain_carve.
            int centerX = (int)(Projectile.Center.X / 16f);
            int centerY = (int)(Projectile.Center.Y / 16f);
            int breakCount = 0;
            for (int x = centerX - CarveRadius; x <= centerX + CarveRadius; x++)
            {{
                for (int y = centerY - CarveRadius; y <= centerY + CarveRadius; y++)
                {{
                    if (breakCount >= TileLimit || !WorldGen.InWorld(x, y, 10))
                    {{
                        continue;
                    }}
                    Tile tile = Main.tile[x, y];
                    if (tile != null && tile.HasTile && Main.tileSolid[tile.TileType])
                    {{
                        WorldGen.KillTile(x, y, fail: false, effectOnly: false, noItem: true);
                        breakCount++;
                    }}
                }}
            }}
        }}

        public override bool PreDraw(ref Color lightColor)
        {{
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            int frameHeight = texture.Height / FrameCount;
            Rectangle frame = new Rectangle(0, Projectile.frame * frameHeight, texture.Width, frameHeight);
            Vector2 origin = frame.Size() * 0.5f;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {{
                Vector2 oldCenter = Projectile.oldPos[i] + Projectile.Size * 0.5f - Main.screenPosition;
                float progress = 1f - i / (float)Projectile.oldPos.Length;
                Main.EntitySpriteDraw(texture, oldCenter, frame, Color.Black * (0.25f * progress), Projectile.rotation, origin, Projectile.scale * progress, SpriteEffects.None, 0);
                Main.EntitySpriteDraw(texture, oldCenter, frame, Color.Violet * (0.45f * progress), Projectile.rotation, origin, Projectile.scale * progress, SpriteEffects.None, 0);
            }}
            Vector2 center = Projectile.Center - Main.screenPosition;
            Main.EntitySpriteDraw(texture, center, frame, Color.Violet, Projectile.rotation, origin, Projectile.scale * 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, center, frame, Color.White, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            return false;
        }}
    }}
}}"""


def _frame_count(animation_tier: str) -> int:
    if ":" not in animation_tier:
        return 1
    try:
        return max(1, int(animation_tier.rsplit(":", 1)[1]))
    except ValueError:
        return 1


def _atom_int(manifest: dict, kind: str, field: str, default: int) -> int:
    ir = manifest.get("mechanics_ir") if isinstance(manifest, dict) else {}
    atoms = ir.get("atoms") if isinstance(ir, dict) else []
    if not isinstance(atoms, list):
        return default
    for atom in atoms:
        if not isinstance(atom, dict) or atom.get("kind") != kind:
            continue
        try:
            return int(atom.get(field) or default)
        except (TypeError, ValueError):
            return default
    return default
