from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from core.weapon_lab_archive import WeaponLabArchive
from pixelsmith.models import PixelsmithHiddenAuditionOutput
from pixelsmith.pixelsmith import ArtistAgent


def _make_good_sprite() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle((8, 6, 23, 25), fill=(20, 20, 20, 255))
    return image


def _make_bad_sprite() -> Image.Image:
    image = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    ImageDraw.Draw(image).rectangle((0, 4, 31, 27), fill=(20, 20, 20, 255))
    return image


def _make_agent(tmp_path: Path) -> ArtistAgent:
    agent = ArtistAgent.__new__(ArtistAgent)
    agent.output_dir = tmp_path
    agent._lora_path = None
    agent._lora_loaded = False
    agent._fal_key = "test-key"
    agent._image_to_image_enabled = False
    return agent


def _stub_projectile_generation(monkeypatch, tmp_path: Path) -> Path:
    projectile_path = tmp_path / "StormBrandProjectile.png"
    _make_good_sprite().save(projectile_path)
    monkeypatch.setattr(
        ArtistAgent,
        "_generate_projectile",
        lambda self, parsed, raw_manifest: str(projectile_path),
    )
    return projectile_path


def _make_manifest() -> dict:
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
        "projectile_visuals": {
            "description": "sharp blue-white lightning sigil bolt",
            "icon_size": [16, 16],
            "art_direction_profile": "balanced",
        },
        "weapon_thesis": {
            "fantasy": "storm brand staff that marks targets before a starfall cashout",
            "combat_package": "storm_brand",
            "delivery_style": "direct",
            "payoff_rate": "fast",
            "loop_family": "mark_cashout",
        },
    }


def _make_conservative_manifest() -> dict:
    manifest = _make_manifest()
    manifest["visuals"]["art_direction_profile"] = "conservative"
    return manifest


def _make_manifest_with_candidate(
    candidate_id: str, item_name: str = "StormBrand"
) -> dict:
    manifest = _make_manifest()
    manifest["candidate_id"] = candidate_id
    manifest["item_name"] = item_name
    return manifest


def _make_conservative_manifest_with_candidate(
    candidate_id: str, item_name: str = "StormBrand"
) -> dict:
    manifest = _make_conservative_manifest()
    manifest["candidate_id"] = candidate_id
    manifest["item_name"] = item_name
    return manifest


