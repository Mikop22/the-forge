from __future__ import annotations

from unittest.mock import MagicMock, patch

from forge_master.forge_master import CoderAgent
from forge_master.forge_master import _reference_snippet_for_codegen
from forge_master.forge_master import _reference_combat_package_key
from forge_master.models import ForgeManifest
from forge_master.forge_master import _validate_projectile_hitbox_contract
from forge_master.models import CSharpOutput
from forge_master.reviewer import ReviewOutput
from forge_master import prompts


def test_codegen_prompt_documents_projectile_hitbox_contract() -> None:
    assert "projectile_visuals.hitbox_size" in prompts.CODEGEN_SYSTEM
    assert "Projectile.width" in prompts.CODEGEN_SYSTEM
    assert "Projectile.height" in prompts.CODEGEN_SYSTEM
    assert "Tier-3 Exemplar Gallery" in prompts.CODEGEN_SYSTEM
    assert "not a menu" in prompts.CODEGEN_SYSTEM
    assert "VoidNeedleSigilProjectile" in prompts.CODEGEN_SYSTEM
    assert "NyanCatStaffProjectile" in prompts.CODEGEN_SYSTEM
    assert "using Terraria.GameContent;" in prompts.CODEGEN_SYSTEM
    assert "projectile_visuals.animation_tier" in prompts.CODEGEN_SYSTEM
    assert "vanilla_frames:N" in prompts.CODEGEN_SYSTEM
    assert "generated_frames:N" in prompts.CODEGEN_SYSTEM
    assert "spectacle_plan" in prompts.CODEGEN_SYSTEM
    assert "PreDraw" in prompts.CODEGEN_SYSTEM
    assert "multi-pass" in prompts.CODEGEN_SYSTEM
    assert "impact payoff" in prompts.CODEGEN_SYSTEM
    assert "must_not_feel_like" in prompts.CODEGEN_SYSTEM
    assert "spectacle_plan.basis" in prompts.CODEGEN_SYSTEM
    assert "spectacle_plan.composition" in prompts.CODEGEN_SYSTEM
    assert "spectacle_plan.must_not_include" in prompts.CODEGEN_SYSTEM
    assert "mechanics_ir.atoms" in prompts.CODEGEN_SYSTEM
    assert "Implement every requested atom" in prompts.CODEGEN_SYSTEM
    assert "Do not implement forbidden_atoms" in prompts.CODEGEN_SYSTEM
    assert "world_interaction" in prompts.CODEGEN_SYSTEM
    assert "tile" in prompts.CODEGEN_SYSTEM.lower()


def test_validate_projectile_hitbox_contract_accepts_matching_dimensions() -> None:
    manifest = {"projectile_visuals": {"hitbox_size": [16, 20]}}
    cs_code = """
public class StormBrandProjectile : ModProjectile
{
    public override void SetDefaults()
    {
        Projectile.width = 16;
        Projectile.height = 20;
    }
}
"""

    assert _validate_projectile_hitbox_contract(manifest, cs_code) == []


def test_validate_projectile_hitbox_contract_rejects_mismatched_dimensions() -> None:
    manifest = {"projectile_visuals": {"hitbox_size": [16, 20]}}
    cs_code = """
public class StormBrandProjectile : ModProjectile
{
    public override void SetDefaults()
    {
        Projectile.width = 10;
        Projectile.height = 10;
    }
}
"""

    violations = _validate_projectile_hitbox_contract(manifest, cs_code)

    assert violations == [
        "Projectile hitbox must match projectile_visuals.hitbox_size [16, 20]; "
        "found Projectile.width=10, Projectile.height=10."
    ]


def test_validate_projectile_hitbox_contract_ignores_item_without_modprojectile() -> None:
    manifest = {"projectile_visuals": {"hitbox_size": [16, 20]}}
    cs_code = """
namespace ForgeGeneratedMod.Content.Items
{
    public class StormBrand : ModItem
    {
        public override void SetDefaults()
        {
            Item.shoot = ProjectileID.MagicMissile;
        }
    }
}
"""

    assert _validate_projectile_hitbox_contract(manifest, cs_code) == []


