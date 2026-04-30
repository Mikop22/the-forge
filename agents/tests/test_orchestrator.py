import asyncio
import json
import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from watchdog.events import FileCreatedEvent, FileMovedEvent

from core import atomic_io
import orchestrator


class ProcessStatAliveTests(unittest.TestCase):
    def test_rejects_zombie_state(self) -> None:
        self.assertFalse(orchestrator._process_stat_alive("Z+"))
        self.assertTrue(orchestrator._process_stat_alive("S+"))


class RunSafeValidationTests(unittest.TestCase):
    def test_invalid_mode_does_not_run_pipeline(self) -> None:
        loop = asyncio.new_event_loop()
        handler = orchestrator._RequestHandler(loop)
        try:

            async def run() -> None:
                with mock.patch.object(orchestrator, "run_pipeline") as rp:
                    with mock.patch.object(orchestrator, "run_instant_pipeline") as rip:
                        with mock.patch.object(orchestrator, "_set_error") as se:
                            await handler._run_safe(Path("/tmp/user_request.json"), {"prompt": "x", "mode": "bogus"})
                            rp.assert_not_called()
                            rip.assert_not_called()
                            se.assert_called_once()

            loop.run_until_complete(run())
        finally:
            loop.close()


class RequestHandlerEventTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loop = asyncio.new_event_loop()
        self.handler = orchestrator._RequestHandler(self.loop)

    def tearDown(self) -> None:
        self.loop.close()

    def test_created_request_file_triggers_pipeline(self) -> None:
        with TemporaryDirectory() as tmpdir:
            request_file = (Path(tmpdir) / "user_request.json").resolve()
            request_file.write_text(json.dumps({"prompt": "Blade"}), encoding="utf-8")

            with mock.patch.object(orchestrator, "REQUEST_FILE", request_file), \
                 mock.patch.object(orchestrator.asyncio, "run_coroutine_threadsafe") as runner:
                key = str(request_file.resolve())
                self.handler._last_trigger = {key: time.monotonic() - 2.0}
                self.handler.on_created(FileCreatedEvent(str(request_file)))

            self.assertEqual(runner.call_count, 1)
            runner.call_args.args[0].close()

    def test_moved_request_file_triggers_pipeline(self) -> None:
        with TemporaryDirectory() as tmpdir:
            request_file = (Path(tmpdir) / "user_request.json").resolve()
            request_file.write_text(json.dumps({"prompt": "Blade"}), encoding="utf-8")
            tmp_request = request_file.with_suffix(".tmp")
            tmp_request.write_text(json.dumps({"prompt": "Blade"}), encoding="utf-8")

            with mock.patch.object(orchestrator, "REQUEST_FILE", request_file), \
                 mock.patch.object(orchestrator.asyncio, "run_coroutine_threadsafe") as runner:
                key = str(request_file.resolve())
                self.handler._last_trigger = {key: time.monotonic() - 2.0}
                self.handler.on_moved(FileMovedEvent(str(tmp_request), str(request_file)))

            self.assertEqual(runner.call_count, 1)
            runner.call_args.args[0].close()


class StatusWriterTests(unittest.TestCase):
    def test_write_status_retries_transient_replace_race(self) -> None:
        with TemporaryDirectory() as tmpdir:
            status_file = (Path(tmpdir) / "generation_status.json").resolve()
            original_os_replace = os.replace
            attempts = {"count": 0}

            def flaky_os_replace(src, dst):
                dst_s = os.path.realpath(os.fspath(dst))
                target_s = os.path.realpath(os.fspath(status_file))
                if dst_s == target_s and "generation_status." in os.fspath(src):
                    attempts["count"] += 1
                    if attempts["count"] < 4:
                        raise FileNotFoundError("simulated ModSources race")
                return original_os_replace(src, dst)

            with mock.patch.object(orchestrator, "STATUS_FILE", status_file), \
                 mock.patch.object(atomic_io.os, "replace", new=flaky_os_replace), \
                 mock.patch.object(atomic_io.time, "sleep", return_value=None):
                orchestrator._write_status({"status": "building"})

            self.assertEqual(attempts["count"], 4)
            payload = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "building")


