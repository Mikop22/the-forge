from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pixelsmith.pixelsmith import ArtistAgent


def _sprite(path: Path, size: tuple[int, int], rect: tuple[int, int, int, int]) -> None:
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle(rect, fill=(20, 20, 20, 255))
    image.save(path)


def test_generate_asset_returns_item_and_projectile_foreground_bboxes(
    monkeypatch, tmp_path: Path
) -> None:
    agent = ArtistAgent.__new__(ArtistAgent)
    agent.output_dir = tmp_path

    item_path = tmp_path / "StormBrand.png"
    projectile_path = tmp_path / "StormBrandProjectile.png"
    _sprite(item_path, (32, 32), (8, 6, 23, 25))
    _sprite(projectile_path, (32, 32), (5, 7, 20, 18))

    monkeypatch.setattr(
        ArtistAgent,
        "_generate_standard_item",
        lambda self, parsed: item_path,
    )
    monkeypatch.setattr(
        ArtistAgent,
        "_generate_projectile",
        lambda self, parsed, raw_manifest: str(projectile_path),
    )

    result = agent.generate_asset(
        {
            "item_name": "StormBrand",
            "type": "Weapon",
            "sub_type": "Staff",
            "visuals": {
                "description": "storm staff",
                "icon_size": [32, 32],
            },
            "projectile_visuals": {
                "description": "storm bolt",
                "icon_size": [32, 32],
            },
        }
    )

    assert result["status"] == "success"
    assert result["item_foreground_bbox"] == [8, 6, 23, 25]
    assert result["projectile_foreground_bbox"] == [5, 7, 20, 18]
