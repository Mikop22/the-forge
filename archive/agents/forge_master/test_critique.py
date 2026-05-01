from __future__ import annotations

from forge_master.critique import (
    CritiqueContext,
    critique_generated_code,
)


def _context() -> CritiqueContext:
    return CritiqueContext(
        manifest={
            "projectile_visuals": {
                "foreground_bbox": [8, 6, 23, 25],
                "hitbox_size": [16, 20],
            }
        },
        valid_symbols={
            "ProjectileID": {"MagicMissile"},
            "ItemID": {"Wood"},
            "TileID": {"WorkBenches"},
            "DustID": {"Electric"},
            "SoundID": {"Item94"},
            "BuffID": {"OnFire"},
        },
        projectile_frame_counts={"ProjectileID.MagicMissile": 1},
        relative_path="Content/Items/StormBrand.cs",
    )


def test_critique_catches_invalid_vanilla_id() -> None:
    code = """
using Terraria.ID;
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrand : ModItem
    {
        public override void SetDefaults()
        {
            Item.shoot = ProjectileID.FairyQueenMagicItem;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("ProjectileID.FairyQueenMagicItem" in issue.message for issue in result.issues)


def test_critique_requires_trail_cache_for_oldpos_reads() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override bool PreDraw(ref Color lightColor)
        {
            var pos = Projectile.oldPos[0];
            return false;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("TrailCacheLength" in issue.message for issue in result.issues)


def test_critique_catches_unthrottled_dust_in_ai() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override void AI()
        {
            Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("Dust.NewDustPerfect" in issue.message for issue in result.issues)


def test_critique_catches_projectile_hitbox_mismatch() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override void SetDefaults()
        {
            Projectile.width = 10;
            Projectile.height = 10;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("hitbox_size" in issue.message for issue in result.issues)


def test_critique_rejects_underwhelming_spectacle_projectile() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class VoidVioletPistol : ModItem { }

    public class VoidVioletPistolProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 6;
        }

        public override void AI()
        {
            Projectile.rotation += 0.2f;
            if (Main.rand.NextBool(3))
                Dust.NewDust(Projectile.position, Projectile.width, Projectile.height, DustID.Electric);
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "violet annihilation orb",
                    "render_passes": ["afterimage trail", "outer glow", "core"],
                    "ai_phases": ["spawn flare", "cruise", "impact collapse"],
                    "impact_payoff": "imploding shock ring",
                    "must_not_feel_like": ["bullet", "generic dust trail"],
                }
            },
            relative_path="Content/Items/VoidVioletPistol.cs",
        ),
    )

    assert not result.passed
    rules = {issue.rule for issue in result.issues}
    assert "spectacle_predraw" in rules
    assert "spectacle_trail" in rules
    assert "spectacle_payoff" in rules


def test_critique_accepts_structured_spectacle_projectile() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidVioletPistol : ModItem { }

    public class VoidVioletPistolProjectile : ModProjectile
    {
        private const int TrailLength = 18;

        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = TrailLength;
            ProjectileID.Sets.TrailingMode[Type] = 2;
        }

        public override void AI()
        {
            Projectile.ai[1]++;
            float phasePulse = (float)System.Math.Sin(Projectile.ai[1] * 0.2f);
            Projectile.scale = 1f + phasePulse * 0.05f;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            Vector2 origin = texture.Size() / 2f;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i] + Projectile.Size / 2f - Main.screenPosition, null, Color.Purple, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale * 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            Collapse();
        }

        private void Collapse()
        {
            for (int i = 0; i < 20; i++)
            {
                Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
            }
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "violet annihilation orb",
                    "render_passes": ["afterimage trail", "outer glow", "core"],
                    "ai_phases": ["spawn flare", "cruise", "impact collapse"],
                    "impact_payoff": "imploding shock ring",
                }
            },
            relative_path="Content/Items/VoidVioletPistol.cs",
        ),
    )

    assert result.passed


def test_critique_accepts_inline_spectacle_payoff_hook() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.Audio;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidVioletPistol : ModItem { }

    public class VoidVioletPistolProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
            ProjectileID.Sets.TrailingMode[Type] = 2;
        }

        public override void AI()
        {
            Projectile.ai[1]++;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            Vector2 origin = texture.Size() / 2f;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i] + Projectile.Size / 2f - Main.screenPosition, null, Color.Purple, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale * 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            SoundEngine.PlaySound(SoundID.Item94, Projectile.Center);
            for (int i = 0; i < 24; i++)
            {
                Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
            }
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "violet annihilation orb",
                    "render_passes": ["afterimage trail", "outer glow", "core"],
                    "ai_phases": ["spawn flare", "cruise", "impact collapse"],
                    "impact_payoff": "imploding shock ring",
                }
            },
            relative_path="Content/Items/VoidVioletPistol.cs",
        ),
    )

    assert result.passed


def test_critique_accepts_secondary_projectile_spectacle_payoff() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.Audio;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class Riftspite : ModItem
    {
        public override void SetDefaults()
        {
            Item.useAmmo = AmmoID.Bullet;
            Item.shoot = ModContent.ProjectileType<RiftspiteShot>();
        }
    }

    public class RiftspiteShot : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override void AI()
        {
            Projectile.ai[0]++;
        }

        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            SpawnRift(target);
        }

        private void SpawnRift(NPC target)
        {
            Projectile.NewProjectile(
                Projectile.GetSource_FromThis(),
                target.Bottom,
                Vector2.Zero,
                ModContent.ProjectileType<RiftspiteRift>(),
                Projectile.damage,
                Projectile.knockBack,
                Projectile.owner);
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            Vector2 origin = texture.Size() / 2f;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i] + Projectile.Size / 2f - Main.screenPosition, null, Color.Violet, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.Black, Projectile.rotation, origin, Projectile.scale * 1.6f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            return false;
        }
    }

    public class RiftspiteRift : ModProjectile
    {
        public override void AI()
        {
            if (++Projectile.ai[0] == 10)
            {
                Projectile.Resize(96, 96);
                Projectile.Damage();
            }
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "sub_type": "Pistol",
                "spectacle_plan": {
                    "fantasy": "rift pistol",
                    "render_passes": ["rift trail", "outer glow", "bright core"],
                    "ai_phases": ["direct fire travel", "underfoot rift open"],
                    "impact_payoff": "spawn a secondary rift under the enemy",
                    "must_not_feel_like": ["bullet", "generic bullet"],
                },
            },
            relative_path="Content/Items/Riftspite.cs",
        ),
    )

    assert result.passed


def test_critique_rejects_forbidden_generic_bullet_projectileid() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class Riftspite : ModItem
    {
        public override void SetDefaults()
        {
            Item.shoot = ProjectileID.Bullet;
        }
    }

    public class RiftspiteProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0]++;
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "rift pistol",
                    "must_not_feel_like": ["bullet"],
                },
            },
            relative_path="Content/Items/Riftspite.cs",
        ),
    )

    assert not result.passed
    assert any(issue.rule == "spectacle_forbidden_mechanic" for issue in result.issues)


def test_critique_accepts_framecounter_charge_as_spectacle_ai_phase() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.Audio;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaff : ModItem { }

    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override void AI()
        {
            Projectile.frameCounter++;
            float chargePulse = (float)System.Math.Sin(Projectile.frameCounter * 0.12f);
            Projectile.scale = 1f + chargePulse * 0.08f;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            Vector2 origin = texture.Size() / 2f;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i] + Projectile.Size / 2f - Main.screenPosition, null, Color.Purple, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale * 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            SoundEngine.PlaySound(SoundID.Item94, Projectile.Center);
            for (int i = 0; i < 24; i++)
            {
                Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
            }
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "violet singularity",
                    "basis": {"world_interaction": ["none"]},
                    "composition": "A charged singularity pulses before collapse.",
                }
            },
            relative_path="Content/Items/VoidConvergenceStaff.cs",
        ),
    )

    assert result.passed


def test_critique_accepts_gametime_predraw_as_spectacle_phase() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.Audio;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaff : ModItem { }

    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            Vector2 origin = texture.Size() / 2f;
            float phasePulse = (float)System.Math.Sin(Main.GameUpdateCount * 0.12f);
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i] + Projectile.Size / 2f - Main.screenPosition, null, Color.Purple, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale * (1.4f + phasePulse * 0.1f), SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center - Main.screenPosition, null, Color.White, Projectile.rotation, origin, Projectile.scale, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            SoundEngine.PlaySound(SoundID.Item94, Projectile.Center);
            for (int i = 0; i < 24; i++)
            {
                Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
            }
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "violet singularity",
                    "basis": {"world_interaction": ["none"]},
                    "composition": "A charged singularity pulses before collapse.",
                }
            },
            relative_path="Content/Items/VoidConvergenceStaff.cs",
        ),
    )

    assert result.passed


def test_critique_rejects_forbidden_spectacle_mechanics() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaff : ModItem { }

    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override void AI()
        {
            Projectile.ai[0]++;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i], null, Color.Purple, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            Collapse();
        }

        private void Collapse()
        {
            Projectile.NewProjectile(Projectile.GetSource_FromThis(), Projectile.Center, Vector2.UnitY, ProjectileID.Starfury, Projectile.damage, 1f, Projectile.owner);
        }
    }

    public class VoidConvergenceStaffStormBrandNPC : GlobalNPC
    {
        public int VoidConvergenceMarkCount;
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "hollow purple singularity",
                    "basis": {
                        "projectile_body": ["singularity orb"],
                        "world_interaction": ["none"],
                    },
                    "composition": "A slow singularity collapses into a shock ring.",
                    "must_not_include": ["starfall", "mark/cashout"],
                }
            },
            relative_path="Content/Items/VoidConvergenceStaff.cs",
        ),
    )

    assert not result.passed
    rules = {issue.rule for issue in result.issues}
    assert "spectacle_forbidden_mechanic" in rules


def test_critique_rejects_normalized_forbidden_mark_cashout_terms() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaff : ModItem { }

    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override void AI()
        {
            Projectile.ai[0]++;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i], null, Color.Purple, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            Collapse();
        }

        private void Collapse()
        {
            Dust.NewDustPerfect(Projectile.Center, DustID.PurpleTorch);
        }
    }

    public class VoidConvergenceStaffStormBrandNPC : GlobalNPC
    {
        public int VoidConvergenceMarkCount;
        public int VoidConvergenceMarkTime;
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "hollow purple singularity",
                    "basis": {"world_interaction": ["none"]},
                    "composition": "A slow singularity collapses into a shock ring.",
                    "must_not_include": ["celestial marks", "mark/cashout"],
                }
            },
            relative_path="Content/Items/VoidConvergenceStaff.cs",
        ),
    )

    assert not result.passed
    messages = [issue.message for issue in result.issues]
    assert any("celestial marks" in message for message in messages)
    assert any("mark/cashout" in message for message in messages)


def test_critique_rejects_renamed_target_stack_cashout_terms() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaff : ModItem { }

    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override void AI()
        {
            Projectile.ai[0]++;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i], null, Color.Purple, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            Collapse();
        }

        private void Collapse()
        {
            Dust.NewDustPerfect(Projectile.Center, DustID.PurpleTorch);
        }

        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            VoidConvergenceTargetState state = target.GetGlobalNPC<VoidConvergenceTargetState>();
            state.InstabilityStacks++;
            if (state.InstabilityStacks >= 3)
            {
                Collapse();
            }
        }
    }

    public class VoidConvergenceTargetState : GlobalNPC
    {
        public int InstabilityStacks;
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "hollow purple singularity",
                    "basis": {"world_interaction": ["none"]},
                    "composition": "A slow singularity collapses into a shock ring.",
                    "must_not_include": ["mark/cashout"],
                }
            },
            relative_path="Content/Items/VoidConvergenceStaff.cs",
        ),
    )

    assert not result.passed
    assert any(issue.rule == "spectacle_forbidden_mechanic" for issue in result.issues)


def test_mechanics_ir_requires_charge_phase_evidence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0]++;
            Projectile.rotation += 0.1f;
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "mechanics_ir": {
                    "atoms": [{"kind": "charge_phase", "duration_ticks": 18}]
                }
            }
        ),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_missing_atom" for issue in result.issues)


def test_mechanics_ir_requires_gravity_pull_evidence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0]++;
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "mechanics_ir": {
                    "atoms": [{"kind": "gravity_pull_field", "radius_tiles": 6}]
                }
            }
        ),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_missing_atom" for issue in result.issues)


def test_mechanics_ir_requires_implosion_payoff_evidence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0]++;
        }

        public override void OnKill(int timeLeft)
        {
            Dust.NewDustPerfect(Projectile.Center, DustID.PurpleTorch);
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "mechanics_ir": {
                    "atoms": [{"kind": "implosion_payoff", "radius_tiles": 7}]
                }
            }
        ),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_missing_atom" for issue in result.issues)


def test_mechanics_ir_requires_bounded_terrain_carve_evidence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        private void ScorchTiles()
        {
            Tile tile = Main.tile[0, 0];
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "mechanics_ir": {
                    "atoms": [{"kind": "bounded_terrain_carve", "radius_tiles": 2}]
                }
            }
        ),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_missing_atom" for issue in result.issues)


def test_mechanics_ir_rejects_forbidden_target_stack_cashout_atom() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void OnHitNPC(NPC target, NPC.HitInfo hit, int damageDone)
        {
            VoidConvergenceTargetState state = target.GetGlobalNPC<VoidConvergenceTargetState>();
            state.InstabilityStacks++;
            if (state.InstabilityStacks >= 3)
            {
                Projectile.NewProjectile(Projectile.GetSource_FromThis(), target.Center, Vector2.Zero, 1, Projectile.damage, 1f, Projectile.owner);
            }
        }
    }

    public class VoidConvergenceTargetState : GlobalNPC
    {
        public int InstabilityStacks;
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "mechanics_ir": {
                    "forbidden_atoms": ["target_stack_cashout"],
                    "atoms": [{"kind": "singularity_projectile"}],
                }
            }
        ),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_forbidden_atom" for issue in result.issues)


def test_mechanics_ir_requires_beam_lance_evidence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class RiftLanceProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0]++;
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(manifest={"mechanics_ir": {"atoms": [{"kind": "beam_lance"}]}}),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_missing_atom" for issue in result.issues)


def test_mechanics_ir_requires_delayed_detonation_evidence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class RiftMineProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0]++;
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={"mechanics_ir": {"atoms": [{"kind": "delayed_detonation"}]}}
        ),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_missing_atom" for issue in result.issues)


def test_mechanics_ir_requires_summoned_construct_evidence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class RiftEyeProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0]++;
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={"mechanics_ir": {"atoms": [{"kind": "summoned_construct"}]}}
        ),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_missing_atom" for issue in result.issues)


def test_mechanics_ir_requires_orbiting_convergence_evidence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class RiftOrbitProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0]++;
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={"mechanics_ir": {"atoms": [{"kind": "orbiting_convergence"}]}}
        ),
    )

    assert not result.passed
    assert any(issue.rule == "mechanics_ir_missing_atom" for issue in result.issues)


def test_critique_requires_tile_code_for_terrain_carve_basis() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaff : ModItem { }

    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override void AI()
        {
            Projectile.ai[0]++;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i], null, Color.Purple, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            Collapse();
        }

        private void Collapse()
        {
            for (int i = 0; i < 20; i++)
            {
                Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
            }
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "hollow purple singularity",
                    "basis": {
                        "projectile_body": ["singularity orb"],
                        "world_interaction": ["radial terrain carve"],
                    },
                    "composition": "A slow singularity scars terrain on collapse.",
                }
            },
            relative_path="Content/Items/VoidConvergenceStaff.cs",
        ),
    )

    assert not result.passed
    assert any(issue.rule == "spectacle_world_interaction" for issue in result.issues)


def test_critique_requires_real_tile_break_for_terrain_carve_basis() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaff : ModItem { }

    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override void AI()
        {
            Projectile.ai[0]++;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i], null, Color.Purple, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            Collapse();
        }

        private void Collapse()
        {
            Tile tile = Main.tile[0, 0];
            Dust.NewDustPerfect(Projectile.Center, DustID.PurpleTorch);
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "hollow purple singularity",
                    "basis": {"world_interaction": ["radial terrain carve"]},
                    "composition": "A slow singularity collapses into a shock ring.",
                }
            },
            relative_path="Content/Items/VoidConvergenceStaff.cs",
        ),
    )

    assert not result.passed
    assert any(issue.rule == "spectacle_world_interaction" for issue in result.issues)


def test_critique_accepts_bounded_tile_code_for_terrain_carve_basis() -> None:
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidConvergenceStaff : ModItem { }

    public class VoidConvergenceStaffProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
        }

        public override void AI()
        {
            Projectile.ai[0]++;
        }

        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            for (int i = Projectile.oldPos.Length - 1; i > 0; i--)
            {
                Main.EntitySpriteDraw(texture, Projectile.oldPos[i], null, Color.Purple, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            }
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1.4f, SpriteEffects.None, 0);
            Main.EntitySpriteDraw(texture, Projectile.Center, null, Color.White, 0f, Vector2.Zero, 1f, SpriteEffects.None, 0);
            return false;
        }

        public override void OnKill(int timeLeft)
        {
            Collapse();
        }

        private void Collapse()
        {
            for (int x = -2; x <= 2; x++)
            {
                for (int y = -2; y <= 2; y++)
                {
                    WorldGen.KillTile((int)(Projectile.Center.X / 16f) + x, (int)(Projectile.Center.Y / 16f) + y, fail: false, effectOnly: false, noItem: true);
                }
            }
            for (int i = 0; i < 20; i++)
            {
                Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
            }
        }
    }
}
"""
    result = critique_generated_code(
        code,
        CritiqueContext(
            manifest={
                "spectacle_plan": {
                    "fantasy": "hollow purple singularity",
                    "basis": {
                        "projectile_body": ["singularity orb"],
                        "world_interaction": ["radial terrain carve"],
                    },
                    "composition": "A slow singularity scars terrain on collapse.",
                }
            },
            relative_path="Content/Items/VoidConvergenceStaff.cs",
        ),
    )

    assert result.passed