def test_validate_projectile_hitbox_contract_scopes_to_projectile_setdefaults() -> None:
    manifest = {"projectile_visuals": {"hitbox_size": [16, 20]}}
    cs_code = """
public class StormBrandProjectile : ModProjectile
{
    // Projectile.width = 16;
    // Projectile.height = 20;
    public void DecorativeHelper()
    {
        Projectile.width = 16;
        Projectile.height = 20;
    }
    public override void SetDefaults()
    {
        Projectile.width = 10;
        Projectile.height = 10;
    }
}
"""

    violations = _validate_projectile_hitbox_contract(manifest, cs_code)

    assert violations == [
        "Projectile hitbox must match projectile_visuals.hitbox_size [16, 20]; "
        "found Projectile.width=10, Projectile.height=10."
    ]


def test_write_code_revalidates_hitbox_after_reviewer_changes_code() -> None:
    agent = CoderAgent.__new__(CoderAgent)
    matching_code = """
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
public class StormBrand : ModItem
{
    public override void SetDefaults()
    {
        Item.damage = 10;
    }
}

public class StormBrandProjectile : ModProjectile
{
    public override void SetDefaults()
    {
        Projectile.width = 16;
        Projectile.height = 20;
    }
}
}
"""
    mismatched_code = """
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
public class StormBrand : ModItem
{
    public override void SetDefaults()
    {
        Item.damage = 10;
    }
}

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
    agent._gen_chain = MagicMock(
        invoke=MagicMock(return_value=CSharpOutput(code=matching_code))
    )
    agent._reviewer = MagicMock(
        review=MagicMock(
            return_value=(
                mismatched_code,
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
                "custom_projectile": True,
            },
            "projectile_visuals": {
                "description": "storm bolt",
                "hitbox_size": [16, 20],
            },
        }
    )

    assert result["status"] == "error"
    assert result["cs_code"] == mismatched_code
    assert result["error"]["code"] == "VALIDATION"
    assert "projectile_visuals.hitbox_size" in result["error"]["message"]


def test_write_code_uses_bespoke_chain_for_spectacle_manifest() -> None:
    agent = CoderAgent.__new__(CoderAgent)
    standard_chain = MagicMock(invoke=MagicMock(return_value=CSharpOutput(code="")))
    bespoke_chain = MagicMock(invoke=MagicMock(return_value=CSharpOutput(code="""
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
public class VoidVioletPistol : ModItem
{
    public override void SetDefaults() { }
}
}
""")))
    agent._gen_chain = standard_chain
    agent._bespoke_gen_chain = bespoke_chain
    agent._reviewer = MagicMock(
        review=MagicMock(
            side_effect=lambda manifest, code: (
                code,
                ReviewOutput(approved=True, issues=[], summary="Looks good!"),
            )
        )
    )

    result = agent.write_code(
        {
            "item_name": "VoidVioletPistol",
            "display_name": "Void Violet",
            "sub_type": "Pistol",
            "stats": {
                "damage": 34,
                "knockback": 4.5,
                "use_time": 22,
                "rarity": "ItemRarityID.Orange",
            },
            "mechanics": {
                "crafting_material": "ItemID.Bone",
                "crafting_cost": 15,
                "crafting_tile": "TileID.Anvils",
                "custom_projectile": True,
            },
            "projectile_visuals": {"description": "violet orb"},
            "spectacle_plan": {"fantasy": "violet annihilation orb"},
        }
    )

    assert result["status"] == "success"
    bespoke_chain.invoke.assert_called_once()
    standard_chain.invoke.assert_not_called()


def test_coder_agent_bespoke_model_uses_medium_reasoning_by_default() -> None:
    llm_instances = []

    class FakeLLM:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            llm_instances.append(kwargs)

        def with_structured_output(self, model):
            return self

        def __or__(self, other):
            return self

        def __ror__(self, other):
            return self

    class FakePrompt:
        def __or__(self, other):
            return other

    with patch("forge_master.forge_master.ChatOpenAI", side_effect=lambda **kwargs: FakeLLM(**kwargs)), \
         patch("forge_master.forge_master.build_codegen_prompt", return_value=FakePrompt()), \
         patch("forge_master.forge_master.build_repair_prompt", return_value=FakePrompt()), \
         patch("forge_master.forge_master.WeaponReviewer"):
        CoderAgent(model_name="gpt-5.4", bespoke_model_name="gpt-5.5")

    assert llm_instances[0]["model"] == "gpt-5.4"
    assert llm_instances[0]["reasoning_effort"] == "high"
    assert llm_instances[1]["model"] == "gpt-5.5"
    assert llm_instances[1]["reasoning_effort"] == "medium"


def test_coder_agent_bespoke_validation_attempts_match_standard_by_default() -> None:
    class FakeLLM:
        def with_structured_output(self, model):
            return self

        def __or__(self, other):
            return self

        def __ror__(self, other):
            return self

    class FakePrompt:
        def __or__(self, other):
            return other

    with patch("forge_master.forge_master.ChatOpenAI", return_value=FakeLLM()), \
         patch("forge_master.forge_master.build_codegen_prompt", return_value=FakePrompt()), \
         patch("forge_master.forge_master.build_repair_prompt", return_value=FakePrompt()), \
         patch("forge_master.forge_master.WeaponReviewer"):
        agent = CoderAgent(model_name="gpt-5.4", bespoke_model_name="gpt-5.5")

    assert agent._bespoke_max_attempts == 3


def test_bespoke_manifest_ignores_combat_package_reference_snippet() -> None:
    manifest = ForgeManifest(
        item_name="AbyssalConvergenceStaff",
        display_name="Abyssal Convergence Staff",
        sub_type="Staff",
        stats={
            "damage": 58,
            "knockback": 5.5,
            "use_time": 20,
            "rarity": "ItemRarityID.Pink",
        },
        mechanics={
            "combat_package": "storm_brand",
            "crafting_material": "ItemID.SoulofLight",
            "crafting_cost": 22,
            "crafting_tile": "TileID.Anvils",
        },
        resolved_combat={
            "package_key": "storm_brand",
            "delivery_module": "direct_seed_bolt",
            "combo_module": "npc_marks_3",
            "finisher_module": "starfall_burst",
            "presentation_module": "celestial_shock",
            "player_state_kind": "none",
            "npc_state_kind": "mark_counter",
            "legacy_projection": {
                "shot_style": "direct",
                "custom_projectile": True,
                "shoot_projectile": None,
                "projectile_visuals_required": True,
            },
        },
        spectacle_plan={
            "fantasy": "hollow purple singularity",
            "must_not_include": ["starfall", "mark/cashout"],
        },
    )

    assert _reference_combat_package_key(manifest, uses_bespoke=True) is None
    assert _reference_combat_package_key(manifest, uses_bespoke=False) == "storm_brand"


def test_bespoke_manifest_uses_neutral_spectacle_reference_snippet() -> None:
    manifest = ForgeManifest(
        item_name="VoidConvergenceStaff",
        display_name="Void Convergence Staff",
        sub_type="Staff",
        stats={
            "damage": 58,
            "knockback": 5.5,
            "use_time": 20,
            "rarity": "ItemRarityID.Pink",
        },
        mechanics={
            "combat_package": "storm_brand",
            "crafting_material": "ItemID.SoulofLight",
            "crafting_cost": 22,
            "crafting_tile": "TileID.Anvils",
        },
        resolved_combat={
            "package_key": "storm_brand",
            "delivery_module": "direct_seed_bolt",
            "combo_module": "npc_marks_3",
            "finisher_module": "starfall_burst",
            "presentation_module": "celestial_shock",
            "player_state_kind": "none",
            "npc_state_kind": "mark_counter",
            "legacy_projection": {
                "shot_style": "direct",
                "custom_projectile": True,
                "shoot_projectile": None,
                "projectile_visuals_required": True,
            },
        },
        spectacle_plan={
            "fantasy": "hollow purple singularity",
            "must_not_include": ["starfall", "mark/cashout"],
        },
    )

    snippet = _reference_snippet_for_codegen(manifest, uses_bespoke=True)

    assert "spectacle_plan" in snippet
    assert "ModProjectile" in snippet
    assert "storm_brand" not in snippet.lower()
    assert "MagicMissile" not in snippet
    assert "ProjectileID.Bullet" not in snippet
    assert "mark" not in snippet.lower()
    assert "star" not in snippet.lower()


def test_write_code_skips_llm_reviewer_for_spectacle_manifest_by_default() -> None:
    agent = CoderAgent.__new__(CoderAgent)
    code = """
