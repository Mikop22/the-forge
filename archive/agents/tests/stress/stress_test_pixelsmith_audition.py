from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from pixelsmith.models import PixelsmithHiddenAuditionOutput
from pixelsmith.pixelsmith import ArtistAgent


def _make_sprite(fill_box: tuple[int, int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle(fill_box, fill=(20, 20, 20, 255))
    return image


def _make_agent(tmp_path: Path) -> ArtistAgent:
    agent = ArtistAgent.__new__(ArtistAgent)
    agent.output_dir = tmp_path
    agent._lora_path = None
    agent._lora_loaded = False
    agent._fal_key = "test-key"
    agent._image_to_image_enabled = False
    return agent


def _make_manifest() -> dict[str, object]:
    return {
        "candidate_id": "candidate-001",
        "item_name": "StormBrand",
        "type": "Weapon",
        "sub_type": "Staff",
        "generation_mode": "text_to_image",
        "visuals": {
            "description": "forked lightning staff with brass filigree",
            "icon_size": [32, 32],
            "art_direction_profile": "exploratory",
        },
        "weapon_thesis": {
            "fantasy": "storm brand staff that marks targets before a starfall cashout",
            "combat_package": "storm_brand",
            "delivery_style": "direct",
            "payoff_rate": "fast",
            "loop_family": "mark_cashout",
        },
    }


def test_pixelsmith_hidden_audition_selects_best_survivor_offline(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [
        _make_sprite((0, 4, 31, 27)),
        _make_sprite((8, 6, 23, 25)),
        _make_sprite((9, 7, 22, 24)),
        _make_sprite((10, 8, 21, 23)),
    ]

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    monkeypatch.setattr(agent, "_run_pipeline", lambda *args, **kwargs: images.pop(0))
    monkeypatch.setattr(
        "pixelsmith.pixelsmith.judge_surviving_candidates",
        lambda survivors, **kwargs: {
            "winner_index": 2,
            "scores": [
                {"motif_strength": 7.5, "family_coherence": 7.0, "notes": "solid"},
                {"motif_strength": 8.4, "family_coherence": 8.2, "notes": "good"},
                {
                    "motif_strength": 9.2,
                    "family_coherence": 9.0,
                    "notes": "strong storm halo and clean staff read",
                },
            ],
        },
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_manifest()],
        prompt="forge a hidden audition storm brand staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    assert validated.status == "success"
    assert (
        validated.art_scored_finalists[0].winner_candidate_id == "candidate-001-art-004"
    )
    assert validated.candidate_archive.finalists == ["candidate-001"]
    assert validated.candidate_archive.rejection_reasons[
        "candidate-001-art-001"
    ].startswith("failed deterministic sprite gates")
    assert validated.candidate_archive.rejection_reasons[
        "candidate-001-art-002"
    ].startswith("lost art judging")
    assert validated.candidate_archive.rejection_reasons[
        "candidate-001-art-003"
    ].startswith("lost art judging")
