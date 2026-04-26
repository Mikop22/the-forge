from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pixelsmith.pixelsmith import ArtistAgent


def _make_agent(tmp_path: Path) -> ArtistAgent:
    agent = ArtistAgent.__new__(ArtistAgent)
    agent.output_dir = tmp_path
    agent._lora_path = None
    agent._lora_loaded = False
    agent._fal_key = "test-key"
    agent._image_to_image_enabled = False
    return agent


def _make_good_item_sprite() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle((8, 6, 23, 25), fill=(20, 20, 20, 255))
    return image


def _make_bad_item_sprite() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle((0, 4, 31, 27), fill=(20, 20, 20, 255))
    return image


def _make_bad_projectile_sprite() -> Image.Image:
    image = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.point((0, 1), fill=(225, 225, 225, 255))
    draw.rectangle((6, 6, 9, 9), fill=(245, 245, 245, 255))
    return image


def _make_manifest() -> dict:
    return {
        "item_name": "StormBrandStaffLive",
        "type": "Weapon",
        "sub_type": "Staff",
        "generation_mode": "text_to_image",
        "visuals": {
            "description": "forked celestial storm staff with blue-white shocklight",
            "icon_size": [32, 32],
            "art_direction_profile": "balanced",
        },
        "projectile_visuals": {
            "description": "sharp blue-white lightning sigil bolt",
            "icon_size": [16, 16],
            "art_direction_profile": "balanced",
        },
        "mechanics": {
            "shoot_projectile": "ModContent.ProjectileType<StormBrandStaffLiveProjectile>()"
        },
    }


def test_generate_asset_rejects_item_that_fails_deterministic_sprite_gates(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    monkeypatch.setattr(
        agent,
        "_generate_with_variants",
        lambda *args, **kwargs: _make_bad_item_sprite(),
    )

    result = agent.generate_asset(_make_manifest())

    assert result["status"] == "error"
    assert "item sprite failed deterministic sprite gates" in result["error"][
        "detail"
    ]


def test_generate_asset_rejects_projectile_that_fails_deterministic_sprite_gates(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [_make_good_item_sprite(), _make_bad_projectile_sprite()]

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    monkeypatch.setattr(
        agent,
        "_generate_with_variants",
        lambda *args, **kwargs: images.pop(0),
    )

    result = agent.generate_asset(_make_manifest())

    assert result["status"] == "error"
    assert "projectile sprite failed deterministic sprite gates" in result["error"][
        "detail"
    ]


def test_forge_connector_source_preserves_last_inject_payload_and_stages_runtime_assets() -> (
    None
):
    source = (
        Path(__file__).resolve().parents[2]
        / "mod"
        / "ForgeConnector"
        / "ForgeConnectorSystem.cs"
    ).read_text(encoding="utf-8")

    assert "forge_last_inject.json" in source
    assert "forge_last_inject_debug.json" in source
    assert "ForgeConnectorInjectedAssets" in source
    assert "StageRuntimeAsset(" in source
    assert "WriteLastInjectArtifacts(" in source