def test_critique_catches_second_mod_subclass() -> None:
    code = """
namespace ForgeGeneratedMod
{
    public class OtherMod : Mod {}
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("must not declare a Mod subclass" in issue.message for issue in result.issues)


def test_critique_catches_item_namespace_path_mismatch() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Projectiles
{
    public class StormBrand : ModItem {}
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("Content.Items" in issue.message for issue in result.issues)


def test_critique_allows_item_child_namespace() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items.Weapons
{
    public class StormBrand : ModItem {}
}
"""

    result = critique_generated_code(code, _context())

    assert result.passed


def test_critique_catches_vanilla_frame_count_mismatch() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override string Texture => "Terraria/Images/Projectile_" + ProjectileID.MagicMissile;
        public override void SetStaticDefaults()
        {
            Main.projFrames[Type] = 4;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("frame count" in issue.message for issue in result.issues)


def test_critique_catches_vanilla_frame_count_constant_mismatch() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        private const int FrameCount = 4;
        public override string Texture => "Terraria/Images/Projectile_" + ProjectileID.MagicMissile;
        public override void SetStaticDefaults()
        {
            Main.projFrames[Type] = FrameCount;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("frame count" in issue.message for issue in result.issues)


def test_critique_catches_predraw_frame_slicing_mismatch() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override string Texture => "Terraria/Images/Projectile_" + ProjectileID.MagicMissile;
        public override void SetStaticDefaults()
        {
            Main.projFrames[Type] = 4;
        }
        public override bool PreDraw(ref Color lightColor)
        {
            Main.EntitySpriteDraw(TextureAssets.Projectile[Type].Value, Projectile.Center, null, Color.White);
            return false;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("frame slicing" in issue.message for issue in result.issues)


def test_critique_accepts_predraw_frame_slicing_math() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        private const int FrameCount = 1;
        public override string Texture => "Terraria/Images/Projectile_" + ProjectileID.MagicMissile;
        public override void SetStaticDefaults()
        {
            Main.projFrames[Type] = FrameCount;
        }
        public override bool PreDraw(ref Color lightColor)
        {
            Texture2D texture = TextureAssets.Projectile[Type].Value;
            int frameHeight = texture.Height / FrameCount;
            Rectangle frame = new Rectangle(0, Projectile.frame * frameHeight, texture.Width, frameHeight);
            Main.EntitySpriteDraw(texture, Projectile.Center, frame, Color.White);
            return false;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert all(issue.rule != "predraw_frame_slicing" for issue in result.issues)


def test_critique_accepts_single_frame_predraw_full_texture() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override string Texture => "Terraria/Images/Projectile_" + ProjectileID.MagicMissile;
        public override void SetStaticDefaults()
        {
            Main.projFrames[Type] = 1;
        }
        public override bool PreDraw(ref Color lightColor)
        {
            Main.EntitySpriteDraw(TextureAssets.Projectile[Type].Value, Projectile.Center, null, Color.White);
            return false;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert all(issue.rule != "predraw_frame_slicing" for issue in result.issues)


def test_critique_allows_projectile_id_sets_without_registry_entry() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 12;
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert all("ProjectileID.Sets" not in issue.message for issue in result.issues)


def test_critique_rejects_dust_with_unrelated_ai_state_but_no_cadence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override void AI()
        {
            Projectile.ai[0] += 1f;
            Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("cadence throttle" in issue.message for issue in result.issues)


def test_critique_rejects_plain_newdust_without_cadence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override void AI()
        {
            Dust.NewDust(Projectile.position, Projectile.width, Projectile.height, DustID.Electric);
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert not result.passed
    assert any("Dust.NewDust" in issue.message for issue in result.issues)


def test_critique_accepts_game_update_count_dust_cadence() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override void AI()
        {
            if ((int)Main.GameUpdateCount % 3 == 0)
            {
                Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
            }
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert all(issue.rule != "dust_throttle" for issue in result.issues)


def test_critique_accepts_cadence_guard_before_long_spectacle_dust_block() -> None:
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile
    {
        public override void AI()
        {
            if ((int)Projectile.ai[0] % 3 == 0)
            {
                Vector2 direction = Projectile.velocity.SafeNormalize(Vector2.UnitX);
                Vector2 normal = new Vector2(-direction.Y, direction.X);
                Vector2 offset = normal * Main.rand.NextFloat(-10f, 10f);
                Vector2 position = Projectile.Center - direction * 18f + offset;
                Vector2 velocity = -direction * Main.rand.NextFloat(0.5f, 1.5f) + normal * Main.rand.NextFloat(-0.4f, 0.4f);
                Dust.NewDustPerfect(position, DustID.Electric, velocity);
            }
        }
    }
}
"""

    result = critique_generated_code(code, _context())

    assert all(issue.rule != "dust_throttle" for issue in result.issues)


def test_critique_rejects_projectile_file_with_item_namespace() -> None:
    context = CritiqueContext(
        manifest={},
        relative_path="Content/Projectiles/StormBrandProjectile.cs",
    )
    code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrandProjectile : ModProjectile {}
}
"""

    result = critique_generated_code(code, context)

    assert not result.passed
    assert any("Content/Projectiles" in issue.message for issue in result.issues)


def test_write_code_repairs_critique_failures(monkeypatch) -> None:
    from unittest.mock import MagicMock

    from forge_master.forge_master import CoderAgent
    from forge_master.models import CSharpOutput
    from forge_master.reviewer import ReviewOutput

    bad_code = """
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;
using Microsoft.Xna.Framework;

namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrand : ModItem
    {
        public override void SetDefaults()
        {
            Item.shoot = ProjectileID.FairyQueenMagicItem;
        }
    }

    public class StormBrandProjectile : ModProjectile
    {
        public override bool PreDraw(ref Color lightColor)
        {
            var pos = Projectile.oldPos[0];
            return false;
        }
    }
}
"""
    fixed_code = bad_code.replace(
        "public class StormBrandProjectile : ModProjectile",
        "public class StormBrandProjectile : ModProjectile\n    {\n        public override void SetStaticDefaults()\n        {\n            ProjectileID.Sets.TrailCacheLength[Type] = 12;\n        }\n    }\n\n    public class RemovedProjectile : ModProjectile",
    )
    agent = CoderAgent.__new__(CoderAgent)
    agent._gen_chain = MagicMock(invoke=MagicMock(return_value=CSharpOutput(code=bad_code)))
    agent._repair_chain = MagicMock(invoke=MagicMock(return_value=fixed_code))
    agent._reviewer = MagicMock(
        review=MagicMock(
            return_value=(
                fixed_code,
                ReviewOutput(approved=True, issues=[], summary="Looks good!"),
            )
        )
    )

    result = agent.write_code(
        {
            "item_name": "StormBrand",
            "display_name": "Storm Brand",
            "stats": {
                "damage": 10,
                "knockback": 4.0,
                "use_time": 20,
                "rarity": "ItemRarityID.Green",
            },
            "mechanics": {
                "crafting_material": "ItemID.Wood",
                "crafting_cost": 5,
                "crafting_tile": "TileID.WorkBenches",
            },
        }
    )

    assert result["status"] == "success"
    agent._repair_chain.invoke.assert_called_once()
    repair_payload = agent._repair_chain.invoke.call_args.args[0]
    assert "TrailCacheLength" in repair_payload["error_log"]
    assert '"item_name": "StormBrand"' in repair_payload["manifest_json"]
