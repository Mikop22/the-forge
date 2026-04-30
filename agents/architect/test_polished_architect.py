import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import orchestrator
from architect import prompts as architect_prompts
from architect.models import ItemManifest


class PromptRoutingTests(unittest.TestCase):
    def test_build_prompt_routes_by_content_type(self) -> None:
        with mock.patch.object(architect_prompts, "build_weapon_prompt", return_value="weapon_prompt") as weapon, \
             mock.patch.object(architect_prompts, "build_accessory_prompt", return_value="accessory_prompt") as accessory, \
             mock.patch.object(architect_prompts, "build_summon_prompt", return_value="summon_prompt") as summon, \
             mock.patch.object(architect_prompts, "build_consumable_prompt", return_value="consumable_prompt") as consumable, \
             mock.patch.object(architect_prompts, "build_tool_prompt", return_value="tool_prompt") as tool:
            self.assertEqual(architect_prompts.build_prompt("Weapon", "Sword"), "weapon_prompt")
            self.assertEqual(architect_prompts.build_prompt("Accessory", "Charm"), "accessory_prompt")
            self.assertEqual(architect_prompts.build_prompt("Summon", "Minion Staff"), "summon_prompt")
            self.assertEqual(architect_prompts.build_prompt("Consumable", "Potion"), "consumable_prompt")
            self.assertEqual(architect_prompts.build_prompt("Tool", "Pickaxe"), "tool_prompt")

            weapon.assert_called_once_with("Sword")
            accessory.assert_called_once_with("Charm")
            summon.assert_called_once_with("Minion Staff")
            consumable.assert_called_once_with("Potion")
            tool.assert_called_once_with("Pickaxe")


