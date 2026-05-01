from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pixelsmith.models import PixelsmithInput
from pixelsmith.pixelsmith import ArtistAgent


def _make_agent(tmp_path: Path) -> ArtistAgent:
    agent = ArtistAgent.__new__(ArtistAgent)
    agent.output_dir = tmp_path
    agent._lora_loaded = False
    agent._image_to_image_enabled = False
    return agent


def _good_frame() -> Image.Image:
    image = Image.new("RGBA", (64, 64), (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle((16, 16, 47, 47), fill=(20, 20, 20, 255))
    return image


def test_projectile_visuals_default_to_static_animation_tier() -> None:
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "StormBrand",
            "visuals": {"description": "storm staff"},
            "projectile_visuals": {"description": "storm bolt"},
        }
    )

    assert parsed.projectile_visuals is not None
    assert parsed.projectile_visuals.animation_tier == "static"


def test_vanilla_frames_tier_skips_projectile_sprite_generation(monkeypatch, tmp_path):
    agent = _make_agent(tmp_path)
    monkeypatch.setattr(
        ArtistAgent,
        "_run_pipeline",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no image call")),
    )
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "StormBrand",
            "visuals": {"description": "storm staff"},
            "projectile_visuals": {
                "description": "use a vanilla animated sigil",
                "animation_tier": "vanilla_frames:4",
            },
        }
    )

    assert agent._generate_projectile(parsed, parsed.model_dump(mode="json")) is None


def test_generated_frames_tier_stitches_vertical_projectile_sheet(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    calls = []

    def fake_run_pipeline(*args, **kwargs):
        calls.append((args, kwargs))
        return _good_frame()

    monkeypatch.setattr(ArtistAgent, "_run_pipeline", fake_run_pipeline)
    monkeypatch.setitem(
        ArtistAgent._generate_projectile.__globals__,
        "build_img2img_prompt",
        lambda description, reference_url, orientation: f"img2img {description}",
    )
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "StormBrand",
            "visuals": {"description": "storm staff"},
            "projectile_visuals": {
                "description": "storm bolt animation",
                "icon_size": [16, 16],
                "animation_tier": "generated_frames:3",
            },
        }
    )

    out_path = agent._generate_projectile(parsed, parsed.model_dump(mode="json"))

    assert out_path is not None
    assert len(calls) == 3
    with Image.open(out_path) as sheet:
        assert sheet.size == (16, 48)


def test_generated_frames_retries_projectile_frame_with_clean_prompt(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    calls = []
    gate_attempts = {"count": 0}

    def fake_run_pipeline(self, prompt, *args, **kwargs):
        calls.append(prompt)
        return _good_frame()

    def fake_require(self, image, *, sprite_kind):
        gate_attempts["count"] += 1
        if gate_attempts["count"] == 1:
            raise RuntimeError(
                "projectile sprite failed deterministic sprite gates: center_background_cleanup"
            )

    monkeypatch.setattr(ArtistAgent, "_run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(ArtistAgent, "_require_readable_sprite", fake_require)
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "VoidConvergenceStaff",
            "visuals": {"description": "void staff"},
            "projectile_visuals": {
                "description": "violet orb with haze, filaments, and distortion wake",
                "icon_size": [16, 16],
                "animation_tier": "generated_frames:2",
            },
        }
    )

    out_path = agent._generate_projectile(parsed, parsed.model_dump(mode="json"))

    assert out_path is not None
    assert gate_attempts["count"] == 3
    assert any("no haze" in prompt for prompt in calls)


def test_generated_frames_uses_procedural_projectile_after_retry_gate_failure(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    gate_attempts = {"count": 0}

    def fake_run_pipeline(self, prompt, *args, **kwargs):
        return _good_frame()

    def fake_require(self, image, *, sprite_kind):
        gate_attempts["count"] += 1
        if gate_attempts["count"] <= 2:
            raise RuntimeError(
                "projectile sprite failed deterministic sprite gates: center_background_cleanup"
            )

    monkeypatch.setattr(ArtistAgent, "_run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(ArtistAgent, "_require_readable_sprite", fake_require)
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "VoidConvergenceStaff",
            "visuals": {"description": "void staff"},
            "projectile_visuals": {
                "description": "violet orb with haze, filaments, and distortion wake",
                "icon_size": [16, 16],
                "animation_tier": "generated_frames:1",
            },
        }
    )

    out_path = agent._generate_projectile(parsed, parsed.model_dump(mode="json"))

    assert out_path is not None
    assert gate_attempts["count"] == 3
    with Image.open(out_path) as image:
        assert image.size == (16, 16)


def test_standard_item_retries_with_clean_prompt_after_background_noise(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    calls = []
    gate_attempts = {"count": 0}

    def fake_generate_with_variants(self, prompt, *args, **kwargs):
        calls.append(prompt)
        return _good_frame()

    def fake_require(self, image, *, sprite_kind):
        gate_attempts["count"] += 1
        if gate_attempts["count"] == 1:
            raise RuntimeError(
                "item sprite failed deterministic sprite gates: center_background_cleanup"
            )

    monkeypatch.setitem(
        ArtistAgent._generate_standard_item.__globals__,
        "_enrich_description",
        lambda description, **kwargs: description,
    )
    monkeypatch.setattr(
        ArtistAgent, "_generate_with_variants", fake_generate_with_variants
    )
    monkeypatch.setattr(ArtistAgent, "_require_readable_sprite", fake_require)
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "VoidConvergenceStaff",
            "visuals": {
                "description": "obsidian staff with wisps and radiant spatial haze",
                "icon_size": [40, 40],
            },
        }
    )

    out_path = agent._generate_standard_item(parsed)

    assert out_path.name == "VoidConvergenceStaff.png"
    assert gate_attempts["count"] == 2
    assert any("no haze" in prompt for prompt in calls)