using Microsoft.Xna.Framework;
using Microsoft.Xna.Framework.Graphics;
using Terraria;
using Terraria.GameContent;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
    public class VoidVioletPistol : ModItem
    {
        public override void SetDefaults()
        {
            Item.damage = 34;
        }
    }

    public class VoidVioletPistolProjectile : ModProjectile
    {
        public override void SetStaticDefaults()
        {
            ProjectileID.Sets.TrailCacheLength[Type] = 18;
            ProjectileID.Sets.TrailingMode[Type] = 2;
        }

        public override void SetDefaults()
        {
            Projectile.width = 16;
            Projectile.height = 16;
        }

        public override void AI()
        {
            Projectile.ai[1]++;
            Projectile.scale = 1f + (float)System.Math.Sin(Projectile.ai[1] * 0.2f) * 0.05f;
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
            Dust.NewDustPerfect(Projectile.Center, DustID.Electric);
        }
    }
}
"""
    agent._gen_chain = MagicMock()
    agent._bespoke_gen_chain = MagicMock(
        invoke=MagicMock(return_value=CSharpOutput(code=code))
    )
    agent._reviewer = MagicMock(
        review=MagicMock(side_effect=AssertionError("reviewer should be skipped"))
    )

    result = agent.write_code(
        {
            "item_name": "VoidVioletPistol",
            "display_name": "Void Violet",
            "sub_type": "Pistol",
            "stats": {
                "damage": 34,
                "knockback": 4.5,
                "use_time": 22,
                "rarity": "ItemRarityID.Orange",
            },
            "mechanics": {
                "crafting_material": "ItemID.Bone",
                "crafting_cost": 15,
                "crafting_tile": "TileID.Anvils",
                "custom_projectile": True,
            },
            "projectile_visuals": {
                "description": "violet orb",
                "hitbox_size": [16, 16],
            },
            "spectacle_plan": {
                "fantasy": "violet annihilation orb",
                "render_passes": ["afterimage trail", "outer glow", "core"],
                "ai_phases": ["spawn flare", "cruise", "impact collapse"],
                "impact_payoff": "imploding shock ring",
            },
        }
    )

    assert result["status"] == "success"
    agent._reviewer.review.assert_not_called()


def test_write_code_can_skip_llm_reviewer_for_operator_test_runs() -> None:
    agent = CoderAgent.__new__(CoderAgent)
    code = """
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