class RequestSubTypeInferenceTests(unittest.TestCase):
    """Keyword inference for weapon sub_type when the TUI sends it empty."""

    def test_explicit_sub_type_passes_through_unchanged(self) -> None:
        req = {"prompt": "frostgun", "content_type": "Weapon", "sub_type": "Staff"}
        self.assertEqual(orchestrator._request_sub_type(req), "Staff")

    def test_frostgun_prompt_infers_gun(self) -> None:
        req = {"prompt": "frostgun", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Gun")

    def test_ice_bow_prompt_infers_bow(self) -> None:
        req = {"prompt": "icy elven bow", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Bow")

    def test_obsidian_pickaxe_prompt_infers_pickaxe(self) -> None:
        # "pickaxe" must win over the "axe" substring inside it.
        req = {"prompt": "obsidian pickaxe", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Pickaxe")

    def test_shotgun_prompt_infers_shotgun_not_gun(self) -> None:
        req = {"prompt": "blizzard shotgun", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Shotgun")

    def test_broadsword_prompt_infers_broadsword_not_sword(self) -> None:
        req = {"prompt": "ancient broadsword of dawn", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Broadsword")

    def test_case_insensitive(self) -> None:
        req = {"prompt": "FROSTGUN", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Gun")

    def test_ambiguous_prompt_falls_back_to_sword(self) -> None:
        # No recognizable weapon noun — preserve current default behavior.
        req = {"prompt": "radiant moonlight artifact", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Sword")

    def test_empty_prompt_falls_back_to_sword(self) -> None:
        req = {"prompt": "", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Sword")

    def test_multi_keyword_prompt_resolves_by_registry_order(self) -> None:
        # "bladed spear" contains both "blade" (→ Sword, low priority) and
        # "spear" (→ Spear, higher priority). Pins the ordering contract so
        # future edits to _WEAPON_SUBTYPE_KEYWORDS can't silently flip precedence.
        req = {"prompt": "bladed spear", "content_type": "Weapon"}
        self.assertEqual(orchestrator._request_sub_type(req), "Spear")

    def test_inference_skipped_for_non_weapon_content_type(self) -> None:
        # Tool/Accessory/etc. have their own DEFAULT_SUB_TYPES downstream in
        # architect.prompts. Orchestrator must not stamp "Gun" on a Tool request
        # just because the prompt contains "gun".
        req = {"prompt": "frostgun", "content_type": "Tool"}
        self.assertEqual(orchestrator._request_sub_type(req), "")


class RequestContentTypeInferenceTests(unittest.TestCase):
    def test_explicit_weapon_pickaxe_prompt_remains_weapon(self) -> None:
        req = {
            "prompt": "obsidian pickaxe with magma cracks",
            "content_type": "Weapon",
            "content_type_explicit": True,
        }
        self.assertEqual(orchestrator._request_content_type_inferred(req), "Weapon")

    def test_non_explicit_weapon_pickaxe_prompt_routes_to_tool(self) -> None:
        req = {
            "prompt": "obsidian pickaxe with magma cracks",
            "content_type": "Weapon",
            "content_type_explicit": False,
        }
        self.assertEqual(orchestrator._request_content_type_inferred(req), "Tool")

    def test_non_explicit_weapon_sword_prompt_remains_weapon(self) -> None:
        req = {
            "prompt": "obsidian sword with magma cracks",
            "content_type": "Weapon",
            "content_type_explicit": False,
        }
        self.assertEqual(orchestrator._request_content_type_inferred(req), "Weapon")


class PipelineHitboxContractTests(unittest.TestCase):
    def test_pipeline_uses_enhanced_prompt_but_preserves_raw_prompt(self) -> None:
        class FakeArchitect:
            seen_kwargs = None

            def generate_manifest(self, **kwargs):
                FakeArchitect.seen_kwargs = kwargs
                return {
                    "item_name": "VoidTestStaff",
                    "display_name": "Void Test Staff",
                    "tooltip": "",
                    "type": "Weapon",
                    "sub_type": "Staff",
                    "stats": {
                        "damage": 10,
                        "knockback": 1.0,
                        "crit_chance": 4,
                        "use_time": 20,
                        "auto_reuse": True,
                        "rarity": "ItemRarityID.White",
                    },
                    "visuals": {"description": "void staff"},
                    "mechanics": {
                        "crafting_material": "ItemID.Wood",
                        "crafting_cost": 1,
                        "crafting_tile": "TileID.WorkBenches",
                        "custom_projectile": True,
                    },
                    "projectile_visuals": {
                        "description": "violet singularity",
                        "icon_size": [16, 16],
                    },
                }

        class FakeCoder:
            def write_code(self, manifest):
                return {
                    "status": "success",
                    "item_name": manifest["item_name"],
                    "cs_code": "public class VoidTestStaff : ModItem { }",
                    "hjson_code": "",
                }

        class FakeArtist:
            def __init__(self, output_dir):
                self.output_dir = output_dir

            def generate_asset(self, manifest):
                return {
                    "status": "success",
                    "item_sprite_path": "/tmp/VoidTestStaff.png",
                    "projectile_sprite_path": "/tmp/VoidTestStaffProjectile.png",
                    "projectile_foreground_bbox": [4, 4, 11, 11],
                }

        class FakeIntegrator:
            def __init__(self, coder):
                self.coder = coder

            def build_and_verify(self, **kwargs):
                return {"status": "success", "item_name": "VoidTestStaff"}

        async def run() -> None:
            with TemporaryDirectory() as tmpdir:
                status_file = Path(tmpdir) / "generation_status.json"
                with mock.patch.object(orchestrator, "STATUS_FILE", status_file):
                    with mock.patch.object(
                        orchestrator,
                        "_import_agents",
                        return_value=(
                            FakeArchitect,
                            FakeCoder,
                            FakeArtist,
                            FakeIntegrator,
                        ),
                    ):
                        await orchestrator.run_pipeline(
                            {
                                "prompt": "a staff that shoots gojo's hollow purple from jjk",
                                "tier": "Tier3_Hardmode",
                            }
                        )

        asyncio.run(run())

        assert FakeArchitect.seen_kwargs is not None
        self.assertIn("singularity", FakeArchitect.seen_kwargs["prompt"])
        self.assertEqual(
            FakeArchitect.seen_kwargs["raw_prompt"],
            "a staff that shoots gojo's hollow purple from jjk",
        )
        self.assertEqual(
            FakeArchitect.seen_kwargs["protected_reference_terms"],
            ["gojo", "hollow purple", "jjk"],
        )

    def test_pipeline_passes_projectile_bbox_hitbox_to_codegen(self) -> None:
        class FakeArchitect:
            def generate_manifest(self, **_: object):
                return {
                    "item_name": "StormBrand",
                    "display_name": "Storm Brand",
                    "tooltip": "",
                    "type": "Weapon",
                    "sub_type": "Staff",
                    "stats": {
                        "damage": 10,
                        "knockback": 1.0,
                        "crit_chance": 4,
                        "use_time": 20,
                        "auto_reuse": True,
                        "rarity": "ItemRarityID.White",
                    },
                    "visuals": {"description": "storm staff"},
                    "mechanics": {
                        "crafting_material": "ItemID.Wood",
                        "crafting_cost": 1,
                        "crafting_tile": "TileID.WorkBenches",
                        "custom_projectile": True,
                    },
                    "projectile_visuals": {
                        "description": "wide storm cat",
                        "icon_size": [64, 40],
                    },
                }

        class FakeCoder:
            seen_manifest = None

            def write_code(self, manifest):
                FakeCoder.seen_manifest = manifest
                return {
                    "status": "success",
                    "item_name": manifest["item_name"],
                    "cs_code": "public class StormBrand : ModItem { }",
                    "hjson_code": "",
                }

        class FakeArtist:
            def __init__(self, output_dir):
                self.output_dir = output_dir

            def generate_asset(self, manifest):
                return {
                    "status": "success",
                    "item_sprite_path": "/tmp/StormBrand.png",
                    "projectile_sprite_path": "/tmp/StormBrandProjectile.png",
                    "projectile_foreground_bbox": [8, 6, 23, 25],
                }

        class FakeIntegrator:
            def __init__(self, coder):
                self.coder = coder

            def build_and_verify(self, **kwargs):
                return {"status": "success", "item_name": "StormBrand"}

        async def run() -> None:
            with TemporaryDirectory() as tmpdir:
                status_file = Path(tmpdir) / "generation_status.json"
                with mock.patch.object(orchestrator, "STATUS_FILE", status_file):
                    with mock.patch.object(
                        orchestrator,
                        "_import_agents",
                        return_value=(
                            FakeArchitect,
                            FakeCoder,
                            FakeArtist,
                            FakeIntegrator,
                        ),
                    ):
                        await orchestrator.run_pipeline({"prompt": "storm brand"})

        asyncio.run(run())

        projectile_visuals = FakeCoder.seen_manifest["projectile_visuals"]
        self.assertEqual(projectile_visuals["foreground_bbox"], [8, 6, 23, 25])
        self.assertEqual(projectile_visuals["hitbox_size"], [16, 20])

    def test_hidden_pipeline_derives_projectile_hitbox_from_winner_sprite(
        self,
    ) -> None:
        from PIL import Image, ImageDraw

        class FakeArchitect:
            def generate_thesis_finalists(self, **_: object):
                return type(
                    "FinalistBundle",
                    (),
                    {"finalists": []},
                )()

        class FakeCoder:
            seen_manifest = None

            def write_code(self, manifest):
                FakeCoder.seen_manifest = manifest
                return {
                    "status": "success",
                    "item_name": manifest["item_name"],
                    "cs_code": "public class StormBrand : ModItem { }",
                    "hjson_code": "",
                }

        class FakeArtist:
            def __init__(self, output_dir):
                self.output_dir = output_dir

        class FakeIntegrator:
            def __init__(self, coder):
                self.coder = coder

            def build_and_verify(self, **kwargs):
                return {"status": "success", "item_name": "StormBrand"}

        async def run() -> None:
            with TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                status_file = tmp / "generation_status.json"
                item_path = tmp / "StormBrand.png"
                projectile_path = tmp / "StormBrandProjectile.png"

                item_image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
                ImageDraw.Draw(item_image).rectangle(
                    (8, 6, 23, 25), fill=(20, 20, 20, 255)
                )
                item_image.save(item_path)

                projectile_image = Image.new(
                    "RGBA", (32, 32), (255, 255, 255, 255)
                )
                ImageDraw.Draw(projectile_image).rectangle(
                    (5, 7, 20, 18), fill=(20, 20, 20, 255)
                )
                projectile_image.save(projectile_path)

                hidden_result = {
                    "winner": {
                        "candidate_id": "candidate-001",
                        "item_name": "StormBrand",
                        "manifest": {
                            "item_name": "StormBrand",
                            "display_name": "Storm Brand",
                            "tooltip": "",
                            "type": "Weapon",
                            "sub_type": "Staff",
                            "stats": {
                                "damage": 10,
                                "knockback": 1.0,
                                "crit_chance": 4,
                                "use_time": 20,
                                "auto_reuse": True,
                                "rarity": "ItemRarityID.White",
                            },
                            "visuals": {"description": "storm staff"},
                            "mechanics": {
                                "crafting_material": "ItemID.Wood",
                                "crafting_cost": 1,
                                "crafting_tile": "TileID.WorkBenches",
                                "custom_projectile": True,
                            },
                            "projectile_visuals": {
                                "description": "storm bolt",
                                "icon_size": [32, 32],
                            },
                        },
                        "item_sprite_path": str(item_path),
                        "projectile_sprite_path": str(projectile_path),
                    }
                }

                with mock.patch.object(orchestrator, "STATUS_FILE", status_file):
                    with mock.patch.object(
                        orchestrator,
                        "_import_agents",
                        return_value=(
                            FakeArchitect,
                            FakeCoder,
                            FakeArtist,
                            FakeIntegrator,
                        ),
                    ):
                        with mock.patch.object(
                            orchestrator,
                            "run_hidden_audition_pipeline",
                            return_value=hidden_result,
                        ):
                            await orchestrator.run_pipeline(
                                {"prompt": "storm brand", "hidden_audition": True}
                            )

        asyncio.run(run())

        projectile_visuals = FakeCoder.seen_manifest["projectile_visuals"]
        self.assertEqual(projectile_visuals["foreground_bbox"], [5, 7, 20, 18])
        self.assertEqual(projectile_visuals["hitbox_size"], [16, 12])

    def test_hidden_audition_preserves_raw_prompt_reference_metadata(self) -> None:
        class FakeFinalistBundle:
            finalists = ["finalist"]

        class FakeArchitect:
            seen_expand_kwargs = None

            def generate_thesis_finalists(self, **_: object):
                return FakeFinalistBundle()

            def expand_thesis_finalist_to_manifest(self, **kwargs):
                FakeArchitect.seen_expand_kwargs = kwargs
                return {
                    "item_name": "VoidHiddenStaff",
                    "display_name": "Void Hidden Staff",
                    "tooltip": "",
                    "type": "Weapon",
                    "sub_type": "Staff",
                    "stats": {
                        "damage": 10,
                        "knockback": 1.0,
                        "crit_chance": 4,
                        "use_time": 20,
                        "auto_reuse": True,
                        "rarity": "ItemRarityID.White",
                    },
                    "visuals": {"description": "void staff"},
                    "mechanics": {
                        "crafting_material": "ItemID.Wood",
                        "crafting_cost": 1,
                        "crafting_tile": "TileID.WorkBenches",
                        "custom_projectile": True,
                    },
                    "projectile_visuals": {
                        "description": "violet singularity",
                        "icon_size": [16, 16],
                    },
                }

        finalists = orchestrator._build_hidden_audition_finalists(
            architect=FakeArchitect(),
            prompt="a forbidden staff that charges a slow black-violet singularity",
            tier="Tier3_Hardmode",
            content_type="Weapon",
            sub_type="Staff",
            crafting_station=None,
            thesis_count=3,
            finalist_count=2,
            raw_prompt="a staff that shoots gojo's hollow purple from jjk",
            protected_reference_terms=["gojo", "hollow purple", "jjk"],
            reference_subject="Gojo Hollow Purple from JJK",
            reference_slots={"projectile": {"subject": "Gojo Hollow Purple from JJK"}},
        )

        self.assertEqual(len(finalists), 1)
        assert FakeArchitect.seen_expand_kwargs is not None
        self.assertEqual(
            FakeArchitect.seen_expand_kwargs["raw_prompt"],
            "a staff that shoots gojo's hollow purple from jjk",
        )
        self.assertEqual(
            FakeArchitect.seen_expand_kwargs["protected_reference_terms"],
            ["gojo", "hollow purple", "jjk"],
        )
        self.assertEqual(
            FakeArchitect.seen_expand_kwargs["reference_subject"],
            "Gojo Hollow Purple from JJK",
        )

    def test_manifest_bbox_fallback_uses_generated_animation_frame_not_full_sheet(
        self,
    ) -> None:
        from PIL import Image, ImageDraw

        with TemporaryDirectory() as tmpdir:
            sheet_path = Path(tmpdir) / "StormBrandProjectile.png"
            sheet = Image.new("RGBA", (16, 48), (255, 255, 255, 255))
            draw = ImageDraw.Draw(sheet)
            for offset in (0, 16, 32):
                draw.rectangle((4, 4 + offset, 11, 11 + offset), fill=(20, 20, 20, 255))
            sheet.save(sheet_path)

            manifest = {
                "item_name": "StormBrand",
                "projectile_visuals": {
                    "icon_size": [16, 16],
                    "animation_tier": "generated_frames:3",
                },
            }
            enriched = orchestrator._manifest_with_pixelsmith_bboxes(
                manifest,
                {
                    "status": "success",
                    "projectile_sprite_path": str(sheet_path),
                },
            )

        projectile_visuals = enriched["projectile_visuals"]
        self.assertEqual(projectile_visuals["foreground_bbox"], [4, 4, 11, 11])
        self.assertEqual(projectile_visuals["hitbox_size"], [8, 8])

    def test_projectile_only_pipeline_reuses_manifest_and_existing_item(self) -> None:
        class FakeArchitect:
            def generate_manifest(self, **_: object):
                raise AssertionError("scoped generation should reuse manifest")

        class FakeCoder:
            seen_manifest = None

            def write_code(self, manifest):
                FakeCoder.seen_manifest = manifest
                return {
                    "status": "success",
                    "item_name": manifest["item_name"],
                    "cs_code": "public class StormBrand : ModItem { }",
                    "hjson_code": "",
                }

        class FakeArtist:
            def __init__(self, output_dir):
                self.output_dir = output_dir

            def generate_scoped_asset(self, manifest, **kwargs):
                self.kwargs = kwargs
                return {
                    "status": "success",
                    "item_sprite_path": kwargs["existing_item_sprite_path"],
                    "projectile_sprite_path": "/tmp/new-projectile.png",
                    "projectile_foreground_bbox": [4, 4, 11, 11],
                }

        class FakeIntegrator:
            seen_kwargs = None

            def __init__(self, coder):
                self.coder = coder

            def build_and_verify(self, **kwargs):
                FakeIntegrator.seen_kwargs = kwargs
                return {"status": "success", "item_name": "StormBrand"}

        async def run() -> None:
            with TemporaryDirectory() as tmpdir:
                status_file = Path(tmpdir) / "generation_status.json"
                with mock.patch.object(orchestrator, "STATUS_FILE", status_file):
                    with mock.patch.object(
                        orchestrator,
                        "_import_agents",
                        return_value=(
                            FakeArchitect,
                            FakeCoder,
                            FakeArtist,
                            FakeIntegrator,
                        ),
                    ):
                        await orchestrator.run_pipeline(
                            {
                                "prompt": "storm brand",
                                "generation_scope": "projectile_only",
                                "existing_item_sprite_path": "/tmp/existing-item.png",
                                "existing_manifest": {
                                    "item_name": "StormBrand",
                                    "display_name": "Storm Brand",
                                    "visuals": {"description": "storm staff"},
                                    "mechanics": {
                                        "crafting_material": "ItemID.Wood",
                                        "crafting_cost": 1,
                                        "crafting_tile": "TileID.WorkBenches",
                                        "custom_projectile": True,
                                    },
                                    "projectile_visuals": {
                                        "description": "storm bolt",
                                        "icon_size": [16, 16],
                                    },
                                },
                            }
                        )

        asyncio.run(run())

        self.assertEqual(FakeCoder.seen_manifest["projectile_visuals"]["hitbox_size"], [8, 8])
        self.assertEqual(
            FakeIntegrator.seen_kwargs["sprite_path"], "/tmp/existing-item.png"
        )
        self.assertEqual(
            FakeIntegrator.seen_kwargs["projectile_sprite_path"],
            "/tmp/new-projectile.png",
        )

    def test_scoped_pipeline_accepts_existing_manifest_without_prompt(self) -> None:
        class FakeArchitect:
            def generate_manifest(self, **_: object):
                raise AssertionError("scoped generation should reuse manifest")

        class FakeCoder:
            def write_code(self, manifest):
                return {
                    "status": "success",
                    "item_name": manifest["item_name"],
                    "cs_code": "public class StormBrand : ModItem { }",
                    "hjson_code": "",
                }

        class FakeArtist:
            def __init__(self, output_dir):
                self.output_dir = output_dir

            def generate_scoped_asset(self, manifest, **kwargs):
                return {
                    "status": "success",
                    "item_sprite_path": kwargs["existing_item_sprite_path"],
                    "projectile_sprite_path": "/tmp/new-projectile.png",
                    "projectile_foreground_bbox": [4, 4, 11, 11],
                }

        class FakeIntegrator:
            def __init__(self, coder):
                self.coder = coder

            def build_and_verify(self, **kwargs):
                return {"status": "success", "item_name": "StormBrand"}

        async def run() -> None:
            with TemporaryDirectory() as tmpdir:
                status_file = Path(tmpdir) / "generation_status.json"
                with mock.patch.object(orchestrator, "STATUS_FILE", status_file):
                    with mock.patch.object(
                        orchestrator,
                        "_import_agents",
                        return_value=(
                            FakeArchitect,
                            FakeCoder,
                            FakeArtist,
                            FakeIntegrator,
                        ),
                    ):
                        await orchestrator.run_pipeline(
                            {
                                "generation_scope": "projectile_only",
                                "existing_item_sprite_path": "/tmp/existing-item.png",
                                "existing_manifest": {
                                    "item_name": "StormBrand",
                                    "display_name": "Storm Brand",
                                    "visuals": {"description": "storm staff"},
                                    "mechanics": {
                                        "crafting_material": "ItemID.Wood",
                                        "crafting_cost": 1,
                                        "crafting_tile": "TileID.WorkBenches",
                                        "custom_projectile": True,
                                    },
                                    "projectile_visuals": {
                                        "description": "storm bolt",
                                        "icon_size": [16, 16],
                                    },
                                },
                            }
                        )

        asyncio.run(run())

    def test_scoped_pipeline_validates_manifest_before_architect_init(self) -> None:
        class ExplodingArchitect:
            def __init__(self):
                raise AssertionError("Architect should not be constructed for invalid scoped request")

        class FakeCoder:
            pass

        class FakeArtist:
            pass

        class FakeIntegrator:
            pass

        async def run() -> None:
            with mock.patch.object(
                orchestrator,
                "_import_agents",
                return_value=(
                    ExplodingArchitect,
                    FakeCoder,
                    FakeArtist,
                    FakeIntegrator,
                ),
            ):
                with self.assertRaisesRegex(
                    ValueError, "Scoped generation requires existing_manifest"
                ):
                    await orchestrator.run_pipeline(
                        {
                            "generation_scope": "projectile_only",
                            "existing_item_sprite_path": "/tmp/existing-item.png",
                        }
                    )

        asyncio.run(run())

    def test_non_explicit_accessory_content_type_is_unchanged(self) -> None:
        req = {
            "prompt": "obsidian pickaxe charm",
            "content_type": "Accessory",
            "content_type_explicit": False,
        }
        self.assertEqual(orchestrator._request_content_type_inferred(req), "Accessory")

    def test_explicit_tool_content_type_remains_tool(self) -> None:
        req = {
            "prompt": "obsidian pickaxe with magma cracks",
            "content_type": "Tool",
            "content_type_explicit": True,
        }
        self.assertEqual(orchestrator._request_content_type_inferred(req), "Tool")


if __name__ == "__main__":
    unittest.main()