def test_generated_frames_generate_asset_reports_per_frame_bbox(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    item_path = tmp_path / "StormBrand.png"
    _good_frame().resize((32, 32)).save(item_path)
    monkeypatch.setattr(
        ArtistAgent,
        "_generate_standard_item",
        lambda self, parsed: item_path,
    )
    monkeypatch.setattr(
        ArtistAgent,
        "_run_pipeline",
        lambda *args, **kwargs: _good_frame(),
    )

    result = agent.generate_asset(
        {
            "item_name": "StormBrand",
            "visuals": {"description": "storm staff", "icon_size": [32, 32]},
            "projectile_visuals": {
                "description": "storm bolt animation",
                "icon_size": [16, 16],
                "animation_tier": "generated_frames:3",
            },
        }
    )

    assert result["status"] == "success"
    assert result["projectile_foreground_bbox"] == [4, 4, 11, 11]


def test_static_img2img_projectile_uses_single_image_call(monkeypatch, tmp_path: Path):
    agent = _make_agent(tmp_path)
    agent._image_to_image_enabled = True
    calls = []

    def fake_run_pipeline(*args, **kwargs):
        calls.append((args, kwargs))
        return _good_frame()

    monkeypatch.setattr(ArtistAgent, "_run_pipeline", fake_run_pipeline)
    monkeypatch.setitem(
        ArtistAgent._generate_projectile.__globals__,
        "build_img2img_prompt",
        lambda description, reference_url, orientation: f"img2img {description}",
    )
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "StormBrand",
            "generation_mode": "image_to_image",
            "reference_image_url": "https://example.com/ref.png",
            "visuals": {"description": "storm staff"},
            "projectile_visuals": {
                "description": "storm bolt",
                "icon_size": [16, 16],
                "animation_tier": "static",
            },
        }
    )

    out_path = agent._generate_projectile(parsed, parsed.model_dump(mode="json"))

    assert out_path is not None
    assert len(calls) == 1


def test_projectile_generation_uses_projectile_slot_reference(monkeypatch, tmp_path: Path):
    agent = _make_agent(tmp_path)
    agent._image_to_image_enabled = True
    seen = {}

    def fake_build_img2img_prompt(description, reference_url, orientation):
        seen["reference_url"] = reference_url
        return f"img2img {description}"

    monkeypatch.setattr(agent, "_generate_with_variants", lambda *_, **__: _good_frame())
    monkeypatch.setitem(
        ArtistAgent._generate_projectile.__globals__,
        "build_img2img_prompt",
        fake_build_img2img_prompt,
    )
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "StormBrand",
            "generation_mode": "text_to_image",
            "reference_image_url": "https://example.com/item.png",
            "references": {
                "projectile": {
                    "image_url": "https://example.com/projectile.png",
                    "generation_mode": "image_to_image",
                }
            },
            "visuals": {"description": "storm staff"},
            "projectile_visuals": {
                "description": "storm bolt",
                "icon_size": [16, 16],
                "animation_tier": "static",
            },
        }
    )

    out_path = agent._generate_projectile(parsed, parsed.model_dump(mode="json"))

    assert out_path is not None
    assert seen["reference_url"] == "https://example.com/projectile.png"


def test_item_generation_uses_item_slot_reference(monkeypatch, tmp_path: Path):
    agent = _make_agent(tmp_path)
    agent._image_to_image_enabled = True
    seen = {}

    def fake_build_img2img_prompt(description, reference_url, orientation):
        seen["reference_url"] = reference_url
        return f"img2img {description}"

    monkeypatch.setattr(agent, "_generate_with_variants", lambda *_, **__: _good_frame())
    monkeypatch.setitem(
        ArtistAgent._generate_standard_item.__globals__,
        "build_img2img_prompt",
        fake_build_img2img_prompt,
    )
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "StormBrand",
            "generation_mode": "text_to_image",
            "reference_image_url": "https://example.com/legacy.png",
            "references": {
                "item": {
                    "image_url": "https://example.com/item.png",
                    "generation_mode": "image_to_image",
                }
            },
            "visuals": {"description": "storm staff", "icon_size": [48, 48]},
        }
    )

    out_path = agent._generate_standard_item(parsed)

    assert out_path.exists()
    assert seen["reference_url"] == "https://example.com/item.png"


def test_projectile_slot_reference_does_not_leak_into_item_slot() -> None:
    parsed = PixelsmithInput.model_validate(
        {
            "item_name": "StormBrand",
            "generation_mode": "image_to_image",
            "reference_image_url": "https://example.com/legacy-projectile.png",
            "references": {
                "projectile": {
                    "image_url": "https://example.com/projectile.png",
                    "generation_mode": "image_to_image",
                }
            },
            "visuals": {"description": "storm staff"},
        }
    )

    mode, reference_url = ArtistAgent._generate_projectile.__globals__[
        "_reference_for_slot"
    ](parsed, parsed.model_dump(mode="json"), "item")

    assert mode == "text_to_image"
    assert reference_url is None