class ArchitectManifestTests(unittest.TestCase):
    def test_generate_manifest_accepts_content_type_and_sub_type(self) -> None:
        class FakePrompt:
            def __or__(self, other):
                return FakeChain()

        class FakeChain:
            def invoke(self, payload):
                return mock.Mock(
                    model_dump=lambda: {
                        "item_name": "FrostCharm",
                        "display_name": "Frost Charm",
                        "tooltip": "A chilly trinket.",
                        "content_type": payload["content_type"],
                        "type": "Weapon",
                        "sub_type": payload["sub_type"],
                        "stats": {
                            "damage": 10,
                            "knockback": 0.0,
                            "crit_chance": 4,
                            "use_time": 20,
                            "auto_reuse": True,
                            "rarity": "ItemRarityID.White",
                        },
                        "visuals": {},
                        "mechanics": {
                            "shoot_projectile": "ProjectileID.Bullet",
                            "crafting_material": "ItemID.IceBlock",
                            "crafting_cost": 5,
                            "crafting_tile": "TileID.WorkBenches",
                        },
                        "generation_mode": "text_to_image",
                        "reference_needed": False,
                        "reference_subject": None,
                        "reference_image_url": None,
                        "reference_attempts": 0,
                        "reference_notes": None,
                    }
                )

        class FakeLLM:
            def with_structured_output(self, model):
                return self

        with mock.patch.object(architect_prompts, "build_prompt", return_value=FakePrompt()), \
             mock.patch("architect.architect.ChatOpenAI", return_value=FakeLLM()), \
             mock.patch("architect.architect.BrowserReferenceFinder", autospec=True), \
             mock.patch("architect.architect.HybridReferenceApprover", autospec=True), \
             mock.patch("architect.architect.ReferencePolicy", autospec=True) as reference_policy_cls:
            reference_policy_cls.return_value.resolve.return_value = {}
            from architect.architect import ArchitectAgent

            agent = ArchitectAgent(model_name="test-model")
            manifest = agent.generate_manifest(
                prompt="A frost charm",
                tier="Tier1_Starter",
                content_type="Accessory",
                sub_type="Charm",
            )

        self.assertEqual(manifest["content_type"], "Accessory")
        self.assertEqual(manifest["sub_type"], "Charm")

    def test_finalize_manifest_default_custom_projectile_from_llm_unset(self) -> None:
        """`model_dump` with no combat_package + ranged + direct: pipeline turns on
        custom_projectile and seeds projectile_visuals (matches LLM `None` fields)."""
        base = {
            "item_name": "VoidSidearm",
            "display_name": "Void Sidearm",
            "tooltip": "Fires void splinters.",
            "content_type": "Weapon",
            "type": "Weapon",
            "sub_type": "Pistol",
            "stats": {
                "damage": 12,
                "knockback": 2.0,
                "crit_chance": 4,
                "use_time": 18,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Green",
            },
            "visuals": {"description": "Compact obsidian frame with purple glow."},
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": None,
                "shoot_projectile": None,
                "crafting_material": "ItemID.Wood",
                "crafting_cost": 5,
                "crafting_tile": "TileID.WorkBenches",
            },
            "reference_needed": False,
        }
        with mock.patch("architect.architect.ReferencePolicy", autospec=True) as reference_policy_cls:
            reference_policy_cls.return_value.resolve.return_value = {}
            from architect.architect import ArchitectAgent

            agent = ArchitectAgent(model_name="test-model")
            out = agent._finalize_manifest_data(
                base,
                prompt="a void pistol with purple shards",
                tier="Tier1_Starter",
                content_type="Weapon",
                sub_type="Pistol",
            )
        self.assertIs(out["mechanics"].get("custom_projectile"), True)
        self.assertIsNone(out["mechanics"].get("shoot_projectile"))
        pv = out.get("projectile_visuals") or {}
        self.assertTrue(str(pv.get("description", "")).strip())

    def test_finalize_manifest_reference_policy_uses_raw_prompt_terms(self) -> None:
        seen = {}

        class FakePolicy:
            def resolve(self, **kwargs):
                seen.update(kwargs)
                return {}

        from architect.architect import ArchitectAgent

        agent = ArchitectAgent.__new__(ArchitectAgent)
        agent._reference_policy = FakePolicy()
        base = {
            "item_name": "VoidTestStaff",
            "display_name": "Void Test Staff",
            "tooltip": "Channels a violet singularity.",
            "content_type": "Weapon",
            "type": "Weapon",
            "sub_type": "Staff",
            "stats": {
                "damage": 58,
                "knockback": 5.0,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Pink",
            },
            "visuals": {"description": "forbidden staff"},
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": True,
                "shoot_projectile": None,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 12,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {
                "description": "violet singularity",
                "icon_size": [20, 20],
            },
            "reference_needed": True,
        }

        agent._finalize_manifest_data(
            base,
            prompt="a forbidden staff that charges a slow black-violet singularity",
            tier="Tier3_Hardmode",
            content_type="Weapon",
            sub_type="Staff",
            raw_prompt="a staff that shoots gojo's hollow purple from jjk",
            protected_reference_terms=["gojo", "hollow purple", "jjk"],
            reference_subject="Gojo Hollow Purple from JJK",
        )

        self.assertIn("gojo", seen["prompt"])
        self.assertIn("hollow purple", seen["prompt"])
        self.assertEqual(seen["reference_subject"], "Gojo Hollow Purple from JJK")

    def test_finalize_manifest_reference_subject_forces_reference_resolution(self) -> None:
        seen = {}

        class FakePolicy:
            def resolve(self, **kwargs):
                seen.update(kwargs)
                return {}

        from architect.architect import ArchitectAgent

        agent = ArchitectAgent.__new__(ArchitectAgent)
        agent._reference_policy = FakePolicy()
        base = {
            "item_name": "VoidTestStaff",
            "display_name": "Void Test Staff",
            "tooltip": "Channels a violet singularity.",
            "content_type": "Weapon",
            "type": "Weapon",
            "sub_type": "Staff",
            "stats": {
                "damage": 58,
                "knockback": 5.0,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Pink",
            },
            "visuals": {"description": "forbidden staff"},
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": True,
                "shoot_projectile": None,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 12,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {
                "description": "violet singularity",
                "icon_size": [20, 20],
            },
            "reference_needed": False,
        }

        agent._finalize_manifest_data(
            base,
            prompt="a forbidden staff that charges a slow black-violet singularity",
            tier="Tier3_Hardmode",
            content_type="Weapon",
            sub_type="Staff",
            raw_prompt="a staff that shoots gojo's hollow purple from jjk",
            protected_reference_terms=["gojo", "hollow purple", "jjk"],
            reference_subject="Gojo Hollow Purple from JJK",
        )

        self.assertIs(seen["reference_needed"], True)
        self.assertEqual(seen["reference_subject"], "Gojo Hollow Purple from JJK")

    def test_finalize_manifest_resolves_projectile_slot_reference(self) -> None:
        calls = []

        class FakePolicy:
            def resolve(self, **kwargs):
                calls.append(kwargs)
                return {
                    "reference_needed": True,
                    "reference_subject": kwargs["reference_subject"],
                    "reference_image_url": "https://example.test/hollow-purple.png",
                    "generation_mode": "image_to_image",
                    "reference_attempts": 1,
                    "reference_notes": "approved",
                }

        from architect.architect import ArchitectAgent
        from architect.prompt_director import ReferenceSlotIntent, ReferenceSlotsIntent

        agent = ArchitectAgent.__new__(ArchitectAgent)
        agent._reference_policy = FakePolicy()
        base = {
            "item_name": "VoidTestStaff",
            "display_name": "Void Test Staff",
            "tooltip": "Channels a violet singularity.",
            "content_type": "Weapon",
            "type": "Weapon",
            "sub_type": "Staff",
            "stats": {
                "damage": 58,
                "knockback": 5.0,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Pink",
            },
            "visuals": {"description": "forbidden staff"},
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": True,
                "shoot_projectile": None,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 12,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {
                "description": "violet singularity",
                "icon_size": [20, 20],
            },
            "reference_needed": False,
        }

        out = agent._finalize_manifest_data(
            base,
            prompt="a forbidden staff that charges a slow black-violet singularity",
            tier="Tier3_Hardmode",
            content_type="Weapon",
            sub_type="Staff",
            raw_prompt="a staff that shoots gojo's hollow purple from jjk",
            protected_reference_terms=["gojo", "hollow purple", "jjk"],
            reference_slots=ReferenceSlotsIntent(
                projectile=ReferenceSlotIntent(
                    subject="Gojo Hollow Purple from JJK",
                    protected_terms=["gojo", "hollow purple", "jjk"],
                )
            ),
        )

        projectile_ref = out["references"]["projectile"]
        self.assertIs(projectile_ref["needed"], True)
        self.assertEqual(projectile_ref["subject"], "Gojo Hollow Purple from JJK")
        self.assertEqual(
            projectile_ref["image_url"], "https://example.test/hollow-purple.png"
        )
        self.assertEqual(projectile_ref["generation_mode"], "image_to_image")
        self.assertTrue(calls)
        self.assertEqual(len(calls), 1)
        self.assertNotIn(
            "Gojo Hollow Purple",
            out["visuals"]["description"],
        )
        self.assertIn(
            "Gojo Hollow Purple",
            out["projectile_visuals"]["description"],
        )

    def test_finalize_manifest_seeds_tier3_spectacle_plan_for_direct_ranged(self) -> None:
        base = {
            "item_name": "VoidVioletPistol",
            "display_name": "Void Violet",
            "tooltip": "Fires a compressed violet annihilation round.",
            "content_type": "Weapon",
            "type": "Weapon",
            "sub_type": "Pistol",
            "stats": {
                "damage": 34,
                "knockback": 4.5,
                "crit_chance": 4,
                "use_time": 22,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Orange",
            },
            "visuals": {"description": "Black pistol with a violet core."},
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": None,
                "shoot_projectile": None,
                "crafting_material": "ItemID.Bone",
                "crafting_cost": 15,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {
                "description": "small violet projectile",
                "animation_tier": "static",
            },
            "reference_needed": False,
        }
        with mock.patch("architect.architect.ReferencePolicy", autospec=True) as reference_policy_cls:
            reference_policy_cls.return_value.resolve.return_value = {}
            from architect.architect import ArchitectAgent

            agent = ArchitectAgent(model_name="test-model")
            out = agent._finalize_manifest_data(
                base,
                prompt="a black pistol that shoots gojo's hollow purple",
                tier="Tier3_Hardmode",
                content_type="Weapon",
                sub_type="Pistol",
            )

        plan = out.get("spectacle_plan") or {}
        self.assertIn("violet", plan.get("fantasy", "").lower())
        self.assertGreaterEqual(len(plan.get("render_passes", [])), 3)
        self.assertIn("bullet", plan.get("must_not_feel_like", []))

    def test_item_manifest_validates_buff_and_ammo_ids(self) -> None:
        manifest = ItemManifest.model_validate({
            "item_name": "FrostCharm",
            "display_name": "Frost Charm",
            "tooltip": "A chilly trinket.",
            "content_type": "Accessory",
            "type": "Weapon",
            "sub_type": "Charm",
            "stats": {
                "damage": 10,
                "knockback": 0.0,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.White",
            },
            "visuals": {},
            "mechanics": {
                "crafting_material": "ItemID.IceBlock",
                "crafting_cost": 5,
                "crafting_tile": "TileID.WorkBenches",
                "buff_id": "BuffID.WellFed",
                "ammo_id": "AmmoID.Arrow",
            },
        })

        self.assertEqual(manifest.mechanics.buff_id, "BuffID.WellFed")
        self.assertEqual(manifest.mechanics.ammo_id, "AmmoID.Arrow")

        bad_manifest = ItemManifest.model_validate({
            "item_name": "BadCharm",
            "display_name": "Bad Charm",
            "tooltip": "Broken.",
            "content_type": "Accessory",
            "type": "Weapon",
            "sub_type": "Charm",
            "stats": {
                "damage": 10,
                "knockback": 0.0,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.White",
            },
            "visuals": {},
            "mechanics": {
                "crafting_material": "ItemID.IceBlock",
                "crafting_cost": 5,
                "crafting_tile": "TileID.WorkBenches",
                "buff_id": "BuffID.NotReal",
                "ammo_id": "AmmoID.Arrow",
            },
        })
        self.assertIsNone(bad_manifest.mechanics.buff_id)

    def test_item_manifest_normalizes_projectile_aliases(self) -> None:
        manifest = ItemManifest.model_validate({
            "item_name": "CinderBrand",
            "display_name": "Cinder Brand",
            "tooltip": "A fiery sword.",
            "content_type": "Weapon",
            "type": "Weapon",
            "sub_type": "Sword",
            "stats": {
                "damage": 34,
                "knockback": 5.5,
                "crit_chance": 4,
                "use_time": 22,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Orange",
            },
            "visuals": {},
            "mechanics": {
                "shoot_projectile": "ProjectileID.Fireball",
                "on_hit_buff": "BuffID.OnFire",
                "crafting_material": "ItemID.HellstoneBar",
                "crafting_cost": 15,
                "crafting_tile": "TileID.Anvils",
            },
        })

        self.assertEqual(manifest.mechanics.shoot_projectile, "ProjectileID.BallofFire")

    def test_llm_returning_sword_does_not_override_orchestrator_gun_sub_type(self) -> None:
        """Regression: LLM's Sword default must not win over orchestrator-inferred Gun."""
        class FakePrompt:
            def __or__(self, other):
                return FakeChain()

        class FakeChain:
            def invoke(self, payload):
                # Simulate the biased LLM always returning "Sword"
                return mock.Mock(
                    model_dump=lambda: {
                        "item_name": "Frostgun",
                        "display_name": "Frostgun",
                        "tooltip": "Fires frost bullets.",
                        "content_type": "Weapon",
                        "type": "Weapon",
                        "sub_type": "Sword",
                        "stats": {
                            "damage": 15,
                            "knockback": 3.0,
                            "crit_chance": 4,
                            "use_time": 20,
                            "auto_reuse": True,
                            "rarity": "ItemRarityID.White",
                        },
                        "visuals": {},
                        "mechanics": {
                            "shoot_projectile": "ProjectileID.Bullet",
                            "crafting_material": "ItemID.IceBlock",
                            "crafting_cost": 5,
                            "crafting_tile": "TileID.WorkBenches",
                        },
                        "generation_mode": "text_to_image",
                        "reference_needed": False,
                        "reference_subject": None,
                        "reference_image_url": None,
                        "reference_attempts": 0,
                        "reference_notes": None,
                    }
                )

        class FakeLLM:
            def with_structured_output(self, model):
                return self

        with mock.patch.object(architect_prompts, "build_prompt", return_value=FakePrompt()), \
             mock.patch("architect.architect.ChatOpenAI", return_value=FakeLLM()), \
             mock.patch("architect.architect.BrowserReferenceFinder", autospec=True), \
             mock.patch("architect.architect.HybridReferenceApprover", autospec=True), \
             mock.patch("architect.architect.ReferencePolicy", autospec=True) as reference_policy_cls:
            reference_policy_cls.return_value.resolve.return_value = {}
            from architect.architect import ArchitectAgent

            agent = ArchitectAgent(model_name="test-model")
            manifest = agent.generate_manifest(
                prompt="a frostgun that fires ice bullets",
                tier="Tier1_Starter",
                content_type="Weapon",
                sub_type="Gun",  # orchestrator-resolved
            )

        self.assertEqual(manifest["sub_type"], "Gun")


class OrchestratorRequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_pipeline_forwards_content_type_and_sub_type(self) -> None:
        request = {
            "prompt": "A frost charm",
            "tier": "Tier1_Starter",
            "content_type": "Accessory",
            "sub_type": "Charm",
        }

        class FakeArchitect:
            def __init__(self):
                self.calls = []

            def generate_manifest(self, **kwargs):
                self.calls.append(kwargs)
                return {
                    "item_name": "FrostCharm",
                    "display_name": "Frost Charm",
                    "tooltip": "A chilly trinket.",
                    "content_type": kwargs["content_type"],
                    "type": "Weapon",
                    "sub_type": kwargs["sub_type"],
                    "stats": {
                        "damage": 10,
                        "knockback": 0.0,
                        "crit_chance": 4,
                        "use_time": 20,
                        "auto_reuse": True,
                        "rarity": "ItemRarityID.White",
                    },
                    "visuals": {},
                    "mechanics": {
                        "crafting_material": "ItemID.IceBlock",
                        "crafting_cost": 5,
                        "crafting_tile": "TileID.WorkBenches",
                    },
                }

        class FakeCoder:
            def write_code(self, manifest):
                return {"status": "success", "cs_code": "", "hjson_code": ""}

        class FakeArtist:
            def __init__(self, output_dir):
                self.output_dir = output_dir

            def generate_asset(self, manifest):
                return {"status": "success", "item_sprite_path": "/tmp/item.png"}

        class FakeIntegrator:
            def __init__(self, coder):
                self.coder = coder

            def build_and_verify(self, **kwargs):
                return {"status": "success", "item_name": kwargs["forge_output"].get("item_name", "FrostCharm")}

        fake_architect = FakeArchitect()

        with TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "generation_status.json"
            with mock.patch.object(orchestrator, "STATUS_FILE", status_file), \
                 mock.patch.object(orchestrator, "_import_agents", return_value=(lambda: fake_architect, FakeCoder, FakeArtist, FakeIntegrator)):
                await orchestrator.run_pipeline(request)

        self.assertEqual(fake_architect.calls[0]["content_type"], "Accessory")
        self.assertEqual(fake_architect.calls[0]["sub_type"], "Charm")

    async def test_run_instant_pipeline_reuses_existing_manifest_and_feedback(self) -> None:
        request = {
            "mode": "instant",
            "prompt": "A frost charm",
            "tier": "Tier1_Starter",
            "content_type": "Accessory",
            "sub_type": "Charm",
            "existing_manifest": {
                "item_name": "FrostCharm",
                "display_name": "Frost Charm",
                "tooltip": "A chilly trinket.",
                "content_type": "Accessory",
                "type": "Weapon",
                "sub_type": "Charm",
                "stats": {
                    "damage": 10,
                    "knockback": 0.0,
                    "crit_chance": 4,
                    "use_time": 20,
                    "auto_reuse": True,
                    "rarity": "ItemRarityID.White",
                },
                "visuals": {
                    "description": "A simple ice charm.",
                },
                "mechanics": {
                    "crafting_material": "ItemID.IceBlock",
                    "crafting_cost": 5,
                    "crafting_tile": "TileID.WorkBenches",
                },
            },
            "art_feedback": "Make the charm glow brighter and feel more crystalline.",
        }

        class FakeArchitect:
            def __init__(self):
                self.called = False

            def generate_manifest(self, **kwargs):
                self.called = True
                return {}

        class FakeArtist:
            def __init__(self, output_dir):
                self.output_dir = output_dir
                self.received_manifest = None

            def generate_asset(self, manifest):
                self.received_manifest = manifest
                return {"status": "success", "item_sprite_path": "/tmp/item.png"}

        fake_architect = FakeArchitect()
        captured_artist = {}

        class CapturingArtist(FakeArtist):
            def __init__(self, output_dir):
                super().__init__(output_dir)
                captured_artist["instance"] = self

        class FakeLoop:
            async def run_in_executor(self, executor, fn, manifest):
                return fn(manifest)

        with TemporaryDirectory() as tmpdir:
            status_file = Path(tmpdir) / "generation_status.json"
            with mock.patch.object(orchestrator, "STATUS_FILE", status_file), \
                 mock.patch.object(orchestrator, "_import_instant_agents", return_value=(lambda: fake_architect, CapturingArtist)), \
                 mock.patch.object(orchestrator.asyncio, "get_running_loop", return_value=FakeLoop()):
                await orchestrator.run_instant_pipeline(request)

        self.assertFalse(fake_architect.called)
        self.assertIn("instance", captured_artist)
        self.assertIn("glow brighter", captured_artist["instance"].received_manifest["visuals"]["description"])
        self.assertIn("more crystalline", captured_artist["instance"].received_manifest["visuals"]["description"])
