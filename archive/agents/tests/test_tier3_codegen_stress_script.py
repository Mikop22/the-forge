from pathlib import Path

from stress_tier3_basis import DEFAULT_PROMPTS
from stress_tier3_codegen import run_codegen_stress


class FakeArchitect:
    def generate_manifest(self, **kwargs):
        prompt = kwargs["prompt"]
        return {
            "item_name": "StressTestItem",
            "display_name": "Stress Test Item",
            "tooltip": "Stress.",
            "content_type": "Weapon",
            "type": "Weapon",
            "sub_type": kwargs["sub_type"],
            "stats": {
                "damage": 58,
                "knockback": 5.0,
                "crit_chance": 4,
                "use_time": 20,
                "auto_reuse": True,
                "rarity": "ItemRarityID.Pink",
            },
            "visuals": {"description": prompt},
            "mechanics": {
                "shot_style": "direct",
                "custom_projectile": True,
                "shoot_projectile": None,
                "crafting_material": "ItemID.SoulofLight",
                "crafting_cost": 12,
                "crafting_tile": "TileID.Anvils",
            },
            "projectile_visuals": {"description": prompt, "icon_size": [20, 20]},
            "mechanics_ir": {
                "atoms": [
                    {"kind": "charge_phase"},
                    {"kind": "beam_lance"},
                ]
            },
        }


class FakeCoder:
    def write_code(self, manifest):
        return {
            "status": "success",
            "item_name": manifest["item_name"],
            "cs_code": "public class StressTestItem : ModItem { }",
            "hjson_code": "",
        }


def test_codegen_stress_runs_prompt_set_and_writes_artifacts(tmp_path: Path) -> None:
    results = run_codegen_stress(
        DEFAULT_PROMPTS[:2],
        architect=FakeArchitect(),
        coder=FakeCoder(),
        output_dir=tmp_path,
    )

    assert [result.prompt for result in results] == DEFAULT_PROMPTS[:2]
    assert all(result.passed for result in results)
    assert all(result.manifest_path for result in results)
    assert all(result.cs_path for result in results)
    assert len(list(tmp_path.glob("*.manifest.json"))) == 2
    assert len(list(tmp_path.glob("*.cs"))) == 2


def test_codegen_stress_reports_codegen_failure(tmp_path: Path) -> None:
    class FailingCoder:
        def write_code(self, manifest):
            return {
                "status": "error",
                "cs_code": "public class BrokenStressItem : ModItem { }",
                "error": {"code": "VALIDATION", "message": "missing beam evidence"},
            }

    [result] = run_codegen_stress(
        [DEFAULT_PROMPTS[1]],
        architect=FakeArchitect(),
        coder=FailingCoder(),
        output_dir=tmp_path,
    )

    assert not result.passed
    assert "missing beam evidence" in result.failures[0]
    assert result.cs_path
    assert Path(result.cs_path).read_text(encoding="utf-8") == (
        "public class BrokenStressItem : ModItem { }"
    )
