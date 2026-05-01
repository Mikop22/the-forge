from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pixelsmith.pixelsmith import ArtistAgent


def _sprite(path: Path, size: tuple[int, int] = (32, 32)) -> None:
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle((8, 8, 23, 23), fill=(20, 20, 20, 255))
    image.save(path)


def _agent(tmp_path: Path) -> ArtistAgent:
    agent = ArtistAgent.__new__(ArtistAgent)
    agent.output_dir = tmp_path
    return agent


def test_item_only_generation_preserves_existing_projectile_path(monkeypatch, tmp_path):
    agent = _agent(tmp_path)
    item_path = tmp_path / "StormBrand.png"
    projectile_path = tmp_path / "StormBrandProjectile.png"
    _sprite(item_path)
    _sprite(projectile_path)
    monkeypatch.setattr(
        ArtistAgent,
        "_generate_standard_item",
        lambda self, parsed: item_path,
    )
    monkeypatch.setattr(
        ArtistAgent,
        "_generate_projectile",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("projectile should be preserved")
        ),
    )

    result = agent.generate_scoped_asset(
        {
            "item_name": "StormBrand",
            "visuals": {"description": "storm staff"},
            "projectile_visuals": {"description": "storm bolt"},
        },
        scope="item",
        existing_projectile_sprite_path=str(projectile_path),
    )

    assert result["status"] == "success"
    assert result["item_sprite_path"] == str(item_path)
    assert result["projectile_sprite_path"] == str(projectile_path)


def test_projectile_only_generation_preserves_existing_item_path(monkeypatch, tmp_path):
    agent = _agent(tmp_path)
    item_path = tmp_path / "StormBrand.png"
    projectile_path = tmp_path / "StormBrandProjectile.png"
    _sprite(item_path)
    _sprite(projectile_path)
    monkeypatch.setattr(
        ArtistAgent,
        "_generate_standard_item",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("item should be preserved")
        ),
    )
    monkeypatch.setattr(
        ArtistAgent,
        "_generate_projectile",
        lambda self, parsed, raw_manifest: str(projectile_path),
    )

    result = agent.generate_scoped_asset(
        {
            "item_name": "StormBrand",
            "visuals": {"description": "storm staff"},
            "projectile_visuals": {"description": "storm bolt"},
        },
        scope="projectile",
        existing_item_sprite_path=str(item_path),
    )

    assert result["status"] == "success"
    assert result["item_sprite_path"] == str(item_path)
    assert result["projectile_sprite_path"] == str(projectile_path)


def test_item_only_generation_requires_existing_projectile_for_generated_projectile(
    monkeypatch, tmp_path
):
    agent = _agent(tmp_path)
    item_path = tmp_path / "StormBrand.png"
    _sprite(item_path)
    monkeypatch.setattr(
        ArtistAgent,
        "_generate_standard_item",
        lambda self, parsed: item_path,
    )

    result = agent.generate_scoped_asset(
        {
            "item_name": "StormBrand",
            "visuals": {"description": "storm staff"},
            "projectile_visuals": {"description": "storm bolt"},
        },
        scope="item",
    )

    assert result["status"] == "error"
    assert "existing_projectile_sprite_path" in result["error"]["detail"]