def test_hidden_pixelsmith_audition_produces_art_scored_winner_and_records_losers(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [
        _make_bad_sprite(),
        _make_good_sprite(),
        _make_good_sprite(),
        _make_good_sprite(),
    ]

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    _stub_projectile_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(
        agent,
        "_run_pipeline",
        lambda *args, **kwargs: images.pop(0),
    )
    monkeypatch.setattr(
        "pixelsmith.pixelsmith.judge_surviving_candidates",
        lambda survivors, **kwargs: {
            "winner_index": 1,
            "scores": [
                {"motif_strength": 7.0, "family_coherence": 7.0, "notes": "good"},
                {
                    "motif_strength": 9.0,
                    "family_coherence": 8.5,
                    "notes": "crackling storm halo around the wand head",
                },
                {
                    "motif_strength": 6.5,
                    "family_coherence": 7.0,
                    "notes": "weaker family match",
                },
            ],
        },
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_manifest()],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    assert validated.status == "success"
    assert isinstance(validated.candidate_archive, WeaponLabArchive)
    assert "final_weapon_winner" not in result
    assert (
        validated.art_scored_finalists[0].winner_candidate_id == "candidate-001-art-003"
    )
    assert validated.art_scored_finalists[0].item_visual_summary == ""
    assert validated.candidate_archive.rejection_reasons[
        "candidate-001-art-001"
    ].startswith("failed deterministic sprite gates")
    assert validated.candidate_archive.rejection_reasons[
        "candidate-001-art-002"
    ].startswith("lost art judging")


def test_hidden_pixelsmith_audition_survivors_have_passed_deterministic_sprite_gates(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [
        _make_bad_sprite(),
        _make_good_sprite(),
        _make_good_sprite(),
        _make_good_sprite(),
    ]

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    _stub_projectile_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(
        agent,
        "_run_pipeline",
        lambda *args, **kwargs: images.pop(0),
    )
    monkeypatch.setattr(
        "pixelsmith.pixelsmith.judge_surviving_candidates",
        lambda survivors, **kwargs: {
            "winner_index": 0,
            "scores": [
                {"motif_strength": 8.0, "family_coherence": 8.0, "notes": "clear"},
                {"motif_strength": 7.0, "family_coherence": 7.0, "notes": "solid"},
                {"motif_strength": 6.0, "family_coherence": 7.0, "notes": "acceptable"},
            ],
        },
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_manifest()],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    survivors = validated.art_scored_finalists[0].surviving_candidates
    assert survivors
    assert all(candidate.sprite_gate_report.passed for candidate in survivors)


def test_hidden_pixelsmith_audition_preserves_projectile_sprite_path(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [
        _make_good_sprite(),
        _make_good_sprite(),
        _make_good_sprite(),
        _make_good_sprite(),
    ]

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    _stub_projectile_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(
        agent,
        "_run_pipeline",
        lambda *args, **kwargs: images.pop(0),
    )
    monkeypatch.setattr(
        "pixelsmith.pixelsmith.judge_surviving_candidates",
        lambda survivors, **kwargs: {
            "winner_index": 0,
            "scores": [
                {"motif_strength": 8.0, "family_coherence": 8.0, "notes": "clear"},
                {"motif_strength": 7.0, "family_coherence": 7.0, "notes": "solid"},
            ],
        },
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_conservative_manifest()],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    finalist = validated.art_scored_finalists[0]
    assert finalist.projectile_sprite_path
    assert Path(finalist.projectile_sprite_path).exists()


def test_hidden_pixelsmith_audition_single_survivor_keeps_structured_evidence_conservative(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [_make_bad_sprite(), _make_good_sprite()]

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    _stub_projectile_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(
        agent,
        "_run_pipeline",
        lambda *args, **kwargs: images.pop(0),
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_conservative_manifest()],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    winner = validated.art_scored_finalists[0]
    assert winner.winner_art_scores.motif_strength == 6.0
    assert winner.winner_art_scores.family_coherence == 6.0
    assert "limited comparative evidence" in winner.winner_art_scores.notes
    assert winner.observed_art_signals.item_motif_strength == 6.0
    assert winner.observed_art_signals.item_family_coherence == 6.0


def test_hidden_pixelsmith_audition_winner_paths_stay_unique_for_same_item_name(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [
        _make_good_sprite(),
        _make_good_sprite(),
        _make_good_sprite(),
        _make_good_sprite(),
    ]

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    _stub_projectile_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(
        agent,
        "_run_pipeline",
        lambda *args, **kwargs: images.pop(0),
    )
    monkeypatch.setattr(
        "pixelsmith.pixelsmith.judge_surviving_candidates",
        lambda survivors, **kwargs: {
            "winner_index": 0,
            "scores": [
                {
                    "motif_strength": 7.0,
                    "family_coherence": 7.0,
                    "notes": "solid survivor",
                }
                for _ in survivors
            ],
        },
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[
            _make_conservative_manifest_with_candidate("candidate-001"),
            _make_conservative_manifest_with_candidate("candidate-002"),
        ],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    paths = [finalist.item_sprite_path for finalist in validated.art_scored_finalists]
    assert len(paths) == 2
    assert len(set(paths)) == 2
    assert all(Path(path).exists() for path in paths)


def test_hidden_pixelsmith_audition_text_to_image_finalists_still_generate_multiple_candidates(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [_make_bad_sprite(), _make_good_sprite(), _make_good_sprite()]
    calls: list[str] = []

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)

    def _run_pipeline(*args, **kwargs):
        calls.append("called")
        return images.pop(0)

    monkeypatch.setattr(agent, "_run_pipeline", _run_pipeline)
    monkeypatch.setattr(
        "pixelsmith.pixelsmith.judge_surviving_candidates",
        lambda survivors, **kwargs: {
            "winner_index": 0,
            "scores": [
                {"motif_strength": 8.0, "family_coherence": 8.0, "notes": "best"},
                {"motif_strength": 7.0, "family_coherence": 7.0, "notes": "solid"},
            ],
        },
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_conservative_manifest()],
        prompt="forge a storm brand hidden audition staff",
    )

    assert result["status"] == "success"
    assert len(calls) >= 2


def test_hidden_pixelsmith_audition_retains_failed_finalist_in_typed_archive(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)
    images = [_make_bad_sprite(), _make_bad_sprite()]

    monkeypatch.setattr("pixelsmith.pixelsmith.remove_background", lambda image: image)
    monkeypatch.setattr("pixelsmith.pixelsmith.downscale", lambda image, target: image)
    _stub_projectile_generation(monkeypatch, tmp_path)
    monkeypatch.setattr(
        agent,
        "_run_pipeline",
        lambda *args, **kwargs: images.pop(0),
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_conservative_manifest()],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    assert validated.art_scored_finalists == []
    assert validated.candidate_archive.finalists == ["candidate-001"]
    assert (
        validated.candidate_archive.theses["candidate-001"].combat_package
        == "storm_brand"
    )
    assert validated.candidate_archive.rejection_reasons["candidate-001"] == (
        "no art candidate survived deterministic sprite gates"
    )


def test_hidden_pixelsmith_audition_returns_typed_validation_error_for_bad_finalist(
    tmp_path: Path,
) -> None:
    agent = _make_agent(tmp_path)

    result = agent.generate_hidden_audition_finalists(
        finalists=[{"candidate_id": "candidate-001", "type": "Weapon"}],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    assert validated.status == "error"
    assert validated.error is not None
    assert validated.error.code == "VALIDATION"
    assert validated.art_scored_finalists == []
    assert (
        validated.candidate_archive.prompt
        == "forge a storm brand hidden audition staff"
    )
    assert validated.candidate_archive.finalists == ["candidate-001"]


def test_hidden_pixelsmith_audition_returns_typed_generation_error_on_internal_failure(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)

    monkeypatch.setattr(
        agent,
        "_audition_item_finalist",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("runner exploded")),
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_manifest()],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    assert validated.status == "error"
    assert validated.error is not None
    assert validated.error.code == "GENERATION"
    assert "runner exploded" in validated.error.message
    assert validated.art_scored_finalists == []
    assert validated.candidate_archive.finalists == ["candidate-001"]


def test_hidden_pixelsmith_audition_classifies_internal_validation_failures_as_generation(
    monkeypatch, tmp_path: Path
) -> None:
    agent = _make_agent(tmp_path)

    monkeypatch.setattr(
        agent,
        "_audition_item_finalist",
        lambda **kwargs: {"winner_candidate_id": "broken"},
    )

    result = agent.generate_hidden_audition_finalists(
        finalists=[_make_manifest()],
        prompt="forge a storm brand hidden audition staff",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    assert validated.status == "error"
    assert validated.error is not None
    assert validated.error.code == "GENERATION"
    assert validated.candidate_archive.finalists == ["candidate-001"]


def test_hidden_pixelsmith_audition_empty_prompt_still_returns_typed_error(
    tmp_path: Path,
) -> None:
    agent = _make_agent(tmp_path)

    result = agent.generate_hidden_audition_finalists(
        finalists=[{"candidate_id": "candidate-001", "type": "Weapon"}],
        prompt="",
    )
    validated = PixelsmithHiddenAuditionOutput.model_validate(result)

    assert validated.status == "error"
    assert validated.error is not None
    assert validated.error.code == "VALIDATION"
    assert validated.candidate_archive.prompt != ""
    assert validated.candidate_archive.finalists == ["candidate-001"]