namespace ForgeGeneratedMod.Content.Items
{
public class TestWand : ModItem
{
    public override void SetDefaults()
    {
        Item.damage = 20;
    }
}
}
"""
    agent._gen_chain = MagicMock(invoke=MagicMock(return_value=CSharpOutput(code=code)))
    agent._reviewer = MagicMock(
        review=MagicMock(side_effect=AssertionError("reviewer should be skipped"))
    )
    agent._review_enabled = False

    result = agent.write_code(
        {
            "item_name": "TestWand",
            "display_name": "Test Wand",
            "sub_type": "Wand",
            "stats": {
                "damage": 20,
                "knockback": 4.5,
                "use_time": 22,
                "rarity": "ItemRarityID.Orange",
            },
            "mechanics": {
                "crafting_material": "ItemID.Bone",
                "crafting_cost": 15,
                "crafting_tile": "TileID.Anvils",
                "shoot_projectile": "ProjectileID.MagicMissile",
            },
        }
    )

    assert result["status"] == "success"
    agent._reviewer.review.assert_not_called()


def test_fix_code_validates_hitbox_when_manifest_is_provided() -> None:
    agent = CoderAgent.__new__(CoderAgent)
    mismatched_code = """
using Terraria;
using Terraria.ID;
using Terraria.ModLoader;

public class StormBrand : ModItem
{
    public override void SetDefaults()
    {
        Item.damage = 10;
    }
}

public class StormBrandProjectile : ModProjectile
{
    public override void SetDefaults()
    {
        Projectile.width = 10;
        Projectile.height = 10;
    }
}
"""
    agent._repair_chain = MagicMock(invoke=MagicMock(return_value=mismatched_code))

    result = agent.fix_code(
        error_log="error CS0103: missing name",
        original_code="broken",
        manifest={"projectile_visuals": {"hitbox_size": [16, 20]}},
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "CS0103"
